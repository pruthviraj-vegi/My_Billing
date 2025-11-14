from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, F, Q
from django.contrib import messages
from django.urls import reverse
from django.views.generic import CreateView, UpdateView
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from .models import Product, ProductVariant, InventoryLog
from .forms import ProductForm, CategoryForm, ClothTypeForm, UOMForm, GSTHsnCodeForm
import logging

logger = logging.getLogger(__name__)

VALID_SORT_FIELDS = {
    "id",
    "-id",
    "brand",
    "-brand",
    "name",
    "-name",
    "category__name",
    "-category__name",
    "status",
    "-status",
    "hsn_code__gst_percentage",
    "-hsn_code__gst_percentage",
    "-hsn_code",
    "cloth_type",
    "-cloth_type",
    "hsn_code",
    "-hsn_code",
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
}

PRODUCTS_PER_PAGE = 20


@login_required
def product_home(request):
    """Product management main page - initial load only."""
    # Get filter options for the template
    from .models import Category

    categories = Category.objects.all().order_by("name")

    context = {
        "categories": categories,
        "status_choices": Product.ProductStatus.choices,
    }
    return render(request, "inventory/product/home.html", context)


@login_required
def fetch_products(request):
    """AJAX endpoint to fetch products with search, filter, and pagination."""
    # Get search and filter parameters
    search_query = request.GET.get("search", "")
    category_filter = request.GET.get("category", "")
    status_filter = request.GET.get("status", "")
    sort_by = request.GET.get("sort", "")

    # Apply search filter
    filters = Q()
    if search_query:
        filters &= (
            Q(brand__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__name__icontains=search_query)
            | Q(hsn_code__code__icontains=search_query)
        )

    # Apply category filter
    if category_filter:
        filters &= Q(category_id=category_filter)

    # Apply status filter
    if status_filter:
        filters &= Q(status=status_filter)

    # Start with all products
    products = Product.objects.select_related(
        "category",
        "cloth_type",
        "hsn_code",
    ).filter(filters)

    # Apply sorting
    if sort_by not in VALID_SORT_FIELDS:
        sort_by = "-id"
    products = products.order_by(sort_by)

    # Pagination
    paginator = Paginator(products, PRODUCTS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Render the HTML template
    context = {
        "page_obj": page_obj,
        "total_count": paginator.count,
        "search_query": search_query,
    }

    # Render the table content (without pagination)
    table_html = render_to_string(
        "inventory/product/fetch.html", context, request=request
    )

    # Render pagination separately
    pagination_html = ""
    if page_obj and page_obj.paginator.num_pages > 1:
        pagination_html = render_to_string(
            "common/_pagination.html", context, request=request
        )

    return JsonResponse(
        {"html": table_html, "pagination": pagination_html, "success": True}
    )


def product_details(request, product_id):
    """Display detailed product information with variants and statistics"""

    product = get_object_or_404(Product, id=product_id)

    # Get all variants for this product
    variants = (
        ProductVariant.objects.filter(product=product)
        .select_related("size", "color")
        .order_by("size__name", "color__name")
    )

    # Calculate statistics
    total_variants = variants.count()
    active_variants = variants.filter(
        status=ProductVariant.VariantStatus.ACTIVE
    ).count()
    out_of_stock = variants.filter(
        quantity=0, status=ProductVariant.VariantStatus.ACTIVE
    ).count()
    low_stock = variants.filter(
        quantity__lte=F("minimum_quantity"),
        status=ProductVariant.VariantStatus.ACTIVE,
    ).count()

    # Calculate inventory values
    total_quantity = variants.aggregate(total=Sum("quantity"))["total"] or 0

    total_damaged = variants.aggregate(total=Sum("damaged_quantity"))["total"] or 0

    total_inventory_value = (
        variants.aggregate(total=Sum(F("quantity") * F("purchase_price")))["total"] or 0
    )

    total_damaged_value = (
        variants.aggregate(total=Sum(F("damaged_quantity") * F("purchase_price")))[
            "total"
        ]
        or 0
    )

    # Get recent inventory logs for this product (only for active variants)
    recent_logs = (
        InventoryLog.objects.filter(variant__product=product, variant__is_deleted=False)
        .select_related(
            "variant", "created_by", "supplier_invoice", "supplier_invoice__supplier"
        )
        .order_by("-timestamp")[:10]
    )

    context = {
        "product": product,
        "variants": variants,
        "total_variants": total_variants,
        "active_variants": active_variants,
        "out_of_stock": out_of_stock,
        "low_stock": low_stock,
        "total_quantity": total_quantity,
        "total_damaged": total_damaged,
        "total_inventory_value": total_inventory_value,
        "total_damaged_value": total_damaged_value,
        "recent_logs": recent_logs,
    }

    return render(request, "inventory/product/details.html", context)


class CreateProduct(CreateView):
    template_name = "inventory/product/form.html"
    form_class = ProductForm
    model = Product
    title = "Create Product"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_form"] = CategoryForm()
        context["cloth_type_form"] = ClothTypeForm()
        context["uom_form"] = UOMForm()
        context["gst_hsn_form"] = GSTHsnCodeForm()
        context["title"] = self.title
        return context

    def form_valid(self, form):
        messages.success(self.request, "Product created successfully")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse(
            "inventory_products:details", kwargs={"product_id": self.object.id}
        )


class EditProduct(UpdateView):
    template_name = "inventory/product/form.html"
    form_class = ProductForm
    model = Product
    title = "Edit Product"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["category_form"] = CategoryForm()
        context["cloth_type_form"] = ClothTypeForm()
        context["uom_form"] = UOMForm()
        context["gst_hsn_form"] = GSTHsnCodeForm()
        return context

    def form_valid(self, form):
        messages.success(self.request, "Product updated successfully")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse(
            "inventory_products:details", kwargs={"product_id": self.object.id}
        )


@login_required
def download_products(request):
    """Download products data as JSON."""
    products = Product.objects.select_related(
        "category", "cloth_type", "hsn_code", "uom"
    ).all()
    data = []

    for product in products:
        data.append(
            {
                "id": product.id,
                "brand": product.brand,
                "name": product.name,
                "category": product.category.name if product.category else None,
                "cloth_type": product.cloth_type.name if product.cloth_type else None,
                "hsn_code": product.hsn_code.code if product.hsn_code else None,
                "gst_percentage": str(product.hsn_code.gst_percentage),
                "status": product.status,
                "variants_count": product.product_variants.count(),
                "created_at": product.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    response = JsonResponse(data, safe=False)
    response["Content-Disposition"] = 'attachment; filename="products.json"'
    return response


@login_required
def search_products_ajax(request):
    """AJAX endpoint for real-time product search."""
    search_query = request.GET.get("q", "")

    if len(search_query) < 2:
        return JsonResponse({"products": []})

    products = Product.objects.select_related("category").filter(
        Q(brand__icontains=search_query)
        | Q(name__icontains=search_query)
        | Q(description__icontains=search_query)
    )[
        :10
    ]  # Limit to 10 results

    data = []
    for product in products:
        data.append(
            {
                "id": product.id,
                "brand": product.brand,
                "name": product.name,
                "category": product.category.name if product.category else None,
                "status": product.status,
            }
        )

    return JsonResponse({"products": data})
