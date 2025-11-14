from email.policy import default
from django.db import models
from django.conf import settings
from base.utility import StringProcessor
from base.manager import SoftDeleteModel, phone_regex
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum, F, ExpressionWrapper, DecimalField, Value
from django.db.models.functions import Coalesce
from django.utils.functional import cached_property

User = settings.AUTH_USER_MODEL

class Customer(SoftDeleteModel):
    """Customer model for storing customer information."""

    name = models.CharField(
        max_length=255, null=True, blank=True, help_text="Customer's full name"
    )
    phone_number = models.CharField(
        max_length=20,
        unique=True,
        validators=[phone_regex],
        help_text="Customer's phone number (unique)",
    )
    email = models.EmailField(
        blank=True, null=True, help_text="Customer's email address"
    )
    address = models.TextField(blank=True, null=True, help_text="Customer's address")
    store_credit_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Customer's store credit balance",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
        help_text="User who created this customer record",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Referral linkage: which customer referred this customer
    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
        help_text="Referring customer (who brought this customer)",
    )

    def __str__(self):
        """Return a string representation of the customer."""
        name_part = self.name or "Unknown"
        phone_part = self.phone_number or "No Phone"

        if self.address:
            return f"{name_part} ({self.address}) {phone_part}"
        return f"{name_part} {phone_part}"

    @property
    def display_name(self):
        """Return formatted display name."""
        return self.name or "Unknown Customer"

    @property
    def short_address(self):
        """Return shortened address for display."""
        if not self.address:
            return "No Address"
        return self.address[:50] + "..." if len(self.address) > 50 else self.address

    @property
    def has_credit(self):
        """Check if customer has store credit."""
        return self.store_credit_balance > 0

    @property
    def credit_status(self):
        """Return credit status as string."""
        if self.store_credit_balance > 0:
            return f"Credit: ₹{self.store_credit_balance}"
        return "No Credit"

    @cached_property
    def credit_amount(self):
        # Sum of amounts for this customer's CREDIT invoices
        try:
            from invoice.models import Invoice

            credit_qs = self.invoices.filter(payment_type=Invoice.PaymentType.CREDIT)
        except Exception:
            # Fallback without importing to avoid circular import issues
            credit_qs = self.invoices.filter(payment_type="CREDIT")

        net_expr = ExpressionWrapper(
            F("amount") - F("discount_amount") - F("advance_amount"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        invoices_total = credit_qs.aggregate(
            total=Coalesce(Sum(net_expr), Value(Decimal("0")))
        )["total"]

        credit_payment_total = self.credit_payment.filter(
            payment_type=Payment.PaymentType.Purchased
        ).aggregate(total=Coalesce(Sum("amount"), Value(Decimal("0"))))["total"]

        return invoices_total + credit_payment_total

    @cached_property
    def debit_amount(self):
        debit_payment_total = self.credit_payment.filter(
            payment_type=Payment.PaymentType.Paid
        ).aggregate(total=Coalesce(Sum("amount"), Value(Decimal("0"))))["total"]
        return debit_payment_total

    @cached_property
    def balance_amount(self):
        return self.credit_amount - self.debit_amount

    @cached_property
    def last_date(self):
        from invoice.models import Invoice

        credit_qs = self.invoices.filter(
            payment_type=Invoice.PaymentType.CREDIT
        ).order_by("invoice_date")
        if credit_qs.exists():
            for invoice in credit_qs:
                if not invoice.amount_cleared:
                    return invoice.invoice_date if not None else invoice.invoice_date
        return None

    def add_credit(self, amount):
        """Add credit to customer's balance."""
        if amount > 0:
            self.store_credit_balance += amount
            self.save(update_fields=["store_credit_balance", "updated_at"])

    def deduct_credit(self, amount):
        """Deduct credit from customer's balance."""
        if amount > 0 and self.store_credit_balance >= amount:
            self.store_credit_balance -= amount
            self.save(update_fields=["store_credit_balance", "updated_at"])
            return True
        return False

    class Meta:
        indexes = [
            models.Index(fields=["name"], name="customer_name_idx"),
            models.Index(fields=["phone_number"], name="customer_phone_number_idx"),
            models.Index(fields=["created_at"], name="customer_created_at_idx"),
            models.Index(fields=["store_credit_balance"], name="customer_credit_idx"),
            models.Index(fields=["referred_by"], name="customer_referred_by_idx"),
        ]
        ordering = ["-created_at"]
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def save(self, *args, **kwargs):
        """Override save method to clean and format data."""
        self.phone_number = StringProcessor(self.phone_number).cleaned_string
        self.name = StringProcessor(self.name).toTitle()
        self.email = StringProcessor(self.email).toLowercase()
        self.address = StringProcessor(self.address).toTitle()

        super().save(*args, **kwargs)

    def clean(self):
        """Custom validation."""
        # Ensure phone number is not empty
        if not self.phone_number:
            raise ValidationError("Phone number is required.")

        # Validate email format if provided
        if self.email and "@" not in self.email:
            raise ValidationError("Please enter a valid email address.")

        # Prevent setting self as referrer
        if self.pk and self.referred_by_id == self.pk:
            raise ValidationError("A customer cannot refer themselves.")


class Payment(SoftDeleteModel):
    class PaymentType(models.TextChoices):
        Paid = "PAID", "Paid"
        Purchased = "PURCHASED", "Purchased"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
        UPI = "UPI", "UPI"
        CHEQUE = "CHEQUE", "Cheque"
        CREDIT_CARD = "CREDIT_CARD", "Credit Card"
        DEBIT_CARD = "DEBIT_CARD", "Debit Card"
        ONLINE_PAYMENT = "ONLINE_PAYMENT", "Online Payment"

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="credit_payment"
    )
    payment_type = models.TextField(
        max_length=20, choices=PaymentType.choices, default=PaymentType.Paid
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Enter the Amount",
    )
    method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        help_text="Payment method used",
    )
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Bank transaction reference number.",
    )
    unallocated_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Amount not yet allocated to invoices",
    )

    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="credit_payment",
    )
    payment_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.unallocated_amount = self.amount
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.customer} - ₹{self.amount} ({self.get_payment_type_display()}) via {self.get_method_display()}"
