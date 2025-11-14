from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db.models import (
    Q,
    Sum,
    Count,
    DecimalField,
    Value,
    ExpressionWrapper,
    F,
    OuterRef,
    Subquery,
)
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from decimal import Decimal
from base.getDates import getDates
from .models import (
    Supplier,
    SupplierInvoice,
    SupplierPayment,
    SupplierPaymentAllocation,
)
from .forms import (
    SupplierForm,
    SupplierInvoiceForm,
    SupplierPaymentForm,
    SupplierPaymentAllocationForm,
)
import logging

logger = logging.getLogger(__name__)


def get_total_outstanding_balance():
    total_all_invoiced = SupplierInvoice.objects.filter(is_deleted=False).aggregate(
        total=Coalesce(
            Sum("total_amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"]

    total_all_paid = SupplierPayment.objects.filter(is_deleted=False).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"]

    return (total_all_invoiced - total_all_paid).quantize(Decimal("0.01"))


@login_required
def dashboard(request):
    """Supplier management dashboard with analytics and insights."""
    date_filter = request.GET.get("date_filter", "this_month")

    # Calculate full balance due (all invoices - all payments, regardless of status)
    # This matches the logic in Supplier.balance_due property
    total_outstanding = get_total_outstanding_balance()

    # Calculate total suppliers (static, doesn't change with date filter)
    total_suppliers = Supplier.objects.filter(is_deleted=False).count()

    context = {
        "date_filter": date_filter,
        "total_outstanding": total_outstanding,
        "total_suppliers": total_suppliers,
    }
    return render(request, "supplier/dashboard.html", context)


def get_comparison_data(date_filter, current_start, current_end):
    """Generate comparison data for line chart based on date filter"""
    # Calculate previous period dates
    period_duration = current_end - current_start

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

    current_invoices = SupplierInvoice.objects.filter(
        is_deleted=False, invoice_date__date__range=[current_start, current_end]
    )
    current_data = get_period_data(
        current_invoices, current_start, current_end, period_type
    )

    previous_invoices = SupplierInvoice.objects.filter(
        is_deleted=False, invoice_date__date__range=[previous_start, previous_end]
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
        total_amount = invoices.aggregate(total=Sum("total_amount"))[
            "total"
        ] or Decimal("0")
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
            day_amount = day_invoices.aggregate(total=Sum("total_amount"))[
                "total"
            ] or Decimal("0")
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
        week_num = 1
        while current_date <= end_date:
            week_end = min(current_date + timedelta(days=6), end_date)
            week_invoices = invoices.filter(
                invoice_date__date__range=[current_date, week_end]
            )
            week_amount = week_invoices.aggregate(total=Sum("total_amount"))[
                "total"
            ] or Decimal("0")
            week_count = week_invoices.count()
            weekly_data.append(
                {
                    "date": current_date.strftime("%Y-%m-%d"),
                    "amount": float(week_amount),
                    "invoices": week_count,
                }
            )
            current_date += timedelta(days=7)
            week_num += 1
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
            month_amount = month_invoices.aggregate(total=Sum("total_amount"))[
                "total"
            ] or Decimal("0")
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
    """AJAX endpoint to fetch supplier dashboard data"""
    date_filter = request.GET.get("date_filter", "this_month")
    start_date, end_date = getDates(request)

    # Filter invoices by date range (for period-based stats)
    invoices = SupplierInvoice.objects.filter(
        is_deleted=False, invoice_date__date__range=[start_date, end_date]
    ).select_related("supplier")

    payments = SupplierPayment.objects.filter(
        is_deleted=False, payment_date__date__range=[start_date, end_date]
    ).select_related("supplier")

    # Calculate PERIOD-BASED totals (for "Total Invoiced" and "Total Paid" display)
    # These show amounts within the selected date range
    total_invoiced = invoices.aggregate(
        total=Coalesce(
            Sum("total_amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"] or Decimal("0.00")

    total_paid = payments.aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"] or Decimal("0.00")

    # Calculate ALL-TIME totals (for "Total Outstanding" calculation)
    total_all_invoiced = SupplierInvoice.objects.filter(is_deleted=False).aggregate(
        total=Coalesce(
            Sum("total_amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"] or Decimal("0.00")

    total_all_paid = SupplierPayment.objects.filter(is_deleted=False).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"] or Decimal("0.00")

    # Calculate metrics
    total_invoices = invoices.count()  # Period-based invoice count
    outstanding_balance = total_invoiced - total_paid  # Period-based outstanding

    # Calculate comparison data for line chart
    comparison_data = get_comparison_data(date_filter, start_date, end_date)

    # Invoice status breakdown (period-based)
    invoice_status_breakdown = (
        invoices.values("status")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum("total_amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
        )
        .order_by("status")
    )

    # Payment method breakdown (period-based)
    payment_method_breakdown = (
        payments.values("method")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum("amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
        )
        .order_by("method")
    )

    # Invoice type breakdown (period-based)
    invoice_type_breakdown = (
        invoices.values("invoice_type")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum("total_amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
        )
        .order_by("invoice_type")
    )

    # Supplier breakdown (period-based) - invoices purchased by supplier
    supplier_breakdown = (
        invoices.values("supplier__name")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum("total_amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
        )
        .order_by("-amount")[:10]  # Top 10 suppliers by amount
    )

    # Prepare response data
    stats = {
        "total_invoices": total_invoices,  # Period-based count
        "total_invoiced": float(total_invoiced),  # Period-based total
        "total_paid": float(total_paid),  # Period-based total
        "outstanding_balance": float(outstanding_balance),  # Period-based outstanding
        "net_amount": float(total_paid),
        "total_profit": float(outstanding_balance),
        "total_discount": float(Decimal("0")),
    }

    # Invoice status data processing
    invoice_status_data = []
    for status in invoice_status_breakdown:
        percentage = (
            (status["count"] / total_invoices * 100) if total_invoices > 0 else 0
        )
        invoice_status_data.append(
            {
                "payment_status": status["status"].replace("_", " ").title(),
                "count": status["count"],
                "amount": float(status["amount"] or 0),
                "percentage": round(percentage, 1),
            }
        )

    # Supplier breakdown data processing
    supplier_data = []
    for supplier in supplier_breakdown:
        percentage = (
            (supplier["count"] / total_invoices * 100) if total_invoices > 0 else 0
        )
        supplier_data.append(
            {
                "supplier_name": supplier["supplier__name"] or "Unknown",
                "count": supplier["count"],
                "amount": float(supplier["amount"] or 0),
                "percentage": round(percentage, 1),
            }
        )

    # Invoice type data processing
    invoice_type_data = []
    for inv_type in invoice_type_breakdown:
        percentage = (
            (inv_type["count"] / total_invoices * 100) if total_invoices > 0 else 0
        )
        invoice_type_data.append(
            {
                "category_name": inv_type["invoice_type"].replace("_", " ").title(),
                "count": inv_type["count"],
                "amount": float(inv_type["amount"] or 0),
                "percentage": round(percentage, 1),
            }
        )

    return JsonResponse(
        {
            "success": True,
            "stats": stats,
            "payment_status_breakdown": invoice_status_data,
            "supplier_breakdown": supplier_data,
            "category_breakdown": invoice_type_data,
            "comparison_data": comparison_data,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "filter": date_filter,
            },
        }
    )


@login_required
def dashboard_old(request):
    """Supplier management dashboard with analytics and insights - OLD VERSION"""

    # Get date range filter (default to current month)
    date_filter = request.GET.get("date_filter", "current_month")

    # Calculate date ranges
    today = timezone.now().date()
    if date_filter == "current_month":
        start_date = today.replace(day=1)
        end_date = today
    elif date_filter == "last_month":
        last_month = today.replace(day=1) - timedelta(days=1)
        start_date = last_month.replace(day=1)
        end_date = today.replace(day=1) - timedelta(days=1)
    elif date_filter == "last_3_months":
        start_date = today - timedelta(days=90)
        end_date = today
    elif date_filter == "last_6_months":
        start_date = today - timedelta(days=180)
        end_date = today
    elif date_filter == "current_year":
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:
        start_date = today.replace(day=1)
        end_date = today

    # Overall Statistics
    total_suppliers = Supplier.objects.filter(is_deleted=False).count()
    active_suppliers = Supplier.objects.filter(is_deleted=False).count()
    inactive_suppliers = Supplier.objects.filter(is_deleted=True).count()

    # Financial Statistics
    total_invoiced = (
        SupplierInvoice.objects.filter(
            is_deleted=False, invoice_date__date__range=[start_date, end_date]
        ).aggregate(total=Sum("total_amount"))["total"]
        or 0
    )

    total_paid = (
        SupplierPayment.objects.filter(
            is_deleted=False, payment_date__date__range=[start_date, end_date]
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    outstanding_balance = total_invoiced - total_paid

    # Invoice Statistics
    total_invoices = SupplierInvoice.objects.filter(
        is_deleted=False, invoice_date__date__range=[start_date, end_date]
    ).count()

    paid_invoices = SupplierInvoice.objects.filter(
        is_deleted=False,
        status="PAID",
        invoice_date__date__range=[start_date, end_date],
    ).count()

    unpaid_invoices = SupplierInvoice.objects.filter(
        is_deleted=False,
        status="UNPAID",
        invoice_date__date__range=[start_date, end_date],
    ).count()

    partially_paid_invoices = SupplierInvoice.objects.filter(
        is_deleted=False,
        status="PARTIALLY_PAID",
        invoice_date__date__range=[start_date, end_date],
    ).count()

    # Payment Statistics
    total_payments = SupplierPayment.objects.filter(
        is_deleted=False, payment_date__date__range=[start_date, end_date]
    ).count()

    # Top Suppliers by Outstanding Balance
    top_suppliers_outstanding = (
        Supplier.objects.filter(is_deleted=False)
        .annotate(
            total_invoiced=Sum(
                "invoices__total_amount", filter=Q(invoices__is_deleted=False)
            ),
            total_paid=Sum(
                "payments_made__amount", filter=Q(payments_made__is_deleted=False)
            ),
        )
        .annotate(
            outstanding=Sum(
                "invoices__total_amount", filter=Q(invoices__is_deleted=False)
            )
            - Sum("payments_made__amount", filter=Q(payments_made__is_deleted=False))
        )
        .filter(outstanding__gt=0)
        .order_by("-outstanding")[:5]
    )

    # Recent Activities
    recent_invoices = (
        SupplierInvoice.objects.filter(is_deleted=False)
        .select_related("supplier")
        .order_by("-created_at")[:5]
    )

    recent_payments = (
        SupplierPayment.objects.filter(is_deleted=False)
        .select_related("supplier")
        .order_by("-created_at")[:5]
    )

    # Monthly Trends (last 6 months)
    monthly_data = []
    for i in range(6):
        month_date = today - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(
            days=1
        )

        month_invoiced = (
            SupplierInvoice.objects.filter(
                is_deleted=False, invoice_date__date__range=[month_start, month_end]
            ).aggregate(total=Sum("total_amount"))["total"]
            or 0
        )

        month_paid = (
            SupplierPayment.objects.filter(
                is_deleted=False, payment_date__date__range=[month_start, month_end]
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        monthly_data.append(
            {
                "month": month_start.strftime("%b %Y"),
                "invoiced": float(month_invoiced),
                "paid": float(month_paid),
                "outstanding": float(month_invoiced - month_paid),
            }
        )

    monthly_data.reverse()  # Show oldest to newest

    # Payment Method Distribution
    payment_methods = (
        SupplierPayment.objects.filter(
            is_deleted=False, payment_date__date__range=[start_date, end_date]
        )
        .values("method")
        .annotate(count=Count("id"), total_amount=Sum("amount"))
        .order_by("-total_amount")
    )

    # Invoice Type Distribution
    invoice_types = (
        SupplierInvoice.objects.filter(
            is_deleted=False, invoice_date__date__range=[start_date, end_date]
        )
        .values("invoice_type")
        .annotate(count=Count("id"), total_amount=Sum("total_amount"))
        .order_by("-total_amount")
    )

    # GST vs Non-GST Analysis
    gst_invoices = SupplierInvoice.objects.filter(
        is_deleted=False,
        invoice_type="GST_APPLICABLE",
        invoice_date__date__range=[start_date, end_date],
    ).aggregate(
        count=Count("id"),
        total_amount=Sum("total_amount"),
        total_gst=Sum("cgst_amount") + Sum("igst_amount"),
    )

    local_invoices = SupplierInvoice.objects.filter(
        is_deleted=False,
        invoice_type="LOCAL_PURCHASE",
        invoice_date__date__range=[start_date, end_date],
    ).aggregate(count=Count("id"), total_amount=Sum("total_amount"))

    # Quick Actions Data
    suppliers_needing_attention = (
        Supplier.objects.filter(is_deleted=False)
        .annotate(
            total_invoiced=Sum(
                "invoices__total_amount", filter=Q(invoices__is_deleted=False)
            ),
            total_paid=Sum(
                "payments_made__amount", filter=Q(payments_made__is_deleted=False)
            ),
        )
        .annotate(
            outstanding=Sum(
                "invoices__total_amount", filter=Q(invoices__is_deleted=False)
            )
            - Sum("payments_made__amount", filter=Q(payments_made__is_deleted=False))
        )
        .filter(outstanding__gt=0)
        .count()
    )

    overdue_invoices = SupplierInvoice.objects.filter(
        is_deleted=False,
        status__in=["UNPAID", "PARTIALLY_PAID"],
        invoice_date__date__lt=today - timedelta(days=30),
    ).count()

    context = {
        # Date filters
        "date_filter": date_filter,
        "start_date": start_date,
        "end_date": end_date,
        # Overall statistics
        "total_suppliers": total_suppliers,
        "active_suppliers": active_suppliers,
        "inactive_suppliers": inactive_suppliers,
        # Financial statistics
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "outstanding_balance": outstanding_balance,
        # Invoice statistics
        "total_invoices": total_invoices,
        "paid_invoices": paid_invoices,
        "unpaid_invoices": unpaid_invoices,
        "partially_paid_invoices": partially_paid_invoices,
        # Payment statistics
        "total_payments": total_payments,
        # Top suppliers
        "top_suppliers_outstanding": top_suppliers_outstanding,
        # Recent activities
        "recent_invoices": recent_invoices,
        "recent_payments": recent_payments,
        # Charts data
        "monthly_data": monthly_data,
        "payment_methods": list(payment_methods),
        "invoice_types": list(invoice_types),
        # GST analysis
        "gst_invoices": gst_invoices,
        "local_invoices": local_invoices,
        # Quick actions
        "suppliers_needing_attention": suppliers_needing_attention,
        "overdue_invoices": overdue_invoices,
    }

    return render(request, "supplier/dashboard.html", context)


@login_required
def home(request):
    """Supplier management main page with search and filter functionality."""

    # Initial render only; data loads via AJAX from fetch_suppliers
    return render(request, "supplier/home.html")


# Constants for AJAX fetch
SUPPLIERS_PER_PAGE = 25
VALID_SORT_FIELDS = {
    "id",
    "-id",
    "name",
    "-name",
    "created_at",
    "-created_at",
    "phone",
    "-phone",
    "contact_person",
    "-contact_person",
    "gstin",
    "-gstin",
    "balance_due",
    "-balance_due",
}


def get_suppliers_data(request):
    search_query = request.GET.get("search", "").strip()
    status_filter = request.GET.get("status", "").strip()
    sort_by = request.GET.get("sort", "-id").strip()

    filters = Q()
    if search_query:
        filters &= (
            Q(name__icontains=search_query)
            | Q(contact_person__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(gstin__icontains=search_query)
            | Q(first_line__icontains=search_query)
            | Q(second_line__icontains=search_query)
            | Q(city__icontains=search_query)
            | Q(state__icontains=search_query)
            | Q(pincode__icontains=search_query)
            | Q(country__icontains=search_query)
        )

    if status_filter == "active":
        filters &= Q(is_deleted=False)
    elif status_filter == "inactive":
        filters &= Q(is_deleted=True)

    if sort_by not in VALID_SORT_FIELDS:
        sort_by = "-id"

    suppliers = Supplier.objects.filter(filters)

    if sort_by in {"balance_due", "-balance_due"}:
        sort_prefix = "-" if sort_by.startswith("-") else ""
        invoice_totals = (
            SupplierInvoice.objects.filter(supplier=OuterRef("pk"), is_deleted=False)
            .order_by()
            .values("supplier")
            .annotate(total=Sum("total_amount"))
            .values("total")
        )
        payment_totals = (
            SupplierPayment.objects.filter(supplier=OuterRef("pk"), is_deleted=False)
            .order_by()
            .values("supplier")
            .annotate(total=Sum("amount"))
            .values("total")
        )

        suppliers = suppliers.annotate(
            total_invoiced=Coalesce(
                Subquery(
                    invoice_totals[:1],
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
            total_paid=Coalesce(
                Subquery(
                    payment_totals[:1],
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
        ).annotate(
            calculated_balance_due=ExpressionWrapper(
                F("total_invoiced") - F("total_paid"),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            )
        )
        sort_by = f"{sort_prefix}calculated_balance_due"

    suppliers = suppliers.order_by(sort_by)
    return suppliers


@login_required
def fetch_suppliers(request):
    """AJAX endpoint to fetch suppliers with search, filter, sorting, and pagination."""

    suppliers = get_suppliers_data(request)
    # Debug prints removed

    paginator = Paginator(suppliers, SUPPLIERS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "total_count": paginator.count,
    }

    table_html = render_to_string("supplier/fetch.html", context, request=request)

    pagination_html = ""
    if page_obj and page_obj.paginator.num_pages > 1:
        pagination_html = render_to_string(
            "common/_pagination.html", context, request=request
        )

    return JsonResponse(
        {"html": table_html, "pagination": pagination_html, "success": True}
    )


@login_required
def fetch_supplier_invoices(request, pk):
    """AJAX: fetch invoices for a supplier with pagination and optional sorting."""
    supplier = get_object_or_404(Supplier, id=pk)

    sort_by = (request.GET.get("sort") or "-invoice_date").strip()
    valid_sort_fields = {
        "invoice_date",
        "-invoice_date",
        "total_amount",
        "-total_amount",
        "sub_total",
        "-sub_total",
        "status",
        "-status",
        "invoice_number",
        "-invoice_number",
    }
    if sort_by not in valid_sort_fields:
        sort_by = "-invoice_date"

    queryset = supplier.invoices.filter(is_deleted=False).order_by(sort_by)

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "supplier": supplier,
        "page_obj": page_obj,
        "total_count": paginator.count,
    }

    table_html = render_to_string(
        "supplier/invoice/fetch.html", context, request=request
    )

    pagination_html = ""
    if page_obj and page_obj.paginator.num_pages > 1:
        pagination_html = render_to_string(
            "common/_pagination.html", context, request=request
        )

    return JsonResponse(
        {"html": table_html, "pagination": pagination_html, "success": True}
    )


@login_required
def fetch_supplier_payments(request, pk):
    """AJAX: fetch payments for a supplier with pagination and optional sorting."""
    supplier = get_object_or_404(Supplier, id=pk)

    sort_by = (request.GET.get("sort") or "-payment_date").strip()
    valid_sort_fields = {
        "payment_date",
        "-payment_date",
        "amount",
        "-amount",
        "unallocated_amount",
        "-unallocated_amount",
        "id",
        "-id",
        "method",
        "-method",
    }
    if sort_by not in valid_sort_fields:
        sort_by = "-payment_date"

    queryset = supplier.payments_made.filter(is_deleted=False).order_by(sort_by)

    paginator = Paginator(queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "supplier": supplier,
        "page_obj": page_obj,
        "total_count": paginator.count,
    }

    table_html = render_to_string(
        "supplier/payment/fetch.html", context, request=request
    )

    pagination_html = ""
    if page_obj and page_obj.paginator.num_pages > 1:
        pagination_html = render_to_string(
            "common/_pagination.html", context, request=request
        )

    return JsonResponse(
        {"html": table_html, "pagination": pagination_html, "success": True}
    )


@login_required
def supplier_detail(request, pk):
    """View supplier details with invoices and payments tables."""
    supplier = get_object_or_404(Supplier, id=pk)

    # Get actual invoices from database
    invoices = supplier.invoices.all().order_by("-invoice_date")

    # Calculate invoice summary data
    total_invoice_amount = sum(invoice.total_amount for invoice in invoices)
    unpaid_invoices_count = sum(1 for invoice in invoices if invoice.status != "PAID")

    # Get actual payments from database (replace sample data later)
    payments = supplier.payments_made.all().order_by("-payment_date")

    # Calculate payment summary data
    total_payment_amount = sum(payment.amount for payment in payments)
    outstanding_amount = total_invoice_amount - total_payment_amount

    context = {
        "supplier": supplier,
        "invoices": invoices,
        "payments": payments,
        "total_invoice_amount": total_invoice_amount,
        "unpaid_invoices_count": unpaid_invoices_count,
        "total_payment_amount": total_payment_amount,
        "outstanding_amount": outstanding_amount,
    }

    return render(request, "supplier/detail.html", context)


@login_required
def delete_invoice(request, supplier_pk, invoice_pk):
    """Delete an invoice."""
    supplier = get_object_or_404(Supplier, id=supplier_pk)
    invoice = get_object_or_404(SupplierInvoice, id=invoice_pk, supplier=supplier)

    if request.method == "POST":
        invoice_number = invoice.invoice_number
        invoice.delete()
        messages.success(request, f"Invoice {invoice_number} deleted successfully!")
        return redirect("supplier:detail", pk=supplier_pk)

    context = {"supplier": supplier, "invoice": invoice}

    return render(request, "supplier/invoice/delete.html", context)


@login_required
def search_suppliers_ajax(request):
    """AJAX endpoint for real-time supplier search."""
    search_query = request.GET.get("q", "")

    if len(search_query) < 2:
        return JsonResponse({"suppliers": []})

    suppliers = Supplier.objects.filter(
        Q(name__icontains=search_query)
        | Q(contact_person__icontains=search_query)
        | Q(phone__icontains=search_query)
        | Q(email__icontains=search_query)
        | Q(gstin__icontains=search_query)
    )[
        :10
    ]  # Limit to 10 results

    data = []
    for supplier in suppliers:
        data.append(
            {
                "id": supplier.id,
                "name": supplier.name,
                "contact_person": supplier.contact_person,
                "phone": supplier.phone,
                "email": supplier.email,
                "gstin": supplier.gstin,
                "is_active": not supplier.is_deleted,
            }
        )

    return JsonResponse({"suppliers": data})


class CreateSupplier(LoginRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "supplier/form.html"
    success_url = reverse_lazy("supplier:home")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Supplier created successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Supplier"
        context["supplier"] = None  # For breadcrumb compatibility
        return context


class EditSupplier(LoginRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "supplier/form.html"
    success_url = reverse_lazy("supplier:home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Supplier"
        context["supplier"] = self.get_object()  # For breadcrumb compatibility
        return context

    def form_valid(self, form):
        messages.success(self.request, "Supplier updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class DeleteSupplier(LoginRequiredMixin, DeleteView):
    model = Supplier
    success_url = reverse_lazy("supplier:home")
    template_name = "supplier/delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["supplier"] = self.get_object()
        return context

    def delete(self, request, *args, **kwargs):
        supplier = self.get_object()
        messages.success(request, f"Supplier '{supplier.name}' deleted successfully!")
        return super().delete(request, *args, **kwargs)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


# Payment Views
class CreatePayment(LoginRequiredMixin, CreateView):
    model = SupplierPayment
    form_class = SupplierPaymentForm
    template_name = "supplier/payment/form.html"

    def get_success_url(self):
        return reverse_lazy("supplier:detail", kwargs={"pk": self.supplier.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Payment"
        context["supplier"] = self.supplier
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["supplier"] = self.supplier
        return kwargs

    def form_valid(self, form):
        form.instance.supplier = self.supplier
        form.instance.created_by = self.request.user
        form.instance.save()
        messages.success(
            self.request,
            f"Payment of ₹{form.instance.amount} recorded successfully!",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        self.supplier = get_object_or_404(Supplier, id=kwargs["supplier_pk"])
        return super().dispatch(request, *args, **kwargs)


class EditPayment(LoginRequiredMixin, UpdateView):
    model = SupplierPayment
    form_class = SupplierPaymentForm
    template_name = "supplier/payment/form.html"
    pk_url_kwarg = "payment_pk"

    def get_success_url(self):
        return reverse_lazy("supplier:detail", kwargs={"pk": self.supplier.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Payment"
        context["supplier"] = self.supplier
        context["payment"] = self.get_object()

        # Get allocation information for warnings
        payment = self.get_object()
        total_allocated = (
            payment.allocations.aggregate(total=Sum("amount_allocated"))["total"] or 0
        )
        context["total_allocated"] = total_allocated
        context["has_allocations"] = total_allocated > 0

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["supplier"] = self.supplier
        return kwargs

    def form_valid(self, form):
        # Get the old payment amount before saving
        old_amount = self.get_object().amount
        new_amount = form.cleaned_data["amount"]

        # Save the payment
        payment = form.save()

        # Recalculate unallocated amount if payment amount changed
        if old_amount != new_amount:
            total_allocated = (
                payment.allocations.aggregate(total=Sum("amount_allocated"))["total"]
                or 0
            )
            payment.unallocated_amount = new_amount - total_allocated
            payment.save(update_fields=["unallocated_amount"])

        messages.success(
            self.request,
            f"Payment updated successfully!",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(
            self.request, "Invalid form submission. Please check your inputs."
        )
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        self.supplier = get_object_or_404(Supplier, id=kwargs["supplier_pk"])
        return super().dispatch(request, *args, **kwargs)


@login_required
def delete_payment(request, supplier_pk, payment_pk):
    """Delete a payment."""
    supplier = get_object_or_404(Supplier, id=supplier_pk)
    payment = get_object_or_404(SupplierPayment, id=payment_pk, supplier=supplier)

    if request.method == "POST":
        payment_amount = payment.amount
        payment.delete()
        messages.success(request, f"Payment of ₹{payment_amount} deleted successfully!")
        return redirect("supplier:detail", pk=supplier_pk)

    context = {"supplier": supplier, "payment": payment}

    return render(request, "supplier/payment/delete.html", context)


@login_required
def payment_detail(request, supplier_pk, payment_pk):
    """View payment details."""
    supplier = get_object_or_404(Supplier, id=supplier_pk)
    payment = get_object_or_404(SupplierPayment, id=payment_pk, supplier=supplier)

    # Get payment allocations if any
    allocations = payment.allocations.all().select_related("invoice")

    context = {
        "supplier": supplier,
        "payment": payment,
        "allocations": allocations,
    }

    return render(request, "supplier/payment/detail.html", context)


# Allocation Views
class CreateAllocation(LoginRequiredMixin, CreateView):
    model = SupplierPaymentAllocation
    form_class = SupplierPaymentAllocationForm
    template_name = "supplier/allocation/form.html"

    def get_success_url(self):
        return reverse_lazy(
            "supplier:payment_detail",
            kwargs={"supplier_pk": self.supplier.pk, "payment_pk": self.payment.pk},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Allocate Payment"
        context["supplier"] = self.supplier
        context["payment"] = self.payment
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["payment"] = self.payment
        kwargs["supplier"] = self.supplier
        return kwargs

    def form_valid(self, form):
        form.instance.payment = self.payment
        form.instance.created_by = self.request.user

        # Save the allocation
        allocation = form.save()

        # Update payment unallocated amount
        self.payment.unallocated_amount -= allocation.amount_allocated
        self.payment.save()

        # Recalculate paid amount for the invoice based on all allocations
        invoice = allocation.invoice
        total_allocated = (
            invoice.allocations.aggregate(total=Sum("amount_allocated"))["total"] or 0
        )
        invoice.paid_amount = total_allocated

        # Update invoice status
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = "PAID"
        elif invoice.paid_amount > 0:
            invoice.status = "PARTIALLY_PAID"
        else:
            invoice.status = "UNPAID"

        invoice.save()

        messages.success(
            self.request,
            f"₹{allocation.amount_allocated:,.2f} allocated to Invoice {invoice.invoice_number} successfully!",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        self.supplier = get_object_or_404(Supplier, id=kwargs["supplier_pk"])
        self.payment = get_object_or_404(
            SupplierPayment, id=kwargs["payment_pk"], supplier=self.supplier
        )
        return super().dispatch(request, *args, **kwargs)


class EditAllocation(LoginRequiredMixin, UpdateView):
    model = SupplierPaymentAllocation
    form_class = SupplierPaymentAllocationForm
    template_name = "supplier/allocation/form.html"
    pk_url_kwarg = "allocation_pk"

    def get_success_url(self):
        return reverse_lazy(
            "supplier:payment_detail",
            kwargs={"supplier_pk": self.supplier.pk, "payment_pk": self.payment.pk},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Allocation"
        context["supplier"] = self.supplier
        context["payment"] = self.payment
        context["allocation"] = self.get_object()

        # Calculate available amount for editing (unallocated + current allocation)
        current_allocation = self.get_object()
        available_amount = (
            self.payment.unallocated_amount + current_allocation.amount_allocated
        )
        context["available_amount"] = available_amount

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Create a temporary payment object for form validation without modifying the actual payment
        temp_payment = type(self.payment)(
            id=self.payment.id,
            amount=self.payment.amount,
            unallocated_amount=self.payment.unallocated_amount
            + self.get_object().amount_allocated,
        )
        kwargs["payment"] = temp_payment
        kwargs["supplier"] = self.supplier
        kwargs["current_allocation"] = self.get_object()
        return kwargs

    def form_valid(self, form):
        old_allocation = self.get_object()
        old_amount = old_allocation.amount_allocated
        old_invoice = old_allocation.invoice

        # Revert old allocation
        self.payment.unallocated_amount += old_amount
        self.payment.save()

        # Save new allocation
        allocation = form.save()

        # Apply new allocation
        self.payment.unallocated_amount -= allocation.amount_allocated
        self.payment.save()

        # Recalculate paid amount for the invoice based on all allocations
        invoice = allocation.invoice
        total_allocated = (
            invoice.allocations.aggregate(total=Sum("amount_allocated"))["total"] or 0
        )
        invoice.paid_amount = total_allocated

        # Update invoice status
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = "PAID"
        elif invoice.paid_amount > 0:
            invoice.status = "PARTIALLY_PAID"
        else:
            invoice.status = "UNPAID"
        invoice.save()

        messages.success(
            self.request,
            f"Allocation updated successfully!",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(
            self.request, "Invalid form submission. Please check your inputs."
        )
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        self.supplier = get_object_or_404(Supplier, id=kwargs["supplier_pk"])
        self.payment = get_object_or_404(
            SupplierPayment, id=kwargs["payment_pk"], supplier=self.supplier
        )
        return super().dispatch(request, *args, **kwargs)


@login_required
def delete_allocation(request, supplier_pk, payment_pk, allocation_pk):
    """Delete an allocation."""
    supplier = get_object_or_404(Supplier, id=supplier_pk)
    payment = get_object_or_404(SupplierPayment, id=payment_pk, supplier=supplier)
    allocation = get_object_or_404(
        SupplierPaymentAllocation, id=allocation_pk, payment=payment
    )

    if request.method == "POST":
        # Revert the allocation
        payment.unallocated_amount += allocation.amount_allocated
        payment.save()

        # Recalculate paid amount for the invoice based on remaining allocations
        invoice = allocation.invoice
        allocation_amount = allocation.amount_allocated
        allocation.delete()

        # Recalculate total allocated amount after deletion
        total_allocated = (
            invoice.allocations.aggregate(total=Sum("amount_allocated"))["total"] or 0
        )
        invoice.paid_amount = total_allocated

        # Update invoice status
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = "PAID"
        elif invoice.paid_amount > 0:
            invoice.status = "PARTIALLY_PAID"
        else:
            invoice.status = "UNPAID"
        invoice.save()

        messages.success(
            request, f"Allocation of ₹{allocation_amount:,.2f} deleted successfully!"
        )
        return redirect(
            "supplier:payment_detail", supplier_pk=supplier_pk, payment_pk=payment_pk
        )

    context = {
        "supplier": supplier,
        "payment": payment,
        "allocation": allocation,
    }

    return render(request, "supplier/allocation/delete.html", context)


class CreateInvoice(LoginRequiredMixin, CreateView):
    model = SupplierInvoice
    form_class = SupplierInvoiceForm
    template_name = "supplier/invoice/form.html"

    def get_success_url(self):
        return reverse_lazy("supplier:detail", kwargs={"pk": self.supplier.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Invoice"
        context["supplier"] = self.supplier
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["supplier"] = self.supplier
        return kwargs

    def form_valid(self, form):
        form.instance.supplier = self.supplier
        form.instance.created_by = self.request.user
        form.instance.total_amount = form.cleaned_data["total_amount"]
        form.instance.save()
        messages.success(
            self.request,
            f"Invoice {form.instance.invoice_number} created successfully!",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        self.supplier = get_object_or_404(Supplier, id=kwargs["supplier_pk"])
        return super().dispatch(request, *args, **kwargs)


class EditInvoice(LoginRequiredMixin, UpdateView):
    model = SupplierInvoice
    form_class = SupplierInvoiceForm
    template_name = "supplier/invoice/form.html"
    pk_url_kwarg = "invoice_pk"  # Use invoice_pk instead of pk

    def get_success_url(self):
        return reverse_lazy("supplier:detail", kwargs={"pk": self.supplier.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Invoice"
        context["supplier"] = self.supplier
        context["invoice"] = self.get_object()
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["supplier"] = self.supplier
        return kwargs

    def form_valid(self, form):
        form.instance.total_amount = form.cleaned_data["total_amount"]
        form.instance.save()
        messages.success(
            self.request,
            f"Invoice {form.instance.invoice_number} updated successfully!",
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        self.supplier = get_object_or_404(Supplier, id=kwargs["supplier_pk"])
        return super().dispatch(request, *args, **kwargs)


@login_required
def supplier_report(request, pk):
    """Generate a comprehensive report showing all purchases and payments for a supplier sorted by date."""
    supplier = get_object_or_404(Supplier, id=pk)

    # Get view type parameter (timeline or table)
    view_type = request.GET.get("view", "timeline")

    # Get all invoices and payments
    invoices = supplier.invoices.all().order_by("invoice_date")
    payments = supplier.payments_made.all().order_by("payment_date")

    # Create a combined timeline of all transactions
    transactions = []

    # Add invoices to transactions
    for invoice in invoices:
        transactions.append(
            {
                "date": invoice.invoice_date,
                "type": "invoice",
                "object": invoice,
                "amount": invoice.total_amount,
                "description": f"Invoice #{invoice.invoice_number}",
                "status": invoice.status,
                "method": None,
                "reference": invoice.invoice_number,
                "gst_type": invoice.gst_type,
                "sub_total": invoice.sub_total,
                "cgst_amount": invoice.cgst_amount,
                "igst_amount": invoice.igst_amount,
                "adjustment_amount": invoice.adjustment_amount,
                "paid_amount": invoice.paid_amount,
                "notes": invoice.notes,
            }
        )

    # Add payments to transactions
    for payment in payments:
        transactions.append(
            {
                "date": payment.payment_date,
                "type": "payment",
                "object": payment,
                "amount": payment.amount,
                "description": f"Payment #{payment.id}",
                "status": "PAID",
                "method": payment.method,
                "reference": payment.transaction_id,
                "gst_type": None,
                "sub_total": None,
                "cgst_amount": None,
                "igst_amount": None,
                "adjustment_amount": None,
                "paid_amount": None,
                "notes": None,
                "unallocated_amount": payment.unallocated_amount,
            }
        )

    # Sort all transactions by date (oldest first)
    transactions.sort(key=lambda x: x["date"])

    # Calculate running balance
    running_balance = 0
    for transaction in transactions:
        if transaction["type"] == "invoice":
            running_balance += transaction["amount"]
        else:  # payment
            running_balance -= transaction["amount"]
        transaction["running_balance"] = running_balance

    # Calculate summary statistics
    total_invoiced = sum(t["amount"] for t in transactions if t["type"] == "invoice")
    total_paid = sum(t["amount"] for t in transactions if t["type"] == "payment")
    outstanding_balance = total_invoiced - total_paid

    # Get date range for filtering
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if start_date:
        try:
            from datetime import datetime

            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            transactions = [t for t in transactions if t["date"] >= start_date]
        except ValueError:
            start_date = None

    if end_date:
        try:
            from datetime import datetime

            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            transactions = [t for t in transactions if t["date"] <= end_date]
        except ValueError:
            end_date = None

    context = {
        "supplier": supplier,
        "transactions": transactions,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "outstanding_balance": outstanding_balance,
        "start_date": start_date,
        "end_date": end_date,
        "transaction_count": len(transactions),
        "view_type": view_type,
    }

    return render(request, "supplier/report.html", context)


@login_required
def auto_reallocate(request, pk):
    """
    Auto reallocate payments using FIFO method.
    This function deletes all existing allocations and reapplies them
    in chronological order (oldest invoices first).
    """
    supplier = get_object_or_404(Supplier, id=pk)

    # Get all invoices and payments for this supplier
    invoices = supplier.invoices.filter(is_deleted=False).order_by("invoice_date")
    payments = supplier.payments_made.filter(is_deleted=False).order_by("payment_date")

    # Delete all existing allocations for this supplier
    SupplierPaymentAllocation.objects.filter(
        payment__supplier=supplier, payment__is_deleted=False
    ).delete()

    # Reset all invoice paid amounts and status
    for invoice in invoices:
        invoice.paid_amount = 0
        invoice.status = "UNPAID"
        invoice.save()

    # Reset all payment unallocated amounts
    for payment in payments:
        payment.unallocated_amount = payment.amount
        payment.save()

    # Implement FIFO allocation
    for payment in payments:
        remaining_payment_amount = payment.unallocated_amount

        # Get unpaid invoices in chronological order (FIFO)
        unpaid_invoices = invoices.filter(
            status__in=["UNPAID", "PARTIALLY_PAID"]
        ).order_by("invoice_date")

        for invoice in unpaid_invoices:
            if remaining_payment_amount <= 0:
                break

            # Calculate how much is still owed on this invoice
            amount_owed = invoice.total_amount - invoice.paid_amount

            if amount_owed > 0:
                # Calculate allocation amount (either full remaining payment or full invoice amount)
                allocation_amount = min(remaining_payment_amount, amount_owed)

                # Create allocation
                allocation = SupplierPaymentAllocation.objects.create(
                    payment=payment,
                    invoice=invoice,
                    amount_allocated=allocation_amount,
                    created_by=request.user,
                )

                # Update invoice paid amount and status
                invoice.paid_amount += allocation_amount
                if invoice.paid_amount >= invoice.total_amount:
                    invoice.status = "PAID"
                elif invoice.paid_amount > 0:
                    invoice.status = "PARTIALLY_PAID"
                invoice.save()

                # Update payment unallocated amount
                remaining_payment_amount -= allocation_amount
                payment.unallocated_amount = remaining_payment_amount
                payment.save()

    messages.success(
        request,
        f"Successfully reallocated payments for {supplier.name} using FIFO method.",
    )
    return redirect("supplier:detail", pk=pk)
