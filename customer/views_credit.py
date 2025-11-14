from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.contrib import messages
from .models import Customer, Payment
from invoice.models import Invoice, PaymentAllocation
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from .forms import PaymentForm
from django.urls import reverse_lazy
from decimal import Decimal
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.http import JsonResponse
from datetime import datetime, timedelta
import logging

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

CUSTOMERS_PER_PAGE = 20


def home(request):
    """Credit management main page - initial load only."""
    # For initial page load, just render the template with empty data
    return render(request, "credit/home.html")


def total_credit_customers_data(request):
    total_outstanding = Decimal("0.00")
    customers = Customer.objects.filter(is_deleted=False)
    for customer in customers:
        total_outstanding += customer.balance_amount.quantize(Decimal("0.01"))

    return total_outstanding


def credit_customers_data(request):

    # Get search and filter parameters
    search_query = request.GET.get("search", "")
    sort_by = request.GET.get("sort", "-created_at")

    # Apply search filter
    filters = Q()
    if search_query:
        filters &= (
            Q(name__icontains=search_query)
            | Q(phone_number__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(address__icontains=search_query)
        )

    # Get customers with credit invoices or payments
    customers = (
        Customer.objects.filter(
            Q(invoices__payment_type=Invoice.PaymentType.CREDIT)
            | Q(credit_payment__isnull=False)
        )
        .filter(filters)
        .distinct()
    )

    # Apply sorting
    if sort_by not in VALID_SORT_FIELDS:
        sort_by = "-created_at"

    # Handle sorting for model properties that can't be sorted in database
    if sort_by in [
        "credit_amount",
        "-credit_amount",
        "debit_amount",
        "-debit_amount",
        "balance_amount",
        "-balance_amount",
        "last_date",
        "-last_date",
    ]:
        # Convert to list to enable Python sorting
        customers_list = list(customers)

        # Define sorting key based on the field
        if sort_by in ["credit_amount", "-credit_amount"]:
            key_func = lambda c: c.credit_amount
        elif sort_by in ["debit_amount", "-debit_amount"]:
            key_func = lambda c: c.debit_amount
        elif sort_by in ["balance_amount", "-balance_amount"]:
            key_func = lambda c: c.balance_amount
        elif sort_by in ["last_date", "-last_date"]:
            # Handle None values by putting them at the end
            # For ascending: None values go to end (use max date)
            # For descending: None values go to end (use min date)
            key_func = lambda c: c.last_date or (
                datetime.min if sort_by.startswith("-") else datetime.max
            )

        # Sort with reverse for descending
        reverse = sort_by.startswith("-")
        customers_list.sort(key=key_func, reverse=reverse)

        # Convert back to queryset-like object for pagination
        customers = customers_list
    else:
        # Regular database sorting for other fields
        customers = customers.order_by(sort_by)

    # Add overdue flag for customers with last activity more than 6 months ago
    six_months_ago = datetime.now() - timedelta(days=180)

    for customer in customers:
        if customer.last_date and customer.last_date < six_months_ago:
            customer.is_overdue = True
        else:
            customer.is_overdue = False

    return customers


def fetch_credits(request):
    """AJAX endpoint to fetch credit customers with search, filter, and pagination."""
    customers = credit_customers_data(request)

    # Pagination
    paginator = Paginator(customers, CUSTOMERS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Render the HTML template
    context = {
        "page_obj": page_obj,
        "total_count": paginator.count,
    }

    # Render the table content (without pagination)
    table_html = render_to_string("credit/fetch.html", context, request=request)

    # Render pagination separately
    pagination_html = ""
    if page_obj and page_obj.paginator.num_pages > 1:
        pagination_html = render_to_string(
            "common/_pagination.html", context, request=request
        )

    return JsonResponse(
        {"html": table_html, "pagination": pagination_html, "success": True}
    )


def _build_ledger_rows(customer):
    """Helper function to build unified ledger rows from invoices and payments."""
    # Fetch credit invoices with allocation information
    credit_invoices = (
        Invoice.objects.filter(
            customer=customer, payment_type=Invoice.PaymentType.CREDIT
        )
        .values(
            "id",
            "invoice_number",
            "invoice_date",
            "amount",
            "discount_amount",
            "advance_amount",
            "paid_amount",
            "payment_status",
            "notes",
        )
        .order_by("invoice_date")
    )

    # Fetch payments
    payments = (
        Payment.objects.filter(customer=customer)
        .values(
            "id",
            "payment_type",
            "payment_date",
            "amount",
            "method",
            "notes",
            "unallocated_amount",
        )
        .order_by("payment_date")
    )

    # Build unified ledger rows
    rows = []
    for inv in credit_invoices:
        # Calculate final invoice amount: amount - discount - advance
        gross_amount = inv["amount"] or Decimal("0")
        discount_amount = inv.get("discount_amount") or Decimal("0")
        advance_amount = inv.get("advance_amount") or Decimal("0")
        net_amount = gross_amount - discount_amount - advance_amount

        paid_amount = inv.get("paid_amount") or Decimal("0")
        payment_status = inv.get("payment_status", "UNPAID")
        outstanding_amount = net_amount - paid_amount

        rows.append(
            {
                "id": inv["id"],
                "date": inv["invoice_date"],
                "type": "Invoice",
                "ref": inv["invoice_number"],
                "notes": inv.get("notes"),
                "credit": net_amount,  # This is the final amount after discounts and advances
                "debit": Decimal("0"),
                "paid_amount": paid_amount,
                "payment_status": payment_status,
                "outstanding": outstanding_amount,
                # Additional fields for debugging/display
                "gross_amount": gross_amount,
                "discount_amount": discount_amount,
                "advance_amount": advance_amount,
            }
        )

    for pay in payments:
        if pay["payment_type"] == Payment.PaymentType.Purchased:
            credit = pay["amount"] or Decimal("0")
            debit = Decimal("0")
        else:
            credit = Decimal("0")
            debit = pay["amount"] or Decimal("0")
        rows.append(
            {
                "id": pay["id"],
                "date": pay["payment_date"],
                "type": "Payment",
                "ref": pay["id"],
                "method": pay.get("method"),
                "notes": pay.get("notes"),
                "credit": credit,
                "debit": debit,
            }
        )

    return rows


@login_required
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

    # Sort rows
    if sort_by == "date":
        rows.sort(key=lambda r: (r["date"] or datetime.min, r["type"]))
    elif sort_by == "-date":
        rows.sort(key=lambda r: (r["date"] or datetime.max, r["type"]), reverse=True)
    elif sort_by == "credit":
        rows.sort(
            key=lambda r: (r["credit"] or Decimal("0"), r["date"] or datetime.min)
        )
    elif sort_by == "-credit":
        rows.sort(
            key=lambda r: (r["credit"] or Decimal("0"), r["date"] or datetime.max),
            reverse=True,
        )
    elif sort_by == "debit":
        rows.sort(key=lambda r: (r["debit"] or Decimal("0"), r["date"] or datetime.min))
    elif sort_by == "-debit":
        rows.sort(
            key=lambda r: (r["debit"] or Decimal("0"), r["date"] or datetime.max),
            reverse=True,
        )
    elif sort_by == "outstanding":
        rows.sort(
            key=lambda r: (
                r.get("outstanding", Decimal("0")) or Decimal("0"),
                r["date"] or datetime.min,
            )
        )
    elif sort_by == "-outstanding":
        rows.sort(
            key=lambda r: (
                r.get("outstanding", Decimal("0")) or Decimal("0"),
                r["date"] or datetime.max,
            ),
            reverse=True,
        )

    # Pagination
    paginator = Paginator(rows, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "customer": customer,
        "page_obj": page_obj,
        "total_count": paginator.count,
    }

    table_html = render_to_string("credit/ledger/fetch.html", context, request=request)

    pagination_html = ""
    if page_obj and page_obj.paginator.num_pages > 1:
        pagination_html = render_to_string(
            "common/_pagination.html", context, request=request
        )

    return JsonResponse(
        {"html": table_html, "pagination": pagination_html, "success": True}
    )


@login_required
def credit_detail(request, customer_id: int):
    template = "credit/detail.html"
    customer = get_object_or_404(Customer, pk=customer_id)

    # Build all ledger rows for totals calculation
    rows = _build_ledger_rows(customer)

    # Sort rows by date descending, then type for stability
    rows.sort(key=lambda r: (r["date"] or 0, r["type"]), reverse=True)

    # Totals
    total_credit = sum((r["credit"] for r in rows), Decimal("0"))
    total_debit = sum((r["debit"] for r in rows), Decimal("0"))
    balance = total_credit - total_debit

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
        "total_credit": total_credit,
        "total_debit": total_debit,
        "balance": balance,
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
        messages.success(self.request, "Payment created successfully.")
        return super().form_valid(form)

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


def _auto_allocate_payment(payment, user):
    """Auto-allocate payment using FIFO method."""
    # Get unpaid credit invoices for this customer in chronological order (FIFO)
    unpaid_invoices = Invoice.objects.filter(
        customer=payment.customer,
        payment_type=Invoice.PaymentType.CREDIT,
        payment_status__in=[
            Invoice.PaymentStatus.UNPAID,
            Invoice.PaymentStatus.PARTIALLY_PAID,
        ],
    ).order_by("invoice_date")

    remaining_payment_amount = payment.unallocated_amount

    for invoice in unpaid_invoices:
        if remaining_payment_amount <= 0:
            break

        # Calculate how much is still owed on this invoice
        # Use remaining_amount which is: (amount - discount - advance) - paid_amount
        amount_owed = invoice.remaining_amount

        if amount_owed > 0:
            # Calculate allocation amount (either full remaining payment or full invoice amount)
            allocation_amount = min(remaining_payment_amount, amount_owed)

            # Create allocation
            PaymentAllocation.objects.create(
                payment=payment,
                invoice=invoice,
                amount_allocated=allocation_amount,
                created_by=user,
            )

            # Update invoice paid amount and status
            invoice.paid_amount += allocation_amount
            # Check if fully paid using net_amount_due (amount - discount - advance)
            if invoice.paid_amount >= invoice.net_amount_due:
                invoice.payment_status = Invoice.PaymentStatus.PAID
            elif invoice.paid_amount > 0:
                invoice.payment_status = Invoice.PaymentStatus.PARTIALLY_PAID
            invoice.save()

            # Update payment unallocated amount
            remaining_payment_amount -= allocation_amount
            payment.unallocated_amount = remaining_payment_amount
            payment.save()


@login_required
def auto_reallocate(request, customer_id):
    """
    Auto reallocate customer payments using FIFO method.
    This function deletes all existing allocations and reapplies them
    in chronological order (oldest invoices first).
    """
    customer = get_object_or_404(Customer, id=customer_id)

    # Get all credit invoices and payments for this customer
    invoices = Invoice.objects.filter(
        customer=customer, payment_type=Invoice.PaymentType.CREDIT
    ).order_by("invoice_date")

    payments = Payment.objects.filter(
        customer=customer, payment_type=Payment.PaymentType.Paid, is_deleted=False
    ).order_by("payment_date")

    # Delete all existing allocations for this customer
    PaymentAllocation.objects.filter(
        payment__customer=customer, payment__is_deleted=False
    ).delete()

    # Reset all invoice paid amounts and status
    for invoice in invoices:
        invoice.paid_amount = 0
        invoice.payment_status = Invoice.PaymentStatus.UNPAID
        invoice.save()

    # Reset all payment unallocated amounts
    for payment in payments:
        payment.unallocated_amount = payment.amount
        payment.save()

    # Implement FIFO allocation
    for payment in payments:
        _auto_allocate_payment(payment, request.user)

    messages.success(
        request,
        f"Successfully reallocated payments for {customer.name} using FIFO method.",
    )
    return redirect("customer:credit_detail", customer_id=customer_id)
