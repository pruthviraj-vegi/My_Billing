from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from customer.models import Customer
from notification.models import MessageLog, MessageStatusChoices


class MessageLogStaleCleanupTestCase(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Test Customer",
            phone_number="9876543210"
        )

    def test_cleanup_stale_messages(self):
        log = MessageLog.objects.create(
            customer=self.customer,
            message_type="balance",
            phone_number=self.customer.phone_number,
            status=MessageStatusChoices.PROCESSING,
        )
        # Backdate updated_at to 10 minutes ago
        MessageLog.objects.filter(id=log.id).update(
            updated_at=timezone.now() - timedelta(minutes=10)
        )

        cleaned_count = MessageLog.cleanup_stale_messages(minutes=5)
        self.assertEqual(cleaned_count, 1)

        log.refresh_from_db()
        self.assertEqual(log.status, MessageStatusChoices.FAILED)
        self.assertIn("Message processing timed out", log.error_message)

    def test_is_duplicate_in_flight_auto_cleans_stale_task(self):
        stale_log = MessageLog.objects.create(
            customer=self.customer,
            message_type="balance",
            phone_number=self.customer.phone_number,
            status=MessageStatusChoices.PROCESSING,
        )
        MessageLog.objects.filter(id=stale_log.id).update(
            updated_at=timezone.now() - timedelta(minutes=10)
        )

        # Calling is_duplicate_in_flight should clean the stale log and return False
        in_flight = MessageLog.is_duplicate_in_flight(self.customer, "balance")
        self.assertFalse(in_flight)

        stale_log.refresh_from_db()
        self.assertEqual(stale_log.status, MessageStatusChoices.FAILED)

    def test_is_duplicate_in_flight_blocks_recent_active_task(self):
        recent_log = MessageLog.objects.create(
            customer=self.customer,
            message_type="balance",
            phone_number=self.customer.phone_number,
            status=MessageStatusChoices.PROCESSING,
        )
        # Recent log updated now
        in_flight = MessageLog.is_duplicate_in_flight(self.customer, "balance")
        self.assertTrue(in_flight)

