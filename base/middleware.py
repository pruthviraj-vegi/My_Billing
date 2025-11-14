from django.conf import settings
from django.shortcuts import redirect
import re
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth import logout


class CustomLoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the path is exempt from login requirement
        path = request.path_info.lstrip("/")

        # Exempt static files, media files, and login page
        if any(re.match(pattern, path) for pattern in settings.LOGIN_EXEMPT_URLS):
            return self.get_response(request)

        # Check if user is authenticated
        if not request.user.is_authenticated:
            # Store the original URL to redirect back after login
            request.session["next"] = request.path
            return redirect("base:login")

        return self.get_response(request)


class SessionMetaMiddleware:
    """Attach client metadata (IP, user agent, last activity) to the session.

    - Stores once per session: ip_address, user_agent
    - Updates last_activity on every request
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            session = request.session
            # Derive client IP
            xff = request.META.get("HTTP_X_FORWARDED_FOR")
            if xff:
                ip_address = xff.split(",")[0].strip()
            else:
                ip_address = request.META.get("REMOTE_ADDR")

            user_agent = request.META.get("HTTP_USER_AGENT", "")

            if session is not None:
                if "ip_address" not in session and ip_address:
                    session["ip_address"] = ip_address
                if "user_agent" not in session and user_agent:
                    session["user_agent"] = user_agent[:512]
                # Always refresh last activity
                session["last_activity"] = timezone.now().isoformat()
        except Exception:
            # Never block the request on metadata capture failures
            pass

        response = self.get_response(request)
        return response


class InactivityLogoutMiddleware:
    """Logs out authenticated users after a period of inactivity.

    Uses `request.session["last_activity"]` set by `SessionMetaMiddleware`.
    Must be placed BEFORE `SessionMetaMiddleware` in `MIDDLEWARE` so a stale
    `last_activity` value is checked prior to being refreshed.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout_seconds = getattr(settings, "INACTIVITY_TIMEOUT_SECONDS", 3 * 60 * 60)

    def __call__(self, request):
        # Skip checks for exempt URLs (e.g., static, media, login)
        path = request.path_info.lstrip("/")
        try:
            if any(re.match(pattern, path) for pattern in settings.LOGIN_EXEMPT_URLS):
                return self.get_response(request)
        except Exception:
            # If settings are misconfigured, do not block the request
            pass

        if request.user.is_authenticated:
            last_activity_str = request.session.get("last_activity")
            if last_activity_str:
                try:
                    last_activity_dt = datetime.fromisoformat(last_activity_str)
                except Exception:
                    last_activity_dt = None

                now_dt = timezone.now()
                # Ensure both datetimes are naive or aware consistently
                # With USE_TZ=False, Django returns naive datetimes by default.
                if last_activity_dt is not None and isinstance(now_dt, datetime):
                    if (now_dt - last_activity_dt) > timedelta(seconds=self.timeout_seconds):
                        logout(request)
                        # Preserve original target to return post-login if desired
                        request.session["next"] = request.path
                        return redirect("base:login")

        return self.get_response(request)


