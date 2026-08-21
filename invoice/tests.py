"""
Tests for the invoice app services: ReturnInvoiceService.approve/process
and InvoiceCancellationService.cancel.

Replaces the placeholder tests.py.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from invoice.services import ReturnInvoiceService, InvoiceCancellationService
from invoice.choices import RefundStatusChoices, PaymentTypeChoices, PaymentStatusChoices
from invoice.models import ReturnInvoice
from Billing.tests.helpers import (
    create_test_user,
    create_test_customer,
    create_test_invoice,
    create_test_variant,
)


class ReturnInvoiceServiceTests(TestCase):
    """Tests for ReturnInvoiceService.approve() and .process()."""

    def setUp(self):
        self.user = create_test_user(is_staff=True)
        self.customer = create_test_customer(created_by=self.user)
        self.invoice = create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            amount=Decimal("1000.00"),
            payment_type="CASH",
            payment_status="PAID",
        )
        self.return_inv = ReturnInvoice.objects.create(
            invoice=self.invoice,
            customer=self.customer,
            total_amount=Decimal("500.00"),
            status=RefundStatusChoices.PENDING,
            created_by=self.user,
        )

    def test_approve_changes_status(self):
        ReturnInvoiceService.approve(self.return_inv, self.user)
        self.return_inv.refresh_from_db()
        self.assertEqual(self.return_inv.status, RefundStatusChoices.APPROVED)
        self.assertEqual(self.return_inv.approved_by, self.user)
        self.assertIsNotNone(self.return_inv.approved_date)

    def test_approve_non_pending_raises(self):
        self.return_inv.status = RefundStatusChoices.APPROVED
        self.return_inv.save()
        with self.assertRaises(ValidationError) as ctx:
            ReturnInvoiceService.approve(self.return_inv, self.user)
        self.assertIn("Only pending returns", str(ctx.exception))

    def test_process_changes_status(self):
        self.return_inv.status = RefundStatusChoices.APPROVED
        self.return_inv.save()
        ReturnInvoiceService.process(self.return_inv, self.user)
        self.return_inv.refresh_from_db()
        self.assertEqual(self.return_inv.status, RefundStatusChoices.COMPLETED)
        self.assertEqual(self.return_inv.processed_by, self.user)

    def test_process_non_approved_raises(self):
        with self.assertRaises(ValidationError) as ctx:
            ReturnInvoiceService.process(self.return_inv, self.user)
        self.assertIn("approved", str(ctx.exception).lower())

    def test_process_completed_raises(self):
        self.return_inv.status = RefundStatusChoices.COMPLETED
        self.return_inv.save()
        with self.assertRaises(ValidationError):
            ReturnInvoiceService.process(self.return_inv, self.user)


class InvoiceCancellationServiceTests(TestCase):
    """Tests for InvoiceCancellationService.cancel()."""

    def setUp(self):
        self.user = create_test_user(is_staff=True)
        self.customer = create_test_customer(created_by=self.user)
        self.variant = create_test_variant(
            purchase_price=Decimal("100.00"),
            mrp=Decimal("180.00"),
            quantity=Decimal("50"),
            user=self.user,
        )
        from inventory.services import InventoryService
        InventoryService.create_initial_log(self.variant, user=self.user)

    def _make_cancellable_invoice(self, **extra):
        from invoice.models import InvoiceItem
        inv = create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            amount=Decimal("1800.00"),
            payment_type="CASH",
            payment_status="PAID",
        )
        InvoiceItem.objects.create(
            invoice=inv,
            product_variant=self.variant,
            quantity=Decimal("10"),
            unit_price=Decimal("180.00"),
            mrp=Decimal("180.00"),
            purchase_price=Decimal("100.00"),
        )
        return inv

    def test_cancel_marks_invoice_cancelled(self):
        inv = self._make_cancellable_invoice()
        success, msg = InvoiceCancellationService.cancel(inv, self.user, "Test cancel")
        self.assertTrue(success)
        inv.refresh_from_db()
        self.assertTrue(inv.is_cancelled)

    def test_cancel_restores_inventory(self):
        inv = self._make_cancellable_invoice()
        InvoiceCancellationService.cancel(inv, self.user, "Test cancel")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.quantity, Decimal("60"))

    def test_cancel_creates_audit_record(self):
        inv = self._make_cancellable_invoice()
        from invoice.models import InvoiceCancellation
        InvoiceCancellationService.cancel(inv, self.user, "Defective items")
        self.assertTrue(
            InvoiceCancellation.objects.filter(invoice=inv).exists()
        )

    def test_cancel_returns_false_for_uncancellable(self):
        inv = self._make_cancellable_invoice()
        InvoiceCancellationService.cancel(inv, self.user, "First cancel")
        inv.refresh_from_db()
        success, msg = InvoiceCancellationService.cancel(inv, self.user, "Second cancel")
        self.assertFalse(success)


class ReturnInvoiceFetchViewTests(TestCase):
    """Tests for fetch_return_invoices AJAX view with date search and filters."""

    def setUp(self):
        from django.contrib.auth.models import Permission
        from django.utils import timezone
        from datetime import timedelta

        self.user = create_test_user(is_staff=True)
        # Grant view_returninvoice permission
        perm = Permission.objects.get(codename="view_returninvoice")
        self.user.user_permissions.add(perm)
        self.client.force_login(self.user)

        self.customer = create_test_customer(created_by=self.user)
        self.invoice = create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            amount=Decimal("1000.00"),
            payment_type="CASH",
            payment_status="PAID",
        )

        now = timezone.now()
        # Create return invoice 1 (today)
        self.return_inv1 = ReturnInvoice.objects.create(
            invoice=self.invoice,
            customer=self.customer,
            return_number="RET-001",
            total_amount=Decimal("300.00"),
            status=RefundStatusChoices.PENDING,
            created_by=self.user,
            return_date=now,
            financial_year="26-27",
        )
        # Create return invoice 2 (30 days ago)
        self.return_inv2 = ReturnInvoice.objects.create(
            invoice=self.invoice,
            customer=self.customer,
            return_number="RET-002",
            total_amount=Decimal("200.00"),
            status=RefundStatusChoices.APPROVED,
            created_by=self.user,
            return_date=now - timedelta(days=30),
            financial_year="25-26",
        )

    def test_fetch_all_returns(self):
        from django.urls import reverse
        response = self.client.get(reverse("invoice:fetch_return_invoices"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("RET-001", data.get("html"))
        self.assertIn("RET-002", data.get("html"))

    def test_fetch_with_date_preset_today(self):
        from django.urls import reverse
        response = self.client.get(
            reverse("invoice:fetch_return_invoices"),
            {"date_filter": "today"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("RET-001", data.get("html"))
        self.assertNotIn("RET-002", data.get("html"))

    def test_fetch_with_custom_date_range(self):
        from django.urls import reverse
        from django.utils import timezone
        from datetime import timedelta
        
        d_from = (timezone.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        d_to = (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        response = self.client.get(
            reverse("invoice:fetch_return_invoices"),
            {"date_filter": "custom", "date_from": d_from, "date_to": d_to},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("RET-001", data.get("html"))
        self.assertNotIn("RET-002", data.get("html"))

    def test_fetch_with_financial_year(self):
        from django.urls import reverse
        response = self.client.get(
            reverse("invoice:fetch_return_invoices"),
            {"financial_year": "25-26"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("RET-002", data.get("html"))
        self.assertNotIn("RET-001", data.get("html"))

