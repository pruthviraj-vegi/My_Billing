from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.db import transaction

from .models import Invoice, InvoiceCancellation
from .form import InvoiceCancellationForm
import logging

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def cancel_invoice(request, pk):
    """
    View to cancel an invoice.
    GET: Display cancellation form
    POST: Process cancellation
    """
    invoice = get_object_or_404(Invoice, pk=pk)

    # Check if invoice can be cancelled
    can_cancel, error_msg = invoice.can_be_cancelled()
    if not can_cancel:
        messages.error(request, error_msg)
        return redirect("invoice:invoice_detail", pk=pk)

    if request.method == "POST":
        form = InvoiceCancellationForm(request.POST, invoice=invoice)
        try:
            with transaction.atomic():
                if form.is_valid():
                    reason = form.cleaned_data["cancellation_reason"]

                # Cancel the invoice
                success, message = invoice.cancel(user=request.user, reason=reason)

                if success:
                    messages.success(
                        request,
                        f"Invoice {invoice.invoice_number} has been cancelled successfully.",
                    )
                    logger.info(
                        f"Invoice {invoice.invoice_number} cancelled by {request.user.username}. "
                        f"Reason: {reason}"
                    )
                    return redirect("invoice:detail", pk=pk)
                else:
                    messages.error(request, f"Failed to cancel invoice: {message}")
                    logger.error(
                        f"Failed to cancel invoice {invoice.invoice_number}: {message}"
                    )
        except Exception as e:
            messages.error(request, f"Failed to cancel invoice: {str(e)}")
            logger.error(f"Failed to cancel invoice {invoice.invoice_number}: {str(e)}")
    else:
        form = InvoiceCancellationForm(invoice=invoice)

    # Calculate financial impact
    context = {
        "invoice": invoice,
        "form": form,
        "financial_impact": {
            "original_amount": invoice.amount,
            "discount": invoice.discount_amount,
            "advance": invoice.advance_amount,
            "paid": invoice.paid_amount,
            "net_amount": invoice.net_amount_due,
            "remaining": invoice.remaining_amount,
        },
    }

    return render(request, "invoice/cancel_invoice.html", context)


@login_required
def cancelled_invoices_list(request):
    """List all cancelled invoices"""

    # Get search and filter parameters
    search_query = request.GET.get("search", "").strip()
    payment_type = request.GET.get("payment_type", "")

    # Base queryset
    invoices = Invoice.objects.filter(is_cancelled=True).select_related(
        "customer", "cancelled_by", "cancellation_record"
    )

    # Apply search
    if search_query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search_query)
            | Q(customer__name__icontains=search_query)
            | Q(cancellation_reason__icontains=search_query)
        )

    # Apply payment type filter
    if payment_type:
        invoices = invoices.filter(payment_type=payment_type)

    # Order by cancellation date
    invoices = invoices.order_by("-cancelled_at")

    # Calculate statistics
    stats = invoices.aggregate(
        total_count=Count("id"),
        total_amount=Sum("amount"),
        cash_count=Count("id", filter=Q(payment_type=Invoice.PaymentType.CASH)),
        credit_count=Count("id", filter=Q(payment_type=Invoice.PaymentType.CREDIT)),
    )

    context = {
        "invoices": invoices,
        "stats": stats,
        "search_query": search_query,
        "payment_type": payment_type,
    }

    return render(request, "invoice/cancelled_invoices_list.html", context)


@login_required
def cancellation_detail(request, pk):
    """View details of a cancelled invoice"""
    invoice = get_object_or_404(Invoice, pk=pk, is_cancelled=True)

    try:
        cancellation_record = invoice.cancellation_record
    except InvoiceCancellation.DoesNotExist:
        cancellation_record = None

    context = {
        "invoice": invoice,
        "cancellation_record": cancellation_record,
    }

    return render(request, "invoice/cancellation_detail.html", context)
