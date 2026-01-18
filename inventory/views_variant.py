from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from django.db import transaction
from django.db.utils import IntegrityError
from django.db.models import Q, F
from decimal import Decimal
from typing import Optional, Union
from .models import (
    ProductVariant,
    InventoryLog,
    Product,
    Category,
    Color,
    Size,
)
from .forms import (
    VariantForm,
    StockInForm,
    AdjustmentInForm,
    AdjustmentOutForm,
    DamageForm,
    SizeForm,
    ColorForm,
)
from base.utility import render_paginated_response
from .services import InventoryService
import logging
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json

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
    variants = (
        ProductVariant.objects.select_related(
            "product", "product__category", "size", "color"
        )
        .prefetch_related("favorite_variants")
        .all()
    )

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

    variants = variants.filter(filters)

    # Apply sorting
    if sort_by not in VALID_SORT_FIELDS:
        sort_by = "-created_at"
    variants = variants.order_by(sort_by)

    return variants


def fetch_variants(request):
    """AJAX endpoint to fetch variants with search, filter, and pagination."""
    variants = get_variants_data(request)

    return render_paginated_response(
        request,
        variants,
        "inventory/product_variant/fetch.html",
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
    session_initial_key = "create_variant_initial"
    session_barcode_key = "redirect_url"
    ACTION_CREATE_ADD = "create_add"

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
        except Exception as e:
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
        logger.error(f"Form invalid: {form.errors.as_text()}")
        if form.non_field_errors():
            for error in form.non_field_errors():
                messages.error(self.request, error)
        else:
            messages.error(self.request, "Error in submitting the form")
        return super().form_invalid(form)

    def get_success_url(self):
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
        if form.non_field_errors():
            for error in form.non_field_errors():
                messages.error(self.request, error)
        else:
            messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(
            "inventory_products:details", kwargs={"product_id": self.object.product.id}
        )


class StockInCreate(CreateView):
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


class AdjustmentInCreate(CreateView):
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


class AdjustmentOutCreate(CreateView):
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


class DamageCreate(CreateView):
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
