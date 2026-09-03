"""
Views for customer credit management, ledger display, and payment CRUD operations.

Handles credit customer listing with search/sort/pagination, credit ledger
construction with opening balance calculations, and payment create/update/delete
flows using Django class-based views.
"""

import logging
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView, DeleteView, UpdateView


from base.decorators import required_permission, RequiredPermissionMixin

from base.utility import build_search_filter, render_paginated_response, table_sorting

from .forms import PaymentForm
from .models import Customer, Payment
from .services import CustomerPaymentService, _build_ledger_rows, get_opening_balance

logger = logging.getLogger(__name__)

VALID_SORT_FIELDS = {
    "id",
    "name",
    "email",
    "created_at",
    "phone_number",
    "address",
    "credit_amount",
    "debit_amount",
    "balance_amount",
    "last_date",
}


@required_permission("customer.view_customercreditsummary")
def home(request):
    """Credit management main page - initial load only."""
    # For initial page load, just render the template with empty data
    return render(request, "credit/home.html")


def total_credit_customers_data(request):
    """Return the aggregate balance amount across all active credit customers."""
    return Customer.objects.filter(is_deleted=False).aggregate(
        total=Coalesce(Sum("credit_summary__balance_amount"), Value(Decimal("0")))
    )["total"]


def credit_customers_data(request):
    """
    ULTRA-OPTIMIZED credit customers view.
    - Single query with select_related
    - All sorting in database
    - No Python computation needed
    """

    search_query = request.GET.get("search", "").strip()
    # ===== BASE QUERYSET =====
    # Only customers with credit activity
    qs = (
        Customer.objects.filter(credit_summary__isnull=False)
        .exclude(Q(credit_summary__credit_amount=0) & Q(credit_summary__debit_amount=0))
        .select_related("credit_summary")
    )  # Single JOIN, exclude customers with both credit and debit = 0

    # ===== SEARCH =====
    filters = build_search_filter(
        search_query,
        ["name", "phone_number", "email", "address"],
    )

    # ===== SORTING (All in database!) =====
    # Map frontend sort keys to database fields
    sort_fields_map = {
        "id": "id",
        "name": "name",
        "email": "email",
        "created_at": "created_at",
        "phone_number": "phone_number",
        "address": "address",
        "credit_amount": "credit_summary__credit_amount",
        "debit_amount": "credit_summary__debit_amount",
        "balance_amount": "credit_summary__balance_amount",
        "last_date": "credit_summary__last_invoice_date",
    }

    # Get valid sort fields (supports multi-column, e.g. "credit_amount, -name")
    # table_sorting will now handle the mapping and direction logic automatically
    final_order_by = table_sorting(request, sort_fields_map, "-created_at")

    qs = qs.filter(filters).order_by(*final_order_by)

    # ===== EXECUTE =====
    customers = list(qs)

    # ===== ATTACH VALUES (already loaded via select_related) =====
    for customer in customers:
        summary = customer.credit_summary

        # Attach for template/serializer compatibility
        customer.credit_amount = summary.credit_amount
        customer.debit_amount = summary.debit_amount
        customer.balance_amount = summary.balance_amount
        customer.last_date = summary.last_invoice_date
        customer.is_overdue = summary.is_overdue

    return customers


@required_permission("customer.view_customercreditsummary")
def fetch_credits(request):
    """AJAX endpoint to fetch credit customers with search, filter, and pagination."""
    customers = credit_customers_data(request)

    return render_paginated_response(
        request,
        customers,
        "credit/fetch.html",
    )


@required_permission("customer.view_customercreditsummary")
def fetch_credit_ledger(request, customer_id: int):
    """AJAX: fetch credit ledger entries for a customer with pagination and optional sorting."""
    customer = get_object_or_404(Customer, pk=customer_id)

    sort_by = (request.GET.get("sort") or "-date").strip()
    valid_sort_fields = {
        "date",
        "-date",
        "credit",
        "-credit",
        "debit",
        "-debit",
        "outstanding",
        "-outstanding",
    }
    if sort_by not in valid_sort_fields:
        sort_by = "-date"

    # Build all ledger rows
    rows = _build_ledger_rows(customer)

    # -------------------------------------------
    # ⭐ Optimized sorter map
    # -------------------------------------------
    sort_key_map = {
        "date": lambda r: (r["date"] or datetime.min, r.get("type")),
        "-date": lambda r: (r["date"] or datetime.min, r.get("type")),
        "credit": lambda r: (r["credit"] or Decimal("0"), r["date"] or datetime.min),
        "-credit": lambda r: (r["credit"] or Decimal("0"), r["date"] or datetime.min),
        "debit": lambda r: (r["debit"] or Decimal("0"), r["date"] or datetime.min),
        "-debit": lambda r: (r["debit"] or Decimal("0"), r["date"] or datetime.min),
        "outstanding": lambda r: (
            r.get("outstanding", Decimal("0")) or Decimal("0"),
            r["date"] or datetime.min,
        ),
        "-outstanding": lambda r: (
            r.get("outstanding", Decimal("0")) or Decimal("0"),
            r["date"] or datetime.min,
        ),
    }

    key_func = sort_key_map[sort_by]
    reverse = sort_by.startswith("-")
    rows.sort(key=key_func, reverse=reverse)

    return render_paginated_response(
        request,
        rows,
        "credit/ledger/fetch.html",
    )


@required_permission("customer.view_customercreditsummary")
def credit_detail(request, customer_id: int):
    """Render the credit detail page for a customer with ledger totals and allocation summary."""
    template = "credit/detail.html"
    customer = get_object_or_404(Customer, pk=customer_id)
    # Build all ledger rows for totals calculation
    rows = _build_ledger_rows(customer)

    # Sort rows by date descending, then type for stability
    rows.sort(key=lambda r: (r["date"] or 0, r["type"]), reverse=True)

    # Calculate allocation totals
    total_allocated = sum(
        (r.get("paid_amount", Decimal("0")) for r in rows if r["type"] == "Invoice"),
        Decimal("0"),
    )
    total_outstanding = sum(
        (r.get("outstanding", Decimal("0")) for r in rows if r["type"] == "Invoice"),
        Decimal("0"),
    )

    # Calculate unallocated amount (sum of unallocated amounts from "Paid" payments)
    payments = Payment.objects.filter(customer=customer)
    unallocated_amount = sum(
        pay.unallocated_amount or Decimal("0")
        for pay in payments
        if pay.payment_type == Payment.PaymentType.Paid
    )

    context = {
        "customer": customer,
        "total_allocated": total_allocated,
        "total_outstanding": total_outstanding,
        "unallocated_amount": unallocated_amount,
    }
    return render(request, template, context)


class PaymentCreateView(RequiredPermissionMixin, CreateView):
    """CBV to create a new payment record for a customer, with auto-allocation via signals."""

    template_name = "credit/form.html"
    form_class = PaymentForm
    model = Payment
    required_permission = "customer.add_payment"
    title = "Create Payment"

    def get_success_url(self):
        return reverse_lazy(
            "customer:credit_detail", kwargs={"customer_id": self.object.customer.id}
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        customer_id = self.kwargs.get("customer_id")
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
                kwargs["customer"] = customer
            except Customer.DoesNotExist:
                pass
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        customer_id = self.kwargs.get("customer_id")
        if customer_id:
            try:
                context["customer"] = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                pass
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        # Allocation is now handled automatically by signals
        # No need to manually call _auto_allocate_payment

        messages.success(self.request, "Payment created successfully.")
        return response

    def form_invalid(self, form):
        logger.error("Form invalid: %s", form.errors)
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class PaymentUpdateView(RequiredPermissionMixin, UpdateView):
    """CBV to update an existing payment record for a customer."""

    template_name = "credit/form.html"
    form_class = PaymentForm
    model = Payment
    required_permission = "customer.change_payment"
    title = "Edit Payment"

    def get_success_url(self):
        return reverse_lazy(
            "customer:credit_detail", kwargs={"customer_id": self.object.customer.id}
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["customer"] = self.object.customer
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        context["customer"] = self.object.customer
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Payment updated successfully.")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error("Form invalid: %s", form.errors)
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class PaymentDeleteView(DeleteView):
    """CBV to delete a payment record and redirect back to the credit detail page."""

    model = Payment
    template_name = "credit/delete.html"
    success_url = reverse_lazy("customer:credit_home")
    required_permission = "customer.delete_payment"

    def get_success_url(self):
        return reverse_lazy(
            "customer:credit_detail", kwargs={"customer_id": self.object.customer.id}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Delete Payment"
        context["customer"] = self.object.customer
        return context

    def form_valid(self, form):
        messages.success(self.request, "Payment deleted successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error("Form invalid: %s", form.errors)
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


def auto_reallocate(request, customer_id):
    """
    Auto reallocate customer payments using FIFO method.

    Uses CustomerPaymentService.reallocate() with skip_signals=True
    to avoid recursive reallocation triggers.
    """
    customer = get_object_or_404(Customer, id=customer_id)

    try:
        CustomerPaymentService.reallocate(customer, skip_signals=True)

        messages.success(
            request,
            f"Successfully reallocated payments for {customer.name} using FIFO method.",
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Reallocation failed for customer %s: %s", customer_id, e)
        messages.error(
            request,
            f"Reallocation failed: {str(e)}",
        )

    return redirect("customer:credit_detail", customer_id=customer_id)
