"""
Mixins for Invoice models to organize related functionality
"""

from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class InvoiceFinancialMixin:
    """Mixin containing all financial calculation properties and methods for Invoice"""

    @property
    def total_payable(self):
        """Total amount customer owes after discount"""
        return self.amount - self.discount_amount

    @property
    def net_amount_due(self):
        """Amount still owed after advance payments"""
        return self.total_payable - self.advance_amount

    @property
    def remaining_amount(self):
        """Final amount still owed by customer"""
        return self.net_amount_due - self.paid_amount

    @property
    def amount_cleared(self):
        """Amount cleared from customer"""
        return True if self.remaining_amount <= 0 else False

    @property
    def total_received(self):
        """Total amount received from customer (advance + payments)"""
        return self.advance_amount + self.paid_amount

    @property
    def is_fully_paid(self):
        """Check if invoice is fully paid"""
        return self.remaining_amount <= 0

    @property
    def is_overdue(self):
        """Check if credit invoice is overdue"""
        if self.payment_type == "CREDIT" and self.due_date and not self.is_fully_paid:
            return timezone.now().date() > self.due_date.date()
        return False

    def _update_payment_status(self):
        """Internal method to update payment status"""
        if self.total_received >= self.total_payable:
            self.payment_status = "PAID"
        elif self.total_received > 0:
            self.payment_status = "PARTIALLY_PAID"
        else:
            self.payment_status = "UNPAID"

    def update_payment_status(self):
        """Public method to update payment status and save"""
        self._update_payment_status()
        self.save(update_fields=["payment_status"])

    @transaction.atomic
    def make_payment(self, amount, payment_method=None):
        """Add a payment to this invoice with proper transaction handling"""
        if amount <= 0:
            raise ValidationError("Payment amount must be positive")

        if amount > self.remaining_amount:
            raise ValidationError("Payment amount exceeds remaining balance")

        # Refresh from database to avoid race conditions
        self.refresh_from_db()

        self.paid_amount += Decimal(str(amount))
        if payment_method:
            self.payment_method = payment_method

        self.save()
        return self.remaining_amount

    ## calculation for the invoice
    @property
    def get_total_quantity(self):
        """Total quantity for the invoice"""
        return self.invoice_items.aggregate(total_quantity=Sum("quantity"))[
            "total_quantity"
        ]

    @property
    def total_tax_value(self):
        """Total tax value (sum of tax_value from all invoice items)"""
        total = Decimal("0.00")
        for item in self.invoice_items.all():
            total += Decimal(str(item.tax_value))
        return round(total, 2)

    @property
    def total_gst_amount(self):
        """Total GST amount (sum of gst_amount from all invoice items)"""
        total = Decimal("0.00")
        for item in self.invoice_items.all():
            total += Decimal(str(item.gst_amount))
        return round(total, 2)

    @property
    def tax_values_by_gst(self):
        """
        Calculate tax values grouped by GST rate
        """
        gst_groups = defaultdict(
            lambda: {"tax_value": Decimal("0.00"), "total_tax_value": Decimal("0.00")}
        )

        for item in self.invoice_items.all():
            gst_rate = item.gst_percentage
            gst_groups[gst_rate]["tax_value"] += Decimal(str(item.tax_value))
            gst_groups[gst_rate]["total_tax_value"] += Decimal(str(item.gst_amount))

        data = {
            "details": {
                gst: {
                    "tax_value": round(values["tax_value"], 2),
                    "total_tax_value": round(values["total_tax_value"], 2),
                }
                for gst, values in gst_groups.items()
            }
        }
        return data


class InvoiceItemFinancialMixin:
    """Mixin containing all financial calculation properties for InvoiceItem"""

    @property
    def amount(self):
        return self.quantity * self.unit_price

    @property
    def discount_amount_per_unit(self):
        """Discount amount per unit"""
        return self.mrp - self.unit_price

    @property
    def total_discount_amount(self):
        """Total discount amount for this line item"""
        return self.discount_amount_per_unit * self.quantity

    @property
    def discount_share(self):
        """
        Proportional share of invoice-level discount for this stock item.
        """
        return (
            (Decimal(self.amount) / self.invoice.amount * self.invoice.discount_amount)
            if self.invoice.amount
            else Decimal(0)
        )

    @property
    def discounted_amount(self):
        """
        Amount after subtracting discount share.
        """
        return Decimal(self.amount) - self.discount_share

    @property
    def tax_value(self):
        return self.discounted_amount / (1 + self.gst_percentage / 100)

    @property
    def gst_amount(self):
        """
        GST amount (total of CGST + SGST or IGST).
        """
        return round(self.discounted_amount - self.tax_value, 2)

    # @property
    # def cgst(self):
    #     return round(self.gst_amount / 2, 2)

    # @property
    # def get_gst_percentage(self):
    #     """Total amount for this line item"""
    #     if self.invoice.invoice_type == "IGST":
    #         return self.gst_percentage
    #     elif self.invoice.invoice_type == "CGST_SGST":
    #         return self.gst_percentage / 2
    #     return Decimal("0")

    # @property
    # def discount_percentage(self):
    #     """Discount percentage based on MRP vs Selling Price"""
    #     logger.debug(f"Discount percentage: {((self.mrp - self.unit_price) / self.mrp) * 100}")
    #     if self.mrp > 0:
    #         return ((self.mrp - self.unit_price) / self.mrp) * 100
    #     return Decimal("0")

    # @property
    # def gross_amount(self):
    #     """Total at MRP (before discount)"""
    #     logger.debug(f"Gross amount: {self.quantity * self.mrp}")
    #     return self.quantity * self.mrp

    # @property
    # def tax_rate(self):
    #     """Get tax rate from product"""
    #     return self.get_gst_percentage

    # @property
    # def calculated_tax_amount(self):
    #     """Tax amount based on net amount and product tax rate"""
    #     if self.tax_rate > 0:
    #         return (self.net_amount * self.tax_rate) / 100
    #     return Decimal("0")

    # @property
    # def total_amount(self):
    #     """Final total including tax"""
    #     return self.net_amount + self.calculated_tax_amount

    # @property
    # def profit_amount_per_unit(self):
    #     """Profit per unit"""
    #     return self.unit_price - self.purchase_price

    # @property
    # def total_profit(self):
    #     """Total profit for this line item"""
    #     return self.profit_amount_per_unit * self.quantity

    # @property
    # def profit_margin_percentage(self):
    #     """Profit margin as percentage of selling price"""
    #     if self.unit_price > 0:
    #         return (self.profit_amount_per_unit / self.unit_price) * 100
    #     return Decimal("0")

    # @property
    # def markup_percentage(self):
    #     """Markup percentage on purchase price"""
    #     if self.purchase_price > 0:
    #         return (self.profit_amount_per_unit / self.purchase_price) * 100
    #     return Decimal("0")

    ## calculation for tax values


class InvoiceValidationMixin:
    """Mixin containing validation methods for Invoice"""

    def validate_financial_amounts(self):
        """Validate all financial amounts"""
        # Validate discount doesn't exceed amount
        if self.discount_amount and self.discount_amount > self.amount:
            raise ValidationError("Discount amount cannot exceed invoice amount")

        if self.discount_amount and self.discount_amount < 0:
            raise ValidationError("Discount amount cannot be negative")

        # Validate advance amount
        if self.advance_amount and self.advance_amount < 0:
            raise ValidationError("Advance amount cannot be negative")

        # Validate advance amount for credit invoices
        if self.payment_type == "CREDIT":
            if self.advance_amount and self.advance_amount > self.total_payable:
                raise ValidationError(
                    {
                        "advance_amount": "Advance amount cannot exceed total payable amount"
                    }
                )

        # Validate due date for credit invoices
        if (
            self.payment_type == "CREDIT"
            and self.due_date
            and self.due_date.date() <= self.invoice_date.date()
        ):
            raise ValidationError(
                "Due date must be after invoice date for credit invoices"
            )

        # Validate payment method for cash invoices
        if self.payment_type == "CASH" and self.payment_method in ["CASH_ON_DELIVERY"]:
            raise ValidationError("Cash on Delivery is not valid for cash invoices")


class InvoiceItemValidationMixin:
    """Mixin containing validation methods for InvoiceItem"""

    def validate_item_amounts(self):
        """Validate all item amounts"""
        # Validate unit price doesn't exceed MRP
        if self.unit_price and self.mrp and self.unit_price > self.mrp:
            raise ValidationError("Unit price cannot exceed MRP")

        # Validate quantity is positive
        if self.quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")

        # Validate prices are non-negative
        if self.unit_price < 0:
            raise ValidationError("Unit price cannot be negative")

        if self.mrp < 0:
            raise ValidationError("MRP cannot be negative")

        if self.purchase_price < 0:
            raise ValidationError("Purchase price cannot be negative")
