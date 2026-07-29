from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customer.models import Customer, CustomerCreditSummary
from notification.models import MessageLog, MessageStatusChoices, Notification
from notification.tasks import send_customer_message_task

User = get_user_model()


class ReportStatementsTests(TestCase):
    """
    Test cases for asynchronous report statements and messaging endpoints.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            first_name="Test",
            phone_number="1234567890",
            password="testpassword",
            email="test@example.com",
        )
        self.customer = Customer.objects.create(
            name="Test Customer", phone_number="9999999999", created_by=self.user
        )

    def test_balance_requires_login(self):
        """
        Verify that send_balance endpoint requires authentication.
        """
        response = self.client.get(
            reverse("report:send_balance", kwargs={"pk": self.customer.pk})
        )
        self.assertEqual(response.status_code, 302)

    @patch("report.statements.send_customer_message_task.delay")
    def test_balance_queues_task_and_creates_log(self, mock_delay):
        """
        Verify that send_balance creates a MessageLog and queues a Celery task on commit.
        """
        summary, _ = CustomerCreditSummary.objects.get_or_create(customer=self.customer)
        summary.balance_amount = 250.50
        summary.save()

        self.client.login(phone_number="1234567890", password="testpassword")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.get(
                reverse("report:send_balance", kwargs={"pk": self.customer.pk})
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("queued in background", data["message"])

        mock_delay.assert_called_once()

        # Check MessageLog creation
        log = MessageLog.objects.get(id=data["log_id"])
        self.assertEqual(log.customer, self.customer)
        self.assertEqual(log.message_type, "balance")

    @patch("report.statements.send_customer_message_task.delay")
    def test_balance_prevents_duplicate_sending(self, mock_delay):
        """
        Verify duplicate send attempts while a task is pending/processing are blocked.
        """
        self.client.login(phone_number="1234567890", password="testpassword")

        # First request
        with self.captureOnCommitCallbacks(execute=True):
            res1 = self.client.get(
                reverse("report:send_balance", kwargs={"pk": self.customer.pk})
            )
        self.assertTrue(res1.json()["success"])
        self.assertEqual(mock_delay.call_count, 1)

        # Duplicate request immediately following
        with self.captureOnCommitCallbacks(execute=True):
            res2 = self.client.get(
                reverse("report:send_balance", kwargs={"pk": self.customer.pk})
            )
        self.assertFalse(res2.json()["success"])
        self.assertIn("already in progress or was sent recently", res2.json()["message"])
        self.assertEqual(mock_delay.call_count, 1)  # Still 1 call

    @patch("notification.tasks.send_template")
    def test_send_customer_message_task_executes_successfully(self, mock_send_template):
        """
        Verify that send_customer_message_task calls send_template, updates status to SENT,
        and creates a Notification.
        """
        mock_send_template.return_value = {"success": True}

        log = MessageLog.objects.create(
            user=self.user,
            customer=self.customer,
            message_type="balance",
            phone_number=self.customer.phone_number,
        )

        send_customer_message_task(log.id)

        log.refresh_from_db()
        self.assertEqual(log.status, MessageStatusChoices.SENT)

        # Verify system notification was generated
        notif = Notification.objects.filter(user=self.user).first()
        self.assertIsNotNone(notif)
        self.assertIn("Balance Sent Successfully", notif.title)

    @patch("report.statements.send_customer_message_task.delay")
    def test_broker_down_marks_log_as_failed(self, mock_delay):
        """
        Verify that if broker (Redis/Celery) raises an exception on .delay(),
        the MessageLog status is updated to FAILED with error detail on commit.
        """
        mock_delay.side_effect = Exception("Connection to Redis refused")

        self.client.login(phone_number="1234567890", password="testpassword")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.get(
                reverse("report:send_balance", kwargs={"pk": self.customer.pk})
            )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        log = MessageLog.objects.get(id=data["log_id"])
        self.assertEqual(log.status, MessageStatusChoices.FAILED)
        self.assertIn("Broker unavailable", log.error_message)

    @patch("notification.tasks.send_template")
    def test_task_failure_marks_log_failed_and_notifies(self, mock_send_template):
        """
        Verify that when task encounters non-retryable failure (retries exhausted),
        log status is set to FAILED and a failure Notification is delivered to user.
        """
        mock_send_template.return_value = {"success": False, "detail": "Invalid phone number"}

        log = MessageLog.objects.create(
            user=self.user,
            customer=self.customer,
            message_type="balance",
            phone_number=self.customer.phone_number,
        )

        # Simulate retries exhausted (retries == max_retries)
        with patch.object(send_customer_message_task.request, "retries", 2):
            send_customer_message_task(log.id)

        log.refresh_from_db()
        self.assertEqual(log.status, MessageStatusChoices.FAILED)

        # Verify failure notification created
        notif = Notification.objects.filter(user=self.user, notification_type="balance_failed").first()
        self.assertIsNotNone(notif)
        self.assertIn("Delivery Failed", notif.title)

    @patch("notification.tasks.send_template")
    @patch("notification.tasks.generate_statement_pdf")
    def test_statement_message_type_execution(self, mock_pdf, mock_send_template):
        """
        Verify statement message type generates PDF and sends template.
        """
        mock_pdf.return_value = {"url": "http://example.com/stmt.pdf", "filename": "stmt.pdf"}
        mock_send_template.return_value = {"success": True}

        log = MessageLog.objects.create(
            user=self.user,
            customer=self.customer,
            message_type="statement",
            phone_number=self.customer.phone_number,
            payload_data={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        )

        send_customer_message_task(log.id)

        log.refresh_from_db()
        self.assertEqual(log.status, MessageStatusChoices.SENT)
        mock_pdf.assert_called_once()
        mock_send_template.assert_called_once()


