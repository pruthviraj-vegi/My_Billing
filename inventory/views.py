from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.db.models import (
    Sum,
    F,
    Q,
    Case,
    When,
    Count,
    Value,
    DecimalField,
    ExpressionWrapper,
    FloatField,
)
from django.db.models.functions import Abs, Coalesce
from django.db import models, transaction
from decimal import Decimal
from django.contrib import messages
from django.views.generic import View, DeleteView
from django.http import JsonResponse

from django.urls import reverse_lazy
from .services import InventoryService

from django.db.utils import IntegrityError
from django.core.cache import cache
from typing import Optional, Union

from .forms import (
    ProductForm,
    VariantForm,
    SizeForm,
    ColorForm,
    CategoryForm,
    ClothTypeForm,
    UOMForm,
    GSTHsnCodeForm,
)
from .models import Product, ProductVariant, InventoryLog

from supplier.models import SupplierInvoice, Supplier
from base.getDates import getDates
from base.utility import render_paginated_response

import logging, json

logger = logging.getLogger(__name__)


def inventory_dashboard(request):
    """Enhanced inventory dashboard with comprehensive metrics"""
    active_variants = ProductVariant.objects.filter(
        is_deleted=False, status=ProductVariant.VariantStatus.ACTIVE
    )

    # Additional metrics
    total_products = Product.objects.filter(is_deleted=False).count()
    total_variants = active_variants.count()
    low_stock_variants = active_variants.filter(
        quantity__lte=F("minimum_quantity")
    ).count()

    # Calculate total inventory value (quantity * purchase_price)
    total_inventory_value = sum(
        variant.quantity * variant.purchase_price for variant in active_variants
    )

    # Calculate and cache total_stock_by_supplier (date-independent, loaded once)
    total_stock_data = _calculate_total_stock_by_supplier()

    context = {
        "total_products": total_products,
        "total_variants": total_variants,
        "low_stock_variants": low_stock_variants,
        "total_inventory_value": total_inventory_value,
        "date_filter": request.GET.get("date_filter", "this_month"),
        "total_stock_data_json": json.dumps(
            total_stock_data
        ),  # Pass as JSON string for template
    }

    return render(request, "inventory/dashboard.html", context)


def inventory_dashboard_fetch(request):
    """AJAX endpoint to fetch dynamic dashboard data based on date filter"""
    start_date, end_date = getDates(request)
    date_filter = request.GET.get("date_filter", "this_month")

    # Calculate monetary Stock In (|quantity| * purchase_price)
    stock_in = (
        InventoryLog.objects.filter(
            transaction_type="STOCK_IN",
            variant__is_deleted=False,
            timestamp__gte=start_date,
            timestamp__lte=end_date,
        ).aggregate(
            total=Sum(
                Abs(F("quantity_change")) * F("purchase_price"),
                output_field=models.DecimalField(max_digits=16, decimal_places=2),
            )
        )[
            "total"
        ]
        or 0
    )

    # Calculate monetary Stock Out valued at purchase price baseline (|quantity| * purchase_price)
    stock_out = (
        InventoryLog.objects.filter(
            transaction_type="SALE",
            variant__is_deleted=False,
            timestamp__gte=start_date,
            timestamp__lte=end_date,
        ).aggregate(
            total=Sum(
                Abs(F("quantity_change")) * F("purchase_price"),
                output_field=models.DecimalField(max_digits=16, decimal_places=2),
            )
        )[
            "total"
        ]
        or 0
    )

    # Get supplier shares for stock_in and stock_out
    def aggregate_by_supplier(qs, supplier_path):
        data = (
            qs.values(name=F(f"{supplier_path}__name"))
            .annotate(
                amount=Sum(
                    Abs(F("quantity_change")) * F("purchase_price"),
                    output_field=models.DecimalField(max_digits=16, decimal_places=2),
                )
            )
            .order_by("-amount")
        )
        result = []
        for item in data:
            result.append(
                {
                    "supplier_name": item["name"] or "Others",
                    "amount": float(item["amount"] or 0),
                    "count": 0,  # Not applicable for inventory, but keeping format consistent
                }
            )
        return result

    # Base query for date range
    base_qs = InventoryLog.objects.filter(
        variant__is_deleted=False, timestamp__gte=start_date, timestamp__lte=end_date
    )

    # Stock in breakdown by supplier
    stock_in_breakdown = aggregate_by_supplier(
        base_qs.filter(transaction_type="STOCK_IN"), "supplier_invoice__supplier"
    )

    # Calculate percentages for stock in
    stock_in_total = float(sum(item["amount"] for item in stock_in_breakdown))
    for item in stock_in_breakdown:
        percentage = (
            (item["amount"] / stock_in_total * 100) if stock_in_total > 0 else 0
        )
        item["percentage"] = round(percentage, 1)

    # Stock out breakdown by supplier
    stock_out_breakdown = aggregate_by_supplier(
        base_qs.filter(transaction_type="SALE"),
        "source_inventory_log__supplier_invoice__supplier",
    )

    # Calculate percentages for stock out
    stock_out_total = float(sum(item["amount"] for item in stock_out_breakdown))
    for item in stock_out_breakdown:
        percentage = (
            (item["amount"] / stock_out_total * 100) if stock_out_total > 0 else 0
        )
        item["percentage"] = round(percentage, 1)

    # Prepare stats
    stats = {
        "stock_in": float(round(stock_in, 2)),
        "stock_out": float(round(stock_out, 2)),
    }

    return JsonResponse(
        {
            "success": True,
            "stats": stats,
            "stock_in_breakdown": stock_in_breakdown,
            "stock_out_breakdown": stock_out_breakdown,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "filter": date_filter,
            },
        }
    )


def _calculate_total_stock_by_supplier():
    """
    Calculate total stock by supplier (cached, date-independent).
    Optimized with bulk queries to avoid N+1 problem.
    """
    cache_key = "inventory_total_stock_by_supplier"
    cached_result = cache.get(cache_key)

    if cached_result is not None:
        return cached_result

    # Get all active variants with their quantities and prices
    active_variants = ProductVariant.objects.filter(
        is_deleted=False, status=ProductVariant.VariantStatus.ACTIVE
    ).values("id", "quantity", "purchase_price")

    variant_ids = [v["id"] for v in active_variants]

    if not variant_ids:
        result = {"labels": [], "values": []}
        cache.set(cache_key, result, 300)  # Cache for 5 minutes
        return result

    # Get all stock-in transactions for variants (ordered by timestamp desc)
    # Then group in Python to get latest per variant (works across all databases)
    all_stock_in_logs = (
        InventoryLog.objects.filter(
            variant_id__in=variant_ids,
            transaction_type__in=["STOCK_IN", "INITIAL"],
            supplier_invoice__isnull=False,
        )
        .select_related("supplier_invoice__supplier")
        .order_by("variant_id", "-timestamp")
        .values("variant_id", "supplier_invoice__supplier__name")
    )

    # Create a mapping of variant_id -> supplier_name (keep first/latest per variant)
    variant_to_supplier = {}
    for log in all_stock_in_logs:
        variant_id = log["variant_id"]
        if (
            variant_id not in variant_to_supplier
        ):  # First occurrence is latest due to ordering
            supplier_name = log.get("supplier_invoice__supplier__name")
            if supplier_name:
                variant_to_supplier[variant_id] = supplier_name

    # Aggregate by supplier
    total_stock_by_supplier = {}
    for variant in active_variants:
        variant_id = variant["id"]
        supplier_name = variant_to_supplier.get(variant_id, "Others")
        stock_value = float(variant["quantity"] * variant["purchase_price"])
        total_stock_by_supplier[supplier_name] = (
            total_stock_by_supplier.get(supplier_name, 0) + stock_value
        )

    # Convert to sorted lists
    sorted_total_stock = sorted(
        total_stock_by_supplier.items(), key=lambda x: x[1], reverse=True
    )

    # Calculate percentages
    total_stock_value = sum(item[1] for item in sorted_total_stock)

    result = {
        "labels": [item[0] for item in sorted_total_stock],
        "values": [round(item[1], 2) for item in sorted_total_stock],
        "percentages": [
            (
                round((item[1] / total_stock_value * 100), 1)
                if total_stock_value > 0
                else 0
            )
            for item in sorted_total_stock
        ],
    }

    # Cache for 5 minutes (300 seconds)
    cache.set(cache_key, result, 300)
    return result


def inventory_supplier_shares_fetch(request):
    """
    Return per-supplier shares for STOCK_IN and SALE (date-dependent only).
    Total stock is loaded once on initial page load and cached.
    """
    start_date, end_date = getDates(request)

    def aggregate_by_supplier(qs, supplier_path):
        data = (
            qs.values(name=F(f"{supplier_path}__name"))
            .annotate(
                amount=Sum(
                    Abs(F("quantity_change")) * F("purchase_price"),
                    output_field=models.DecimalField(max_digits=16, decimal_places=2),
                )
            )
            .order_by("-amount")
        )
        labels = [item["name"] or "Others" for item in data]
        values = [round(item["amount"] or 0, 2) for item in data]
        return labels, values

    # Only calculate date-dependent metrics (stock_in and stock_out)
    # total_stock is loaded once on initial page render and stays cached
    base_qs = InventoryLog.objects.filter(
        variant__is_deleted=False, timestamp__gte=start_date, timestamp__lte=end_date
    )

    in_labels, in_values = aggregate_by_supplier(
        base_qs.filter(transaction_type="STOCK_IN"), "supplier_invoice__supplier"
    )

    # STOCK_OUT share attributed to the source stock's supplier - date-dependent
    out_labels, out_values = aggregate_by_supplier(
        base_qs.filter(transaction_type="SALE"),
        "source_inventory_log__supplier_invoice__supplier",
    )

    return JsonResponse(
        {
            "stock_in": {"labels": in_labels, "values": in_values},
            "stock_out": {"labels": out_labels, "values": out_values},
        }
    )


def low_stock_page(request):
    """Display all low stock items with pagination"""

    # Get active variants that are low on stock
    low_stock_variants = (
        ProductVariant.objects.filter(
            is_deleted=False,
            status=ProductVariant.VariantStatus.ACTIVE,
            quantity__lte=F("minimum_quantity"),
        )
        .select_related("product")
        .order_by("quantity")
    )

    # Pagination
    from django.core.paginator import Paginator

    paginator = Paginator(low_stock_variants, 20)  # 20 items per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Calculate summary stats
    total_low_stock = low_stock_variants.count()
    out_of_stock = low_stock_variants.filter(quantity=0).count()
    critical_stock = low_stock_variants.filter(
        quantity__lt=F("minimum_quantity") * 0.5
    ).count()

    # Add critical threshold to each variant for template use
    for variant in page_obj:
        variant.critical_threshold = float(variant.minimum_quantity) * 0.5

    context = {
        "page_obj": page_obj,
        "total_low_stock": total_low_stock,
        "out_of_stock": out_of_stock,
        "critical_stock": critical_stock,
        "title": "Low Stock Items",
    }

    return render(request, "inventory/low_stock.html", context)


class CreateProduct(View):
    template_name = "inventory/product_create.html"
    title = "Create Product"
    session_initial_key = "create_product_initial"
    session_barcode_key = "redirect_url"
    ACTION_CREATE_ADD = "create_add"

    def get(self, request):
        product_form, variant_form = self._get_initial_forms(request)
        return self._render_response(request, product_form, variant_form)

    def post(self, request):
        product_form = ProductForm(request.POST)
        variant_form = VariantForm(request.POST)
        action = request.POST.get("action")
        if not (product_form.is_valid() and variant_form.is_valid()):
            logger.warning(
                "Product creation form validation failed",
                extra={
                    "user_id": request.user.id,
                    "product_errors": product_form.errors,
                    "variant_errors": variant_form.errors,
                },
            )
            messages.error(request, "Please correct the errors below.")
            return self._render_response(request, product_form, variant_form)

        # Valid forms — create inside atomic block
        try:
            with transaction.atomic():
                product = product_form.save()
                variant = variant_form.save(commit=False)
                variant.product = product
                variant.created_by = request.user
                variant.save()
                InventoryService.create_initial_log(
                    variant,
                    request.user,
                    "Initial stock",
                    variant_form.cleaned_data.get("supplier_invoice"),
                )

        except IntegrityError as e:
            logger.exception(
                "Database integrity error during product creation",
                extra={"user_id": request.user.id, "error": str(e)},
            )
            messages.error(request, "A product with similar details already exists.")
            return self._render_response(request, product_form, variant_form)
        except Exception as e:
            logger.exception(
                "Product creation failed unexpectedly",
                extra={"user_id": request.user.id, "error": str(e)},
            )
            messages.error(request, "An unexpected error occurred. Please try again.")
            return self._render_response(request, product_form, variant_form)

        messages.success(request, "Product created successfully")

        if action == self.ACTION_CREATE_ADD:
            self._persist_initial_fields(request, product_form, variant_form)
            # Store barcode URL in session for JavaScript to open
            barcode_url = reverse("report:barcode", kwargs={"pk": variant.id})
            request.session[self.session_barcode_key] = barcode_url
            request.session.modified = True
            return redirect(request.path)

        self._clear_initial_fields(request)
        return redirect("inventory_products:details", product_id=product.id)

    # ------------------ Helpers ------------------

    def _render_response(self, request, product_form, variant_form):
        return render(
            request,
            self.template_name,
            self.get_context_data(
                request, product_form=product_form, variant_form=variant_form
            ),
        )

    def get_context_data(self, request, product_form=None, variant_form=None, **kwargs):
        context = {
            "title": self.title,
            "product_form": product_form or ProductForm(),
            "variant_form": variant_form or VariantForm(),
        }
        context.update(self._get_aux_forms())

        # Add barcode URL to context and clear it from session
        barcode_url = request.session.pop(self.session_barcode_key, None)
        if barcode_url:
            context["redirect_url"] = barcode_url

        return context

    def _get_aux_forms(self):
        return {
            "category_form": CategoryForm(),
            "cloth_type_form": ClothTypeForm(),
            "uom_form": UOMForm(),
            "gst_hsn_form": GSTHsnCodeForm(),
            "size_form": SizeForm(),
            "color_form": ColorForm(),
        }

    def _get_initial_forms(self, request):
        stored = request.session.pop(self.session_initial_key, None) or {}
        return (
            ProductForm(initial=stored.get("product", {})),
            VariantForm(initial=stored.get("variant", {})),
        )

    def _get_fields_to_persist(self):
        """Define which fields should persist in 'create and add another' workflow"""
        return {
            "product": ["cloth_type", "category", "hsn_code", "uom"],
            "variant": [
                "supplier_invoice",
                "commission_percentage",
                "discount_percentage",
            ],
        }

    def _persist_initial_fields(self, request, product_form, variant_form):
        """Persist form fields to session for 'create and add another' workflow"""
        serialize = self._serialize_value
        fields_to_persist = self._get_fields_to_persist()
        persisted_data = {}

        for form_type, field_names in fields_to_persist.items():
            form = product_form if form_type == "product" else variant_form
            persisted_data[form_type] = {
                field: serialize(form.cleaned_data.get(field)) for field in field_names
            }

        request.session[self.session_initial_key] = persisted_data
        request.session.modified = True

    def _clear_initial_fields(self, request):
        request.session.pop(self.session_initial_key, None)

    @staticmethod
    def _serialize_value(value) -> Optional[Union[int, str]]:
        """Serialize form field values for session storage"""
        if hasattr(value, "pk"):
            return value.pk
        if isinstance(value, Decimal):
            return str(value)
        return value


class DeleteProductVariant(DeleteView):
    template_name = "inventory/product_variant/delete.html"
    title = "Delete Product Variant"
    model = ProductVariant

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["variant"] = self.get_object()
        return context

    def get_success_url(self):
        # Store product ID before deletion
        product_id = (
            self.object.product.id if self.object and self.object.product else None
        )
        if product_id:
            return reverse_lazy("inventory:product_details", kwargs={"id": product_id})
        else:
            return reverse_lazy("inventory:product_home")

    def form_valid(self, form):
        # Store product ID before deletion
        product_id = (
            self.object.product.id if self.object and self.object.product else None
        )

        # Let Django handle the deletion properly
        result = super().form_valid(form)

        # Add success message
        messages.success(self.request, "Product variant deleted successfully")

        # Redirect to appropriate page
        if product_id:
            return redirect("inventory:product_details", id=product_id)
        else:
            return redirect("inventory:product_home")

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


def variant_update(request, pk):
    """Update product variant details"""
    variant = get_object_or_404(ProductVariant, pk=pk)

    if request.method == "POST":
        form = VariantForm(request.POST, instance=variant)
        if form.is_valid():
            try:
                with transaction.atomic():
                    old_purchase_price = variant.purchase_price
                    old_mrp = variant.mrp

                    # Save the updated variant
                    variant = form.save(commit=False)
                    variant.save()

                    # Create inventory log for price changes
                    if (
                        variant.purchase_price != old_purchase_price
                        or variant.mrp != old_mrp
                    ):
                        InventoryLog.objects.create(
                            variant=variant,
                            transaction_type="ADJUSTMENT_IN",
                            quantity_change=0,
                            new_quantity=variant.quantity,
                            purchase_price=variant.purchase_price,
                            mrp=variant.mrp,
                            notes=f"Price update: Purchase {old_purchase_price}→{variant.purchase_price}, Selling {old_mrp}→{variant.mrp}",
                            created_by=request.user,
                        )

                    messages.success(
                        request, f"Successfully updated {variant.full_name}"
                    )
                    return redirect("inventory:variant_details", pk=pk)
            except Exception as e:
                logger.error(f"Error updating variant: {str(e)}")
                messages.error(request, f"Error updating variant: {str(e)}")
    else:
        form = VariantForm(instance=variant)
        logger.error(f"Form invalid: {form.errors}")
        messages.error(request, "Please correct the errors below.")

    context = {
        "form": form,
        "variant": variant,
        "title": f"Update {variant.full_name}",
        "subtitle": "Update variant details and pricing",
    }
    return render(request, "inventory/variant_update.html", context)


def _supplier_invoice_tracking_queryset(request):
    search_query = request.GET.get("search", "").strip()
    supplier_filter = request.GET.get("supplier", "").strip()
    sort_by = (request.GET.get("sort") or "-invoice_date").strip()

    supplier_invoices = (
        SupplierInvoice.objects.select_related("supplier")
        .filter(is_deleted=False)
        .annotate(
            stock_in_quantity=Coalesce(
                Sum(
                    Case(
                        When(
                            inventory_logs__transaction_type__in=[
                                "STOCK_IN",
                                "INITIAL",
                            ],
                            then=F("inventory_logs__quantity_change"),
                        ),
                        default=Decimal("0"),
                        output_field=models.DecimalField(),
                    )
                ),
                Decimal("0"),
            ),
            sales_quantity=Coalesce(
                Sum(
                    Case(
                        When(
                            inventory_logs__transaction_type="SALE",
                            then=Abs(F("inventory_logs__quantity_change")),
                        ),
                        default=Decimal("0"),
                        output_field=models.DecimalField(),
                    )
                ),
                Decimal("0"),
            )
            - Coalesce(
                Sum(
                    Case(
                        When(
                            inventory_logs__transaction_type="RETURN",
                            then=Abs(F("inventory_logs__quantity_change")),
                        ),
                        default=Decimal("0"),
                        output_field=models.DecimalField(),
                    )
                ),
                Decimal("0"),
            )
            - Coalesce(
                Sum(
                    Case(
                        When(
                            inventory_logs__transaction_type="DAMAGE",
                            then=Abs(F("inventory_logs__quantity_change")),
                        ),
                        default=Decimal("0"),
                        output_field=models.DecimalField(),
                    )
                ),
                Decimal("0"),
            ),
            stock_amount=Coalesce(
                Sum(
                    Case(
                        When(
                            inventory_logs__transaction_type__in=[
                                "STOCK_IN",
                                "INITIAL",
                            ],
                            then=ExpressionWrapper(
                                F("inventory_logs__quantity_change")
                                * F("inventory_logs__purchase_price"),
                                output_field=DecimalField(
                                    max_digits=16, decimal_places=2
                                ),
                            ),
                        ),
                        default=Value(0),
                        output_field=DecimalField(max_digits=16, decimal_places=2),
                    )
                ),
                Value(0),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
            products_count=Count(
                "inventory_logs__variant__product",
                filter=Q(inventory_logs__transaction_type__in=["STOCK_IN", "INITIAL"]),
                distinct=True,
            ),
        )
    )
    supplier_invoices = supplier_invoices.annotate(
        remaining_quantity=ExpressionWrapper(
            F("stock_in_quantity") - F("sales_quantity"),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        ),
    )

    supplier_invoices = supplier_invoices.annotate(
        remaining_percentage=Case(
            When(
                stock_in_quantity__gt=0,
                then=ExpressionWrapper(
                    Value(100.0)
                    - (F("remaining_quantity") * Value(100.0) / F("stock_in_quantity")),
                    output_field=FloatField(),
                ),
            ),
            default=Value(0.0),
            output_field=FloatField(),
        )
    ).filter(stock_in_quantity__gt=0)

    if search_query:
        supplier_invoices = supplier_invoices.filter(
            Q(invoice_number__icontains=search_query)
            | Q(supplier__name__icontains=search_query)
        )

    if supplier_filter:
        supplier_invoices = supplier_invoices.filter(supplier_id=supplier_filter)

    ordering_map = {
        "invoice_number": "invoice_number",
        "-invoice_number": "-invoice_number",
        "supplier_name": "supplier__name",
        "-supplier_name": "-supplier__name",
        "invoice_date": "invoice_date",
        "-invoice_date": "-invoice_date",
        "invoice_amount": "total_amount",
        "-invoice_amount": "-total_amount",
        "stock_in_quantity": "stock_in_quantity",
        "-stock_in_quantity": "-stock_in_quantity",
        "sales_quantity": "sales_quantity",
        "-sales_quantity": "-sales_quantity",
        "remaining_quantity": "remaining_quantity",
        "-remaining_quantity": "-remaining_quantity",
        "remaining_percentage": "remaining_percentage",
        "-remaining_percentage": "-remaining_percentage",
        "stock_amount": "stock_amount",
        "-stock_amount": "-stock_amount",
    }

    return supplier_invoices.order_by(ordering_map.get(sort_by, "-invoice_date"))


def supplier_invoice_tracking(request):
    """Render main page; data loads via AJAX fetch endpoint."""
    suppliers = Supplier.objects.filter(is_deleted=False).order_by("name")
    return render(
        request,
        "inventory/supplier_invoice_tracking.html",
        {
            "suppliers": suppliers,
            "search_query": request.GET.get("search", ""),
            "supplier_filter": request.GET.get("supplier", ""),
        },
    )


def supplier_invoice_tracking_fetch(request):
    """AJAX endpoint powering supplier invoice tracking table."""
    invoices = _supplier_invoice_tracking_queryset(request)
    return render_paginated_response(
        request,
        invoices,
        "inventory/supplier_invoice_tracking_fetch.html",
    )


def supplier_invoice_details(request, invoice_id):
    """View to show detailed breakdown of a specific supplier invoice"""

    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")
    sort_by = request.GET.get("sort", "-stock_in_quantity")

    products_query = (
        InventoryLog.objects.filter(supplier_invoice__id=invoice_id)
        .values(
            "variant__product__brand",
            "variant__product__name",
            "variant__size__name",
            "variant__color__name",
            "variant__barcode",
            "variant__id",
        )
        .with_stock_summary()
        .annotate(
            purchase_price=Coalesce(
                Sum(
                    Case(
                        When(
                            transaction_type__in=["STOCK_IN", "INITIAL"],
                            then=F("purchase_price"),
                        ),
                        default=Value(0),
                        output_field=models.DecimalField(),
                    )
                ),
                Value(0),
                output_field=models.DecimalField(),
            )
        )
    )

    if search_query:
        products_query = products_query.filter(
            Q(variant__product__brand__icontains=search_query)
            | Q(variant__product__name__icontains=search_query)
            | Q(variant__barcode__icontains=search_query)
        )

    # Apply sorting for stock-in data
    sort_mapping = {
        "brand": "variant__product__brand",
        "-brand": "-variant__product__brand",
        "stock_in_quantity": "stock_in_quantity",
        "-stock_in_quantity": "-stock_in_quantity",
    }

    order_field = sort_mapping.get(sort_by, "-stock_in_quantity")
    products_in_invoice = list(products_query.order_by(order_field))

    for product in products_in_invoice:
        stock_in = product.get("stock_in_quantity") or Decimal("0")
        sales_quantity = abs(product.get("sales_quantity") or Decimal("0"))
        damage_quantity = abs(product.get("damage_quantity") or Decimal("0"))

        product["sales_quantity"] = sales_quantity
        product["damage_quantity"] = damage_quantity
        product["remaining_quantity"] = stock_in - sales_quantity - damage_quantity

    # Apply status filter after calculating remaining quantities
    if status_filter == "sold_out":
        products_in_invoice = [
            p for p in products_in_invoice if p["remaining_quantity"] <= 0
        ]
    elif status_filter == "in_stock":
        products_in_invoice = [
            p for p in products_in_invoice if p["remaining_quantity"] > 0
        ]
    elif status_filter == "low_stock":
        products_in_invoice = [
            p for p in products_in_invoice if 0 < p["remaining_quantity"] <= 5
        ]

    # Apply additional sorting after calculating sales quantities
    if sort_by in [
        "sales_quantity",
        "-sales_quantity",
        "remaining_quantity",
        "-remaining_quantity",
    ]:
        reverse = sort_by.startswith("-")
        field = sort_by.lstrip("-")
        products_in_invoice.sort(key=lambda x: x[field], reverse=reverse)

    # Single query for totals using aggregation
    totals = InventoryLog.objects.filter(supplier_invoice__id=invoice_id).aggregate(
        total_sales=Coalesce(
            Sum(
                Case(
                    When(transaction_type="SALE", then=F("quantity_change")),
                    default=Decimal("0"),
                    output_field=models.DecimalField(),
                )
            )
            + Sum(
                Case(
                    When(transaction_type="RETURN", then=F("quantity_change")),
                    default=Decimal("0"),
                    output_field=models.DecimalField(),
                )
            )
            - Sum(
                Case(
                    When(transaction_type="DAMAGE", then=F("quantity_change")),
                    default=Decimal("0"),
                    output_field=models.DecimalField(),
                )
            ),
            Decimal("0"),
        ),
        total_stock_in=Coalesce(
            Sum(
                Case(
                    When(
                        transaction_type__in=["STOCK_IN", "INITIAL"],
                        then=F("quantity_change"),
                    ),
                    default=Decimal("0"),
                    output_field=models.DecimalField(),
                )
            ),
            Decimal("0"),
        ),
    )

    # Get invoice info in single query
    invoice_info = (
        InventoryLog.objects.filter(supplier_invoice__id=invoice_id)
        .select_related("supplier_invoice__supplier")
        .values(
            "supplier_invoice__supplier__name",
            "supplier_invoice__invoice_date",
            "supplier_invoice__invoice_number",
        )
        .first()
    )

    context = {
        "invoice_number": invoice_info["supplier_invoice__invoice_number"],
        "invoice_info": invoice_info,
        "products_in_invoice": products_in_invoice,
        "title": f"Invoice - {invoice_info['supplier_invoice__invoice_number']}",
        "total_sales": abs(totals["total_sales"]),
        "total_stock_in": totals["total_stock_in"],
        "total_remaining": totals["total_stock_in"] - abs(totals["total_sales"]),
        "search_query": search_query,
        "status_filter": status_filter,
        "sort_by": sort_by,
    }
    return render(request, "inventory/supplier_invoice_details.html", context)


# def product_invoice_analytics(request, variant_id):
#     """View to show analytics for a specific product variant by supplier invoice"""

#     variant = get_object_or_404(ProductVariant, id=variant_id)

#     # Get all supplier invoices for this variant
#     invoices = (
#         InventoryLog.objects.filter(variant=variant, supplier_invoice__isnull=False)
#         .values("supplier_invoice__invoice_number", "supplier_invoice__supplier__name")
#         .distinct()
#     )

#     analytics = []
#     for invoice in invoices:
#         invoice_number = invoice["supplier_invoice__invoice_number"]
#         supplier_name = invoice["supplier_invoice__supplier__name"]

#         # Get stock in for this invoice
#         stock_in_logs = InventoryLog.objects.filter(
#             variant=variant,
#             supplier_invoice__invoice_number=invoice_number,
#             transaction_type__in=["STOCK_IN", "INITIAL"],
#         )

#         # Get sales for this invoice
#         sales_logs = InventoryLog.objects.filter(
#             product_variant=variant,
#             supplier_invoice__invoice_number=invoice_number,
#             transaction_type="SALE",
#         )

#         # Calculate metrics
#         total_stock_in = (
#             stock_in_logs.aggregate(total=Sum("quantity_change"))["total"] or 0
#         )
#         total_sales = abs(
#             sales_logs.aggregate(total=Sum("quantity_allocated"))["total"] or 0
#         )
#         remaining = total_stock_in - total_sales

#         # Calculate movement rate
#         if stock_in_logs.exists():
#             first_stock_in = stock_in_logs.order_by("timestamp").first()
#             days_since_stock_in = (timezone.now() - first_stock_in.timestamp).days
#             movement_rate = (
#                 total_sales / max(days_since_stock_in, 1)
#                 if days_since_stock_in > 0
#                 else 0
#             )
#         else:
#             movement_rate = 0
#             days_since_stock_in = 0

#         analytics.append(
#             {
#                 "invoice_number": invoice_number,
#                 "supplier_name": supplier_name,
#                 "total_stock_in": total_stock_in,
#                 "total_sales": total_sales,
#                 "remaining_quantity": remaining,
#                 "movement_rate": round(movement_rate, 2),
#                 "days_since_stock_in": days_since_stock_in,
#             }
#         )

#     context = {
#         "variant": variant,
#         "analytics": analytics,
#         "title": f"{variant.simple_name} - Invoice Analytics",
#     }
#     return render(request, "inventory/product_invoice_analytics.html", context)


# def supplier_analytics(request, supplier_id):
#     """View to show analytics for a specific supplier"""

#     supplier = get_object_or_404(Supplier, id=supplier_id)

#     # Get all invoices for this supplier
#     invoices = (
#         InventoryLog.objects.filter(
#             supplier_invoice__supplier=supplier,
#             transaction_type__in=["STOCK_IN", "INITIAL"],
#         )
#         .values("supplier_invoice__invoice_number", "supplier_invoice__invoice_date")
#         .distinct()
#         .order_by("-supplier_invoice__invoice_date")
#     )

#     movement_data = []
#     for invoice in invoices:
#         invoice_number = invoice["supplier_invoice__invoice_number"]
#         invoice_date = invoice["supplier_invoice__invoice_date"]

#         # Get stock in for this invoice
#         stock_in = (
#             InventoryLog.objects.filter(
#                 supplier_invoice__invoice_number=invoice_number,
#                 transaction_type__in=["STOCK_IN", "INITIAL"],
#             ).aggregate(total=Sum("quantity_change"))["total"]
#             or 0
#         )

#         # Get sales for this invoice
#         sales = abs(
#             InventoryLog.objects.filter(
#                 supplier_invoice__invoice_number=invoice_number,
#                 transaction_type="SALE",
#             ).aggregate(total=Sum("quantity_allocated"))["total"]
#             or 0
#         )

#         # Calculate days since invoice
#         days_since = (timezone.now() - invoice_date).days

#         movement_data.append(
#             {
#                 "invoice_number": invoice_number,
#                 "invoice_date": invoice_date,
#                 "stock_in_quantity": stock_in,
#                 "sales_quantity": sales,
#                 "remaining_quantity": stock_in - sales,
#                 "days_since_invoice": days_since,
#                 "movement_rate": sales / max(days_since, 1) if days_since > 0 else 0,
#             }
#         )

#     context = {
#         "supplier": supplier,
#         "movement_data": movement_data,
#         "title": f"{supplier.name} - Analytics",
#     }
#     return render(request, "inventory/supplier_analytics.html", context)
