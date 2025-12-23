from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
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
from datetime import timedelta
from decimal import Decimal
from base.getDates import getDates
from .models import Supplier, SupplierInvoice, SupplierPayment
from .forms import SupplierForm, SupplierInvoiceForm, SupplierPaymentForm

from base.utility import get_periodic_data, get_period_label, render_paginated_response
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


def dashboard(request):
    """Supplier management dashboard with analytics and insights."""

    # Calculate full balance due (all invoices - all payments, regardless of status)
    # This matches the logic in Supplier.balance_due property
    total_outstanding = get_total_outstanding_balance()

    # Calculate total suppliers (static, doesn't change with date filter)
    total_suppliers = Supplier.objects.filter(is_deleted=False).count()

    context = {
        "total_outstanding": total_outstanding,
        "total_suppliers": total_suppliers,
    }
    return render(request, "supplier/dashboard.html", context)


def get_comparison_data(date_filter, current_start, current_end):
    """Generate comparison data for line chart based on date filter"""
    # Calculate previous period dates
    previous_start, previous_end, period_type = get_periodic_data(
        date_filter, current_start, current_end
    )

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
            (status["amount"] / total_invoiced * 100) if total_invoiced > 0 else 0
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
    # Calculate percentage based on sum of top 10 suppliers only (for pie chart accuracy)
    # This ensures percentages add up to 100% for the displayed suppliers
    supplier_data = []
    # Convert QuerySet to list to avoid multiple evaluations
    supplier_list = list(supplier_breakdown)
    # Calculate total of top 10 suppliers only
    top10_total = sum(float(s["amount"] or 0) for s in supplier_list)

    for supplier in supplier_list:
        supplier_amount = float(supplier["amount"] or 0)
        percentage = (supplier_amount / top10_total * 100) if top10_total > 0 else 0
        supplier_data.append(
            {
                "supplier_name": supplier["supplier__name"] or "Unknown",
                "count": supplier["count"],
                "amount": supplier_amount,
                "percentage": round(percentage, 1),
            }
        )

    # Invoice type data processing
    # Calculate percentage: (type_amount / total_invoiced) * 100
    # This shows what percentage of total invoiced amount belongs to each invoice type
    invoice_type_data = []
    for inv_type in invoice_type_breakdown:
        type_amount = float(inv_type["amount"] or 0)
        percentage = (
            (type_amount / float(total_invoiced) * 100) if total_invoiced > 0 else 0
        )
        invoice_type_data.append(
            {
                "category_name": inv_type["invoice_type"].replace("_", " ").title(),
                "count": inv_type["count"],
                "amount": type_amount,
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


def fetch_suppliers(request):
    """AJAX endpoint to fetch suppliers with search, filter, sorting, and pagination."""

    suppliers = get_suppliers_data(request)

    return render_paginated_response(
        request,
        suppliers,
        "supplier/fetch.html",
        per_page=SUPPLIERS_PER_PAGE,
    )


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

    return render_paginated_response(
        request,
        queryset,
        "supplier/invoice/fetch.html",
        per_page=8,
        supplier=supplier,
    )


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

    return render_paginated_response(
        request,
        queryset,
        "supplier/payment/fetch.html",
        per_page=8,
        supplier=supplier,
    )


def supplier_detail(request, pk):
    """View supplier details with invoices and payments tables."""
    supplier = get_object_or_404(Supplier, id=pk)

    # Get actual invoices from database
    invoices = supplier.invoices.filter(is_deleted=False).order_by("-invoice_date")

    # Calculate invoice summary data
    total_invoice_amount = sum(invoice.total_amount for invoice in invoices)
    unpaid_invoices_count = sum(1 for invoice in invoices if invoice.status != "PAID")

    # Get actual payments from database (replace sample data later)
    payments = supplier.payments_made.filter(is_deleted=False).order_by("-payment_date")

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


class CreateSupplier(CreateView):
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


class EditSupplier(UpdateView):
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


class DeleteSupplier(DeleteView):
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
class CreatePayment(CreateView):
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
        # Let super().form_valid() handle the save - it will trigger the signal correctly
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Payment of ₹{form.instance.amount} recorded successfully!",
        )
        return response

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        self.supplier = get_object_or_404(Supplier, id=kwargs["supplier_pk"])
        return super().dispatch(request, *args, **kwargs)


class EditPayment(UpdateView):
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
        # Save the payment - signals will handle reallocation automatically
        payment = form.save()

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


class CreateInvoice(CreateView):
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


class EditInvoice(UpdateView):
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


def get_opening_balance(supplier, start_date):
    """Get the opening balance for a supplier at a specific date."""
    invoice_filters = Q(is_deleted=False) & Q(invoice_date__date__lt=start_date)
    payment_filters = Q(is_deleted=False) & Q(payment_date__date__lt=start_date)
    invoices = supplier.invoices.filter(invoice_filters).order_by("invoice_date")
    payments = supplier.payments_made.filter(payment_filters).order_by("payment_date")
    total_invoiced = invoices.aggregate(total=Sum("total_amount"))["total"] or 0
    total_paid = payments.aggregate(total=Sum("amount"))["total"] or 0
    return total_invoiced - total_paid


def get_supplier_report_data(supplier, date_range):
    # Fetch only necessary fields

    opening_balance = get_opening_balance(supplier, date_range[0])

    invoices = (
        supplier.invoices.filter(is_deleted=False, invoice_date__date__range=date_range)
        .only("id", "invoice_date", "total_amount", "invoice_number", "status", "notes")
        .order_by("invoice_date")
    )

    payments = (
        supplier.payments_made.filter(
            is_deleted=False, payment_date__date__range=date_range
        )
        .only("id", "payment_date", "amount", "transaction_id")
        .order_by("payment_date")
    )

    # Build transactions list using list comprehension
    transactions = []

    # Add invoices
    transactions.extend(
        [
            {
                "date": invoice.invoice_date,
                "type": "invoice",
                "invoice_id": invoice.id,
                "credit": invoice.total_amount,
                "debit": Decimal("0"),
                "description": invoice.invoice_number,
                "status": invoice.status,
                "reference": invoice.invoice_number,
                "notes": invoice.notes or "",
            }
            for invoice in invoices
        ]
    )

    # Add payments
    transactions.extend(
        [
            {
                "date": payment.payment_date,
                "type": "payment",
                "payment_id": payment.id,
                "credit": Decimal("0"),
                "debit": payment.amount,
                "description": f"Payment #{payment.id}",
                "status": "",
                "reference": payment.transaction_id or "",
                "notes": "",
            }
            for payment in payments
        ]
    )

    # Sort by date (oldest first)
    transactions.sort(key=lambda x: x["date"])

    # Single-pass calculation: running balance and totals
    running_balance = opening_balance
    total_invoiced = Decimal("0")
    total_paid = Decimal("0")

    for transaction in transactions:
        credit = transaction["credit"]
        debit = transaction["debit"]

        running_balance += credit - debit
        transaction["running_balance"] = running_balance

        total_invoiced += credit
        total_paid += debit

    outstanding_balance = total_invoiced - total_paid

    context = {
        "transactions": transactions,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "outstanding_balance": outstanding_balance,
        "opening_balance": opening_balance,
    }

    return context


def supplier_report(request, pk):
    """Generate a comprehensive report showing all purchases and payments for a supplier sorted by date."""
    supplier = get_object_or_404(Supplier, id=pk)

    # Get date filter from request (default value)
    date_filter = request.GET.get("date_filter", "this_month")

    # Only pass supplier details - all transaction data will be loaded via AJAX
    context = {
        "supplier": supplier,
        "date_filter": date_filter,
    }

    return render(request, "supplier/report.html", context)


def supplier_report_fetch(request, pk):
    """AJAX endpoint to fetch supplier report data - optimized version"""

    supplier = get_object_or_404(Supplier, id=pk)
    start_date, end_date = getDates(request)

    # Get opening balance

    # Define filters
    date_range = [start_date, end_date]

    # Get report data
    context = get_supplier_report_data(supplier, date_range)

    # Render table HTML
    table_html = render_to_string(
        "supplier/report/fetch.html",
        {
            "supplier": supplier,
            "transactions": context["transactions"],
            "opening_balance": context["opening_balance"],
            "start_date": start_date,
        },
        request=request,
    )

    return JsonResponse(
        {
            "success": True,
            "total_invoiced": float(context["total_invoiced"]),
            "total_paid": float(context["total_paid"]),
            "outstanding_balance": float(context["outstanding_balance"]),
            "opening_balance": float(context["opening_balance"]),
            "transaction_count": len(context["transactions"]),
            "table_html": table_html,
        }
    )


def auto_reallocate(request, pk):
    """
    Auto reallocate payments using FIFO method.
    This function uses the signal's reallocation logic but skips signals
    to avoid double reallocation.
    """
    from supplier.signals import reallocate_supplier_payments

    supplier = get_object_or_404(Supplier, id=pk)

    # Use the signal's reallocation function directly
    # This ensures consistency with automatic reallocation
    reallocate_supplier_payments(supplier)

    messages.success(
        request,
        f"Successfully reallocated payments for {supplier.name} using FIFO method.",
    )
    return redirect("supplier:detail", pk=pk)
