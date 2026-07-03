"""Notification Middleware — Injects cached unread count into every request."""

from django.core.cache import cache

from .models import Notification


class NotificationCountMiddleware:
    """Attach ``request.notification_count`` on every authenticated request.

    The count is cached in Redis for 5 minutes per user to avoid
    hitting the database on every page load.  Signals in ``signals.py``
    invalidate the cache whenever a Notification is created, updated,
    or deleted.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            cache_key = f"user_{request.user.id}_unread_notifs"
            unread_count = cache.get(cache_key)

            if unread_count is None:
                # Cache miss: hit the database only once
                unread_count = Notification.objects.filter(
                    user=request.user,
                    is_read=False,
                ).count()
                # Save in cache for 5 minutes (300 seconds)
                cache.set(cache_key, unread_count, timeout=300)

            request.notification_count = unread_count
        else:
            request.notification_count = 0

        return self.get_response(request)
