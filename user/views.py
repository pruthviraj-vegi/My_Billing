from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth import get_user_model
from .forms import CustomUserForm, PasswordResetForm
import json
from django.utils import timezone
from django.contrib.sessions.models import Session
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from .models import LoginEvent
import csv
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


@login_required
def home(request):
    """User management main page with search and filter functionality."""

    # Get search and filter parameters
    search_query = request.GET.get("search", "")
    role_filter = request.GET.get("role", "")
    status_filter = request.GET.get("status", "")
    commission_filter = request.GET.get("commission", "")
    sort_by = request.GET.get("sort", "-date_joined")

    # Start with all users
    users = User.objects.all()

    # Apply search filter
    if search_query:
        users = users.filter(
            Q(full_name__icontains=search_query)
            | Q(phone_number__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(address__icontains=search_query)
        )

    # Apply role filter
    if role_filter:
        users = users.filter(role=role_filter)

    # Apply status filter (active/inactive)
    if status_filter == "active":
        users = users.filter(is_active=True)
    elif status_filter == "inactive":
        users = users.filter(is_active=False)

    # Apply commission filter
    if commission_filter == "yes":
        users = users.filter(commision=True)
    elif commission_filter == "no":
        users = users.filter(commision=False)

    # Apply sorting
    if sort_by in [
        "full_name",
        "-full_name",
        "date_joined",
        "-date_joined",
        "phone_number",
        "-phone_number",
        "role",
        "-role",
        "commision",
        "-commision",
    ]:
        users = users.order_by(sort_by)
    else:
        users = users.order_by("-date_joined")

    context = {
        "data": users,
        "search_query": search_query,
        "role_filter": role_filter,
        "status_filter": status_filter,
        "commission_filter": commission_filter,
        "sort_by": sort_by,
        "roles": User.Roles.choices,
    }

    return render(request, "user/home.html", context)


class CreateUser(LoginRequiredMixin, CreateView):
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


class EditUser(LoginRequiredMixin, UpdateView):
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


class DeleteUser(LoginRequiredMixin, DeleteView):
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


@login_required
def user_detail(request, pk):
    """View user details."""
    user = get_object_or_404(User, id=pk)
    recent_logins = LoginEvent.objects.filter(
        user=user, event_type=LoginEvent.EventType.LOGIN
    )[:10]
    return render(
        request, "user/detail.html", {"user": user, "recent_logins": recent_logins}
    )


@login_required
def user_delete(request, user_id):
    """Delete user."""
    if request.method == "POST":
        user = get_object_or_404(User, id=user_id)
        user.delete()
        messages.success(request, "User deleted successfully!")
        return redirect("user:home")

    return redirect("user:home")


@login_required
def download_users(request):
    """Download users data as JSON."""
    users = User.objects.all()
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
                "date_joined": user.date_joined.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="users.json"'
    return response


@login_required
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


@login_required
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


@login_required
def logins_overview(request):
    events = LoginEvent.objects.select_related("user").all()[:500]
    return render(request, "user/logins.html", {"events": events})


@login_required
@staff_member_required
def download_logins(request):
    """Download recent login events as CSV."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="login_events.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "occurred_at",
            "event",
            "user_id",
            "full_name",
            "phone",
            "ip",
            "user_agent",
            "session_key",
        ]
    )

    events = LoginEvent.objects.select_related("user").order_by("-occurred_at")[:5000]
    for ev in events:
        user = ev.user
        writer.writerow(
            [
                (
                    ev.occurred_at.isoformat(sep=" ")
                    if hasattr(ev.occurred_at, "isoformat")
                    else ev.occurred_at
                ),
                ev.event_type,
                user.id if user else "",
                getattr(user, "full_name", "") if user else "",
                getattr(user, "phone_number", "") if user else "",
                ev.ip_address or "",
                ev.user_agent or "",
                ev.session_key or "",
            ]
        )

    return response


@login_required
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


@login_required
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


@login_required
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


@login_required
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
