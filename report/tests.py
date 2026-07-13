from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customer.models import Customer, CustomerCreditSummary

User = get_user_model()


class ReportStatementsTests(TestCase):
    """
    Test cases for report statements and messaging endpoints.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            first_name="Test",
            phone_number="1234567890",
            password="testpassword",
            email="test@example.com"
        )
        self.customer = Customer.objects.create(
            name="Test Customer",
            phone_number="9999999999",
            created_by=self.user
        )

    def test_balance_requires_login(self):
        """
        Verify that send_balance endpoint requires authentication.
        """
        response = self.client.get(
            reverse("report:send_balance", kwargs={"pk": self.customer.pk})
        )
        self.assertEqual(response.status_code, 302)

    @patch("report.statements.send_template")
    def test_balance_success_with_credit_summary(self, mock_send_template):
        """
        Verify that send_balance successfully sends balance when credit summary exists.
        """
        # Create credit summary
        summary, _ = CustomerCreditSummary.objects.get_or_create(customer=self.customer)
        summary.balance_amount = 250.50
        summary.save()

        # Login
        self.client.login(phone_number="1234567890", password="testpassword")

        # Mock successful template send response
        mock_send_template.return_value = {"success": True}

        response = self.client.get(
            reverse("report:send_balance", kwargs={"pk": self.customer.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Balance sent successfully")

        # Verify send_template was called with correct parameters
        mock_send_template.assert_called_once()
        args, kwargs = mock_send_template.call_args
        self.assertEqual(args[1], self.customer.phone_number)
        self.assertEqual(args[3]["customer_name"], self.customer.name)
        self.assertEqual(args[3]["balance"], "250.5")

    @patch("report.statements.send_template")
    def test_balance_default_no_credit_summary(self, mock_send_template):
        """
        Verify that send_balance defaults to 0.0 balance if credit summary is missing.
        """
        # Ensure credit summary is deleted
        CustomerCreditSummary.objects.filter(customer=self.customer).delete()

        # Login
        self.client.login(phone_number="1234567890", password="testpassword")

        # Mock successful template send response
        mock_send_template.return_value = {"success": True}

        response = self.client.get(
            reverse("report:send_balance", kwargs={"pk": self.customer.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Balance sent successfully")

        # Verify send_template was called with 0.0 balance
        mock_send_template.assert_called_once()
        args, kwargs = mock_send_template.call_args
        self.assertEqual(args[3]["balance"], "0.0")

    @patch("report.statements.send_template")
    def test_balance_send_template_failure(self, mock_send_template):
        """
        Verify that send_balance returns success=False if template sending fails.
        """
        self.client.login(phone_number="1234567890", password="testpassword")

        # Mock failed template send response
        mock_send_template.return_value = {"success": False, "detail": "API error"}

        response = self.client.get(
            reverse("report:send_balance", kwargs={"pk": self.customer.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["message"], "API error")
