from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.db import IntegrityError, transaction
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.db.models import Q, F
from .models import ProductVariant, InventoryLog, Product, Category, Color, Size
from .forms import (
    VariantForm,
    StockInForm,
    AdjustmentInForm,
    AdjustmentOutForm,
    DamageForm,
    SizeForm,
    ColorForm,
)
from .services import InventoryService
import logging

logger = logging.getLogger(__name__)

VALID_SORT_FIELDS = {
    "id",
    "-id",
    "barcode",
    "-barcode",
    "product__brand",
    "-product__brand",
    "product__name",
    "-product__name",
    "product__category__name",
    "-product__category__name",
    "size__name",
    "-size__name",
    "color__name",
    "-color__name",
    "quantity",
    "-quantity",
    "mrp",
    "-mrp",
    "status",
    "-status",
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
}

VARIANTS_PER_PAGE = 20


@login_required
def variant_home(request):
    """Product variant management main page - initial load only."""
    # Get filter options for the template
    categories = Category.objects.all().order_by("name")
    colors = Color.objects.all().order_by("name")
    sizes = Size.objects.all().order_by("name")

    context = {
        "categories": categories,
        "colors": colors,
        "sizes": sizes,
        "status_choices": ProductVariant.VariantStatus.choices,
    }
    return render(request, "inventory/product_variant/home.html", context)


def get_variants_data(request):

    # Get search and filter parameters
    search_query = request.GET.get("search", "")
    category_filter = request.GET.get("category", "")
    color_filter = request.GET.get("color", "")
    size_filter = request.GET.get("size", "")
    status_filter = request.GET.get("status", "")
    stock_filter = request.GET.get("stock", "")
    sort_by = request.GET.get("sort", "")

    # Start with all variants
    variants = ProductVariant.objects.select_related(
        "product", "product__category", "size", "color"
    ).all()

    # Apply search filter
    filters = Q()
    if search_query:
        filters &= (
            Q(product__brand__icontains=search_query)
            | Q(product__name__icontains=search_query)
            | Q(barcode__icontains=search_query)
            | Q(product__description__icontains=search_query)
            | Q(product__category__name__icontains=search_query)
        )

    # Apply category filter
    if category_filter:
        filters &= Q(product__category_id=category_filter)

    # Apply color filter
    if color_filter:
        filters &= Q(color_id=color_filter)

    # Apply size filter
    if size_filter:
        filters &= Q(size_id=size_filter)

    # Apply status filter
    if status_filter:
        filters &= Q(status=status_filter)

    # Apply stock filter
    if stock_filter == "in_stock":
        filters &= Q(quantity__gt=0)
    elif stock_filter == "out_of_stock":
        filters &= Q(quantity=0)
    elif stock_filter == "low_stock":
        filters &= Q(quantity__lte=F("minimum_quantity"), quantity__gt=0)

    variants = variants.filter(filters)

    # Apply sorting
    if sort_by not in VALID_SORT_FIELDS:
        sort_by = "-created_at"
    variants = variants.order_by(sort_by)

    return variants


@login_required
def fetch_variants(request):
    """AJAX endpoint to fetch variants with search, filter, and pagination."""
    variants = get_variants_data(request)

    # Pagination
    paginator = Paginator(variants, VARIANTS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Render the HTML template
    context = {
        "page_obj": page_obj,
        "total_count": paginator.count,
    }

    # Render the table content (without pagination)
    table_html = render_to_string(
        "inventory/product_variant/fetch.html", context, request=request
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


def variant_details(request, variant_id):
    """Detailed view for a single product variant with stock management options"""

    variant = get_object_or_404(ProductVariant, id=variant_id)

    # Get recent activity logs for this variant (only for active variants)
    recent_logs = variant.inventory_logs.select_related(
        "supplier_invoice", "supplier_invoice__supplier"
    ).order_by("-timestamp")[:20]

    # Calculate stock statistics
    stock_stats = {
        "total_quantity": variant.total_quantity,
        "available_quantity": variant.available_quantity,
        "damaged_quantity": variant.damaged_quantity,
        "damage_percentage": variant.damage_percentage,
        "stock_health": variant.stock_health,
        "profit_margin": variant.profit_margin,
        "total_value": variant.total_value,
        "damaged_value": variant.damaged_value,
    }

    context = {
        "variant": variant,
        "product": variant.product,
        "recent_logs": recent_logs,
        "stock_stats": stock_stats,
    }

    return render(request, "inventory/product_variant/details.html", context)


class CreateProductVariant(CreateView):
    template_name = "inventory/product_variant/form.html"
    form_class = VariantForm
    model = ProductVariant
    title = "Create Product Variant"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["size_form"] = SizeForm()
        context["color_form"] = ColorForm()
        product = Product.objects.get(id=self.kwargs["product_id"])
        context["product"] = product
        context["gst_rate"] = product.hsn_code.gst_percentage

        # Check if this is the first variant for this product
        existing_variants = ProductVariant.objects.filter(product=product)
        context["is_first_variant"] = (
            existing_variants.count() == 0 if existing_variants.exists() else True
        )

        # Add existing variants to context for reference
        if existing_variants.exists():
            context["existing_variants"] = existing_variants
            context["latest_variant"] = existing_variants.latest(
                "created_at"
            )  # Assuming you have a created_at field

        return context

    def get_initial(self):
        """Set initial values for the form"""
        initial = super().get_initial()

        # Get the product
        product = Product.objects.get(id=self.kwargs["product_id"])
        # Check if this is the first variant
        existing_variants = ProductVariant.objects.filter(product=product)

        if existing_variants.exists():
            # For subsequent variants, copy data from the most recent variant
            # You can change this logic to copy from a specific variant if needed
            latest_variant = existing_variants.latest(
                "created_at"
            )  # or use 'id' if no created_at field

            initial.update(
                {
                    "purchase_price": latest_variant.purchase_price,
                    "mrp": latest_variant.mrp,
                    "discount_percentage": latest_variant.discount_percentage,
                    "quantity": 0,
                }
            )

        return initial

    def form_valid(self, form):
        # Get the product
        product = Product.objects.get(id=self.kwargs["product_id"])

        # Save the variant
        variant = form.save(commit=False)
        variant.product = product
        variant.created_by = self.request.user

        try:
            variant.save()
        except IntegrityError as e:
            # Check if it's a unique constraint violation
            if "unique_product" in str(e):
                # Determine which fields are causing the conflict
                size = form.cleaned_data.get("size")
                color = form.cleaned_data.get("color")

                if size and color:
                    error_msg = f"A variant with size '{size}' and color '{color}' already exists for this product."
                elif size:
                    error_msg = (
                        f"A variant with size '{size}' already exists for this product."
                    )
                elif color:
                    error_msg = f"A variant with color '{color}' already exists for this product."
                else:
                    error_msg = "A variant without size and color already exists for this product."

                form.add_error(None, error_msg)
                return self.form_invalid(form)
            else:
                # Re-raise if it's a different integrity error
                raise

        # Create inventory log for initial stock
        InventoryService.create_initial_log(
            variant,
            self.request.user,
            "Initial stock",
            form.cleaned_data.get("supplier_invoice"),
        )

        messages.success(self.request, f"Product variant created successfully")

        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(
            "inventory_products:details", kwargs={"product_id": self.object.product.id}
        )


class EditProductVariant(UpdateView):
    template_name = "inventory/product_variant/form.html"
    form_class = VariantForm
    model = ProductVariant
    title = "Edit Product Variant"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["variant"] = self.object
        context["sizes_form"] = SizeForm()
        context["colors_form"] = ColorForm()
        context["gst_rate"] = self.object.product.hsn_code.gst_percentage
        return context

    def form_valid(self, form):

        try:
            with transaction.atomic():
                variant = form.save(commit=False)
                variant.updated_by = self.request.user
                variant.save()

                InventoryService.update_initial_log(
                    variant, self.request.user, "Initial stock"
                )

            messages.success(self.request, "Product variant updated successfully")
            return super().form_valid(form)

        except IntegrityError as e:
            # Check if it's a unique constraint violation
            if "unique_product" in str(e):
                # Determine which fields are causing the conflict
                size = form.cleaned_data.get("size")
                color = form.cleaned_data.get("color")

                if size and color:
                    error_msg = f"A variant with size '{size}' and color '{color}' already exists for this product."
                elif size:
                    error_msg = (
                        f"A variant with size '{size}' already exists for this product."
                    )
                elif color:
                    error_msg = f"A variant with color '{color}' already exists for this product."
                else:
                    error_msg = "A variant without size and color already exists for this product."

                form.add_error(None, error_msg)
                return self.form_invalid(form)
            else:
                # Re-raise if it's a different integrity error
                raise

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(
            "inventory_products:details", kwargs={"product_id": self.object.product.id}
        )


class StockInCreate(LoginRequiredMixin, CreateView):
    template_name = "inventory/product_variant/inventory_operation_form.html"
    form_class = StockInForm
    model = InventoryLog

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Stock In"
        context["operation_type"] = "stock_in"

        # Get the variant if variant_id is provided
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, is_deleted=False)
                context["selected_variant"] = variant
            except ProductVariant.DoesNotExist:
                messages.error(self.request, "Selected variant not found.")

        return context

    def get_form_kwargs(self):
        """Pass variant to form constructor"""
        kwargs = super().get_form_kwargs()
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, is_deleted=False)
                kwargs["variant"] = variant
            except ProductVariant.DoesNotExist:
                messages.error(self.request, "Selected variant not found.")
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id)
                initial["purchase_price"] = variant.purchase_price
                initial["mrp"] = variant.mrp
            except ProductVariant.DoesNotExist:
                messages.error(self.request, "Selected variant not found.")
        return initial

    def get_success_url(self):
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            return reverse_lazy(
                "inventory_variant:details", kwargs={"variant_id": variant_id}
            )
        else:
            # If no variant_id, redirect to products page
            messages.error(
                self.request,
                "Please select a variant from the variant details page.",
            )
            return redirect("inventory:product_home")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Get the variant
                variant_id = self.kwargs.get("variant_id")
                if variant_id:
                    variant = get_object_or_404(
                        ProductVariant, id=variant_id, is_deleted=False
                    )
                else:
                    # If no variant_id, redirect to products page
                    messages.error(
                        self.request,
                        "Please select a variant from the variant details page.",
                    )
                    return redirect("inventory:product_home")

                # Use InventoryService instead of direct method call
                inventory_log = InventoryService.update_stock_in_log(
                    variant,
                    quantity_change=form.cleaned_data.get("quantity_change"),
                    user=self.request.user,
                    notes=form.cleaned_data.get("notes"),
                    supplier_invoice=form.cleaned_data.get("supplier_invoice"),
                    purchase_price=form.cleaned_data.get("purchase_price"),
                    mrp=form.cleaned_data.get("mrp"),
                )

                if inventory_log:
                    messages.success(
                        self.request,
                        f"Stock in entry created successfully. {form.cleaned_data.get('quantity_change')} units added to {variant.full_name}",
                    )
                    return redirect(self.get_success_url())
                else:
                    messages.error(self.request, "Failed to create stock in entry.")
                    return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Error creating stock in entry: {str(e)}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        print(form.errors)
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class AdjustmentInCreate(LoginRequiredMixin, CreateView):
    template_name = "inventory/product_variant/inventory_operation_form.html"
    form_class = AdjustmentInForm
    model = InventoryLog

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Adjustment In"
        context["operation_type"] = "adjustment_in"

        # Get the variant if variant_id is provided
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, is_deleted=False)
                context["selected_variant"] = variant
            except ProductVariant.DoesNotExist:
                messages.error(self.request, "Selected variant not found.")

        return context

    def get_form_kwargs(self):
        """Pass variant to form constructor"""
        kwargs = super().get_form_kwargs()
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, is_deleted=False)
                kwargs["variant"] = variant
            except ProductVariant.DoesNotExist:
                messages.error(self.request, "Selected variant not found.")
        return kwargs

    def get_success_url(self):
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            return reverse_lazy(
                "inventory_variant:details", kwargs={"variant_id": variant_id}
            )
        return reverse_lazy("inventory:product_home")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Get the variant
                variant_id = self.kwargs.get("variant_id")
                if variant_id:
                    variant = get_object_or_404(
                        ProductVariant, id=variant_id, is_deleted=False
                    )
                else:
                    # If no variant_id, redirect to products page
                    messages.error(
                        self.request,
                        "Please select a variant from the variant details page.",
                    )
                    return redirect("inventory:product_home")

                # Use InventoryService instead of direct method call
                InventoryService.adjust_in_quantity(
                    variant,
                    change=form.cleaned_data.get("quantity_change"),
                    user=self.request.user,
                    notes=form.cleaned_data.get("notes"),
                )

                messages.success(
                    self.request,
                    f"Adjustment in entry created successfully. {form.cleaned_data.get('quantity_change')} units added to {variant.full_name}",
                )
                return redirect(self.get_success_url())
        except Exception as e:
            logger.error(f"Error creating adjustment out entry: {str(e)}")
            messages.error(
                self.request, f"Error creating adjustment in entry: {str(e)}"
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class AdjustmentOutCreate(LoginRequiredMixin, CreateView):
    template_name = "inventory/product_variant/inventory_operation_form.html"
    form_class = AdjustmentOutForm
    model = InventoryLog

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Adjustment Out"
        context["operation_type"] = "adjustment_out"

        # Get the variant if variant_id is provided
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, is_deleted=False)
                context["selected_variant"] = variant
            except ProductVariant.DoesNotExist:
                messages.error(self.request, "Selected variant not found.")

        return context

    def get_form_kwargs(self):
        """Pass variant to form constructor"""
        kwargs = super().get_form_kwargs()
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id, is_deleted=False)
                kwargs["variant"] = variant
            except ProductVariant.DoesNotExist:
                messages.error(self.request, "Selected variant not found.")
        return kwargs

    def get_success_url(self):
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            return reverse_lazy(
                "inventory_variant:details", kwargs={"variant_id": variant_id}
            )
        return reverse_lazy("inventory:product_home")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Get the variant
                variant_id = self.kwargs.get("variant_id")
                if variant_id:
                    variant = get_object_or_404(
                        ProductVariant, id=variant_id, is_deleted=False
                    )
                else:
                    # If no variant_id, redirect to operations page
                    messages.error(
                        self.request,
                        "Please select a variant from the variant details page.",
                    )
                    return redirect("inventory:product_home")

                # Use InventoryService instead of direct method call
                InventoryService.adjust_out_quantity(
                    variant,
                    change=form.cleaned_data.get("quantity_change"),
                    user=self.request.user,
                    notes=form.cleaned_data.get("notes"),
                )

                messages.success(
                    self.request,
                    f"Adjustment out entry created successfully. {form.cleaned_data.get('quantity_change')} units removed from {variant.full_name}",
                )
                return redirect(self.get_success_url())
        except Exception as e:
            print(e)
            messages.error(
                self.request, f"Error creating adjustment out entry: {str(e)}"
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


@login_required
def download_variants(request):
    """Download variants data as JSON."""
    variants = ProductVariant.objects.select_related(
        "product", "product__category", "size", "color"
    ).all()
    data = []

    for variant in variants:
        data.append(
            {
                "id": variant.id,
                "barcode": variant.barcode,
                "brand": variant.product.brand,
                "product_name": variant.product.name,
                "category": (
                    variant.product.category.name if variant.product.category else None
                ),
                "size": variant.size.name if variant.size else None,
                "color": variant.color.name if variant.color else None,
                "quantity": str(variant.quantity),
                "mrp": str(variant.mrp),
                "discount_percentage": str(variant.discount_percentage),
                "final_price": str(variant.final_price),
                "status": variant.status,
                "created_at": variant.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    response = JsonResponse(data, safe=False)
    response["Content-Disposition"] = 'attachment; filename="variants.json"'
    return response


@login_required
def search_variants_ajax(request):
    """AJAX endpoint for real-time variant search."""
    search_query = request.GET.get("q", "")

    if len(search_query) < 2:
        return JsonResponse({"variants": []})

    variants = ProductVariant.objects.select_related(
        "product", "product__category"
    ).filter(
        Q(product__brand__icontains=search_query)
        | Q(product__name__icontains=search_query)
        | Q(barcode__icontains=search_query)
    )[
        :10
    ]  # Limit to 10 results

    data = []
    for variant in variants:
        data.append(
            {
                "id": variant.id,
                "barcode": variant.barcode,
                "brand": variant.product.brand,
                "product_name": variant.product.name,
                "category": (
                    variant.product.category.name if variant.product.category else None
                ),
                "status": variant.status,
            }
        )

    return JsonResponse({"variants": data})


class DamageCreate(LoginRequiredMixin, CreateView):
    template_name = "inventory/product_variant/inventory_operation_form.html"
    form_class = DamageForm
    model = InventoryLog

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Mark as Damaged"
        context["operation_type"] = "damage"

        # Get the variant if variant_id is provided
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id)
                context["selected_variant"] = variant
            except ProductVariant.DoesNotExist as e:
                logger.error(f"Selected variant not found: {e}")
                messages.error(self.request, "Selected variant not found.")

        return context

    def get_form_kwargs(self):
        """Pass variant to form constructor"""
        kwargs = super().get_form_kwargs()
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id)
                kwargs["variant"] = variant
            except ProductVariant.DoesNotExist as e:
                logger.error(f"Selected variant not found: {e}")
                messages.error(self.request, "Selected variant not found.")
        return kwargs

    def get_success_url(self):
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            return reverse_lazy(
                "inventory_variant:details", kwargs={"variant_id": variant_id}
            )
        return reverse_lazy("inventory:product_home")

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Get the variant
                variant_id = self.kwargs.get("variant_id")
                if variant_id:
                    variant = get_object_or_404(ProductVariant, id=variant_id)
                else:
                    # If no variant_id, redirect to operations page
                    messages.error(
                        self.request,
                        "Please select a variant from the variant details page.",
                    )
                    return redirect("inventory:product_home")

                # Use InventoryService instead of direct method call
                InventoryService.damage_log(
                    variant,
                    quantity_damaged=form.cleaned_data.get("quantity_change"),
                    user=self.request.user,
                    notes=form.cleaned_data.get("notes"),
                    supplier_invoice=form.cleaned_data.get("supplier_invoice"),
                )

                messages.success(
                    self.request,
                    f"Damage entry created successfully. {form.cleaned_data.get('quantity_change')} units marked as damaged for {variant.full_name}",
                )
                return redirect(self.get_success_url())
        except Exception as e:
            logger.error(f"Error creating damage entry: {str(e)}")
            messages.error(self.request, f"Error creating damage entry: {str(e)}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)
