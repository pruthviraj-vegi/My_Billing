"""Views for authentication, home page, dashboard stats, and error handling."""

import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Abs, Coalesce, TruncDate, TruncMonth, TruncWeek
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView

from base.getDates import getDates
from base.utility import get_period_label, get_periodic_data

from customer.models import Customer, CustomerCreditSummary, Payment
from inventory.models import InventoryLog, ProductVariant
from invoice.models import Invoice
from invoice.choices import PaymentTypeChoices
from supplier.models import SupplierInvoice, SupplierPayment

from .forms import CustomLoginForm

logger = logging.getLogger(__name__)


class CustomLoginView(LoginView):
    """Handle user login with remember-me and safe redirect support."""

    form_class = CustomLoginForm
    template_name = "base/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        """
        Redirect to the exact page after login.
        Priority:
        1. 'next' parameter from POST request (form submission)
        2. 'next' URL parameter from GET request
        3. 'next' stored in session (by middleware)
        4. Default to home page
        """
        redirect_url = self.request.POST.get("next") or self.request.GET.get("next")

        # If not in GET/POST, check session (stored by middleware)
        if not redirect_url:
            redirect_url = self.request.session.get("next")
            # Clean up session after retrieving
            if redirect_url:
                del self.request.session["next"]

        # Validate the redirect URL for security
        if redirect_url:
            # Check if URL is safe (same host, allowed scheme)
            if url_has_allowed_host_and_scheme(redirect_url, allowed_hosts=None):
                return redirect_url

        # Default to home page
        return reverse_lazy("base:home")

    def form_valid(self, form):
        remember = form.cleaned_data.get("remember")
        if not remember:
            # Set session to expire when browser closes
            self.request.session.set_expiry(0)

        # Call parent form_valid to handle login
        response = super().form_valid(form)

        # Add success message
        messages.success(self.request, f"Welcome back, {self.request.user.full_name}!")

        return response

    def form_invalid(self, form):
        # Add error message for invalid login
        messages.error(
            self.request, "Invalid phone number or password. Please try again."
        )

        return super().form_invalid(form)


class HomeView(TemplateView):
    """Dashboard home page, accessible to all authenticated roles."""

    template_name = "base/home.html"
    login_url = "base:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer_receivable = CustomerCreditSummary.objects.aggregate(
            total=Coalesce(
                Sum("balance_amount", filter=Q(balance_amount__gt=0)), Decimal("0")
            )
        )["total"]

        # Total active customers
        total_customers = (
            Customer.objects.filter(is_deleted=False).exclude(phone_number="3").count()
        )

        # Supplier balance (all-time outstanding)
        supplier_invoiced = SupplierInvoice.objects.filter(is_deleted=False).aggregate(
            total=Coalesce(Sum("total_amount"), Decimal("0"))
        )["total"]

        supplier_paid = SupplierPayment.objects.filter(is_deleted=False).aggregate(
            total=Coalesce(Sum("amount"), Decimal("0"))
        )["total"]

        supplier_balance = supplier_invoiced - supplier_paid

        # Total active products (variants)
        total_products = ProductVariant.objects.filter(
            is_deleted=False, status=ProductVariant.VariantStatus.ACTIVE
        ).count()

        context["user"] = self.request.user
        context["customer_receivable"] = customer_receivable
        context["total_customers"] = total_customers
        context["supplier_balance"] = supplier_balance
        context["total_products"] = total_products

        return context


def custom_404_view(request, _exception):
    """
    Custom 404 error handler.
    Django error handlers must be function-based views that accept:
    - handler404: (request, exception)
    - handler500: (request)
    - handler403: (request, exception)
    - handler400: (request, exception)
    """
    return render(request, "404.html", status=404)


def logout_view(request):
    """Log the user out and redirect to the login page."""
    logout(request)
    return redirect("base:login")


@login_required
def dashboard_stats(request):
    """Return date-dependent dashboard statistics for the main dashboard.

    AJAX endpoint that returns invoice stats, combined payment method breakdown,
    and comparison data for the revenue chart based on the selected date filter.
    """
    date_filter = request.GET.get("date_filter", "this_month")
    start_date, end_date = getDates(request)

    # Invoice stats for the period (cash invoices only)
    invoices = Invoice.objects.filter(
        invoice_date__date__range=[start_date, end_date],
        is_cancelled=False,
        payment_type=PaymentTypeChoices.CASH,
    )

    invoice_stats = invoices.aggregate(
        total_invoices=Count("id"),
        total_amount=Coalesce(
            Sum(F("amount") - F("discount_amount")),
            Decimal("0"),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        ),
    )

    # Invoice payment method breakdown
    invoice_method_breakdown = list(
        invoices.values("payment_method")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum(F("amount") - F("discount_amount")),
                Decimal("0"),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
        )
        .order_by("payment_method")
    )

    # Received payments (from Payment model - credit payments received)
    received_payments = Payment.objects.filter(
        payment_type=Payment.PaymentType.Paid,
        payment_date__date__range=[start_date, end_date],
    )

    total_received_payments = received_payments.aggregate(
        total=Coalesce(
            Sum("amount"),
            Decimal("0"),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
    )["total"]

    received_method_breakdown = list(
        received_payments.values("method")
        .annotate(
            count=Count("id"),
            amount=Coalesce(
                Sum("amount"),
                Decimal("0"),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
        )
        .order_by("method")
    )

    # Merge both sources into a single breakdown by method
    combined = {}
    for item in invoice_method_breakdown:
        method = item["payment_method"].title().replace("_", " ")
        combined[method] = {
            "count": item["count"],
            "amount": float(item["amount"]),
        }

    for item in received_method_breakdown:
        method = item["method"].title().replace("_", " ")
        if method in combined:
            combined[method]["count"] += item["count"]
            combined[method]["amount"] += float(item["amount"])
        else:
            combined[method] = {
                "count": item["count"],
                "amount": float(item["amount"]),
            }

    # Calculate total received (invoices + payments)
    total_received = float(invoice_stats["total_amount"]) + float(
        total_received_payments
    )

    # Build final breakdown list with percentages
    combined_breakdown = [
        {
            "payment_method": method,
            "count": data["count"],
            "amount": data["amount"],
            "percentage": (
                round(data["amount"] / total_received * 100, 1)
                if total_received > 0
                else 0
            ),
        }
        for method, data in sorted(combined.items())
    ]

    # Comparison data for stock in vs stock out chart
    comparison_data = get_inventory_comparison_data(date_filter, start_date, end_date)

    return JsonResponse(
        {
            "success": True,
            "stats": {
                "total_invoices": invoice_stats["total_invoices"],
                "total_received": total_received,
            },
            "payment_method_breakdown": combined_breakdown,
            "comparison_data": comparison_data,
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "filter": date_filter,
            },
        }
    )


def get_inventory_comparison_data(date_filter, current_start, current_end):
    """Generate stock in vs stock out comparison data for the line chart.

    Returns current and previous period data in the same format as
    ``customer.views.get_comparison_data`` so the frontend can reuse
    ``ModernCharts.updateRevenueChart``.
    """
    previous_start, previous_end, period_type = get_periodic_data(
        date_filter, current_start, current_end
    )

    current_logs = InventoryLog.objects.filter(
        variant__is_deleted=False,
        timestamp__date__range=[current_start, current_end],
    )
    current_data = _get_inventory_period_data(
        current_logs, current_start, current_end, period_type
    )

    previous_logs = InventoryLog.objects.filter(
        variant__is_deleted=False,
        timestamp__date__range=[previous_start, previous_end],
    )
    previous_data = _get_inventory_period_data(
        previous_logs, previous_start, previous_end, period_type
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


def _get_inventory_period_data(logs_qs, start_date, _end_date, period_type):
    """Aggregate stock-in and stock-out values by time bucket.

    Each data point contains both ``amount`` (stock in value) and
    ``stock_out`` (stock out value) so the frontend can plot two lines.
    """
    amount_field = DecimalField(max_digits=16, decimal_places=2)

    stock_in_sum = Coalesce(
        Sum(
            Abs(F("quantity_change")) * F("purchase_price"),
            filter=Q(transaction_type__in=["STOCK_IN", "INITIAL"]),
            output_field=amount_field,
        ),
        Decimal("0"),
    )
    stock_out_sum = Coalesce(
        Sum(
            Abs(F("quantity_change")) * F("purchase_price"),
            filter=Q(transaction_type="SALE"),
            output_field=amount_field,
        ),
        Decimal("0"),
    )

    if period_type == "daily":
        agg = logs_qs.aggregate(stock_in=stock_in_sum, stock_out=stock_out_sum)
        return [
            {
                "date": start_date.strftime("%Y-%m-%d"),
                "amount": float(agg["stock_in"]),
                "stock_out": float(agg["stock_out"]),
            }
        ]

    # Choose the truncation function
    trunc_map = {
        "monthly": ("day", TruncDate("timestamp")),
        "quarterly": ("week", TruncWeek("timestamp")),
        "yearly": ("month", TruncMonth("timestamp")),
    }
    bucket_name, trunc_fn = trunc_map.get(period_type, ("day", TruncDate("timestamp")))

    rows = (
        logs_qs.annotate(bucket=trunc_fn)
        .values("bucket")
        .annotate(stock_in=stock_in_sum, stock_out=stock_out_sum)
        .order_by("bucket")
    )

    return [
        {
            "date": row["bucket"].strftime("%Y-%m-%d"),
            "amount": float(row["stock_in"]),
            "stock_out": float(row["stock_out"]),
        }
        for row in rows
    ]
