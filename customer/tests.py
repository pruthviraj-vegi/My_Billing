"""Tests for the customer app."""

import datetime
from decimal import Decimal

from django.test import TestCase

from customer.services import CustomerPaymentService
from customer.models import Customer, Payment
from invoice.models import Invoice
from invoice.choices import PaymentTypeChoices, PaymentStatusChoices
from Billing.tests.helpers import (
    create_test_user,
    create_test_customer,
    create_test_invoice,
    create_test_payment,
)


class ShouldReallocatePaymentTests(TestCase):
    """Tests for CustomerPaymentService.should_reallocate_payment()."""

    def setUp(self):
        self.user = create_test_user()
        self.customer = create_test_customer(created_by=self.user)
        self.payment = create_test_payment(
            customer=self.customer,
            amount=Decimal("1000.00"),
            created_by=self.user,
        )

    def test_created_returns_true(self):
        result = CustomerPaymentService.should_reallocate_payment(
            self.payment, old_amount=None, old_is_deleted=None,
            old_payment_type=None, created=True,
        )
        self.assertTrue(result)

    def test_amount_changed_returns_true(self):
        result = CustomerPaymentService.should_reallocate_payment(
            self.payment, old_amount=Decimal("500.00"), old_is_deleted=False,
            old_payment_type=self.payment.payment_type, created=False,
        )
        self.assertTrue(result)

    def test_is_deleted_changed_returns_true(self):
        self.payment.is_deleted = True
        self.payment.save()
        result = CustomerPaymentService.should_reallocate_payment(
            self.payment, old_amount=self.payment.amount, old_is_deleted=False,
            old_payment_type=self.payment.payment_type, created=False,
        )
        self.assertTrue(result)

    def test_payment_type_changed_returns_true(self):
        result = CustomerPaymentService.should_reallocate_payment(
            self.payment, old_amount=self.payment.amount, old_is_deleted=self.payment.is_deleted,
            old_payment_type=Payment.PaymentType.Purchased, created=False,
        )
        self.assertTrue(result)

    def test_no_change_returns_false(self):
        result = CustomerPaymentService.should_reallocate_payment(
            self.payment, old_amount=self.payment.amount, old_is_deleted=self.payment.is_deleted,
            old_payment_type=self.payment.payment_type, created=False,
        )
        self.assertFalse(result)


class ShouldReallocateInvoiceTests(TestCase):
    """Tests for CustomerPaymentService.should_reallocate_invoice()."""

    def setUp(self):
        self.user = create_test_user()
        self.customer = create_test_customer(created_by=self.user)

    def _make_invoice(self, **kwargs):
        return create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            payment_type="CREDIT",
            payment_status="UNPAID",
            amount=Decimal("5000.00"),
            **kwargs,
        )

    def test_created_returns_true(self):
        invoice = self._make_invoice()
        result = CustomerPaymentService.should_reallocate_invoice(
            invoice, old_values={}, created=True,
        )
        self.assertEqual(result, (True, None))

    def test_amount_changed_returns_true(self):
        invoice = self._make_invoice()
        old_values = {
            "payment_type": PaymentTypeChoices.CREDIT,
            "amount": Decimal("3000.00"),
            "discount_amount": Decimal("0"),
            "advance_amount": Decimal("0"),
            "customer": self.customer,
        }
        result = CustomerPaymentService.should_reallocate_invoice(
            invoice, old_values, created=False,
        )
        self.assertEqual(result, (True, None))

    def test_discount_changed_returns_true(self):
        invoice = self._make_invoice()
        old_values = {
            "payment_type": PaymentTypeChoices.CREDIT,
            "amount": Decimal("5000.00"),
            "discount_amount": Decimal("100.00"),
            "advance_amount": Decimal("0"),
            "customer": self.customer,
        }
        result = CustomerPaymentService.should_reallocate_invoice(
            invoice, old_values, created=False,
        )
        self.assertEqual(result, (True, None))

    def test_advance_changed_returns_true(self):
        invoice = self._make_invoice()
        old_values = {
            "payment_type": PaymentTypeChoices.CREDIT,
            "amount": Decimal("5000.00"),
            "discount_amount": Decimal("0"),
            "advance_amount": Decimal("200.00"),
            "customer": self.customer,
        }
        result = CustomerPaymentService.should_reallocate_invoice(
            invoice, old_values, created=False,
        )
        self.assertEqual(result, (True, None))

    def test_customer_changed_returns_true_and_old_customer(self):
        invoice = self._make_invoice()
        old_customer = create_test_customer(created_by=self.user)
        old_values = {
            "payment_type": PaymentTypeChoices.CREDIT,
            "amount": Decimal("5000.00"),
            "discount_amount": Decimal("0"),
            "advance_amount": Decimal("0"),
            "customer": old_customer,
        }
        result = CustomerPaymentService.should_reallocate_invoice(
            invoice, old_values, created=False,
        )
        self.assertEqual(result, (True, old_customer))

    def test_payment_type_changed_from_cash_to_credit_returns_true(self):
        invoice = self._make_invoice()
        old_values = {
            "payment_type": PaymentTypeChoices.CASH,
            "amount": Decimal("5000.00"),
            "discount_amount": Decimal("0"),
            "advance_amount": Decimal("0"),
            "customer": self.customer,
        }
        result = CustomerPaymentService.should_reallocate_invoice(
            invoice, old_values, created=False,
        )
        self.assertEqual(result, (True, None))

    def test_payment_type_changed_from_credit_to_cash_returns_true(self):
        self.customer2 = create_test_customer(created_by=self.user)
        invoice = create_test_invoice(
            customer=self.customer2,
            sold_by=self.user,
            created_by=self.user,
            payment_type="CASH",
            payment_status="PAID",
            amount=Decimal("5000.00"),
        )
        old_values = {
            "payment_type": PaymentTypeChoices.CREDIT,
            "amount": Decimal("5000.00"),
            "discount_amount": Decimal("0"),
            "advance_amount": Decimal("0"),
            "customer": self.customer2,
        }
        result = CustomerPaymentService.should_reallocate_invoice(
            invoice, old_values, created=False,
        )
        self.assertEqual(result, (True, None))

    def test_no_change_cash_invoice_returns_false(self):
        self.customer2 = create_test_customer(created_by=self.user)
        invoice = create_test_invoice(
            customer=self.customer2,
            sold_by=self.user,
            created_by=self.user,
            payment_type="CASH",
            payment_status="PAID",
            amount=Decimal("5000.00"),
        )
        old_values = {
            "payment_type": PaymentTypeChoices.CASH,
            "amount": Decimal("5000.00"),
            "discount_amount": Decimal("0"),
            "advance_amount": Decimal("0"),
            "customer": self.customer2,
        }
        result = CustomerPaymentService.should_reallocate_invoice(
            invoice, old_values, created=False,
        )
        self.assertEqual(result, (False, None))

    def test_no_change_credit_invoice_returns_false(self):
        invoice = self._make_invoice()
        old_values = {
            "payment_type": PaymentTypeChoices.CREDIT,
            "amount": Decimal("5000.00"),
            "discount_amount": Decimal("0"),
            "advance_amount": Decimal("0"),
            "customer": self.customer,
        }
        result = CustomerPaymentService.should_reallocate_invoice(
            invoice, old_values, created=False,
        )
        self.assertEqual(result, (False, None))


class ReallocateTests(TestCase):
    """Tests for CustomerPaymentService.reallocate() — FIFO payment allocation."""

    def setUp(self):
        self.user = create_test_user()
        self.customer = create_test_customer(created_by=self.user)

    def _make_credit_invoice(self, amount=Decimal("5000.00"), date=None):
        inv = create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            payment_type="CREDIT",
            payment_status="UNPAID",
            amount=amount,
        )
        if date:
            Invoice.objects.filter(id=inv.id).update(invoice_date=date)
        return inv

    def _make_payment(self, amount=Decimal("3000.00"), payment_type="PAID", date=None):
        payment = Payment.objects.create(
            customer=self.customer,
            amount=amount,
            payment_type=payment_type,
            created_by=self.user,
            method=Payment.PaymentMethod.CASH,
            unallocated_amount=amount,
        )
        if date:
            Payment.objects.filter(id=payment.id).update(payment_date=date)
        return payment

    def test_reallocate_fully_pays_single_invoice(self):
        inv = self._make_credit_invoice(amount=Decimal("3000.00"))
        self._make_payment(amount=Decimal("3000.00"))

        CustomerPaymentService.reallocate(self.customer)

        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal("3000.00"))
        self.assertEqual(inv.payment_status, PaymentStatusChoices.PAID)

    def test_reallocate_partially_pays_invoice(self):
        inv = self._make_credit_invoice(amount=Decimal("5000.00"))
        self._make_payment(amount=Decimal("3000.00"))

        CustomerPaymentService.reallocate(self.customer)

        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal("3000.00"))
        self.assertEqual(inv.payment_status, PaymentStatusChoices.PARTIALLY_PAID)

    def test_reallocate_fifo_pays_oldest_first(self):
        old_inv = self._make_credit_invoice(
            amount=Decimal("3000.00"),
            date=datetime.datetime(2024, 1, 15),
        )
        new_inv = self._make_credit_invoice(
            amount=Decimal("3000.00"),
            date=datetime.datetime(2024, 2, 15),
        )
        self._make_payment(amount=Decimal("4000.00"))

        CustomerPaymentService.reallocate(self.customer)

        old_inv.refresh_from_db()
        new_inv.refresh_from_db()
        self.assertEqual(old_inv.payment_status, PaymentStatusChoices.PAID)
        self.assertEqual(old_inv.paid_amount, Decimal("3000.00"))
        self.assertEqual(new_inv.paid_amount, Decimal("1000.00"))
        self.assertEqual(new_inv.payment_status, PaymentStatusChoices.PARTIALLY_PAID)

    def test_reallocate_no_payments_resets_invoices(self):
        inv = self._make_credit_invoice(amount=Decimal("3000.00"))
        inv.paid_amount = Decimal("1000.00")
        inv.payment_status = PaymentStatusChoices.PARTIALLY_PAID
        inv.save()

        CustomerPaymentService.reallocate(self.customer)

        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal("0"))
        self.assertEqual(inv.payment_status, PaymentStatusChoices.UNPAID)

    def test_reallocate_multiple_payments(self):
        inv = self._make_credit_invoice(amount=Decimal("10000.00"))
        self._make_payment(amount=Decimal("3000.00"))
        self._make_payment(amount=Decimal("4000.00"))

        CustomerPaymentService.reallocate(self.customer)

        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal("7000.00"))
        self.assertEqual(inv.payment_status, PaymentStatusChoices.PARTIALLY_PAID)

    def test_reallocate_purchased_payment_item(self):
        inv = self._make_credit_invoice(
            amount=Decimal("5000.00"),
            date=datetime.datetime(2024, 1, 10),
        )
        self._make_payment(
            amount=Decimal("2000.00"),
            payment_type="PURCHASED",
            date=datetime.datetime(2024, 1, 5),
        )
        self._make_payment(
            amount=Decimal("7000.00"),
            payment_type="PAID",
            date=datetime.datetime(2024, 1, 20),
        )

        CustomerPaymentService.reallocate(self.customer)

        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal("5000.00"))
        self.assertEqual(inv.payment_status, PaymentStatusChoices.PAID)

    def test_reallocate_with_discount(self):
        inv = self._make_credit_invoice(amount=Decimal("5000.00"))
        inv.discount_amount = Decimal("500.00")
        inv.save()
        self._make_payment(amount=Decimal("4500.00"))

        CustomerPaymentService.reallocate(self.customer)

        inv.refresh_from_db()
        self.assertEqual(inv.paid_amount, Decimal("4500.00"))
        self.assertEqual(inv.payment_status, PaymentStatusChoices.PAID)


class GetOpeningBalanceTests(TestCase):
    """Tests for get_opening_balance() from customer/views_credit.py."""

    def setUp(self):
        from django.utils import timezone as tz
        self.user = create_test_user()
        self.customer = create_test_customer(created_by=self.user)

    def test_no_transactions_returns_zero(self):
        from customer.views_credit import get_opening_balance
        balance = get_opening_balance(self.customer)
        self.assertEqual(balance, Decimal("0"))

    def test_opening_balance_includes_credit_invoices(self):
        import datetime
        from customer.views_credit import get_opening_balance

        inv = create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            payment_type="CREDIT",
            payment_status="UNPAID",
            amount=Decimal("5000.00"),
        )
        Invoice.objects.filter(id=inv.id).update(
            invoice_date=datetime.datetime(2024, 1, 15)
        )
        start = datetime.datetime(2024, 3, 1)
        balance = get_opening_balance(self.customer, start_date=start)
        self.assertEqual(balance, Decimal("5000.00"))

    def test_opening_balance_excludes_after_start_date(self):
        import datetime
        from customer.views_credit import get_opening_balance

        inv = create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            payment_type="CREDIT",
            payment_status="UNPAID",
            amount=Decimal("5000.00"),
        )
        Invoice.objects.filter(id=inv.id).update(
            invoice_date=datetime.datetime(2024, 3, 15)
        )
        start = datetime.datetime(2024, 3, 1)
        balance = get_opening_balance(self.customer, start_date=start)
        self.assertEqual(balance, Decimal("0"))

    def test_payment_reduces_opening_balance(self):
        import datetime
        from customer.views_credit import get_opening_balance

        inv = create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            payment_type="CREDIT",
            payment_status="UNPAID",
            amount=Decimal("5000.00"),
        )
        Invoice.objects.filter(id=inv.id).update(
            invoice_date=datetime.datetime(2024, 1, 15)
        )
        Payment.objects.create(
            customer=self.customer,
            amount=Decimal("2000.00"),
            payment_type="PAID",
            created_by=self.user,
            method=Payment.PaymentMethod.CASH,
            unallocated_amount=Decimal("0"),
        )
        Payment.objects.filter(customer=self.customer).update(
            payment_date=datetime.datetime(2024, 1, 20)
        )
        start = datetime.datetime(2024, 3, 1)
        balance = get_opening_balance(self.customer, start_date=start)
        self.assertEqual(balance, Decimal("3000.00"))


class BuildLedgerRowsTests(TestCase):
    """Tests for _build_ledger_rows() from customer/views_credit.py."""

    def setUp(self):
        self.user = create_test_user()
        self.customer = create_test_customer(created_by=self.user)

    def test_no_transactions_returns_empty(self):
        from customer.views_credit import _build_ledger_rows
        rows = _build_ledger_rows(self.customer)
        self.assertEqual(rows, [])

    def test_includes_credit_invoice(self):
        from customer.views_credit import _build_ledger_rows
        inv = create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            payment_type="CREDIT",
            payment_status="UNPAID",
            amount=Decimal("5000.00"),
        )
        rows = _build_ledger_rows(self.customer)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "Invoice")
        self.assertEqual(rows[0]["credit"], Decimal("5000.00"))

    def test_excludes_cash_invoice(self):
        from customer.views_credit import _build_ledger_rows
        create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            payment_type="CASH",
            payment_status="PAID",
            amount=Decimal("5000.00"),
        )
        rows = _build_ledger_rows(self.customer)
        self.assertEqual(rows, [])

    def test_includes_payment(self):
        from customer.views_credit import _build_ledger_rows
        Payment.objects.create(
            customer=self.customer,
            amount=Decimal("3000.00"),
            payment_type="PAID",
            created_by=self.user,
            method=Payment.PaymentMethod.CASH,
            unallocated_amount=Decimal("0"),
        )
        rows = _build_ledger_rows(self.customer)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "Paid")
        self.assertEqual(rows[0]["debit"], Decimal("3000.00"))

    def test_date_range_filter(self):
        import datetime
        from customer.views_credit import _build_ledger_rows

        inv = create_test_invoice(
            customer=self.customer,
            sold_by=self.user,
            created_by=self.user,
            payment_type="CREDIT",
            payment_status="UNPAID",
            amount=Decimal("5000.00"),
        )
        Invoice.objects.filter(id=inv.id).update(
            invoice_date=datetime.datetime(2024, 1, 15)
        )
        Payment.objects.create(
            customer=self.customer,
            amount=Decimal("3000.00"),
            payment_type="PAID",
            created_by=self.user,
            method=Payment.PaymentMethod.CASH,
            unallocated_amount=Decimal("0"),
        )
        Payment.objects.filter(customer=self.customer).update(
            payment_date=datetime.datetime(2024, 6, 15)
        )
        start = datetime.datetime(2024, 5, 1)
        end = datetime.datetime(2024, 12, 31)
        rows = _build_ledger_rows(self.customer, start_date=start, end_date=end)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "Paid")

    def test_purchased_payment_shows_as_credit(self):
        from customer.views_credit import _build_ledger_rows
        Payment.objects.create(
            customer=self.customer,
            amount=Decimal("2000.00"),
            payment_type="PURCHASED",
            created_by=self.user,
            method=Payment.PaymentMethod.CASH,
            unallocated_amount=Decimal("0"),
        )
        rows = _build_ledger_rows(self.customer)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "Purchased")
        self.assertEqual(rows[0]["credit"], Decimal("2000.00"))