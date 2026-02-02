from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Sum
from django.contrib import messages
from .models import Customer, Payment
from invoice.models import Invoice, PaymentAllocation, ReturnInvoice
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from .forms import PaymentForm
from django.urls import reverse_lazy
from decimal import Decimal
from django.http import HttpResponse
from datetime import datetime, timedelta
from django.db.models import (
    Sum,
    F,
    Value,
    Case,
    When,
    DecimalField,
    OuterRef,
    Subquery,
    Prefetch,
    Q,
)
from django.db.models.functions import Coalesce
import hashlib
import json

from invoice.models import Invoice
from customer.models import Payment
from django.db.models import DateTimeField
from django.utils import timezone
import logging


from base.utility import render_paginated_response

logger = logging.getLogger(__name__)

VALID_SORT_FIELDS = {
    "id",
    "-id",
    "name",
    "-name",
    "email",
    "-email",
    "created_at",
    "-created_at",
    "phone_number",
    "-phone_number",
    "address",
    "-address",
    "credit_amount",
    "-credit_amount",
    "debit_amount",
    "-debit_amount",
    "balance_amount",
    "-balance_amount",
    "last_date",
    "-last_date",
}


def home(request):
    """Credit management main page - initial load only."""
    # For initial page load, just render the template with empty data
    return render(request, "credit/home.html")


def total_credit_customers_data(request):
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
    sort_by = request.GET.get("sort", "-created_at")

    # ===== BASE QUERYSET =====
    # Only customers with credit activity
    qs = (
        Customer.objects.filter(credit_summary__isnull=False)
        .exclude(Q(credit_summary__credit_amount=0) & Q(credit_summary__debit_amount=0))
        .select_related("credit_summary")
    )  # Single JOIN, exclude customers with both credit and debit = 0

    # ===== SEARCH =====
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(phone_number__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(address__icontains=search_query)
        )

    # ===== SORTING (All in database!) =====
    sort_map = {
        "credit_amount": "credit_summary__credit_amount",
        "-credit_amount": "-credit_summary__credit_amount",
        "debit_amount": "credit_summary__debit_amount",
        "-debit_amount": "-credit_summary__debit_amount",
        "balance_amount": "credit_summary__balance_amount",
        "-balance_amount": "-credit_summary__balance_amount",
        "last_date": "credit_summary__last_invoice_date",
        "-last_date": "-credit_summary__last_invoice_date",
    }

    if sort_by in sort_map:
        qs = qs.order_by(sort_map[sort_by])
    else:
        # Fallback to valid field
        valid_fields = {"id", "-id", "name", "-name", "created_at", "-created_at"}
        if sort_by not in valid_fields:
            sort_by = "-created_at"
        qs = qs.order_by(sort_by)

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


def fetch_credits(request):
    """AJAX endpoint to fetch credit customers with search, filter, and pagination."""
    customers = credit_customers_data(request)

    return render_paginated_response(
        request,
        customers,
        "credit/fetch.html",
    )


def get_opening_balance(customer, start_date=None):
    """Calculate opening balance without loops using ORM aggregation."""

    # 1️⃣ CREDIT INVOICES NET AMOUNT
    invoice_net = (
        Invoice.objects.filter(
            customer=customer,
            payment_type=Invoice.PaymentType.CREDIT,
            is_cancelled=False,
            invoice_date__lt=start_date,
        )
        .annotate(
            net_amount=Coalesce(F("amount"), Decimal(0))
            - Coalesce(F("discount_amount"), Decimal(0))
            - Coalesce(F("advance_amount"), Decimal(0))
        )
        .aggregate(total=Coalesce(Sum("net_amount"), Decimal(0)))["total"]
    )

    # 2️⃣ PAYMENT BALANCE (credit - debit)
    payment_balance = (
        Payment.objects.filter(
            customer=customer,
            payment_date__lt=start_date,
        )
        .annotate(
            credit=Case(
                When(
                    payment_type=Payment.PaymentType.Purchased,
                    then=Coalesce(F("amount"), Decimal(0)),
                ),
                default=Decimal(0),
            ),
            debit=Case(
                When(
                    payment_type=Payment.PaymentType.Paid,
                    then=Coalesce(F("amount"), Decimal(0)),
                ),
                default=Decimal(0),
            ),
        )
        .aggregate(total=Coalesce(Sum(F("credit") - F("debit")), Decimal(0)))["total"]
    )

    return invoice_net + payment_balance


def _build_ledger_rows(customer, start_date=None, end_date=None):
    """Helper function to build unified ledger rows from invoices and payments."""

    # -----------------------------------
    # 1️⃣ Build filters dynamically
    # -----------------------------------
    invoice_filters = Q(
        customer=customer, payment_type=Invoice.PaymentType.CREDIT, is_cancelled=False
    )
    payment_filters = Q(customer=customer)

    if start_date and end_date:
        invoice_filters &= Q(invoice_date__range=(start_date, end_date))
        payment_filters &= Q(payment_date__range=(start_date, end_date))

    # -----------------------------------
    # 2️⃣ Fetch Invoices (annotated)
    # -----------------------------------
    credit_invoices = (
        Invoice.objects.filter(invoice_filters)
        .annotate(
            gross=Coalesce(F("amount"), Decimal("0"), output_field=DecimalField()),
            discount=Coalesce(
                F("discount_amount"), Decimal("0"), output_field=DecimalField()
            ),
            advance=Coalesce(
                F("advance_amount"), Decimal("0"), output_field=DecimalField()
            ),
            # Calculate return amount from related ReturnInvoice records
            return_amt=Coalesce(
                Subquery(
                    ReturnInvoice.objects.filter(invoice=OuterRef("pk"))
                    .values("invoice")
                    .annotate(total=Sum("refund_amount"))
                    .values("total")[:1],
                    output_field=DecimalField(),
                ),
                Decimal("0"),
                output_field=DecimalField(),
            ),
            net_amount=Coalesce(F("amount"), Decimal("0"), output_field=DecimalField())
            - Coalesce(F("discount_amount"), Decimal("0"), output_field=DecimalField())
            - Coalesce(F("advance_amount"), Decimal("0"), output_field=DecimalField())
            - Coalesce(
                Subquery(
                    ReturnInvoice.objects.filter(invoice=OuterRef("pk"))
                    .values("invoice")
                    .annotate(total=Sum("refund_amount"))
                    .values("total")[:1],
                    output_field=DecimalField(),
                ),
                Decimal("0"),
                output_field=DecimalField(),
            ),
            paid_amt=Coalesce(
                F("paid_amount"), Decimal("0"), output_field=DecimalField()
            ),
            # Outstanding = Gross - Discount - Advance - Paid - Return
            outstanding=Coalesce(F("amount"), Decimal("0"), output_field=DecimalField())
            - Coalesce(F("discount_amount"), Decimal("0"), output_field=DecimalField())
            - Coalesce(F("advance_amount"), Decimal("0"), output_field=DecimalField())
            - Coalesce(F("paid_amount"), Decimal("0"), output_field=DecimalField())
            - Coalesce(
                Subquery(
                    ReturnInvoice.objects.filter(invoice=OuterRef("pk"))
                    .values("invoice")
                    .annotate(total=Sum("refund_amount"))
                    .values("total")[:1],
                    output_field=DecimalField(),
                ),
                Decimal("0"),
                output_field=DecimalField(),
            ),
        )
        .values(
            "id",
            "invoice_number",
            "invoice_date",
            "gross",
            "discount",
            "advance",
            "return_amt",
            "net_amount",
            "paid_amt",
            "outstanding",
            "payment_status",
            "notes",
        )
        .order_by("invoice_date")
    )

    # -----------------------------------
    # 3️⃣ Fetch Payments (annotated)
    # -----------------------------------
    payments = (
        Payment.objects.filter(payment_filters)
        .annotate(
            credit=Case(
                When(
                    payment_type=Payment.PaymentType.Purchased,
                    then=Coalesce(
                        F("amount"), Decimal("0"), output_field=DecimalField()
                    ),
                ),
                default=Value(Decimal("0")),
                output_field=DecimalField(),
            ),
            debit=Case(
                When(
                    payment_type=Payment.PaymentType.Paid,
                    then=Coalesce(
                        F("amount"), Decimal("0"), output_field=DecimalField()
                    ),
                ),
                default=Value(Decimal("0")),
                output_field=DecimalField(),
            ),
        )
        .values(
            "id",
            "payment_date",
            "payment_type",
            "credit",
            "debit",
            "method",
            "notes",
        )
        .order_by("payment_date")
    )

    # -----------------------------------
    # 4️⃣ Build Unified Ledger Rows
    # -----------------------------------
    rows = []

    for inv in credit_invoices:
        rows.append(
            {
                "id": inv["id"],
                "date": inv["invoice_date"],
                "type": "Invoice",
                "ref": inv["invoice_number"],
                "notes": inv["notes"],
                "credit": inv["net_amount"],
                "debit": Decimal("0"),
                "paid_amount": inv["paid_amt"],
                "payment_status": inv["payment_status"],
                "outstanding": inv["outstanding"],
                "gross_amount": inv["gross"],
                "discount_amount": inv["discount"],
                "advance_amount": inv["advance"],
            }
        )

    for pay in payments:
        rows.append(
            {
                "id": pay["id"],
                "date": pay["payment_date"],
                "type": pay["payment_type"].title(),
                "ref": pay["id"],
                "method": pay["method"],
                "notes": pay["notes"],
                "credit": pay["credit"],
                "debit": pay["debit"],
            }
        )

    return rows


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


def credit_detail(request, customer_id: int):
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


class PaymentCreateView(CreateView):
    template_name = "credit/form.html"
    form_class = PaymentForm
    model = Payment
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
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class PaymentUpdateView(UpdateView):
    template_name = "credit/form.html"
    form_class = PaymentForm
    model = Payment
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
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class PaymentDeleteView(DeleteView):
    model = Payment
    template_name = "credit/delete.html"
    success_url = reverse_lazy("customer:credit_home")

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
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


def auto_reallocate(request, customer_id):
    """
    Auto reallocate customer payments using FIFO method.
    This function uses the signal's reallocation logic but skips signals
    to avoid double reallocation.
    """
    from customer.signals import reallocate_customer_payments

    customer = get_object_or_404(Customer, id=customer_id)

    try:
        # Use the signal's reallocation function directly
        # Skip signals to avoid recursive reallocation
        reallocate_customer_payments(customer, skip_signals=True)

        messages.success(
            request,
            f"Successfully reallocated payments for {customer.name} using FIFO method.",
        )
    except Exception as e:
        logger.error(f"Reallocation failed for customer {customer_id}: {str(e)}")
        messages.error(
            request,
            f"Reallocation failed: {str(e)}",
        )

    return redirect("customer:credit_detail", customer_id=customer_id)
