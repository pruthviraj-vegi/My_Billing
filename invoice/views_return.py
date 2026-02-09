from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q

from django.views.generic.edit import CreateView
from django.views.generic import DetailView
from django.urls import reverse_lazy
from datetime import datetime
from decimal import Decimal
from .models import ReturnInvoice, Invoice, InvoiceItem, ReturnInvoiceItem
from .form import ReturnInvoiceForm
from .choices import ItemConditionChoices, ItemReturnReasonChoices, RefundStatusChoices
from inventory.services import InventoryService
from base.utility import render_paginated_response, table_sorting
import logging

logger = logging.getLogger(__name__)

valid_sort_fields = [
    "return_number",
    "customer__name",
    "invoice__invoice_number",
    "status",
    "refund_type",
    "total_amount",
    "return_date",
    "created_at",
]


def home(request):
    """Home page for return invoices - loads empty table, data fetched via AJAX"""
    # Get filter choices for dropdowns
    status_choices = ReturnInvoice.RefundStatus.choices
    refund_type_choices = ReturnInvoice.RefundType.choices

    context = {
        "status_choices": status_choices,
        "refund_type_choices": refund_type_choices,
    }

    return render(request, "invoice_return/home.html", context)


def fetch_return_invoices(request):
    """AJAX endpoint to fetch return invoices with search, filter, and pagination."""
    # Get search and filter parameters
    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")
    refund_type_filter = request.GET.get("refund_type", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    # Apply search filter
    filters = Q()
    if search_query:
        filters &= (
            Q(return_number__icontains=search_query)
            | Q(customer__name__icontains=search_query)
            | Q(invoice__invoice_number__icontains=search_query)
            | Q(notes__icontains=search_query)
        )

    # Apply status filter
    if status_filter:
        filters &= Q(status=status_filter)

    # Apply refund type filter
    if refund_type_filter:
        filters &= Q(refund_type=refund_type_filter)

    # Apply date filters
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
            filters &= Q(return_date__date__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
            filters &= Q(return_date__date__lte=date_to_obj)
        except ValueError:
            pass

    return_invoices = ReturnInvoice.objects.select_related(
        "customer", "invoice", "created_by", "approved_by", "processed_by"
    ).filter(filters)

    # Apply sorting
    valid_sorts = table_sorting(request, valid_sort_fields, "-created_at")
    return_invoices = return_invoices.order_by(*valid_sorts)

    return render_paginated_response(
        request,
        return_invoices,
        "invoice_return/fetch.html",
    )


class ReturnInvoiceCreateView(CreateView):
    model = ReturnInvoice
    form_class = ReturnInvoiceForm
    template_name = "invoice_return/create.html"
    success_url = reverse_lazy("invoice:return_home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Return Invoice"
        return context

    @transaction.atomic
    def form_valid(self, form):
        try:
            # Check if a pending return invoice already exists for this invoice
            invoice = form.cleaned_data.get("invoice")
            if invoice:
                existing_return = ReturnInvoice.objects.filter(
                    invoice=invoice, status=RefundStatusChoices.PENDING
                ).first()

                if existing_return:
                    return redirect(existing_return.get_absolute_url())

            # Set the created_by user
            form.instance.created_by = self.request.user

            # Save the return invoice first
            return_invoice = form.save()

            # Get the original invoice
            original_invoice = return_invoice.invoice

            # Copy all InvoiceItems to ReturnInvoiceItems with quantity_returned=0
            original_items = InvoiceItem.objects.filter(invoice=original_invoice)

            if not original_items.exists():
                messages.error(
                    self.request, "The selected invoice has no items to return."
                )
                return self.form_invalid(form)

            # Create ReturnInvoiceItems for each original item using bulk_create
            return_items_to_create = []
            for item in original_items:
                return_item = ReturnInvoiceItem(
                    return_invoice=return_invoice,
                    product_variant=item.product_variant,
                    original_invoice_item=item,
                    quantity_returned=0,  # Start with 0 - user will select items
                    quantity_original=item.get_return_available_quantity,
                    unit_price=item.unit_price,
                    total_amount=0,  # Will be calculated when items are selected
                    condition=ItemConditionChoices.NEW,
                    return_reason=ItemReturnReasonChoices.CUSTOMER_REQUEST,
                )
                return_items_to_create.append(return_item)

            # Bulk create all return items
            ReturnInvoiceItem.objects.bulk_create(return_items_to_create)

            # Calculate initial total amount (will be updated when items are selected)
            return_invoice.total_amount = 0
            return_invoice.refund_amount = 0
            return_invoice.save()

            messages.success(
                self.request,
                f"Return invoice created successfully! {original_items.count()} items added. "
                f"Please select which items to return.",
            )

            # Redirect to edit page to select items (we'll implement this next)
            return redirect("invoice:return_home")  # For now, redirect to home

        except Exception as e:
            logger.error(f"Error creating return invoice: {e}")
            messages.error(self.request, f"Error creating return invoice: {str(e)}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        logger.error(f"Form validation error: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class ReturnStockAdjustmentView(DetailView):
    """View for managing return item quantities, conditions, and reasons"""

    model = ReturnInvoice
    template_name = "invoice_return/stock_adjustment.html"
    context_object_name = "return_invoice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return_invoice = self.get_object()

        # Get all return items with related data
        return_items = (
            ReturnInvoiceItem.objects.filter(return_invoice=return_invoice)
            .select_related("product_variant__product", "original_invoice_item")
            .order_by("id")
        )

        context.update(
            {
                "return_invoice": return_invoice,
                "return_items": return_items,
                "item_condition_choices": ItemConditionChoices.choices,
                "item_return_reason_choices": ItemReturnReasonChoices.choices,
                "title": f"Stock Adjustment - {return_invoice.return_number}",
            }
        )

        return context


class ReturnInvoiceDetailView(DetailView):
    """View for displaying return invoice details"""

    model = ReturnInvoice
    template_name = "invoice_return/detail.html"
    context_object_name = "return_invoice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return_invoice = self.get_object()

        # Get return items that are actually being returned (quantity > 0)
        returned_items = (
            ReturnInvoiceItem.objects.filter(
                return_invoice=return_invoice, quantity_returned__gt=0
            )
            .select_related("product_variant__product", "original_invoice_item")
            .order_by("id")
        )

        # Calculate summary statistics
        total_items_returned = returned_items.count()
        total_quantity_returned = sum(item.quantity_returned for item in returned_items)
        total_return_amount = sum(item.total_amount for item in returned_items)

        context.update(
            {
                "returned_items": returned_items,
                "total_items_returned": total_items_returned,
                "total_quantity_returned": total_quantity_returned,
                "total_return_amount": total_return_amount,
                "title": f"Return Details - {return_invoice.return_number}",
            }
        )

        return context


@transaction.atomic
def create_auto_return_invoice(request, invoice_id):

    try:

        invoice = get_object_or_404(Invoice, id=invoice_id)

        invoice_items = InvoiceItem.objects.filter(invoice=invoice)

        if not invoice_items.exists():
            return JsonResponse(
                {"success": False, "error": "No items found for this invoice."}
            )

        # Check if a pending return invoice already exists for this invoice
        existing_return = ReturnInvoice.objects.filter(
            invoice=invoice, status=RefundStatusChoices.PENDING
        ).first()

        if existing_return:
            # Redirect to the existing return invoice instead of creating a new one
            return redirect(existing_return.get_absolute_url())

        return_invoice = ReturnInvoice(
            invoice=invoice,
            customer=invoice.customer,
            created_by=request.user,
            approved_by=request.user,
            processed_by=request.user,
            total_amount=invoice.amount,
        )

        # Validate the return invoice before saving
        try:
            return_invoice.clean()
        except ValidationError as ve:
            return JsonResponse({"success": False, "error": str(ve)})

        return_invoice.save()

        return_items_to_create = []
        for item in invoice_items:
            return_item = ReturnInvoiceItem(
                return_invoice=return_invoice,
                product_variant=item.product_variant,
                original_invoice_item=item,
                quantity_returned=0,
                quantity_original=item.get_return_available_quantity,
                unit_price=item.unit_price,
                total_amount=0,
                condition=ItemConditionChoices.NEW,
                return_reason=ItemReturnReasonChoices.CUSTOMER_REQUEST,
            )
            return_items_to_create.append(return_item)

        ReturnInvoiceItem.objects.bulk_create(return_items_to_create)

        return redirect(return_invoice.get_absolute_url())

    except Exception as e:
        logger.error(f"Error creating auto return invoice: {e}")
        return JsonResponse({"success": False, "error": str(e)})


@transaction.atomic
def update_return_item(request, item_id):
    """API endpoint to update return item quantity, condition, and reason"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Only POST method allowed"})

    try:
        item = ReturnInvoiceItem.objects.get(id=item_id)

        # Get data from request
        quantity_returned = request.POST.get("quantity_returned", "0")
        condition = request.POST.get("condition", item.condition)
        return_reason = request.POST.get("return_reason", item.return_reason)

        # Validate quantity
        try:
            quantity_returned = Decimal(quantity_returned)
            if quantity_returned < 0:
                return JsonResponse(
                    {"success": False, "error": "Quantity cannot be negative"}
                )
            if quantity_returned > item.quantity_original:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Return quantity cannot exceed original quantity",
                    }
                )
        except ValueError as e:
            logger.error(f"Invalid quantity format: {e}")
            return JsonResponse({"success": False, "error": "Invalid quantity format"})

        # Update item
        item.quantity_returned = quantity_returned
        item.condition = condition
        item.return_reason = return_reason

        # Calculate total amount - convert to Decimal for proper calculation
        item.total_amount = quantity_returned * Decimal(item.unit_price)
        item.save()

        # Update return invoice totals
        return_invoice = item.return_invoice

        # Calculate return amount (sum of all return item amounts)
        return_amount = sum(
            ri_item.total_amount
            for ri_item in ReturnInvoiceItem.objects.filter(
                return_invoice=return_invoice
            )
        )

        # Total amount should be the original invoice amount
        return_invoice.total_amount = return_invoice.invoice.amount

        # Refund amount is what we're actually refunding based on returns
        return_invoice.refund_amount = return_amount
        return_invoice.save()

        return JsonResponse(
            {
                "success": True,
                "item_total": str(item.total_amount),
                "return_total": str(return_invoice.total_amount),
                "refund_amount": str(return_invoice.refund_amount),
            }
        )

    except ReturnInvoiceItem.DoesNotExist:
        logger.error(f"Return item not found: {item_id}")
        return JsonResponse({"success": False, "error": "Return item not found"})
    except Exception as e:
        logger.error(f"Error updating return item: {e}")
        return JsonResponse({"success": False, "error": str(e)})


@transaction.atomic
def submit_return_invoice(request, pk):
    """Submit return invoice for processing"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Only POST method allowed"})

    try:
        return_invoice = get_object_or_404(ReturnInvoice, pk=pk)

        # Check if return invoice is in valid state for submission
        if return_invoice.status != RefundStatusChoices.PENDING:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Return invoice is already {return_invoice.get_status_display()}. Cannot submit.",
                }
            )

        # Get all return items
        return_items = ReturnInvoiceItem.objects.filter(return_invoice=return_invoice)

        if not return_items.exists():
            return JsonResponse(
                {"success": False, "error": "No items found for this return invoice."}
            )

        # Check if there are any items to return
        items_to_return = return_items.filter(quantity_returned__gt=0)

        for item in items_to_return:
            InventoryService.return_sale(
                item.product_variant,
                item.quantity_returned,
                request.user,
                item.original_invoice_item,
                notes=f"Return invoice {item.return_invoice.return_number} - {item.product_variant.product.name}",
            )

        if not items_to_return.exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": "No items selected for return. Please select at least one item.",
                }
            )

        # Calculate final amounts
        total_return_amount = sum(item.total_amount for item in items_to_return)

        # Update return invoice with final calculations
        return_invoice.total_amount = (
            return_invoice.invoice.amount
        )  # Original invoice amount
        return_invoice.refund_amount = total_return_amount  # Amount to refund
        return_invoice.status = RefundStatusChoices.APPROVED
        return_invoice.processed_by = request.user
        return_invoice.processed_at = timezone.now()
        return_invoice.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Return invoice submitted successfully",
                "return_number": return_invoice.return_number,
                "total_amount": str(return_invoice.total_amount),
                "refund_amount": str(return_invoice.refund_amount),
                "items_count": items_to_return.count(),
                "status": return_invoice.get_status_display(),
            }
        )

    except ReturnInvoice.DoesNotExist:
        return JsonResponse({"success": False, "error": "Return invoice not found"})
    except Exception as e:
        logger.error(f"Error submitting return invoice: {e}")
        return JsonResponse({"success": False, "error": str(e)})


@transaction.atomic
def delete_return_invoice(request, pk):
    """Delete a return invoice"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Only POST method allowed"})

    try:
        return_invoice = get_object_or_404(ReturnInvoice, pk=pk)

        # Check if return invoice is in valid state for deletion
        if return_invoice.status not in [
            RefundStatusChoices.PENDING,
            RefundStatusChoices.REJECTED,
        ]:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Return invoice is already {return_invoice.get_status_display()}. Cannot delete.",
                }
            )

        # Delete all related items
        ReturnInvoiceItem.objects.filter(return_invoice=return_invoice).delete()

        # Delete the return invoice
        return_invoice.delete()

        return JsonResponse(
            {
                "success": True,
                "message": "Return invoice deleted successfully",
            }
        )

    except ReturnInvoice.DoesNotExist:
        return JsonResponse({"success": False, "error": "Return invoice not found"})
    except Exception as e:
        logger.error(f"Error deleting return invoice: {e}")
        return JsonResponse({"success": False, "error": str(e)})
