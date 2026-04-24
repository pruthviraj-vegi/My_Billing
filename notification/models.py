"""Notification Models."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

User = settings.AUTH_USER_MODEL


class Notification(models.Model):
    """A flexible notification that can link to ANY model via GenericForeignKey.

    Notification types are free strings registered in registry.py,
    so new types can be added without database migrations.
    """

    # ── Core ──────────────────────────────────────────
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Type / Category ───────────────────────────────
    notification_type = models.CharField(max_length=100, db_index=True)

    # ── Optional Action (CTA button in the notification) ──
    action_label = models.CharField(max_length=100, blank=True)
    action_url = models.CharField(max_length=500, blank=True)

    # ── Generic link to ANY model ─────────────────────
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    linked_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        """Return a string representation of the notification."""
        return f"[{self.notification_type}] {self.title} → {self.user}"

    def mark_read(self):
        """Mark this notification as read (no-op if already read)."""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=["is_read"])

    @classmethod
    def bulk_mark_read(cls, user):
        """Mark all unread notifications for a user as read.

        Returns:
            int: Number of notifications updated.
        """
        return cls.objects.filter(user=user, is_read=False).update(is_read=True)

    @classmethod
    def unread_count(cls, user):
        """Get the count of unread notifications for a user."""
        return cls.objects.filter(user=user, is_read=False).count()

    @classmethod
    def cleanup_old(cls, days=30):
        """Delete notifications older than `days` days.

        Returns:
            int: Number of notifications deleted.
        """
        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        count, _ = cls.objects.filter(created_at__lt=cutoff).delete()
        return count
