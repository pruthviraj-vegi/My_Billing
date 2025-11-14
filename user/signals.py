from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.sessions.models import Session
from django.utils import timezone
from .models import LoginEvent


def _extract_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    try:
        LoginEvent.objects.create(
            user=user,
            event_type=LoginEvent.EventType.LOGIN,
            occurred_at=timezone.now(),
            ip_address=_extract_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
            session_key=getattr(request.session, "session_key", None),
        )
    except Exception:
        pass


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    try:
        LoginEvent.objects.create(
            user=user,
            event_type=LoginEvent.EventType.LOGOUT,
            occurred_at=timezone.now(),
            ip_address=_extract_ip(request) if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:512] if request else None),
            session_key=(getattr(request.session, "session_key", None) if request else None),
        )
    except Exception:
        pass


