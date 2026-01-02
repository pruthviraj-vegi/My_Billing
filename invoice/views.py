from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Sum, Count, F
from django.contrib import messages
from django.views import View
from cart.models import Cart
from .form import InvoiceForm
from .models import Invoice, InvoiceItem, ReturnInvoice, ReturnInvoiceItem
from django.utils import timezone
from django.db import transaction
from inventory.services import InventoryService
from datetime import timedelta
import logging
from customer.forms import CustomerForm
from decimal import Decimal
from base.getDates import getDates
from base.utility import get_periodic_data, get_period_label, render_paginated_response

logger = logging.getLogger(__name__)


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
    """Get aggregated data for a specific period"""
    if period_type == "daily":
        # For daily, return single data point
        total_amount = invoices.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_invoices = invoices.count()
        return [
            {
                "date": start_date.strftime("%Y-%m-%d"),
                "amount": float(total_amount),
                "invoices": total_invoices,
            }
        ]

    elif period_type == "monthly":
        # Group by day
        daily_data = []
        current_date = start_date
        while current_date <= end_date:
            day_invoices = invoices.filter(invoice_date__date=current_date)
            day_amount = day_invoices.aggregate(total=Sum("amount"))[
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
        # Group by week
        weekly_data = []
        current_date = start_date
        week_start = current_date

        while current_date <= end_date:
            if (
                current_date.weekday() == 6 or current_date == end_date
            ):  # Sunday or end of period
                week_invoices = invoices.filter(
                    invoice_date__date__range=[week_start, current_date]
                )
                week_amount = week_invoices.aggregate(total=Sum("amount"))[
                    "total"
                ] or Decimal("0")
                week_count = week_invoices.count()

                weekly_data.append(
                    {
                        "date": week_start.strftime("%Y-%m-%d"),
                        "amount": float(week_amount),
                        "invoices": week_count,
                    }
                )
                week_start = current_date + timedelta(days=1)

            current_date += timedelta(days=1)

        return weekly_data

    else:  # yearly
        # Group by month
        monthly_data = []
        current_date = start_date

        while current_date <= end_date:
            # Get last day of current month
            if current_date.month == 12:
                next_month = current_date.replace(
                    year=current_date.year + 1, month=1, day=1
                )
            else:
                next_month = current_date.replace(month=current_date.month + 1, day=1)

            month_end = next_month - timedelta(days=1)
            if month_end > end_date:
                month_end = end_date

            month_invoices = invoices.filter(
                invoice_date__date__range=[current_date, month_end]
            )
            month_amount = month_invoices.aggregate(total=Sum("amount"))[
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

            current_date = next_month

        return monthly_data


# Create your views here.

VALID_SORT_FIELDS = {
    "id",
    "-id",
    "invoice_number",
    "-invoice_number",
    "customer__name",
    "-customer__name",
    "amount",
    "-amount",
    "payment_status",
    "-payment_status",
    "payment_type",
    "-payment_type",
    "invoice_date",
    "-invoice_date",
    "due_date",
    "-due_date",
    "created_at",
    "-created_at",
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

    invoices = Invoice.objects.select_related("customer", "sold_by").filter(filters)

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
    elif sort_by in VALID_SORT_FIELDS:
        invoices = invoices.order_by(sort_by)

    else:
        invoices = invoices.order_by("-invoice_date")

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
        for ret in return_invoices:
            ret.returned_items_count = len(
                [
                    item
                    for item in ret.return_invoice_items.all()
                    if item.quantity_returned > 0
                ]
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


def invoice_dashboard(request):
    """Invoice dashboard with date filtering and metrics"""

    return render(request, "invoice/dashboard.html")


def invoice_dashboard_fetch(request):
    """AJAX endpoint to fetch dashboard data"""

    # Get date filter from request
    date_filter = request.GET.get("date_filter", "this_month")

    start_date, end_date = getDates(request)

    # Filter invoices by date range
    invoices = Invoice.objects.filter(
        invoice_date__date__range=[start_date, end_date]
    ).select_related("customer")

    return_invoices = ReturnInvoice.objects.filter(
        return_date__date__range=[start_date, end_date]
    ).select_related("invoice", "customer")

    # Calculate metrics
    total_invoices = invoices.count()
    total_amount = invoices.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_return_amount = return_invoices.aggregate(total=Sum("refund_amount"))[
        "total"
    ] or Decimal("0")
    total_amount = total_amount
    total_discount = invoices.aggregate(total=Sum("discount_amount"))[
        "total"
    ] or Decimal("0")
    total_paid = invoices.aggregate(total=Sum("paid_amount"))["total"] or Decimal("0")

    # Calculate profit from invoice items
    invoice_items = InvoiceItem.objects.filter(
        invoice__invoice_date__date__range=[start_date, end_date]
    )

    total_profit = Decimal("0")
    for item in invoice_items:
        profit_per_unit = item.unit_price - item.purchase_price
        total_profit += profit_per_unit * item.actual_quantity

    total_profit = total_profit - total_discount

    # Calculate net amount (amount - discount)
    net_amount = total_amount - total_discount

    # Calculate outstanding amount (net amount - paid amount)
    outstanding_amount = net_amount - total_paid

    # Calculate comparison data for line chart
    comparison_data = get_comparison_data(date_filter, start_date, end_date)

    # Payment status breakdown
    payment_status_breakdown = (
        invoices.values("payment_status")
        .annotate(count=Count("id"), amount=Sum("amount"))
        .order_by("payment_status")
    )

    # Payment type breakdown
    payment_type_breakdown = (
        invoices.values("payment_type")
        .annotate(count=Count("id"), amount=Sum("amount"))
        .order_by("payment_type")
    )

    # Category breakdown from invoice items
    category_breakdown = (
        invoice_items.select_related("product_variant__product__category")
        .values("product_variant__product__category__name")
        .annotate(count=Count("id"), amount=Sum(F("unit_price") * F("quantity")))
        .order_by("-count")
    )

    # Prepare response data
    stats = {
        "total_invoices": total_invoices,
        "total_amount": float(total_amount),
        "total_discount": float(total_discount),
        "total_paid": float(total_paid),
        "net_amount": float(net_amount),
        "outstanding_amount": float(outstanding_amount),
        "total_profit": float(total_profit),
        "total_return_amount": float(total_return_amount),
    }

    # Add percentage calculations for breakdowns
    payment_status_data = []
    for status in payment_status_breakdown:
        percentage = (status["amount"] / total_amount * 100) if total_amount > 0 else 0
        payment_status_data.append(
            {
                "payment_status": status["payment_status"].title(),
                "count": status["count"],
                "amount": float(status["amount"]),
                "percentage": round(percentage, 1),
            }
        )

    payment_type_data = []
    for type_data in payment_type_breakdown:
        percentage = (
            (type_data["amount"] / total_amount * 100) if total_amount > 0 else 0
        )
        payment_type_data.append(
            {
                "payment_type": type_data["payment_type"].title(),
                "count": type_data["count"],
                "amount": float(type_data["amount"]),
                "percentage": round(percentage, 1),
            }
        )

    # Category data processing
    # Calculate total for category percentages
    category_total = float(
        sum(cat["amount"] for cat in category_breakdown if cat["amount"])
    )

    category_data = []
    for category in category_breakdown:
        category_name = (
            category["product_variant__product__category__name"] or "Uncategorized"
        )
        category_amount = float(category["amount"] or 0)
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


def search_invoices_home(request):
    return render(request, "search_invoice/home.html")


def fetch_search_invoices(request):
    search_query = request.GET.get("search", "")
    invoice_items = InvoiceItem.objects.filter(
        product_variant__barcode__iexact=search_query
    ).select_related("product_variant__product", "invoice")
    return render_paginated_response(
        request, invoice_items, "search_invoice/fetch.html"
    )
