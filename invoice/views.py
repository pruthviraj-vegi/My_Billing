from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Sum, Count, F, DecimalField, OuterRef, Subquery
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, Coalesce
from django.contrib import messages
from django.views import View
from cart.models import Cart
from .form import InvoiceForm
from .models import Invoice, InvoiceItem, ReturnInvoice, ReturnInvoiceItem
from django.utils import timezone
from django.db import transaction
from inventory.services import InventoryService
from datetime import timedelta
from customer.forms import CustomerForm
from decimal import Decimal
from base.getDates import getDates
from base.utility import (
    get_periodic_data,
    get_period_label,
    render_paginated_response,
    table_sorting,
)
from customer.signals import reallocate_customer_payments

import logging


logger = logging.getLogger(__name__)


def invoice_dashboard(request):
    """Invoice dashboard with date filtering and metrics"""

    return render(request, "invoice/dashboard.html")


def invoice_dashboard_fetch(request):
    """
    AJAX endpoint to fetch dashboard data

    Optimizations:
    - Reduced database queries using aggregations
    - Used Coalesce for cleaner null handling
    - Consolidated related queries
    - Improved readability with better variable names
    """

    # Get date filter and range
    date_filter = request.GET.get("date_filter", "this_month")
    start_date, end_date = getDates(request)

    # Base queryset with date filtering
    invoices = Invoice.objects.filter(invoice_date__date__range=[start_date, end_date])

    # Get all metrics in a single query using aggregation
    invoice_metrics = invoices.aggregate(
        total_invoices=Count("id"),
        total_amount=Coalesce(Sum("amount"), Decimal("0")),
        total_discount=Coalesce(Sum("discount_amount"), Decimal("0")),
        total_paid=Coalesce(Sum("paid_amount"), Decimal("0")),
        cancelled_amount=Coalesce(
            Sum("amount", filter=Q(is_cancelled=True)), Decimal("0")
        ),
    )

    # Get return invoice metrics
    return_metrics = ReturnInvoice.objects.filter(
        return_date__date__range=[start_date, end_date],
        invoice__is_cancelled=False,
    ).aggregate(total_return_amount=Coalesce(Sum("refund_amount"), Decimal("0")))

    # Calculate profit from invoice items in a single query
    # Note: We need to account for returned items when calculating profit
    # actual_quantity = quantity - returned_quantity
    from .models import ReturnInvoiceItem

    returned_subquery = (
        ReturnInvoiceItem.objects.filter(
            original_invoice_item=OuterRef("pk"), quantity_returned__gt=0
        )
        .values("original_invoice_item")
        .annotate(total_returned=Sum("quantity_returned"))
        .values("total_returned")
    )

    profit_data = (
        InvoiceItem.objects.filter(
            invoice__invoice_date__date__range=[start_date, end_date],
            invoice__is_cancelled=False,
            unit_price__isnull=False,
            purchase_price__isnull=False,
        )
        .annotate(
            returned_quantity=Coalesce(
                Subquery(returned_subquery),
                Decimal("0"),
            ),
            actual_qty=F("quantity") - F("returned_quantity"),
        )
        .aggregate(
            total_profit=Coalesce(
                Sum(
                    (F("unit_price") - F("purchase_price")) * F("actual_qty"),
                    output_field=DecimalField(),
                ),
                Decimal("0"),
            )
        )
    )

    # Extract metrics
    total_amount = invoice_metrics["total_amount"]
    total_discount = invoice_metrics["total_discount"]
    total_paid = invoice_metrics["total_paid"]
    total_cancelled_amount = invoice_metrics["cancelled_amount"]
    total_return_amount = return_metrics["total_return_amount"]
    total_profit = profit_data["total_profit"] - total_discount

    # Calculate derived metrics
    net_amount = (
        total_amount - total_discount - total_return_amount - total_cancelled_amount
    )
    outstanding_amount = net_amount - total_paid

    # Calculate margin percentage (Profit / Net Revenue * 100)
    margin_percentage = (
        round((total_profit / net_amount) * 100, 2) if net_amount > 0 else Decimal("0")
    )

    # Get comparison data for line chart
    comparison_data = get_comparison_data(date_filter, start_date, end_date)

    # Payment status breakdown with annotations
    payment_status_breakdown = list(
        invoices.values("payment_status")
        .annotate(count=Count("id"), amount=Coalesce(Sum("amount"), Decimal("0")))
        .order_by("payment_status")
    )

    # Payment type breakdown with annotations
    payment_type_breakdown = list(
        invoices.values("payment_type")
        .annotate(count=Count("id"), amount=Coalesce(Sum("amount"), Decimal("0")))
        .order_by("payment_type")
    )

    # Category breakdown from invoice items
    category_breakdown = list(
        InvoiceItem.objects.filter(
            invoice__invoice_date__date__range=[start_date, end_date],
            invoice__is_cancelled=False,
        )
        .select_related("product_variant__product__category")
        .values("product_variant__product__category__name")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum(F("unit_price") * F("quantity"), output_field=DecimalField()),
                Decimal("0"),
            ),
        )
        .order_by("-count")
    )

    # Build stats dictionary
    stats = {
        "total_invoices": invoice_metrics["total_invoices"],
        "total_amount": float(total_amount),
        "total_discount": float(total_discount),
        "total_paid": float(total_paid),
        "net_amount": float(net_amount),
        "outstanding_amount": float(outstanding_amount),
        "total_profit": float(total_profit),
        "margin_percentage": float(margin_percentage),
        "total_return_amount": float(total_return_amount + total_cancelled_amount),
    }

    # Process payment status breakdown
    payment_status_data = _process_breakdown_data(
        payment_status_breakdown, total_amount, "payment_status"
    )

    # Process payment type breakdown
    payment_type_data = _process_breakdown_data(
        payment_type_breakdown, total_amount, "payment_type"
    )

    # Process category breakdown
    category_total = sum(float(cat["amount"]) for cat in category_breakdown)
    category_data = _process_category_data(category_breakdown, category_total)

    # Return response
    return JsonResponse(
        {
            "success": True,
            "stats": stats,
            "payment_status_breakdown": payment_status_data,
            "payment_type_breakdown": payment_type_data,
            "category_breakdown": category_data,
            "comparison_data": comparison_data,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "filter": date_filter,
            },
        }
    )


def _process_breakdown_data(breakdown_list, total_amount, field_name):
    """
    Helper function to process payment status/type breakdown data

    Args:
        breakdown_list: List of breakdown dictionaries
        total_amount: Total amount for percentage calculation
        field_name: Name of the field (payment_status or payment_type)

    Returns:
        List of processed breakdown data with percentages
    """
    processed_data = []
    total_amount_float = float(total_amount)

    for item in breakdown_list:
        amount = float(item["amount"])
        percentage = (
            (amount / total_amount_float * 100) if total_amount_float > 0 else 0
        )

        processed_data.append(
            {
                field_name: item[field_name].title(),
                "count": item["count"],
                "amount": amount,
                "percentage": round(percentage, 1),
            }
        )

    return processed_data


def _process_category_data(category_breakdown, category_total):
    """
    Helper function to process category breakdown data

    Args:
        category_breakdown: List of category dictionaries
        category_total: Total amount for percentage calculation

    Returns:
        List of processed category data with percentages
    """
    category_data = []

    for category in category_breakdown:
        category_name = (
            category["product_variant__product__category__name"] or "Uncategorized"
        )
        category_amount = float(category["amount"])
        percentage = (
            (category_amount / category_total * 100) if category_total > 0 else 0
        )

        category_data.append(
            {
                "category_name": category_name,
                "count": category["count"],
                "amount": category_amount,
                "percentage": round(percentage, 1),
            }
        )

    return category_data


def get_comparison_data(date_filter, current_start, current_end):
    """Generate comparison data for line chart based on date filter"""

    # Calculate previous period dates
    previous_start, previous_end, period_type = get_periodic_data(
        date_filter, current_start, current_end
    )

    # Get current period data
    current_invoices = Invoice.objects.filter(
        invoice_date__date__range=[current_start, current_end]
    )
    current_data = get_period_data(
        current_invoices, current_start, current_end, period_type
    )

    # Get previous period data
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
            "start_date": current_start.isoformat(),
            "end_date": current_end.isoformat(),
        },
        "previous_period": {
            "label": get_period_label(previous_start, previous_end, period_type),
            "data": previous_data,
            "start_date": previous_start.isoformat(),
            "end_date": previous_end.isoformat(),
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
            total_amount=Coalesce(Sum("amount"), Decimal("0")),
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
                amount=Coalesce(Sum("amount"), Decimal("0")), invoices=Count("id")
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
                amount=Coalesce(Sum("amount"), Decimal("0")), invoices=Count("id")
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
                amount=Coalesce(Sum("amount"), Decimal("0")), invoices=Count("id")
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


# ALTERNATIVE: If you need to fill in missing dates with zeros
def get_period_data_with_zeros(invoices, start_date, end_date, period_type):
    """
    Same as get_period_data but fills in missing dates with zero values

    Use this version if you need a data point for every period even when
    there are no invoices (e.g., for continuous chart lines)
    """

    if period_type == "daily":
        # Single day - same as original
        aggregated = invoices.aggregate(
            total_amount=Coalesce(Sum("amount"), Decimal("0")),
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
        # Get daily data from database
        daily_data = (
            invoices.annotate(day=TruncDate("invoice_date"))
            .values("day")
            .annotate(
                amount=Coalesce(Sum("amount"), Decimal("0")), invoices=Count("id")
            )
        )

        # Create lookup dictionary
        data_dict = {
            item["day"]: {"amount": float(item["amount"]), "invoices": item["invoices"]}
            for item in daily_data
        }

        # Fill in all dates
        result = []
        current_date = start_date
        while current_date <= end_date:
            if current_date in data_dict:
                result.append(
                    {
                        "date": current_date.strftime("%Y-%m-%d"),
                        **data_dict[current_date],
                    }
                )
            else:
                result.append(
                    {
                        "date": current_date.strftime("%Y-%m-%d"),
                        "amount": 0.0,
                        "invoices": 0,
                    }
                )
            current_date += timedelta(days=1)

        return result

    elif period_type == "quarterly":
        # Get weekly data from database
        weekly_data = (
            invoices.annotate(week=TruncWeek("invoice_date"))
            .values("week")
            .annotate(
                amount=Coalesce(Sum("amount"), Decimal("0")), invoices=Count("id")
            )
        )

        # Create lookup dictionary
        data_dict = {
            item["week"]: {
                "amount": float(item["amount"]),
                "invoices": item["invoices"],
            }
            for item in weekly_data
        }

        # Fill in all weeks
        result = []
        current_date = start_date
        # Adjust to start of week (Monday)
        current_date = current_date - timedelta(days=current_date.weekday())

        while current_date <= end_date:
            if current_date in data_dict:
                result.append(
                    {
                        "date": current_date.strftime("%Y-%m-%d"),
                        **data_dict[current_date],
                    }
                )
            else:
                result.append(
                    {
                        "date": current_date.strftime("%Y-%m-%d"),
                        "amount": 0.0,
                        "invoices": 0,
                    }
                )
            current_date += timedelta(weeks=1)

        return result

    else:  # yearly
        # Get monthly data from database
        monthly_data = (
            invoices.annotate(month=TruncMonth("invoice_date"))
            .values("month")
            .annotate(
                amount=Coalesce(Sum("amount"), Decimal("0")), invoices=Count("id")
            )
        )

        # Create lookup dictionary
        data_dict = {
            item["month"]: {
                "amount": float(item["amount"]),
                "invoices": item["invoices"],
            }
            for item in monthly_data
        }

        # Fill in all months
        result = []
        current_date = start_date.replace(day=1)

        while current_date <= end_date:
            if current_date in data_dict:
                result.append(
                    {
                        "date": current_date.strftime("%Y-%m-%d"),
                        **data_dict[current_date],
                    }
                )
            else:
                result.append(
                    {
                        "date": current_date.strftime("%Y-%m-%d"),
                        "amount": 0.0,
                        "invoices": 0,
                    }
                )

            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

        return result


# Create your views here.

VALID_SORT_FIELDS = {
    "id",
    "invoice_number",
    "customer__name",
    "amount",
    "payment_status",
    "payment_type",
    "invoice_date",
    "due_date",
    "created_at",
    "created_by__first_name",
}


def invoiceHome(request):
    """Invoice management main page - initial load only."""
    # For initial page load, just render the template with empty data

    financial_years = (
        Invoice.objects.values_list("financial_year", flat=True)
        .distinct()
        .filter(financial_year__isnull=False)
        .order_by("-financial_year")
    )
    context = {
        "payment_type_choices": Invoice.PaymentType.choices,
        "bill_types": Invoice.Invoice_type.choices,
        "financial_years": financial_years,
    }
    return render(request, "invoice/home.html", context)


def get_data(request):
    # Get search and filter parameters
    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")
    payment_type_filter = request.GET.get("payment_type", "")
    sort_by = request.GET.get("sort", "-id")
    bill_types_filter = request.GET.get("bill_types", "")

    # Apply search filter
    filters = Q()
    if search_query:
        filters &= (
            Q(invoice_number__icontains=search_query)
            | Q(customer__name__icontains=search_query)
            | Q(customer__phone_number__icontains=search_query)
            | Q(notes__icontains=search_query)
        )

    # Apply status filter
    if status_filter:
        filters &= Q(payment_status=status_filter)

    # Apply payment type filter
    if payment_type_filter:
        filters &= Q(payment_type=payment_type_filter)

    # Apply bill types filter
    if bill_types_filter:
        filters &= Q(invoice_type=bill_types_filter)

    invoices = Invoice.objects.select_related("customer").filter(filters)

    # ---------------- SORTING MAP ----------------
    SORT_MAP = {
        "gst_bills": ("invoice_type", Invoice.Invoice_type.GST),
        "cash_bills": ("invoice_type", Invoice.Invoice_type.CASH),
    }

    # Special type sorting
    if sort_by in SORT_MAP:
        field, value = SORT_MAP[sort_by]
        invoices = invoices.filter(**{field: value}).order_by("-invoice_date")

    # Validate sort field
    final_order_by = table_sorting(request, VALID_SORT_FIELDS, "-invoice_date")
    invoices = invoices.order_by(*final_order_by)

    return invoices


def fetch_invoices(request):
    """AJAX endpoint to fetch invoices with search, filter, and pagination."""
    invoices = get_data(request)

    return render_paginated_response(
        request,
        invoices,
        "invoice/fetch.html",
    )


class CreateInvoice(View):
    template_name = "invoice/form.html"
    form_class = InvoiceForm

    def get(self, request, pk):
        cart = get_object_or_404(Cart, id=pk)
        if int(cart.total_amount) <= 0:
            messages.error(request, "Cart is empty")
            return redirect("cart:getCartData", pk=cart.id)
        form = self.form_class(
            initial={
                "payment_type": Invoice.PaymentType.CASH,
                "amount": cart.total_amount,
                "due_date": timezone.now() + timedelta(days=30),
            }
        )
        context = {
            "cart": cart,
            "form": form,
            "title": "Create Invoice",
            "customer_form": CustomerForm(),
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        cart = get_object_or_404(Cart, id=pk)
        if int(cart.total_amount) <= 0:
            messages.error(request, "Cart is empty")
            return redirect("cart:getCartData", pk=cart.id)
        form = self.form_class(request.POST)
        if form.is_valid():
            with transaction.atomic():
                invoice = form.save(commit=False)
                invoice.cart_no = cart.id
                invoice.amount = cart.total_amount
                invoice.modified_by = request.user
                invoice.created_by = request.user
                invoice.save()

                for item in cart.cart_items.all():
                    invoice_item = InvoiceItem.objects.create(
                        invoice=invoice,
                        product_variant=item.product_variant,
                        quantity=item.quantity,
                        unit_price=item.price,
                        purchase_price=item.product_variant.purchase_price,
                        mrp=item.product_variant.mrp,
                        commission_percentage=item.product_variant.commission_percentage,
                    )
                    InventoryService.sale(
                        variant=item.product_variant,
                        quantity_sold=item.quantity,
                        user=request.user,
                        notes=f"Invoice {invoice.invoice_number} - {item.product_variant.product.name}",
                        invoice_item=invoice_item,
                    )

                cart.delete()
                messages.success(request, "Invoice created successfully")
                return render(
                    request, "intermediate_page.html", {"invoice_no": invoice.id}
                )

        else:
            context = {"cart": cart, "form": form, "title": "Create Invoice"}
            logger.error(f"Form invalid: {form.errors}")
            return render(request, self.template_name, context)


class InvoiceDetail(View):
    template_name = "invoice/detail.html"

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, id=pk)

        # Get return invoices for this invoice
        return_invoices = (
            invoice.return_invoices.select_related(
                "created_by", "approved_by", "processed_by"
            )
            .prefetch_related("return_invoice_items")
            .order_by("-created_at")
        )

        # Calculate return summary
        total_return_amount = sum(ret.refund_amount for ret in return_invoices)
        total_return_items = sum(
            len(
                [
                    item
                    for item in ret.return_invoice_items.all()
                    if item.quantity_returned > 0
                ]
            )
            for ret in return_invoices
        )

        # Add return item counts to each return invoice for template use
        return_invoices = (
            invoice.return_invoices.select_related(
                "created_by", "approved_by", "processed_by"
            )
            .prefetch_related("return_invoice_items")
            .annotate(
                returned_items_count=Count(
                    "return_invoice_items",
                    filter=Q(return_invoice_items__quantity_returned__gt=0),
                )
            )
            .order_by("-created_at")
        )

        # Get return items with details
        return_items_with_details = []
        for return_invoice in return_invoices:
            items = return_invoice.return_invoice_items.filter(
                quantity_returned__gt=0
            ).select_related("product_variant__product", "original_invoice_item")
            return_items_with_details.extend(items)

        # Calculate adjusted invoice total (original amount minus returns)
        adjusted_invoice_total = invoice.total_payable - total_return_amount

        context = {
            "invoice": invoice,
            "title": f"Invoice {invoice.invoice_number}",
            "return_invoices": return_invoices,
            "total_return_amount": total_return_amount,
            "total_return_items": total_return_items,
            "return_items_with_details": return_items_with_details,
            "adjusted_invoice_total": adjusted_invoice_total,
        }
        return render(request, self.template_name, context)


class InvoiceEdit(View):
    template_name = "invoice/form.html"
    form_class = InvoiceForm

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, id=pk)
        form = self.form_class(instance=invoice)
        context = {
            "invoice": invoice,
            "form": form,
            "title": f"Edit Invoice {invoice.invoice_number}",
            "customer_form": CustomerForm(),
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, id=pk)
        form = self.form_class(request.POST, instance=invoice)

        new_payment_type = request.POST.get("payment_type")
        old_payment_type = invoice.payment_type

        if form.is_valid():
            # Handle payment type changes and set paid_amount accordingly
            invoice_instance = form.save(commit=False)

            if (
                new_payment_type == Invoice.PaymentType.CREDIT
                and old_payment_type == Invoice.PaymentType.CASH
            ):
                # When changing from CASH to CREDIT: reset paid_amount to 0
                # For CASH invoices, paid_amount = amount - discount_amount
                # For CREDIT invoices, paid_amount should start at 0
                invoice_instance.paid_amount = Decimal("0")

            # Model's save() will handle CASH invoices automatically
            # (setting paid_amount = amount - discount_amount and advance_amount = 0)
            invoice_instance.save()

            messages.success(request, "Invoice updated successfully")
            return redirect("invoice:detail", pk=invoice.id)

        logger.error(f"Form invalid: {form.errors}")

        context = {
            "invoice": invoice,
            "form": form,
            "title": f"Edit Invoice {invoice.invoice_number}",
        }
        return render(request, self.template_name, context)


class InvoiceDelete(View):
    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, id=pk)
        invoice.delete()
        messages.success(request, "Invoice deleted successfully")
        return redirect("invoice:home")


def search_invoices_home(request):
    return render(request, "search_invoice/home.html")


def fetch_search_invoices(request):
    search_query = request.GET.get("search", "")
    invoice_items = (
        InvoiceItem.objects.filter(product_variant__barcode__iexact=search_query)
        .select_related("product_variant__product", "invoice")
        .order_by("-id")
    )
    return render_paginated_response(
        request, invoice_items, "search_invoice/fetch.html"
    )
