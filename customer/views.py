from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count, Case, When, DecimalField, Value, F
from django.db.models.functions import Coalesce
from django.contrib import messages
from .models import Customer, Payment
from invoice.models import Invoice
import json
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from .forms import CustomerForm
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.template.loader import render_to_string, get_template
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from base.getDates import getDates
import logging
from weasyprint import HTML
from setting.models import ShopDetails, ReportConfiguration

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
}

CUSTOMERS_PER_PAGE = 20


@login_required
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


@login_required
def fetch_customers(request):
    """AJAX endpoint to fetch customers with search, filter, and pagination."""
    customers = get_data(request)

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
    table_html = render_to_string("customer/fetch.html", context, request=request)

    # Render pagination via template (clean and maintainable)
    pagination_html = ""
    if page_obj and page_obj.paginator.num_pages > 1:
        pagination_html = render_to_string(
            "common/_pagination.html", context, request=request
        )

    return JsonResponse(
        {"html": table_html, "pagination": pagination_html, "success": True}
    )


class CreateCustomer(LoginRequiredMixin, CreateView):
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


class EditCustomer(LoginRequiredMixin, UpdateView):
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


class DeleteCustomer(LoginRequiredMixin, DeleteView):
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


@login_required
def customer_detail(request, pk):
    """View customer details."""
    customer = get_object_or_404(Customer, id=pk)
    invoices = Invoice.objects.filter(customer=customer)

    # Get customer payments (FIFO system)
    context = {
        "customer": customer,
        "invoices": invoices,
    }
    context.update(get_calculations(pk))
    return render(request, "customer/detail.html", context)


@login_required
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

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "customer": customer,
        "page_obj": page_obj,
        "total_count": paginator.count,
    }

    table_html = render_to_string(
        "customer/invoice/fetch.html", context, request=request
    )

    pagination_html = ""
    if page_obj and page_obj.paginator.num_pages > 1:
        pagination_html = render_to_string(
            "common/_pagination.html", context, request=request
        )

    return JsonResponse(
        {"html": table_html, "pagination": pagination_html, "success": True}
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


@login_required
def customer_delete(request, customer_id):
    """Delete customer (soft delete)."""
    if request.method == "POST":
        customer = get_object_or_404(Customer, id=customer_id)
        customer.delete()  # This will use soft delete
        messages.success(request, "Customer deleted successfully!")
        return redirect("customer:home")

    return redirect("customer:home")


@login_required
def customer_search_api(request):
    """API endpoint for searching customers (for autocomplete)."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    query = request.GET.get("q", "").strip()

    if len(query) < 2:
        return JsonResponse({"customers": []})

    # Search customers by name or phone number
    customers = (
        Customer.objects.filter(
            Q(name__icontains=query) | Q(phone_number__icontains=query),
            is_deleted=False,
        )
        .exclude(
            # Exclude current customer if editing
            id=request.GET.get("exclude", -1)
        )
        .order_by("name")[:10]
    )  # Limit to 10 results

    # Format response
    customers_data = []
    for customer in customers:
        customers_data.append(
            {
                "id": customer.id,
                "name": customer.name or "",
                "phone_number": customer.phone_number or "",
                "email": customer.email or "",
            }
        )

    return JsonResponse({"customers": customers_data})


@login_required
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


@login_required
def dashboard(request):
    """Customer management dashboard with analytics and insights."""
    date_filter = request.GET.get("date_filter", "this_month")

    # Calculate total outstanding using customer model's balance_amount method
    # balance_amount = credit_amount - debit_amount
    # where credit_amount = (credit invoices - discount - advance) + purchased payments
    # and debit_amount = paid payments
    total_outstanding = Decimal("0.00")
    customers = Customer.objects.filter(is_deleted=False)
    for customer in customers:
        total_outstanding += customer.balance_amount

    total_outstanding = total_outstanding.quantize(Decimal("0.01"))

    # Calculate total customers (static, doesn't change with date filter)
    total_customers = Customer.objects.filter(is_deleted=False).count()

    context = {
        "date_filter": date_filter,
        "total_outstanding": total_outstanding,
        "total_customers": total_customers,
    }
    return render(request, "customer/dashboard.html", context)


def get_comparison_data(date_filter, current_start, current_end):
    """Generate comparison data for line chart based on date filter"""
    if date_filter in ["today", "yesterday"]:
        previous_start = current_start - timedelta(days=1)
        previous_end = current_end - timedelta(days=1)
        period_type = "daily"
    elif date_filter in ["this_month", "last_month"]:
        if current_start.month == 1:
            previous_start = current_start.replace(
                year=current_start.year - 1, month=12
            )
        else:
            previous_start = current_start.replace(month=current_start.month - 1)
        if previous_start.month == 12:
            next_month = previous_start.replace(year=previous_start.year + 1, month=1)
        else:
            next_month = previous_start.replace(month=previous_start.month + 1)
        previous_end = next_month - timedelta(days=1)
        period_type = "monthly"
    elif date_filter in ["this_quarter", "last_quarter"]:
        quarter = (current_start.month - 1) // 3
        quarter_start_month = quarter * 3 + 1
        previous_quarter_start = current_start.replace(
            month=quarter_start_month - 3 if quarter_start_month > 3 else 9, day=1
        )
        if previous_quarter_start.month == 10:
            previous_quarter_start = previous_quarter_start.replace(
                year=previous_quarter_start.year - 1
            )
        previous_start = previous_quarter_start
        period_type = "quarterly"
    elif date_filter in ["this_finance", "last_finance"]:
        if current_start.month >= 4:
            previous_start = current_start.replace(
                year=current_start.year - 1, month=4, day=1
            )
            previous_end = current_start.replace(
                year=current_start.year, month=3, day=31
            )
        else:
            previous_start = current_start.replace(
                year=current_start.year - 2, month=4, day=1
            )
            previous_end = current_start.replace(
                year=current_start.year - 1, month=3, day=31
            )
        period_type = "yearly"
    else:
        if current_start.month == 1:
            previous_start = current_start.replace(
                year=current_start.year - 1, month=12
            )
        else:
            previous_start = current_start.replace(month=current_start.month - 1)
        if previous_start.month == 12:
            next_month = previous_start.replace(year=previous_start.year + 1, month=1)
        else:
            next_month = previous_start.replace(month=previous_start.month + 1)
        previous_end = next_month - timedelta(days=1)
        period_type = "monthly"

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
            "label": f"{current_start.strftime('%b %d, %Y')} - {current_end.strftime('%b %d, %Y')}",
            "data": current_data,
        },
        "previous_period": {
            "label": f"{previous_start.strftime('%b %d, %Y')} - {previous_end.strftime('%b %d, %Y')}",
            "data": previous_data,
        },
        "period_type": period_type,
    }


def get_period_data(invoices, start_date, end_date, period_type):
    """Get aggregated data for a specific period"""
    if period_type == "daily":
        total_amount = invoices.aggregate(
            total=Coalesce(
                Sum(F("amount") - F("discount_amount")),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            )
        )["total"] or Decimal("0.00")
        total_invoices = invoices.count()
        return [
            {
                "date": start_date.strftime("%Y-%m-%d"),
                "amount": float(total_amount),
                "invoices": total_invoices,
            }
        ]
    elif period_type == "monthly":
        daily_data = []
        current_date = start_date
        while current_date <= end_date:
            day_invoices = invoices.filter(invoice_date__date=current_date)
            day_amount = day_invoices.aggregate(
                total=Coalesce(
                    Sum(F("amount") - F("discount_amount")),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                )
            )["total"] or Decimal("0.00")
            day_count = day_invoices.count()
            daily_data.append(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "amount": float(day_amount),
                    "invoices": day_count,
                }
            )
            current_date += timedelta(days=1)
        return daily_data
    elif period_type == "quarterly":
        weekly_data = []
        current_date = start_date
        while current_date <= end_date:
            week_end = min(current_date + timedelta(days=6), end_date)
            week_invoices = invoices.filter(
                invoice_date__date__range=[current_date, week_end]
            )
            week_amount = week_invoices.aggregate(
                total=Coalesce(
                    Sum(F("amount") - F("discount_amount")),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                )
            )["total"] or Decimal("0.00")
            week_count = week_invoices.count()
            weekly_data.append(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "amount": float(week_amount),
                    "invoices": week_count,
                }
            )
            current_date += timedelta(days=7)
        return weekly_data
    else:  # yearly
        monthly_data = []
        current_date = start_date
        while current_date <= end_date:
            month_end = (current_date.replace(day=28) + timedelta(days=4)).replace(
                day=1
            ) - timedelta(days=1)
            month_end = min(month_end, end_date)
            month_invoices = invoices.filter(
                invoice_date__date__range=[current_date, month_end]
            )
            month_amount = month_invoices.aggregate(
                total=Coalesce(
                    Sum(F("amount") - F("discount_amount")),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                )
            )["total"] or Decimal("0.00")
            month_count = month_invoices.count()
            monthly_data.append(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "amount": float(month_amount),
                    "invoices": month_count,
                }
            )
            if month_end.month == 12:
                current_date = month_end.replace(
                    year=month_end.year + 1, month=1, day=1
                )
            else:
                current_date = month_end.replace(month=month_end.month + 1, day=1)
        return monthly_data


@login_required
def dashboard_fetch(request):
    """AJAX endpoint to fetch customer dashboard data"""
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

    # Calculate PERIOD-BASED totals
    total_sales = invoices.aggregate(
        total=Coalesce(
            Sum(F("amount") - F("discount_amount")),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"] or Decimal("0.00")

    total_received = invoices.aggregate(
        total=Coalesce(
            Sum("paid_amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"] or Decimal("0.00")

    # Add payments received
    payments_received = payments.aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"] or Decimal("0.00")

    total_received = total_received + payments_received

    # Calculate metrics
    total_invoices = invoices.count()
    outstanding_balance = total_sales - total_received  # Period-based outstanding

    # Calculate comparison data for line chart
    comparison_data = get_comparison_data(date_filter, start_date, end_date)

    # Payment status breakdown
    payment_status_breakdown = (
        invoices.values("payment_status")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum(F("amount") - F("discount_amount")),
                Value(Decimal("0.00")),
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
                Value(Decimal("0.00")),
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
                Value(Decimal("0.00")),
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

    # Payment status data processing
    payment_status_data = []
    for status in payment_status_breakdown:
        percentage = (
            (status["count"] / total_invoices * 100) if total_invoices > 0 else 0
        )
        payment_status_data.append(
            {
                "payment_status": status["payment_status"].replace("_", " ").title(),
                "count": status["count"],
                "amount": float(status["amount"] or 0),
                "percentage": round(percentage, 1),
            }
        )

    # Payment type data processing
    payment_type_data = []
    for ptype in payment_type_breakdown:
        percentage = (
            (ptype["count"] / total_invoices * 100) if total_invoices > 0 else 0
        )
        payment_type_data.append(
            {
                "payment_type": ptype["payment_type"].replace("_", " ").title(),
                "count": ptype["count"],
                "amount": float(ptype["amount"] or 0),
                "percentage": round(percentage, 1),
            }
        )

    # Customer breakdown data processing
    customer_data = []
    for customer in customer_breakdown:
        percentage = (
            (customer["count"] / total_invoices * 100) if total_invoices > 0 else 0
        )
        customer_data.append(
            {
                "customer_name": customer["customer__name"] or "Unknown",
                "count": customer["count"],
                "amount": float(customer["amount"] or 0),
                "percentage": round(percentage, 1),
            }
        )

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
