from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Sum, Count, Case, When, DecimalField, Value, F
from django.db.models.functions import Coalesce, TruncDate, TruncWeek, TruncMonth
from django.contrib import messages
from .models import Customer, Payment
from invoice.models import Invoice
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from .forms import CustomerForm
from django.urls import reverse_lazy
from datetime import timedelta
from decimal import Decimal
from base.getDates import getDates
import logging
from base.utility import get_periodic_data, get_period_label, render_paginated_response

logger = logging.getLogger(__name__)


def dashboard(request):
    """
    Customer management dashboard with analytics and insights.

    OPTIMIZED: Uses single query with multiple aggregations instead of separate queries.
    """
    date_filter = request.GET.get("date_filter", "this_month")

    # Calculate total outstanding using customer model's balance_amount method
    # balance_amount = credit_amount - debit_amount
    # where credit_amount = (credit invoices - discount - advance) + purchased payments
    # and debit_amount = paid payments

    # Get both metrics in a single query
    metrics = Customer.objects.filter(is_deleted=False).aggregate(
        total_outstanding=Coalesce(Sum("credit_summary__balance_amount"), Decimal("0")),
        total_customers=Count("id"),
    )

    context = {
        "date_filter": date_filter,
        "total_outstanding": metrics["total_outstanding"],
        "total_customers": metrics["total_customers"],
    }
    return render(request, "customer/dashboard.html", context)


def get_comparison_data(date_filter, current_start, current_end):
    """Generate comparison data for line chart based on date filter"""
    previous_start, previous_end, period_type = get_periodic_data(
        date_filter, current_start, current_end
    )

    current_invoices = Invoice.objects.filter(
        invoice_date__date__range=[current_start, current_end]
    )
    current_data = get_period_data(
        current_invoices, current_start, current_end, period_type
    )

    previous_invoices = Invoice.objects.filter(
        invoice_date__date__range=[previous_start, previous_end]
    )
    previous_data = get_period_data(
        previous_invoices, previous_start, previous_end, period_type
    )

    return {
        "current_period": {
            "label": get_period_label(current_start, current_end, period_type),
            "data": current_data,
        },
        "previous_period": {
            "label": get_period_label(previous_start, previous_end, period_type),
            "data": previous_data,
        },
        "period_type": period_type,
    }


def get_period_data(invoices, start_date, end_date, period_type):
    """
    Get aggregated data for a specific period using database-level grouping

    OPTIMIZED: Uses Django's date truncation functions instead of Python loops
    to perform grouping at the database level, dramatically reducing queries.

    Args:
        invoices: QuerySet of Invoice objects
        start_date: Period start date
        end_date: Period end date
        period_type: One of 'daily', 'monthly', 'quarterly', 'yearly'

    Returns:
        List of dictionaries containing date, amount, and invoice count
    """

    if period_type == "daily":
        # For daily, return single aggregated data point
        aggregated = invoices.aggregate(
            total_amount=Coalesce(
                Sum(F("amount") - F("discount_amount")),
                Decimal("0"),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
            total_invoices=Count("id"),
        )

        return [
            {
                "date": start_date.strftime("%Y-%m-%d"),
                "amount": float(aggregated["total_amount"]),
                "invoices": aggregated["total_invoices"],
            }
        ]

    elif period_type == "monthly":
        # Group by day using database truncation
        daily_data = (
            invoices.annotate(day=TruncDate("invoice_date"))
            .values("day")
            .annotate(
                amount=Coalesce(
                    Sum(F("amount") - F("discount_amount")),
                    Decimal("0"),
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                ),
                invoices=Count("id"),
            )
            .order_by("day")
        )

        return [
            {
                "date": item["day"].strftime("%Y-%m-%d"),
                "amount": float(item["amount"]),
                "invoices": item["invoices"],
            }
            for item in daily_data
        ]

    elif period_type == "quarterly":
        # Group by week using database truncation
        weekly_data = (
            invoices.annotate(week=TruncWeek("invoice_date"))
            .values("week")
            .annotate(
                amount=Coalesce(
                    Sum(F("amount") - F("discount_amount")),
                    Decimal("0"),
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                ),
                invoices=Count("id"),
            )
            .order_by("week")
        )

        return [
            {
                "date": item["week"].strftime("%Y-%m-%d"),
                "amount": float(item["amount"]),
                "invoices": item["invoices"],
            }
            for item in weekly_data
        ]

    else:  # yearly
        # Group by month using database truncation
        monthly_data = (
            invoices.annotate(month=TruncMonth("invoice_date"))
            .values("month")
            .annotate(
                amount=Coalesce(
                    Sum(F("amount") - F("discount_amount")),
                    Decimal("0"),
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                ),
                invoices=Count("id"),
            )
            .order_by("month")
        )

        return [
            {
                "date": item["month"].strftime("%Y-%m-%d"),
                "amount": float(item["amount"]),
                "invoices": item["invoices"],
            }
            for item in monthly_data
        ]


def dashboard_fetch(request):
    """
    AJAX endpoint to fetch customer dashboard data

    OPTIMIZED: Combines multiple aggregations into fewer queries and uses
    single-pass list comprehensions for percentage calculations.
    """
    date_filter = request.GET.get("date_filter", "this_month")
    start_date, end_date = getDates(request)

    # Filter invoices by date range
    invoices = Invoice.objects.filter(
        invoice_date__date__range=[start_date, end_date]
    ).select_related("customer")

    payments = Payment.objects.filter(
        payment_type=Payment.PaymentType.Paid,
        payment_date__date__range=[start_date, end_date],
    ).select_related("customer")

    # Calculate PERIOD-BASED totals in a single query
    invoice_metrics = invoices.aggregate(
        total_sales=Coalesce(
            Sum(F("amount") - F("discount_amount")),
            Decimal("0"),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        ),
        total_received_from_invoices=Coalesce(
            Sum("paid_amount"),
            Decimal("0"),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        ),
        total_invoices=Count("id"),
    )

    # Get payments received
    payments_received = payments.aggregate(
        total=Coalesce(
            Sum("amount"),
            Decimal("0"),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"]

    # Calculate final metrics
    total_sales = invoice_metrics["total_sales"]
    total_received = invoice_metrics["total_received_from_invoices"] + payments_received
    total_invoices = invoice_metrics["total_invoices"]
    outstanding_balance = total_sales - total_received

    # Calculate comparison data for line chart
    comparison_data = get_comparison_data(date_filter, start_date, end_date)

    # Payment status breakdown
    payment_status_breakdown = (
        invoices.values("payment_status")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum(F("amount") - F("discount_amount")),
                Decimal("0"),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
        )
        .order_by("payment_status")
    )

    # Payment type breakdown (Cash vs Credit)
    payment_type_breakdown = (
        invoices.values("payment_type")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum(F("amount") - F("discount_amount")),
                Decimal("0"),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
        )
        .order_by("payment_type")
    )

    # Customer breakdown (sales by customer)
    customer_breakdown = (
        invoices.values("customer__name")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum(F("amount") - F("discount_amount")),
                Decimal("0"),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
        )
        .order_by("-amount")[:10]  # Top 10 customers by sales amount
    )

    # Prepare response data
    stats = {
        "total_invoices": total_invoices,
        "total_sales": float(total_sales),
        "total_received": float(total_received),
        "outstanding_balance": float(outstanding_balance),
    }

    # Convert total_sales to float once for reuse
    total_sales_float = float(total_sales)

    # Payment status data processing - single pass with list comprehension
    payment_status_data = [
        {
            "payment_status": status["payment_status"].replace("_", " ").title(),
            "count": status["count"],
            "amount": float(status["amount"]),
            "percentage": (
                round((float(status["amount"]) / total_sales_float * 100), 1)
                if total_sales_float > 0
                else 0
            ),
        }
        for status in payment_status_breakdown
    ]

    # Payment type data processing - single pass with list comprehension
    payment_type_data = [
        {
            "payment_type": ptype["payment_type"].replace("_", " ").title(),
            "count": ptype["count"],
            "amount": float(ptype["amount"]),
            "percentage": (
                round((float(ptype["amount"]) / total_sales_float * 100), 1)
                if total_sales_float > 0
                else 0
            ),
        }
        for ptype in payment_type_breakdown
    ]

    # Customer breakdown data processing - single pass with list comprehension
    customer_list = list(customer_breakdown)
    top10_customer_total = float(sum(float(c["amount"]) for c in customer_list))

    customer_data = [
        {
            "customer_name": customer["customer__name"] or "Unknown",
            "count": customer["count"],
            "amount": float(customer["amount"]),
            "percentage": (
                round((float(customer["amount"]) / top10_customer_total * 100), 1)
                if top10_customer_total > 0
                else 0
            ),
        }
        for customer in customer_list
    ]

    return JsonResponse(
        {
            "success": True,
            "stats": stats,
            "payment_status_breakdown": payment_status_data,
            "payment_type_breakdown": payment_type_data,
            "customer_breakdown": customer_data,
            "comparison_data": comparison_data,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "filter": date_filter,
            },
        }
    )


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
}

CUSTOMERS_PER_PAGE = 20


def home(request):
    """Customer management main page - initial load only."""
    # For initial page load, just render the template with empty data
    return render(request, "customer/home.html")


def get_data(request):
    # Get search and filter parameters
    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")
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

    # Apply status filter (active/inactive based on soft delete)
    if status_filter == "active":
        filters &= Q(is_deleted=False)
    elif status_filter == "inactive":
        filters &= Q(is_deleted=True)

    customers = Customer.objects.filter(filters)

    # Apply sorting
    if sort_by not in VALID_SORT_FIELDS:
        sort_by = "-id"
    customers = customers.order_by(sort_by)

    return customers


def fetch_customers(request):
    """AJAX endpoint to fetch customers with search, filter, and pagination."""
    customers = get_data(request)

    return render_paginated_response(
        request,
        customers,
        "customer/fetch.html",
    )


class CreateCustomer(CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customer/form.html"
    success_url = reverse_lazy("customer:home")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Customer created successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Customer"
        context["customer"] = None  # For breadcrumb compatibility
        return context

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy("customer:home")


class EditCustomer(UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customer/form.html"
    success_url = reverse_lazy("customer:home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Customer"
        context["customer"] = self.get_object()  # For breadcrumb compatibility

        return context

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, "Customer updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class DeleteCustomer(DeleteView):
    model = Customer
    template_name = "customer/delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["customer"] = self.get_object()
        return context

    def delete(self, request, *args, **kwargs):
        customer = self.get_object()
        messages.success(request, f"Customer '{customer.name}' deleted successfully!")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("customer:home")

    def form_valid(self, form):
        messages.success(self.request, "Customer deleted successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


def customer_detail(request, pk):
    """View customer details."""
    customer = get_object_or_404(Customer, id=pk)

    # Get customer payments (FIFO system)
    context = {"customer": customer}
    context.update(get_calculations(pk))
    return render(request, "customer/detail.html", context)


def fetch_customer_invoices(request, pk):
    """AJAX: fetch invoices for a customer with pagination and optional sorting."""
    customer = get_object_or_404(Customer, id=pk)

    sort_by = (request.GET.get("sort") or "-invoice_date").strip()
    valid_sort_fields = {
        "invoice_date",
        "-invoice_date",
        "invoice_number",
        "-invoice_number",
        "amount",
        "-amount",
        "total_payable",
        "-total_payable",
    }
    if sort_by not in valid_sort_fields:
        sort_by = "-invoice_date"

    queryset = Invoice.objects.filter(customer=customer).order_by(sort_by)

    return render_paginated_response(
        request,
        queryset,
        "customer/invoice/fetch.html",
    )


def get_calculations(pk):
    customer = get_object_or_404(Customer, id=pk)
    invoices = Invoice.objects.filter(customer=customer)

    aggregates = invoices.aggregate(
        total_invoices=Count("id"),
        invoices_amount=Sum("amount"),
        cash_amount=Sum(
            Case(
                When(payment_type="CASH", then="amount"),
                default=0,
                output_field=DecimalField(),
            )
        ),
        credit_amount=Sum(
            Case(
                When(payment_type="CREDIT", then="amount"),
                default=0,
                output_field=DecimalField(),
            )
        ),
    )

    return {
        "total_invoices": aggregates["total_invoices"] or 0,
        "invoices_amount": aggregates["invoices_amount"] or 0,
        "cash_amount": aggregates["cash_amount"] or 0,
        "credit_amount": aggregates["credit_amount"] or 0,
    }


def customer_delete(request, customer_id):
    """Delete customer (soft delete)."""
    if request.method == "POST":
        customer = get_object_or_404(Customer, id=customer_id)
        customer.delete()  # This will use soft delete
        messages.success(request, "Customer deleted successfully!")
        return redirect("customer:home")

    return redirect("customer:home")


def create_customer_ajax(request):
    """AJAX endpoint for creating customers via modal"""
    try:
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Customer created successfully",
                    "data": {"id": customer.id, "name": customer.name},
                }
            )
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})
