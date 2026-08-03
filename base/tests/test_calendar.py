from decimal import Decimal
import datetime
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils import timezone

from base.views import CalendarView
from customer.models import Customer
from invoice.models import Invoice

User = get_user_model()


class CalendarViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            first_name="Test",
            phone_number="9876543210",
            password="password123"
        )
        perm = Permission.objects.get(codename="view_invoice")
        self.user.user_permissions.add(perm)

        self.customer = Customer.objects.create(
            name="Test Customer",
            phone_number="9876543210"
        )

    def test_calendar_view_context_data(self):
        now = timezone.now()

        Invoice.objects.create(
            sequence_no=1,
            customer=self.customer,
            invoice_number="INV-2026-001",
            amount=Decimal("1000.00"),
            discount_amount=Decimal("100.00"),
            paid_amount=Decimal("500.00"),
            sold_by=self.user,
            created_by=self.user,
            invoice_date=now
        )

        # Naive datetime
        Invoice.objects.create(
            sequence_no=2,
            customer=self.customer,
            invoice_number="INV-2026-002",
            amount=Decimal("500.00"),
            discount_amount=Decimal("50.00"),
            paid_amount=Decimal("450.00"),
            sold_by=self.user,
            created_by=self.user,
            invoice_date=datetime.datetime.now()
        )

        request = self.factory.get(f"/calendar/?year={now.year}&month={now.month}")
        request.user = self.user

        view = CalendarView()
        view.setup(request)
        context = view.get_context_data()

        self.assertIn("month_kpi", context)
        self.assertEqual(context["month_kpi"]["total_billing"], 1350.0)
        self.assertEqual(context["month_kpi"]["total_invoices"], 2)
        self.assertEqual(context["month_kpi"]["paid_amount"], 1350.0)
        self.assertEqual(context["month_kpi"]["pending_amount"], 0.0)
