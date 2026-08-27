"""Views for BulkUpload batch management."""

import csv
import json
import logging

from django.contrib import messages
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from base.decorators import RequiredPermissionMixin, required_permission
from base.utility import build_search_filter, render_paginated_response
from .forms import BulkUploadForm
from .models import (
    BulkUpload,
    BulkUploadItem,
    Category,
    ClothType,
    Color,
    GSTHsnCode,
    Product,
    ProductVariant,
    Size,
    UOM,
)
from .services import BulkUploadService

logger = logging.getLogger(__name__)

VALID_BULK_UPLOAD_SORT_FIELDS = [
    "id",
    "-id",
    "status",
    "-status",
    "supplier_invoice__invoice_number",
    "-supplier_invoice__invoice_number",
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
]


@required_permission("inventory.view_bulkupload")
def bulk_upload_home(request):
    return render(request, "inventory/bulk_upload/home.html")


@required_permission("inventory.view_bulkupload")
def bulk_upload_fetch(request):
    search_query = request.GET.get("search", "")
    sort_by = request.GET.get("sort", "-created_at")

    filters = build_search_filter(
        search_query,
        ["supplier_invoice__invoice_number", "status"],
    )

    batches = (
        BulkUpload.objects
        .filter(filters)
        .select_related("supplier_invoice", "created_by")
        .annotate(
            item_count=Count("items", filter=Q(items__is_deleted=False)),
            total_quantity=Sum("items__quantity", filter=Q(items__is_deleted=False)),
            total_purchase_amount=Sum(
                F("items__quantity") * F("items__purchase_price"),
                filter=Q(items__is_deleted=False),
            ),
        )
    )

    if sort_by not in VALID_BULK_UPLOAD_SORT_FIELDS:
        sort_by = "-created_at"
    batches = batches.order_by(sort_by)

    return render_paginated_response(
        request,
        batches,
        "inventory/bulk_upload/fetch.html",
    )


class CreateBulkUpload(RequiredPermissionMixin, CreateView):
    required_permission = "inventory.add_bulkupload"

    model = BulkUpload
    form_class = BulkUploadForm
    template_name = "inventory/bulk_upload/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Bulk Upload Batch"
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Bulk upload batch created successfully")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error("BulkUpload form invalid: %s", form.errors)
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("inventory_bulk_upload:home")


class UpdateBulkUpload(RequiredPermissionMixin, UpdateView):
    required_permission = "inventory.change_bulkupload"

    model = BulkUpload
    form_class = BulkUploadForm
    template_name = "inventory/bulk_upload/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Update Bulk Upload Batch"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Bulk upload batch updated successfully")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("inventory_bulk_upload:home")


class DeleteBulkUpload(RequiredPermissionMixin, DeleteView):
    required_permission = "inventory.delete_bulkupload"

    model = BulkUpload
    template_name = "inventory/bulk_upload/delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Delete Bulk Upload Batch"
        return context

    def get_success_url(self):
        return reverse("inventory_bulk_upload:home")

    def form_valid(self, form):
        messages.success(self.request, "Bulk upload batch deleted successfully")
        return super().form_valid(form)


BULK_UPLOAD_ITEM_CSV_HEADERS = [
    "brand", "name", "category", "cloth_type", "uom", "hsn_code",
    "quantity", "purchase_price", "mrp", "discount_percentage",
    "commission_percentage", "description", "size", "color", "minimum_quantity",
]


@required_permission("inventory.view_bulkupload")
def bulk_upload_detail(request, pk):
    batch = get_object_or_404(BulkUpload, pk=pk)
    items = batch.items.select_related(
        "product", "variant", "category", "cloth_type", "uom", "hsn_code", "size", "color"
    ).all()
    summary = items.aggregate(
        total_items=Count("id"),
        total_qty=Sum("quantity"),
        total_purchase_value=Sum(F("quantity") * F("purchase_price")),
        total_selling_value=Sum(F("quantity") * F("mrp")),
    )
    context = {
        "batch": batch,
        "items": items,
        "summary": summary,
        "products": Product.objects.filter(is_deleted=False).order_by("name"),
        "variants": ProductVariant.objects.filter(is_deleted=False).select_related("product", "size", "color").order_by("product__name", "barcode"),
        "categories": Category.objects.all().order_by("name"),
        "cloth_types": ClothType.objects.all().order_by("name"),
        "uoms": UOM.objects.filter(is_active=True).order_by("name"),
        "hsn_codes": GSTHsnCode.objects.filter(is_active=True).order_by("code"),
        "sizes": Size.objects.all().order_by("name"),
        "colors": Color.objects.all().order_by("name"),
    }
    return render(request, "inventory/bulk_upload/detail.html", context)


@required_permission("inventory.view_bulkupload")
def bulk_upload_sample_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="bulk_upload_sample.csv"'
    writer = csv.writer(response)
    writer.writerow(BULK_UPLOAD_ITEM_CSV_HEADERS)
    return response


@required_permission("inventory.add_bulkuploaditem")
@require_http_methods(["POST"])
def bulk_upload_csv(request, pk):
    """Upload CSV file and parse items via BulkUploadService."""
    batch = get_object_or_404(BulkUpload, pk=pk)

    if "csv_file" not in request.FILES:
        return JsonResponse({"success": False, "message": "No CSV file provided."})

    result = BulkUploadService.process_csv_import(batch, request.FILES["csv_file"])
    return JsonResponse(result)


@required_permission("inventory.change_bulkuploaditem")
@require_http_methods(["POST"])
def bulk_upload_item_update(request, pk, item_id):
    """Update a single BulkUploadItem fields via AJAX."""
    batch = get_object_or_404(BulkUpload, pk=pk)
    item = get_object_or_404(BulkUploadItem, pk=item_id, bulk_upload=batch)

    if item.is_committed:
        return JsonResponse({
            "success": False,
            "message": "This item has already been committed to inventory and cannot be updated here.",
        })

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON."})

    result = BulkUploadService.update_item(item, data)
    return JsonResponse(result)


@required_permission("inventory.delete_bulkuploaditem")
@require_http_methods(["POST"])
def bulk_upload_item_delete(request, pk, item_id):
    """Delete a single BulkUploadItem via AJAX."""
    batch = get_object_or_404(BulkUpload, pk=pk)
    item = get_object_or_404(BulkUploadItem, pk=item_id, bulk_upload=batch)

    if item.is_committed:
        return JsonResponse({
            "success": False,
            "message": "This item has already been committed to inventory and cannot be deleted from the batch.",
        })

    result = BulkUploadService.delete_item(item)
    return JsonResponse(result)


@required_permission("inventory.add_product")
@require_http_methods(["POST"])
def bulk_upload_item_commit(request, pk, item_id):
    """Commit a single BulkUploadItem: save/create real Product and ProductVariant in inventory."""
    batch = get_object_or_404(BulkUpload, pk=pk)
    item = get_object_or_404(BulkUploadItem, pk=item_id, bulk_upload=batch)

    data = None
    if request.body:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            pass

    result = BulkUploadService.commit_item(item, request.user, data)
    return JsonResponse(result)


@required_permission("inventory.add_product")
@require_http_methods(["POST"])
def bulk_upload_commit_all(request, pk):
    """Commit all uncommitted items in a batch at once."""
    batch = get_object_or_404(BulkUpload, pk=pk)
    result = BulkUploadService.commit_all_items(batch, request.user)
    return JsonResponse(result)


@required_permission("inventory.delete_bulkuploaditem")
@require_http_methods(["POST"])
def bulk_upload_delete_uncommitted(request, pk):
    """Delete all uncommitted items from a batch at once."""
    batch = get_object_or_404(BulkUpload, pk=pk)
    result = BulkUploadService.delete_uncommitted_items(batch)
    return JsonResponse(result)
