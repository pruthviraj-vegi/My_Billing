"""Product variant management views."""

import logging
from decimal import Decimal
from typing import Optional, Union

from django.contrib import messages
from django.db import transaction
from django.db.models import F, Q, Sum, DecimalField
from django.db.utils import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from base.decorators import RequiredPermissionMixin, required_permission
from base.utility import render_paginated_response, table_sorting

from inventory.forms import (
    AdjustmentInForm,
    AdjustmentOutForm,
    ColorForm,
    DamageForm,
    SizeForm,
    StockInForm,
    VariantForm,
    VariantMediaForm,
)
from inventory.models import (
    Category,
    Color,
    InventoryLog,
    Product,
    ProductVariant,
    Size,
    VariantMedia,
)
from inventory.services import InventoryService

logger = logging.getLogger(__name__)

VALID_SORT_FIELDS = {
    "id",
    "barcode",
    "product__brand",
    "product__name",
    "product__category__name",
    "size__name",
    "color__name",
    "quantity",
    "mrp",
    "commission_percentage",
    "discount_percentage",
    "status",
    "created_at",
}

VARIANTS_PER_PAGE = 20


@required_permission("inventory.view_productvariant")
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
    """Retrieve and filter variants based on request parameters."""

    # Get search and filter parameters
    search_query = request.GET.get("search", "")
    category_filter = request.GET.get("category", "")
    color_filter = request.GET.get("color", "")
    size_filter = request.GET.get("size", "")
    status_filter = request.GET.get("status", "")
    stock_filter = request.GET.get("stock", "")

    # Apply search filter
    filters = Q()
    if search_query:
        # Split query into words so multiple terms can be matched
        terms = search_query.split()
        for term in terms:
            filters &= (
                Q(product__brand__icontains=term)
                | Q(product__name__icontains=term)
                | Q(barcode__icontains=term)
                | Q(product__description__icontains=term)
                | Q(product__category__name__icontains=term)
                | Q(size__name__icontains=term)
                | Q(color__name__icontains=term)
                | Q(mrp__icontains=term)
                | Q(purchase_price__icontains=term)
            )

    # Apply category filter (supports both ID and name search)
    if category_filter:
        try:
            # Try as ID first
            category_id = int(category_filter)
            filters &= Q(product__category_id=category_id)
        except ValueError:
            # If not a number, search by name
            filters &= Q(product__category__name__icontains=category_filter)

    # Apply color filter (supports both ID and name search)
    if color_filter:
        try:
            # Try as ID first
            color_id = int(color_filter)
            filters &= Q(color_id=color_id)
        except ValueError:
            # If not a number, search by name
            filters &= Q(color__name__icontains=color_filter)

    # Apply size filter (supports both ID and name search)
    if size_filter:
        try:
            # Try as ID first
            size_id = int(size_filter)
            filters &= Q(size_id=size_id)
        except ValueError:
            # If not a number, search by name
            filters &= Q(size__name__icontains=size_filter)

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

    variants = (
        ProductVariant.objects.select_related(
            "product", "product__category", "size", "color"
        )
        .filter(filters)
    )

    # Apply sorting
    valid_sorts = table_sorting(request, VALID_SORT_FIELDS, "-created_at")
    variants = variants.order_by(*valid_sorts)

    return variants


def total_inventory_value(request) -> float:
    """Calculate total inventory value."""
    total_value = ProductVariant.objects.aggregate(
        total_value=Sum(
            F("quantity") * F("purchase_price"),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )
    return total_value["total_value"]


def fetch_variants(request):
    """AJAX endpoint to fetch variants with search, filter, and pagination."""
    variants = get_variants_data(request)

    return render_paginated_response(
        request,
        variants,
        "inventory/product_variant/fetch.html",
    )


@required_permission("inventory.view_productvariant")
def variant_details(request, variant_id):
    """Detailed view for a single product variant with stock management options"""

    variant = get_object_or_404(ProductVariant, id=variant_id)

    # Get recent activity logs for this variant (only for active variants)
    recent_logs = variant.inventory_logs.select_related(
        "supplier_invoice", "supplier_invoice__supplier"
    ).order_by("-timestamp")[:20]

    # Get media files for this variant
    media_files = variant.media_files.all()

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
        "media_files": media_files,
        "media_form": VariantMediaForm(),
    }

    return render(request, "inventory/product_variant/details.html", context)


def recent_variants_logs(request, variant_id):
    """AJAX endpoint to fetch recent inventory logs for a variant"""
    variant_logs = (
        get_object_or_404(ProductVariant, id=variant_id)
        .inventory_logs.select_related("supplier_invoice", "supplier_invoice__supplier")
        .order_by("-timestamp")
    )
    return render_paginated_response(
        request,
        variant_logs,
        "inventory/product_variant/recent_logs.html",
        7,
    )


class CreateProductVariant(RequiredPermissionMixin, CreateView):
    """View to create a new product variant"""

    required_permission = "inventory.add_productvariant"

    template_name = "inventory/product_variant/form.html"
    form_class = VariantForm
    model = ProductVariant
    title = "Create Product Variant"
    session_initial_key = "create_variant_initial"
    session_barcode_key = "redirect_url"
    ACTION_CREATE_ADD = "create_add"

    def get_context_data(self, **kwargs):
        """Prepare context data for the variant creation form."""
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["size_form"] = SizeForm()
        context["color_form"] = ColorForm()
        product = Product.objects.get(id=self.kwargs["product_id"])
        context["product"] = product
        context["gst_rate"] = product.hsn_code.gst_percentage

        # Check if this is the first variant for this product
        existing_variants = ProductVariant.objects.filter(product=product)
        context["is_first_variant"] = not existing_variants.exists()

        # Add existing variants to context for reference
        if existing_variants.exists():
            context["existing_variants"] = existing_variants
            context["latest_variant"] = existing_variants.latest(
                "created_at"
            )  # Assuming you have a created_at field

        # Add barcode URL to context and clear it from session
        redirect_url = self.request.session.pop(self.session_barcode_key, None)
        if redirect_url:
            context["redirect_url"] = redirect_url

        return context

    def get_initial(self):
        """Set initial values for the form"""
        initial = super().get_initial()

        # Check session for persisted fields first
        stored = self.request.session.pop(self.session_initial_key, None)
        if stored:
            initial.update(stored)
            return initial

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
        """Handle valid variant creation form submission."""
        # Get the product
        product = Product.objects.get(id=self.kwargs["product_id"])
        action = self.request.POST.get("action")

        # Save the variant inside atomic block
        try:
            with transaction.atomic():
                variant = form.save(commit=False)
                variant.product = product
                variant.created_by = self.request.user
                variant.save()

                # Create inventory log for initial stock
                InventoryService.create_initial_log(
                    variant,
                    self.request.user,
                    "Initial stock",
                    form.cleaned_data.get("supplier_invoice"),
                )
        except IntegrityError as e:
            # Check if it's a unique constraint violation
            if "unique_product" in str(e) or "barcode" in str(e).lower():
                # Determine which fields are causing the conflict
                size = form.cleaned_data.get("size")
                color = form.cleaned_data.get("color")

                if "barcode" in str(e).lower():
                    error_msg = "A variant with this barcode already exists."
                elif size and color:
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
                logger.exception(
                    "Database integrity error during variant creation",
                    extra={"user_id": self.request.user.id, "error": str(e)},
                )
                messages.error(
                    self.request, "A variant with similar details already exists."
                )
                return self.form_invalid(form)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Variant creation failed unexpectedly",
                extra={"user_id": self.request.user.id, "error": str(e)},
            )
            messages.error(
                self.request, "An unexpected error occurred. Please try again."
            )
            return self.form_invalid(form)

        messages.success(self.request, "Product variant created successfully")

        # Handle "create and add another" action
        # Check action value (strip whitespace and compare case-insensitively for robustness)
        action_normalized = (action or "").strip().lower()
        if action_normalized == self.ACTION_CREATE_ADD.lower():
            self._persist_initial_fields(self.request, form)
            # Store barcode URL in session for JavaScript to open
            barcode_url = reverse("report:barcode", kwargs={"pk": variant.id})
            self.request.session[self.session_barcode_key] = barcode_url
            self.request.session.modified = True
            # Use reverse to get the correct URL instead of self.request.path
            create_url = reverse(
                "inventory_variant:create", kwargs={"product_id": product.id}
            )
            return redirect(create_url)

        self._clear_initial_fields(self.request)
        return redirect("inventory_products:details", product_id=product.id)

    def form_invalid(self, form):
        """Handle invalid variant creation form submission."""
        logger.error("Form invalid: %s", form.errors.as_text())
        if form.non_field_errors():
            for error in form.non_field_errors():
                messages.error(self.request, error)
        else:
            messages.error(self.request, "Error in submitting the form")
        return super().form_invalid(form)

    def get_success_url(self):
        """Return the URL to redirect to upon successful variant creation."""
        # This method is only called if form_valid doesn't return a redirect
        # The actual redirect is handled in form_valid based on action
        return reverse_lazy(
            "inventory_products:details", kwargs={"product_id": self.object.product.id}
        )

    # ------------------ Helpers ------------------

    def _get_fields_to_persist(self):
        """Define which fields should persist in 'create and add another' workflow"""
        return [
            "supplier_invoice",
            "commission_percentage",
            "discount_percentage",
            "purchase_price",
            "mrp",
        ]

    def _persist_initial_fields(self, request, form):
        """Persist form fields to session for 'create and add another' workflow"""
        serialize = self._serialize_value
        fields_to_persist = self._get_fields_to_persist()
        persisted_data = {
            field: serialize(form.cleaned_data.get(field))
            for field in fields_to_persist
        }

        request.session[self.session_initial_key] = persisted_data
        request.session.modified = True

    def _clear_initial_fields(self, request):
        """Clear persisted fields from session"""
        request.session.pop(self.session_initial_key, None)

    @staticmethod
    def _serialize_value(value) -> Optional[Union[int, str]]:
        """Serialize form field values for session storage"""
        if hasattr(value, "pk"):
            return value.pk
        if isinstance(value, Decimal):
            return str(value)
        return value


class EditProductVariant(RequiredPermissionMixin, UpdateView):
    """View to edit an existing product variant"""

    required_permission = "inventory.change_productvariant"

    template_name = "inventory/product_variant/form.html"
    form_class = VariantForm
    model = ProductVariant
    title = "Edit Product Variant"

    def get_context_data(self, **kwargs):
        """Prepare context data for the variant editing form."""
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["variant"] = self.object
        context["size_form"] = SizeForm()
        context["color_form"] = ColorForm()
        return context

    def form_valid(self, form):
        """Handle valid variant edit form submission."""

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
        """Handle invalid variant edit form submission."""
        if form.non_field_errors():
            for error in form.non_field_errors():
                messages.error(self.request, error)
        else:
            messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_success_url(self):
        """Return the URL to redirect to upon successful variant edit."""
        return reverse_lazy(
            "inventory_products:details", kwargs={"product_id": self.object.product.id}
        )


class StockInCreate(RequiredPermissionMixin, CreateView):
    """View to process stock in operations for a variant"""

    required_permission = "inventory.add_inventorylog"

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
        """Set initial values for the Stock In form."""
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
                        "Stock in entry created successfully. "
                        f"{form.cleaned_data.get('quantity_change')} units "
                        f"added to {variant.full_name}",
                    )
                    return redirect(self.get_success_url())
                else:
                    messages.error(self.request, "Failed to create stock in entry.")
                    return self.form_invalid(form)
        except Exception as e:  # pylint: disable=broad-except
            messages.error(self.request, f"Error creating stock in entry: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Handle invalid Stock In form submission."""
        logger.error("Form validation error: %s", form.errors)
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class AdjustmentInCreate(RequiredPermissionMixin, CreateView):
    """View to process adjustment in operations for a variant"""

    required_permission = "inventory.add_inventorylog"

    template_name = "inventory/product_variant/inventory_operation_form.html"
    form_class = AdjustmentInForm
    model = InventoryLog

    def get_context_data(self, **kwargs):
        """Prepare context data for the Adjustment In form."""
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
        """Return the URL to redirect to upon successful Adjustment In."""
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            return reverse_lazy(
                "inventory_variant:details", kwargs={"variant_id": variant_id}
            )
        return reverse_lazy("inventory:product_home")

    def form_valid(self, form):
        """Handle valid Adjustment In form submission."""
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
                    "Adjustment in entry created successfully. "
                    f"{form.cleaned_data.get('quantity_change')} units "
                    f"added to {variant.full_name}",
                )
                return redirect(self.get_success_url())
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error creating adjustment in entry: %s", e)
            messages.error(self.request, f"Error creating adjustment in entry: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Handle invalid Adjustment In form submission."""
        logger.error("Form invalid: %s", form.errors)
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class AdjustmentOutCreate(RequiredPermissionMixin, CreateView):
    """View to process adjustment out operations for a variant"""

    required_permission = "inventory.add_inventorylog"

    template_name = "inventory/product_variant/inventory_operation_form.html"
    form_class = AdjustmentOutForm
    model = InventoryLog

    def get_context_data(self, **kwargs):
        """Prepare context data for the Adjustment Out form."""
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
        """Return the URL to redirect to upon successful Adjustment Out."""
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            return reverse_lazy(
                "inventory_variant:details", kwargs={"variant_id": variant_id}
            )
        return reverse_lazy("inventory:product_home")

    def form_valid(self, form):
        """Handle valid Adjustment Out form submission."""
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
                    "Adjustment out entry created successfully. "
                    f"{form.cleaned_data.get('quantity_change')} units "
                    f"removed from {variant.full_name}",
                )
                return redirect(self.get_success_url())
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error creating adjustment out entry: %s", e)
            messages.error(self.request, f"Error creating adjustment out entry: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Handle invalid Adjustment Out form submission."""
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class DamageCreate(RequiredPermissionMixin, CreateView):
    """View to process damage out operations for a variant"""

    required_permission = "inventory.add_inventorylog"

    template_name = "inventory/product_variant/inventory_operation_form.html"
    form_class = DamageForm
    model = InventoryLog

    def get_context_data(self, **kwargs):
        """Prepare context data for the Damage Out form."""
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
                logger.error("Selected variant not found: %s", e)
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
                logger.error("Selected variant not found: %s", e)
                messages.error(self.request, "Selected variant not found.")
        return kwargs

    def get_success_url(self):
        """Return the URL to redirect to upon successful Damage Out."""
        variant_id = self.kwargs.get("variant_id")
        if variant_id:
            return reverse_lazy(
                "inventory_variant:details", kwargs={"variant_id": variant_id}
            )
        return reverse_lazy("inventory:product_home")

    def form_valid(self, form):
        """Handle valid Damage form submission."""
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
                    "Damage entry created successfully. "
                    f"{form.cleaned_data.get('quantity_change')} units "
                    f"marked as damaged for {variant.full_name}",
                )
                return redirect(self.get_success_url())
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error creating damage entry: %s", e)
            messages.error(self.request, f"Error creating damage entry: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Handle invalid Damage form submission."""
        logger.error("Form invalid: %s", form.errors)
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


# ========================================
#  VARIANT MEDIA VIEWS (AJAX)
# ========================================


@require_POST
@required_permission("inventory.change_productvariant")
def variant_media_upload(request, variant_id):
    """AJAX endpoint to upload media files for a variant."""
    variant = get_object_or_404(ProductVariant, id=variant_id)
    files = request.FILES.getlist("file")

    if not files:
        return JsonResponse(
            {"success": False, "error": "No files provided."}, status=400
        )

    uploaded = []
    errors = []

    for f in files:
        form = VariantMediaForm(
            data={"alt_text": "", "is_featured": False}, files={"file": f}
        )
        if form.is_valid():
            media = form.save(commit=False)
            media.variant = variant
            media.save()
            uploaded.append(
                {
                    "id": media.id,
                    "url": media.gallery_url,
                    "original_url": media.original_url,
                    "media_type": media.media_type,
                    "file_size": media.file_size_display,
                    "is_featured": media.is_featured,
                    "featured_url": reverse(
                        "inventory_variant:media_set_featured", args=[media.id]
                    ),
                    "delete_url": reverse(
                        "inventory_variant:media_delete", args=[media.id]
                    ),
                }
            )
        else:
            errors.append(
                {"file": f.name, "errors": form.errors.get("file", ["Unknown error"])}
            )

    return JsonResponse(
        {
            "success": len(uploaded) > 0,
            "uploaded": uploaded,
            "errors": errors,
            "total_media": variant.media_files.count(),
        }
    )


@require_POST
@required_permission("inventory.change_productvariant")
def variant_media_delete(request, media_id):
    """AJAX endpoint to delete a single media item."""
    import gc
    import time

    media = get_object_or_404(VariantMedia, id=media_id)
    variant_id = media.variant_id

    # Collect file paths before deleting the DB record
    file_fields = []
    if media.file:
        file_fields.append(media.file)
    if media.thumbnail:
        file_fields.append(media.thumbnail)

    # Close any open file handles (Pillow lazy-loads on Windows)
    for field in file_fields:
        try:
            field.close()
        except Exception:  # noqa: BLE001
            pass

    # Force garbage collection to release lingering file handles
    gc.collect()

    # Delete the physical files with retry for Windows file-locking
    for field in file_fields:
        for attempt in range(3):
            try:
                field.storage.delete(field.name)
                break
            except PermissionError:
                if attempt < 2:
                    gc.collect()
                    time.sleep(0.2)
                else:
                    logger.warning(
                        "Could not delete file %s — it may be locked by another "
                        "process. The DB record will still be removed.",
                        field.name,
                    )

    # Always delete the DB record
    media.delete()
    return JsonResponse(
        {
            "success": True,
            "total_media": VariantMedia.objects.filter(variant_id=variant_id).count(),
        }
    )


@require_POST
@required_permission("inventory.change_productvariant")
def variant_media_set_featured(request, media_id):
    """AJAX endpoint to toggle featured status of a media item."""
    media = get_object_or_404(VariantMedia, id=media_id)
    media.is_featured = not media.is_featured
    media.save()  # save() handles un-featuring others
    return JsonResponse(
        {
            "success": True,
            "is_featured": media.is_featured,
        }
    )
