from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import (
    Q,
    Sum,
    Exists,
    OuterRef,
)
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth import get_user_model
from .forms import CustomUserForm, PasswordResetForm, SalaryForm, TransactionForm
from .models import LoginEvent, Salary, Transaction
from django.utils import timezone
from django.contrib.sessions.models import Session
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from .models import LoginEvent
from base.utility import render_paginated_response
from base.getDates import getDates
from invoice.models import Invoice, InvoiceItem
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

VALID_SORT_FIELDS = {
    "full_name",
    "-full_name",
    "date_joined",
    "-date_joined",
    "phone_number",
    "-phone_number",
    "email",
    "-email",
    "role",
    "-role",
}

USERS_PER_PAGE = 20


def home(request):
    """User management main page - initial load only."""
    # For initial page load, just render the template with empty data
    context = {
        "roles": User.Roles.choices,
    }
    return render(request, "user/home.html", context)


def get_data(request):
    """Helper function to get filtered and sorted users."""
    # Get search and filter parameters
    search_query = request.GET.get("search", "")
    role_filter = request.GET.get("role", "")
    status_filter = request.GET.get("status", "")
    commission_filter = request.GET.get("commission", "")
    sort_by = request.GET.get("sort", "-date_joined")

    # Apply search filter
    filters = Q()
    if search_query:
        filters &= (
            Q(full_name__icontains=search_query)
            | Q(phone_number__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(address__icontains=search_query)
        )

    # Apply role filter
    if role_filter:
        filters &= Q(role=role_filter)

    # Apply status filter (active/inactive)
    if status_filter == "active":
        filters &= Q(is_active=True)
    elif status_filter == "inactive":
        filters &= Q(is_active=False)

    # Apply commission filter (check current salary's commission)
    if commission_filter == "yes":
        # Users with current salary (effective_to is null) AND commission=True
        filters &= Q(salaries__effective_to__isnull=True, salaries__commission=True)
    elif commission_filter == "no":
        # Users with no current salary OR current salary with commission=False
        # Exclude users who have current salary with commission=True
        from .models import Salary

        has_commission = Salary.objects.filter(
            user=OuterRef("pk"), effective_to__isnull=True, commission=True
        )
        filters &= ~Exists(has_commission)

    users = User.objects.filter(filters)

    # Apply sorting
    if sort_by not in VALID_SORT_FIELDS:
        sort_by = "-date_joined"
    users = users.order_by(sort_by)

    return users


def fetch_users(request):
    """AJAX endpoint to fetch users with search, filter, and pagination."""
    users = get_data(request)

    return render_paginated_response(
        request,
        users,
        "user/fetch.html",
    )


class CreateUser(CreateView):
    model = User
    form_class = CustomUserForm
    template_name = "user/form.html"
    success_url = reverse_lazy("user:home")

    def form_valid(self, form):
        # Set a default password for new users (they can change it later)
        user = form.save(commit=False)
        user.set_password("changeme123")  # Default password
        user.save()
        messages.success(self.request, "User created successfully!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create User"
        context["user"] = None  # For breadcrumb compatibility
        return context

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class EditUser(UpdateView):
    model = User
    form_class = CustomUserForm
    template_name = "user/form.html"
    success_url = reverse_lazy("user:home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit User"
        context["user"] = self.get_object()  # For breadcrumb compatibility
        return context

    def form_valid(self, form):
        messages.success(self.request, "User updated successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class DeleteUser(DeleteView):
    model = User
    template_name = "user/delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.get_object()
        return context

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        messages.success(request, f"User '{user.full_name}' deleted successfully!")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy("user:home")

    def form_valid(self, form):
        messages.success(self.request, "User deleted successfully!")
        return super().form_valid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid: {form.errors}")
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


def user_detail(request, pk):
    """View user details."""
    user = get_object_or_404(User, id=pk)
    recent_logins = LoginEvent.objects.filter(
        user=user, event_type=LoginEvent.EventType.LOGIN
    )[:10]
    salaries = user.salaries.all()[:50]  # Last 50 salary records
    transactions = user.transactions.all()[:50]  # Last 50 transactions
    current_salary = user.current_salary

    # Calculate summary statistics
    total_salaries = user.salaries.count()
    total_transactions = user.transactions.count()

    # Calculate transaction totals
    credit_transactions = user.transactions.filter(
        transaction_type__in=[
            Transaction.TransactionType.SALE,
            Transaction.TransactionType.DEPOSIT,
            Transaction.TransactionType.PAYMENT,
            Transaction.TransactionType.COMMISSION,
            Transaction.TransactionType.SALARY,
        ]
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    debit_transactions = user.transactions.filter(
        transaction_type__in=[
            Transaction.TransactionType.REFUND,
            Transaction.TransactionType.WITHDRAWAL,
            Transaction.TransactionType.EXPENSE,
        ]
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    net_amount = credit_transactions - debit_transactions

    return render(
        request,
        "user/detail.html",
        {
            "user": user,
            "recent_logins": recent_logins,
            "salaries": salaries,
            "transactions": transactions,
            "current_salary": current_salary,
            "total_salaries": total_salaries,
            "total_transactions": total_transactions,
            "credit_transactions": credit_transactions,
            "debit_transactions": debit_transactions,
            "net_amount": net_amount,
        },
    )


def user_delete(request, user_id):
    """Delete user."""
    if request.method == "POST":
        user = get_object_or_404(User, id=user_id)
        user.delete()
        messages.success(request, "User deleted successfully!")
        return redirect("user:home")

    return redirect("user:home")


def search_users_ajax(request):
    """AJAX endpoint for real-time user search."""
    search_query = request.GET.get("q", "")

    if len(search_query) < 2:
        return JsonResponse({"users": []})

    users = User.objects.filter(
        Q(full_name__icontains=search_query)
        | Q(phone_number__icontains=search_query)
        | Q(email__icontains=search_query)
        | Q(address__icontains=search_query)
    )[
        :10
    ]  # Limit to 10 results

    data = []
    for user in users:
        data.append(
            {
                "id": user.id,
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            }
        )

    return JsonResponse({"users": data})


def change_user_status(request, user_id):
    """Toggle user active/inactive status."""
    if request.method == "POST":
        user = get_object_or_404(User, id=user_id)
        user.is_active = not user.is_active
        user.save()

        status = "activated" if user.is_active else "deactivated"
        messages.success(request, f"User '{user.full_name}' {status} successfully!")

        return redirect("user:home")

    return redirect("user:home")


def logins_overview(request):
    events = LoginEvent.objects.select_related("user").all()[:500]
    return render(request, "user/logins.html", {"events": events})


def sessions_overview(request):
    """List active sessions and users' last login details."""
    now = timezone.now()
    active_sessions = Session.objects.filter(expire_date__gt=now)

    sessions_data = []
    session_key_to_is_current = (
        {request.session.session_key: True} if request.session.session_key else {}
    )

    for session in active_sessions:
        data = session.get_decoded()
        user_id = data.get("_auth_user_id")
        if not user_id:
            continue
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            continue

        ip_address = data.get("ip_address")
        user_agent = data.get("user_agent")
        last_activity = data.get("last_activity")

        sessions_data.append(
            {
                "session_key": session.session_key,
                "user": user,
                "last_login": user.last_login,
                "expire_date": session.expire_date,
                "is_current": session_key_to_is_current.get(session.session_key, False),
                "ip_address": ip_address,
                "user_agent": user_agent,
                "last_activity": last_activity,
            }
        )

    # Sort by user then expire_date desc
    sessions_data.sort(
        key=lambda s: (s["user"].full_name or "", -int(s["expire_date"].timestamp()))
    )

    context = {
        "sessions": sessions_data,
        "active_count": active_sessions.count(),
    }

    return render(request, "user/sessions.html", context)


@staff_member_required
@require_POST
def invalidate_all_sessions(request):
    """Invalidate all active sessions (logs everyone out)."""
    now = timezone.now()
    qs = Session.objects.filter(expire_date__gt=now)
    deleted = qs.count()
    qs.delete()
    messages.success(request, f"Invalidated {deleted} active session(s).")
    return redirect("user:sessions")


@staff_member_required
@require_POST
def invalidate_session(request, session_key):
    """Invalidate a specific session by key."""
    try:
        session = Session.objects.get(session_key=session_key)
        session.delete()
        messages.success(request, "Session invalidated.")
    except Session.DoesNotExist:
        messages.error(request, "Session not found.")
    return redirect("user:sessions")


def reset_user_password(request, user_id):
    """Reset password for a specific user."""
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data["new_password"]
            user.set_password(new_password)
            user.save()
            messages.success(
                request, f"Password reset successfully for {user.full_name}!"
            )
            return redirect("user:detail", pk=user_id)
    else:
        form = PasswordResetForm()

    context = {
        "form": form,
        "user": user,
        "title": f"Reset Password - {user.full_name}",
    }

    return render(request, "user/reset_password.html", context)


# ==================== SALARY CRUD ====================


def salary_create(request, user_id):
    """Create a new salary record for a user."""
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        form = SalaryForm(request.POST, user=user)
        if form.is_valid():
            salary = form.save(commit=False)
            salary.user = user
            salary.created_by = request.user
            # If effective_to is set, end the current salary
            if salary.effective_to:
                current_salary = user.salaries.filter(effective_to__isnull=True).first()
                if current_salary:
                    current_salary.effective_to = salary.effective_from
                    current_salary.save()
            salary.save()
            messages.success(request, "Salary record created successfully!")
            return redirect("user:detail", pk=user_id)
    else:
        form = SalaryForm(user=user)

    context = {
        "form": form,
        "user": user,
        "title": f"Create Salary - {user.full_name}",
    }
    return render(request, "user/salary/form.html", context)


def salary_edit(request, user_id, salary_id):
    """Edit an existing salary record."""
    user = get_object_or_404(User, id=user_id)
    salary = get_object_or_404(Salary, id=salary_id, user=user)

    if request.method == "POST":
        form = SalaryForm(request.POST, instance=salary, user=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Salary record updated successfully!")
            return redirect("user:detail", pk=user_id)
    else:
        form = SalaryForm(instance=salary, user=user)

    context = {
        "form": form,
        "user": user,
        "salary": salary,
        "title": f"Edit Salary - {user.full_name}",
    }
    return render(request, "user/salary/form.html", context)


def salary_delete(request, user_id, salary_id):
    """Delete a salary record."""
    user = get_object_or_404(User, id=user_id)
    salary = get_object_or_404(Salary, id=salary_id, user=user)

    if request.method == "POST":
        salary.delete()
        messages.success(request, "Salary record deleted successfully!")
        return redirect("user:detail", pk=user_id)

    context = {"user": user, "salary": salary}
    return render(request, "user/salary/delete.html", context)


# ==================== TRANSACTION CRUD ====================


def transaction_create(request, user_id):
    """Create a new transaction for a user."""
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        form = TransactionForm(request.POST, user=user)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = user
            transaction.created_by = request.user
            transaction.save()
            messages.success(request, "Transaction created successfully!")
            return redirect("user:detail", pk=user_id)
    else:
        form = TransactionForm(user=user)

    context = {
        "form": form,
        "user": user,
        "title": f"Create Transaction - {user.full_name}",
    }
    return render(request, "user/transaction/form.html", context)


def transaction_edit(request, user_id, transaction_id):
    """Edit an existing transaction."""
    user = get_object_or_404(User, id=user_id)
    transaction = get_object_or_404(Transaction, id=transaction_id, user=user)

    if request.method == "POST":
        form = TransactionForm(request.POST, instance=transaction, user=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Transaction updated successfully!")
            return redirect("user:detail", pk=user_id)
    else:
        form = TransactionForm(instance=transaction, user=user)

    context = {
        "form": form,
        "user": user,
        "transaction": transaction,
        "title": f"Edit Transaction - {user.full_name}",
    }
    return render(request, "user/transaction/form.html", context)


def transaction_delete(request, user_id, transaction_id):
    """Delete a transaction."""
    user = get_object_or_404(User, id=user_id)
    transaction = get_object_or_404(Transaction, id=transaction_id, user=user)

    if request.method == "POST":
        transaction.delete()
        messages.success(request, "Transaction deleted successfully!")
        return redirect("user:detail", pk=user_id)

    context = {"user": user, "transaction": transaction}
    return render(request, "user/transaction/delete.html", context)


# ==================== COMMISSION VIEWS ====================


def user_commission(request, user_id):
    """View commission data for a user by month and year."""
    user = get_object_or_404(User, id=user_id)
    current_salary = user.current_salary

    # Get date range using getDates utility (now accepts date_range and start_date/end_date directly)
    start_datetime, end_datetime = getDates(request)

    # Get invoices created by this user and filter by date range
    invoices = Invoice.objects.filter(sold_by=user).filter(
        invoice_date__gte=start_datetime, invoice_date__lte=end_datetime
    )

    # Format dates for template
    start_date = start_datetime.strftime("%Y-%m-%d")
    end_date = end_datetime.strftime("%Y-%m-%d")

    # Get invoice items with commission
    invoice_items_all = InvoiceItem.objects.filter(
        invoice__in=invoices, commission_percentage__gt=0
    ).select_related("invoice", "product_variant__product")

    # Calculate commission by month
    monthly_totals = defaultdict(
        lambda: {
            "total_sales": Decimal("0"),
            "total_commission": Decimal("0"),
            "invoice_count": 0,
            "item_count": 0,
        }
    )

    # Calculate totals from all items (for summary, not for display)
    for item in invoice_items_all:
        # Calculate commission amount on discounted amount (after invoice-level discount)
        item_amount = item.discounted_amount  # Uses discounted_amount property
        commission_amount = (item.commission_percentage / Decimal("100")) * item_amount

        # Get month/year
        invoice_date = item.invoice.invoice_date
        month_key = invoice_date.strftime("%Y-%m")

        # Update totals
        monthly_totals[month_key]["total_sales"] += item_amount
        monthly_totals[month_key]["total_commission"] += commission_amount
        monthly_totals[month_key]["item_count"] += 1

    # Convert monthly totals to list and sort
    monthly_summary = []
    for month_key, totals in sorted(monthly_totals.items(), reverse=True):
        # Count unique invoices for this month
        month_invoices = invoices.filter(
            invoice_date__year=int(month_key.split("-")[0]),
            invoice_date__month=int(month_key.split("-")[1]),
        )
        totals["invoice_count"] = month_invoices.count()
        totals["month_key"] = month_key
        totals["month_label"] = datetime(
            int(month_key.split("-")[0]), int(month_key.split("-")[1]), 1
        ).strftime("%B %Y")
        monthly_summary.append(totals)

    # Calculate overall totals
    total_sales = sum(data["total_sales"] for data in monthly_totals.values())
    total_commission = sum(data["total_commission"] for data in monthly_totals.values())

    context = {
        "user": user,
        "current_salary": current_salary,
        "monthly_summary": monthly_summary,
        "total_sales": total_sales,
        "total_commission": total_commission,
        "selected_start_date": start_date,
        "selected_end_date": end_date,
    }

    return render(request, "user/commission/home.html", context)


def fetch_user_commission(request, user_id):
    """AJAX: fetch commission data for a user with pagination and optional sorting."""
    user = get_object_or_404(User, id=user_id)

    # Get filter parameters
    sort_by = request.GET.get("sort", "-invoice_date")

    # Get date range using getDates utility (now accepts date_range and start_date/end_date directly)
    start_datetime, end_datetime = getDates(request)

    # Get invoices created by this user and filter by date range
    invoices = Invoice.objects.filter(sold_by=user).filter(
        invoice_date__gte=start_datetime, invoice_date__lte=end_datetime
    )

    # Get invoice items with commission, ordered by invoice date
    valid_sort_fields = {
        "invoice_date": "invoice__invoice_date",
        "-invoice_date": "-invoice__invoice_date",
        "commission_amount": "commission_percentage",  # Approximate sort
        "-commission_amount": "-commission_percentage",
    }

    if sort_by in valid_sort_fields:
        order_by = valid_sort_fields[sort_by]
    else:
        order_by = "-invoice__invoice_date"

    invoice_items = (
        InvoiceItem.objects.filter(invoice__in=invoices, commission_percentage__gt=0)
        .select_related("invoice", "product_variant__product")
        .order_by(order_by)
    )

    # Convert to list for pagination (since we need to calculate commission)
    commission_list = []
    for item in invoice_items:
        item_amount = item.discounted_amount  # Uses discounted_amount property
        commission_amount = (item.commission_percentage / Decimal("100")) * item_amount

        commission_list.append(
            {
                "invoice": item.invoice,
                "invoice_item": item,
                "product_name": (
                    item.product_variant.product.name if item.product_variant else "N/A"
                ),
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "item_amount": item_amount,
                "commission_percentage": item.commission_percentage,
                "commission_amount": commission_amount,
                "date": item.invoice.invoice_date,
            }
        )

    return render_paginated_response(
        request,
        commission_list,
        "user/commission/fetch.html",
        per_page=20,
    )


def fetch_commission_summary(request, user_id):
    """AJAX: fetch commission summary data (totals and monthly summary)."""
    user = get_object_or_404(User, id=user_id)

    # Get date range using getDates utility (now accepts date_range and start_date/end_date directly)
    start_datetime, end_datetime = getDates(request)

    # Get invoices created by this user and filter by date range
    invoices = Invoice.objects.filter(sold_by=user).filter(
        invoice_date__gte=start_datetime, invoice_date__lte=end_datetime
    )

    # Get invoice items with commission
    invoice_items_all = InvoiceItem.objects.filter(
        invoice__in=invoices, commission_percentage__gt=0
    ).select_related("invoice", "product_variant__product")

    # Calculate commission by month
    monthly_totals = defaultdict(
        lambda: {
            "total_sales": Decimal("0"),
            "total_commission": Decimal("0"),
            "invoice_count": 0,
            "item_count": 0,
        }
    )

    # Calculate totals from all items
    for item in invoice_items_all:
        item_amount = item.discounted_amount  # Uses discounted_amount property
        commission_amount = (item.commission_percentage / Decimal("100")) * item_amount

        invoice_date = item.invoice.invoice_date
        month_key = invoice_date.strftime("%Y-%m")

        monthly_totals[month_key]["total_sales"] += item_amount
        monthly_totals[month_key]["total_commission"] += commission_amount
        monthly_totals[month_key]["item_count"] += 1

    # Convert monthly totals to list and sort
    monthly_summary = []
    for month_key, totals in sorted(monthly_totals.items(), reverse=True):
        month_invoices = invoices.filter(
            invoice_date__year=int(month_key.split("-")[0]),
            invoice_date__month=int(month_key.split("-")[1]),
        )
        totals["invoice_count"] = month_invoices.count()
        totals["month_key"] = month_key
        totals["month_label"] = datetime(
            int(month_key.split("-")[0]), int(month_key.split("-")[1]), 1
        ).strftime("%B %Y")
        monthly_summary.append(totals)

    # Calculate overall totals
    total_sales = sum(data["total_sales"] for data in monthly_totals.values())
    total_commission = sum(data["total_commission"] for data in monthly_totals.values())

    return JsonResponse(
        {
            "success": True,
            "total_sales": float(total_sales),
            "total_commission": float(total_commission),
            "monthly_summary": [
                {
                    "month_label": s["month_label"],
                    "invoice_count": s["invoice_count"],
                    "item_count": s["item_count"],
                    "total_sales": float(s["total_sales"]),
                    "total_commission": float(s["total_commission"]),
                }
                for s in monthly_summary
            ],
        }
    )
