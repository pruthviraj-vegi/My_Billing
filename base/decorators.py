"""
Decorators and mixins for the application.
"""

import time
from functools import wraps

from django.conf import settings
from django.db import connection
from django.shortcuts import render


def timed(fn):
    """
    Decorator to measure execution time of a function.
    Stores the last execution time in `fn._last_elapsed_time`.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - start

        print(f"Time taken: {elapsed} seconds")

        # Store timing on the function itself
        wrapper.last_elapsed_time = elapsed
        return result

    wrapper.last_elapsed_time = None  # init attribute
    return wrapper


def query_debugger(func):
    """Decorator to count queries and execution time"""

    def wrapper(*args, **kwargs):
        # Only run in debug mode
        if not settings.DEBUG:
            return func(*args, **kwargs)

        # Reset queries
        connection.queries_log.clear()

        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        query_count = len(connection.queries)
        execution_time = (end_time - start_time) * 1000

        print(f"\n{'='*60}")
        print(f"Function: {func.__name__}")
        print(f"Queries: {query_count}")
        print(f"Time: {execution_time:.2f}ms")
        print(f"{'='*60}\n")

        return result

    return wrapper


# ── Role group constants ─────────────────────────────────────────
ALL_ROLES = ["OWNER", "MANAGER", "CASHIER", "STAFF", "SALESPERSON"]
MANAGEMENT = ["OWNER", "MANAGER"]
OWNER_ONLY = ["OWNER"]


def get_client_ip(request):
    """Helper function to get client's IP address"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def _log_unauthorized_access(request, view_name, allowed_roles):
    """Shared helper to log unauthorized access attempts."""
    from user.models import UnauthorizedAccess

    UnauthorizedAccess.objects.create(
        user=request.user,
        view_name=view_name,
        user_role=request.user.role,
        required_roles=", ".join(allowed_roles),
        ip_address=get_client_ip(request),
        url_path=request.path,
    )


def require_role(allowed_roles):
    """
    Decorator to check if user has required role.
    Authentication is handled by middleware — this only checks authorization.

    Usage:
        @require_role(['OWNER', 'MANAGER'])
        def my_view(request):
            pass

    Args:
        allowed_roles: List of role strings that are allowed to access the view
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if user's role is in allowed roles
            if request.user.role not in allowed_roles:
                _log_unauthorized_access(request, view_func.__name__, allowed_roles)
                return render(request, "base/403.html", status=403)

            # User has permission, execute the view
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


class RoleRequiredMixin:
    """
    Mixin for class-based views that checks user role.
    Authentication is handled by middleware.
    Usage:
        class MyView(RoleRequiredMixin, TemplateView):
            allowed_roles = ["OWNER", "MANAGER"]
    """

    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        """Check if user role is in allowed roles before dispatching request."""
        if request.user.role not in self.allowed_roles:
            _log_unauthorized_access(
                request, self.__class__.__name__, self.allowed_roles
            )
            return render(request, "base/403.html", status=403)
        return super().dispatch(request, *args, **kwargs)
