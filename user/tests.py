"""Unit tests for user app (CustomUser, CustomUserManager, Salary, Transaction, and User views)."""

from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from Billing.tests.helpers import create_test_user
from user.models import CustomUser, Salary, Transaction


class CustomUserModelTestCase(TestCase):
    """Test CustomUser model methods, managers, and properties."""

    def test_create_user_and_superuser(self):
        """Test manager create_user and create_superuser methods."""
        user = CustomUser.objects.create_user(
            phone_number="9876543210",
            first_name="john",
            last_name="doe",
            email="JOHN@EXAMPLE.COM",
            password="password123",
        )
        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.last_name, "Doe")
        self.assertEqual(user.email, "john@example.com")
        self.assertTrue(user.profile_id.startswith("SSC@"))
        self.assertEqual(user.full_name, "John Doe")
        self.assertEqual(user.username, "John")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

        superuser = CustomUser.objects.create_superuser(
            phone_number="9999999999",
            first_name="admin",
            password="password123",
        )
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)

    def test_salary_and_commission_properties(self):
        """Test user.current_salary and commission eligibility properties."""
        user = create_test_user(first_name="SalaryUser")

        # Initial salary
        salary1 = Salary.objects.create(
            user=user,
            amount=Decimal("15000.00"),
            commission=True,
            effective_from=timezone.now(),
        )

        self.assertEqual(user.current_salary, salary1)
        self.assertTrue(user.is_commission_eligible)
        self.assertTrue(user.commission)

        # Update salary history (supersede old salary)
        salary1.effective_to = timezone.now()
        salary1.save()

        salary2 = Salary.objects.create(
            user=user,
            amount=Decimal("20000.00"),
            commission=False,
            effective_from=timezone.now(),
        )

        self.assertEqual(user.current_salary, salary2)
        self.assertFalse(user.is_commission_eligible)


class TransactionModelTestCase(TestCase):
    """Test Transaction model auto ID generation, credit/debit properties, and amounts."""

    def setUp(self):
        self.user = create_test_user(first_name="TxnUser")

    def test_transaction_id_generation(self):
        """Test auto-generated unique transaction ID format."""
        txn = Transaction.objects.create(
            user=self.user,
            transaction_type=Transaction.TransactionType.SALE,
            amount=Decimal("500.00"),
            payment_method=Transaction.PaymentMethod.CASH,
            created_by=self.user,
        )
        self.assertTrue(txn.transaction_id.startswith("TXN-"))

    def test_credit_debit_classification(self):
        """Test is_credit and is_debit properties."""
        sale_txn = Transaction.objects.create(
            user=self.user,
            transaction_type=Transaction.TransactionType.SALE,
            amount=Decimal("1000.00"),
        )
        self.assertTrue(sale_txn.is_credit)
        self.assertFalse(sale_txn.is_debit)
        self.assertEqual(sale_txn.get_display_amount(), Decimal("1000.00"))

        expense_txn = Transaction.objects.create(
            user=self.user,
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal("250.00"),
        )
        self.assertFalse(expense_txn.is_credit)
        self.assertTrue(expense_txn.is_debit)
        self.assertEqual(expense_txn.get_display_amount(), Decimal("-250.00"))


class UserViewsTestCase(TestCase):
    """Test user app views."""

    def setUp(self):
        self.admin = create_test_user(first_name="Admin", is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)
        self.test_user = create_test_user(first_name="RegularUser")

    def test_user_list_and_dashboard_views(self):
        """Test user list page and dashboard pages."""
        res_home = self.client.get(reverse("user:home"))
        self.assertEqual(res_home.status_code, 200)

        res_fetch = self.client.get(reverse("user:fetch"))
        self.assertEqual(res_fetch.status_code, 200)

        res_dash = self.client.get(reverse("user:dashboard"))
        self.assertEqual(res_dash.status_code, 200)

        res_dash_fetch = self.client.get(reverse("user:dashboard_fetch"))
        self.assertEqual(res_dash_fetch.status_code, 200)

    def test_user_detail_and_status_views(self):
        """Test user detail page and status change endpoint."""
        res_detail = self.client.get(reverse("user:detail", kwargs={"pk": self.test_user.pk}))
        self.assertEqual(res_detail.status_code, 200)

        res_status = self.client.post(
            reverse("user:change_status", kwargs={"user_id": self.test_user.pk}),
            {"is_active": "false"},
        )
        self.assertEqual(res_status.status_code, 302)
        self.test_user.refresh_from_db()
        self.assertFalse(self.test_user.is_active)

    def test_salary_and_transaction_creation_views(self):
        """Test salary and transaction create views."""
        res_salary = self.client.post(
            reverse("user:salary_create", kwargs={"user_id": self.test_user.pk}),
            {
                "amount": "12000.00",
                "commission": "on",
                "effective_from": "2026-08-03 12:00:00",
            },
        )
        self.assertEqual(res_salary.status_code, 302)
        self.assertTrue(self.test_user.salaries.exists())

        res_txn = self.client.post(
            reverse("user:transaction_create", kwargs={"user_id": self.test_user.pk}),
            {
                "transaction_type": "SALARY",
                "amount": "500.00",
                "payment_method": "CASH",
                "description": "Performance bonus",
                "date": "2026-08-03 12:00:00",
            },
        )
        self.assertEqual(res_txn.status_code, 302)
