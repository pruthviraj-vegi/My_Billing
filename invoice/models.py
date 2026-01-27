from django.db import models
from django.conf import settings
from decimal import Decimal
from customer.models import Customer, Payment
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from inventory.models import ProductVariant
from inventory.services import InventoryService
from base.utility import get_financial_year, StringProcessor
from base.manager import SoftDeleteModel
from django.db import transaction
from django.urls import reverse
from django.db.models import Sum
from inventory.models import GSTHsnCode

# Import organized components
from .choices import (
    GstTypeChoices,
    InvoiceTypeChoices,
    PaymentTypeChoices,
    PaymentStatusChoices,
    PaymentMethodChoices,
    AuditTypeChoices,
    AuditStatusChoices,
    ChangeTypeChoices,
    RefundTypeChoices,
    RefundStatusChoices,
    RefundReasonChoices,
    ItemConditionChoices,
    ItemReturnReasonChoices,
)
from .constraints import (
    InvoiceConstraints,
    InvoiceIndexes,
    InvoiceItemConstraints,
    AuditTableConstraints,
    InvoiceAuditConstraints,
    InvoiceSequenceConstraints,
)
from .managers import (
    InvoiceManager,
    InvoiceItemManager,
    AuditTableManager,
    InvoiceAuditManager,
    PaymentAllocationManager,
    ReturnInvoiceManager,
    ReturnInvoiceItemManager,
)
from .mixins import (
    InvoiceFinancialMixin,
    InvoiceItemFinancialMixin,
    InvoiceValidationMixin,
    InvoiceItemValidationMixin,
)

User = settings.AUTH_USER_MODEL


def get_next_sequence(invoice_type, financial_year):
    """Atomically return both sequence number and formatted invoice number"""
    with transaction.atomic():
        seq, _ = InvoiceSequence.objects.select_for_update().get_or_create(
            invoice_type=invoice_type,
            financial_year=financial_year,
            defaults={"last_number": 0},
        )
        seq.last_number += 1
        seq.save(update_fields=["last_number"])

        sequence_no = seq.last_number
        seq_str = str(sequence_no).zfill(3)

        if invoice_type == Invoice.Invoice_type.CASH:
            invoice_number = f"CASH/{financial_year}/{seq_str}"
        else:
            invoice_number = f"{financial_year}/{seq_str}"

        return sequence_no, invoice_number


class Invoice(InvoiceFinancialMixin, InvoiceValidationMixin, models.Model):
    """Main Invoice model with organized structure"""

    GstType = GstTypeChoices

    # Use imported choices
    Invoice_type = InvoiceTypeChoices
    PaymentType = PaymentTypeChoices
    PaymentStatus = PaymentStatusChoices
    PaymentMethod = PaymentMethodChoices

    sequence_no = models.PositiveIntegerField()  # strictly for ordering
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    cart_no = models.CharField(max_length=50, null=True, blank=True)
    invoice_number = models.CharField(
        max_length=50, unique=True
    )  # Remove null=True for auto-generation
    original_invoice_no = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Original invoice number before conversion",
    )
    invoice_type = models.CharField(
        max_length=20,
        choices=InvoiceTypeChoices.choices,
        default=InvoiceTypeChoices.GST,
    )
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentTypeChoices.choices,
        default=PaymentTypeChoices.CASH,
    )
    payment_status = models.CharField(
        max_length=25,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.UNPAID,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Total invoice amount before discount",
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Discount given to customer",
    )
    advance_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Amount received in advance (only for credit invoices)",
    )
    payment_method = models.CharField(
        max_length=25,
        choices=PaymentMethodChoices.choices,
        default=PaymentMethodChoices.CASH,
    )
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Amount paid against this invoice",
    )
    invoice_date = models.DateTimeField(default=timezone.now)
    financial_year = models.CharField(max_length=10, null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    sold_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="invoices_sold_by",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="invoices_created_by",
    )
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices_modified_by",
    )
    gst_type = models.CharField(
        max_length=20, choices=GstTypeChoices.choices, default=GstTypeChoices.CGST_SGST
    )

    # Cancellation tracking
    is_cancelled = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this invoice has been cancelled",
    )
    cancelled_at = models.DateTimeField(
        null=True, blank=True, help_text="When the invoice was cancelled"
    )
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices_cancelled_by",
        help_text="User who cancelled this invoice",
    )
    cancellation_reason = models.TextField(
        blank=True, null=True, help_text="Reason for cancellation"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Custom manager
    objects = InvoiceManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = InvoiceIndexes.get_all_indexes()
        constraints = InvoiceConstraints.get_all_constraints()

    def __str__(self):
        return self.invoice_number or f"Invoice-{self.id}"

    def clean(self):
        """Validate invoice data using mixin validation"""
        self.validate_financial_amounts()

    def save(self, *args, **kwargs):
        # Prevent modifications to cancelled invoices
        # Allow updates only for specific cancellation-related fields
        if self.pk and self.is_cancelled:
            # Check if we're only updating cancellation fields
            update_fields = kwargs.get("update_fields", [])
            allowed_fields = {
                "is_cancelled",
                "cancelled_at",
                "cancelled_by",
                "cancellation_reason",
                "payment_status",
                "updated_at",
            }

            # If update_fields is specified, check if all are allowed
            if update_fields and not set(update_fields).issubset(allowed_fields):
                raise ValidationError("Cannot modify a cancelled invoice")

            # If no update_fields specified and invoice exists, prevent modification
            if not update_fields:
                raise ValidationError("Cannot modify a cancelled invoice")

        # Automatically set advance_amount to 0 and mark as fully paid for cash invoices
        if self.payment_type == PaymentTypeChoices.CASH:
            self.advance_amount = Decimal("0")
            # Ensure paid_amount exactly matches the constraint calculation to avoid precision issues
            self.paid_amount = self.amount - self.discount_amount - self.advance_amount
            self.payment_status = PaymentStatusChoices.PAID
        else:
            self._update_payment_status()

        if not self.financial_year or self.financial_year != get_financial_year(
            self.invoice_date
        ):
            self.financial_year = get_financial_year(self.invoice_date)

        if not self.sequence_no or not self.invoice_number:
            self.sequence_no, self.invoice_number = get_next_sequence(
                self.invoice_type, self.financial_year
            )

        super().save(*args, **kwargs)

    def can_be_cancelled(self):
        """Check if invoice can be cancelled"""
        if self.is_cancelled:
            return False, "Invoice is already cancelled"

        # Add any other business rules here
        # For example: prevent cancellation after certain time period
        # from datetime import timedelta
        # if timezone.now() - self.created_at > timedelta(days=30):
        #     return False, "Cannot cancel invoices older than 30 days"

        return True, ""

    def cancel(self, user, reason):
        """
        Cancel this invoice and reverse all financial impacts.

        Args:
            user: User performing the cancellation
            reason: Reason for cancellation

        Returns:
            tuple: (success: bool, message: str)
        """
        can_cancel, error_msg = self.can_be_cancelled()
        if not can_cancel:
            return False, error_msg

        with transaction.atomic():
            # Mark invoice as cancelled
            self.is_cancelled = True
            self.cancelled_at = timezone.now()
            self.cancelled_by = user
            self.cancellation_reason = reason
            self.payment_status = PaymentStatusChoices.CANCELLED

            # Save invoice
            self.save(
                update_fields=[
                    "is_cancelled",
                    "cancelled_at",
                    "cancelled_by",
                    "cancellation_reason",
                    "payment_status",
                    "updated_at",
                ]
            )

            # Soft delete all payment allocations for this invoice
            from invoice.models import PaymentAllocation

            allocations = PaymentAllocation.objects.filter(
                invoice=self, is_deleted=False
            )
            for allocation in allocations:
                allocation.is_deleted = True
                allocation.save(update_fields=["is_deleted", "updated_at"])

            # Create cancellation audit record
            InvoiceCancellation.objects.create(
                invoice=self,
                cancelled_by=user,
                reason=reason,
                original_amount=self.amount,
                discount_amount=self.discount_amount,
                advance_amount=self.advance_amount,
                paid_amount=self.paid_amount,
                payment_type=self.payment_type,
            )

            # Cancel inventory allocations
            invoice_items = InvoiceItem.objects.filter(invoice=self)
            if invoice_items.exists():
                for item in invoice_items:
                    if item.get_return_available_quantity > 0:
                        InventoryService.cancelled_sale(
                            variant=item.product_variant,
                            quantity_cancelled=item.get_return_available_quantity,
                            user=user,
                            invoice_item=item,
                            notes=f"Cancelled Invoice: {self.invoice_number}",
                        )

            # Trigger reallocation for credit invoices
            if self.payment_type == PaymentTypeChoices.CREDIT:
                from customer.signals import reallocate_customer_payments

                reallocate_customer_payments(self.customer)

        return True, "Invoice cancelled successfully"


class InvoiceItem(InvoiceItemFinancialMixin, InvoiceItemValidationMixin, models.Model):
    """Invoice line items with organized structure"""

    # Custom manager
    objects = InvoiceItemManager()

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="invoice_items"
    )
    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="invoice_items"
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,  # Standardized to 2 decimal places for consistency
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    mrp = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        editable=False,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Maximum Retail Price / Actual Price",
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Actual selling price per unit (after discount)",
    )
    purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Cost price per unit (for profit calculation)",
    )
    hsn_code = models.ForeignKey(
        GSTHsnCode,
        on_delete=models.PROTECT,
        related_name="invoice_items",
        null=True,
        blank=True,
    )
    cess_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Cess rate",
    )
    gst_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="GST percentage",
    )

    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Commission percentage",
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(100)],
    )

    # Metadata
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        indexes = InvoiceItemConstraints.get_all_indexes()
        # Prevent duplicate items on same invoice
        # unique_together = ["invoice", "product_variant"]

    def __str__(self):
        try:
            # Use cached product name if available, otherwise fetch safely
            product_name = getattr(self, "_cached_product_name", None)
            if not product_name:
                product_name = self.product_variant.get_name(
                    include_barcode=False, include_variants=True
                )
            return f"#{self.invoice_id} - {self.quantity} × {product_name}"
        except Exception:
            return f"#{self.invoice_id} - {self.quantity} × Product #{self.product_variant_id}"

    @classmethod
    def get_invoice_items_with_details(cls, invoice_id):
        """Optimized query to get invoice items with related data"""
        return cls.objects.select_related(
            "product_variant__product", "product_variant__product__category", "invoice"
        ).filter(invoice_id=invoice_id)

    def get_product_name(self):
        """Get product name without hitting DB if already cached"""
        if hasattr(self, "_cached_product_name"):
            return self._cached_product_name
        return self.product_variant.product.name

    def cache_product_details(self):
        """Cache frequently accessed product details"""
        self._cached_product_name = self.product_variant.product.name
        self._cached_variant_name = self.product_variant.name
        return self

    def save(self, *args, **kwargs):
        if not self.hsn_code:
            self.hsn_code = self.product_variant.product.hsn_code

        if not self.gst_percentage:
            self.gst_percentage = self.hsn_code.gst_percentage

        if not self.cess_rate:
            self.cess_rate = self.hsn_code.cess_rate

        super().save(*args, **kwargs)

    @property
    def get_return_available_quantity(self):
        """Check if return is available for the invoice item"""
        # Calculate total quantity already returned (regardless of status)
        # This prevents over-returning even with multiple pending returns
        total_returned = self.return_items.filter(
            return_invoice__invoice=self.invoice,
            quantity_returned__gt=0,  # Only count items that are actually being returned
        ).aggregate(total_quantity=Sum("quantity_returned"))[
            "total_quantity"
        ] or Decimal(
            "0"
        )

        # Available quantity = Original quantity - Total returned quantity
        available = self.quantity - total_returned

        # Ensure we don't return negative values
        return max(available, Decimal("0"))

    def clean(self):
        """Custom validation for invoice items using mixin validation"""
        self.validate_item_amounts()


class InvoiceSequence(models.Model):
    """Sequence tracking for invoice numbering"""

    invoice_type = models.CharField(
        max_length=20,
        choices=InvoiceTypeChoices.choices,
        default=InvoiceTypeChoices.GST,
    )
    financial_year = models.CharField(max_length=10)  # Increased to match Invoice model
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("invoice_type", "financial_year")
        indexes = InvoiceSequenceConstraints.get_all_indexes()


class AuditTable(models.Model):
    """
    Table to store the audit trail for the audit trail view

    audit_type: CONVERSION, RENUMBER, MODIFICATION
    financial_year: 2024-2025
    """

    # Use imported choices
    AuditType = AuditTypeChoices
    Status = AuditStatusChoices

    # Custom manager
    objects = AuditTableManager()

    # Basic info
    title = models.CharField(max_length=200, help_text="Audit session title")
    description = models.TextField(
        blank=True, help_text="Description of the audit session"
    )

    # Audit type and scope
    audit_type = models.CharField(
        max_length=20,
        choices=AuditTypeChoices.choices,
        default=AuditTypeChoices.CONVERSION,
    )

    # Date range for the audit
    start_date = models.DateField(help_text="Start date of audit period")
    end_date = models.DateField(help_text="End date of audit period")

    # Financial year context
    financial_year = models.CharField(max_length=10, null=True, blank=True)

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=AuditStatusChoices.choices,
        default=AuditStatusChoices.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_table_created_by",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = AuditTableConstraints.get_all_indexes()

    def __str__(self):
        return f"{self.title} ({self.audit_type})"

    @property
    def total_changes(self):
        """Total number of changes in this audit session"""
        return self.invoice_audits.count()

    def clean(self):
        """Custom validation for business rules"""

        # Rule 1: Start <= End
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Start date cannot be greater than end date.")

        # Rule 2: Only one active audit per type
        qs = AuditTable.objects.filter(
            audit_type=self.audit_type,
            status__in=[AuditStatusChoices.PENDING, AuditStatusChoices.IN_PROGRESS],
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)  # exclude self when updating
        if qs.exists():
            raise ValidationError(f"An active {self.audit_type} audit already exists.")

        # Rule 3: Special for CONVERSION
        if self.audit_type == AuditTypeChoices.CONVERSION:
            # Ensure same financial year
            fy_start = get_financial_year(self.start_date)
            fy_end = get_financial_year(self.end_date)
            if fy_start != fy_end:
                raise ValidationError(
                    "For CONVERSION audits, start and end date must be in the same financial year."
                )

            # Ensure no overlap with previous conversions
            last_conversion = (
                AuditTable.objects.filter(audit_type=AuditTypeChoices.CONVERSION)
                .exclude(pk=self.pk)
                .order_by("-end_date")
                .first()
            )
            if last_conversion and self.start_date < last_conversion.end_date:
                raise ValidationError(
                    f"New CONVERSION audit cannot start before "
                    f"{last_conversion.end_date.strftime('%Y-%m-%d')}."
                )

    @transaction.atomic
    def save(self, *args, **kwargs):

        self.title = StringProcessor(self.title).toTitle()
        self.description = StringProcessor(self.description).toTitle()

        if self.start_date > self.end_date:
            raise ValidationError("Start date cannot be greater than end date")

        # Auto-fill financial year if missing
        if not self.financial_year and self.start_date:
            self.financial_year = get_financial_year(self.start_date)

        if not self.status:
            self.status = AuditStatusChoices.PENDING
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if (
            self.audit_type == AuditTypeChoices.CONVERSION
            and self.status == AuditStatusChoices.PENDING
        ):
            return reverse("invoice:invoice_manager", kwargs={"pk": self.pk})

        elif (
            self.audit_type == AuditTypeChoices.CONVERSION
            and self.status == AuditStatusChoices.COMPLETED
        ):
            return reverse("invoice:audit_detail", kwargs={"pk": self.pk})

        return None


class InvoiceAudit(models.Model):
    """
    Audit trail for invoice conversions and modifications
    """

    # Custom manager
    objects = InvoiceAuditManager()

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="audit_logs"
    )
    audit_table = models.ForeignKey(
        AuditTable, on_delete=models.CASCADE, related_name="invoice_audits"
    )
    old_invoice_no = models.CharField(max_length=50, null=True, blank=True)
    new_invoice_no = models.CharField(max_length=50)
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="invoice_audit_changes"
    )
    reason = models.CharField(max_length=200, default="Invoice conversion")
    change_type = models.CharField(
        max_length=20,
        choices=ChangeTypeChoices.choices,
        default=ChangeTypeChoices.CONVERSION,
    )
    old_invoice_type = models.CharField(max_length=20, null=True, blank=True)
    new_invoice_type = models.CharField(max_length=20)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = InvoiceAuditConstraints.get_all_indexes()

    def __str__(self):
        return f"{self.invoice.id}: {self.old_invoice_no} → {self.new_invoice_no} ({self.change_type})"


class PaymentAllocation(SoftDeleteModel):
    """
    The "bridge" model. This links a specific payment to a specific invoice,
    recording how much of that payment was used to clear that invoice.
    """

    # Custom manager
    objects = PaymentAllocationManager()

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="allocations"
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="allocations"
    )
    amount_allocated = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="payment_allocation_created_by",
    )
    allocated_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Removed unique_together constraint to allow multiple allocations
        # from the same payment to the same invoice
        pass

    def __str__(self):
        return f"₹{self.amount_allocated} of Payment {self.payment.id} allocated to Invoice {self.invoice.invoice_number}"


class ReturnInvoice(models.Model):
    """
    Model to store return invoices with comprehensive tracking
    """

    # Use imported choices
    RefundType = RefundTypeChoices
    RefundStatus = RefundStatusChoices
    RefundReason = RefundReasonChoices

    # Custom manager
    objects = ReturnInvoiceManager()

    # Core relationships
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="return_invoices",
        help_text="Original invoice being returned",
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="return_invoices"
    )

    # Return identification
    return_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text="Auto-generated return invoice number",
    )
    sequence_no = models.PositiveIntegerField(null=True, blank=True)

    # Return details
    refund_type = models.CharField(
        max_length=20,
        choices=RefundTypeChoices.choices,
        default=RefundTypeChoices.CASH_REFUND,
        help_text="Type of refund to be processed",
    )
    status = models.CharField(
        max_length=20,
        choices=RefundStatusChoices.choices,
        default=RefundStatusChoices.PENDING,
        help_text="Current status of the return",
    )
    reason = models.CharField(
        max_length=20,
        choices=RefundReasonChoices.choices,
        default=RefundReasonChoices.CUSTOMER_REQUEST,
        help_text="Reason for the return",
    )

    # Financial fields
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Total return amount",
    )
    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Actual amount to be refunded",
    )
    restocking_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Fee charged for restocking",
    )

    # Dates and tracking
    return_date = models.DateTimeField(
        default=timezone.now, help_text="Date when return was initiated"
    )
    approved_date = models.DateTimeField(
        null=True, blank=True, help_text="Date when return was approved"
    )
    processed_date = models.DateTimeField(
        null=True, blank=True, help_text="Date when return was processed"
    )
    financial_year = models.CharField(max_length=10, null=True, blank=True)

    # Additional information
    notes = models.TextField(
        blank=True, null=True, help_text="Additional notes about the return"
    )
    internal_notes = models.TextField(
        blank=True, null=True, help_text="Internal notes for staff only"
    )

    # Approval workflow
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_invoice_approved_by",
        help_text="User who approved the return",
    )
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_invoice_processed_by",
        help_text="User who processed the return",
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="return_invoice_created_by",
    )
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_invoice_modified_by",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["return_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["refund_type"]),
            models.Index(fields=["financial_year"]),
            models.Index(fields=["invoice"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(refund_amount__lte=models.F("total_amount")),
                name="refund_amount_check",
            ),
            models.CheckConstraint(
                check=models.Q(
                    models.Q(status="COMPLETED") | models.Q(processed_date__isnull=True)
                ),
                name="processed_date_check",
            ),
            # Prevent multiple pending returns for the same invoice
            models.UniqueConstraint(
                fields=["invoice"],
                condition=models.Q(status="PENDING"),
                name="unique_pending_return_per_invoice",
            ),
        ]

    def clean(self):
        """Custom validation for business rules"""
        if self.refund_amount > self.total_amount:
            raise ValidationError("Refund amount cannot exceed total amount")

        # Check for duplicate pending return invoices for the same invoice
        if self.invoice_id and self.status == RefundStatusChoices.PENDING:
            existing_pending = ReturnInvoice.objects.filter(
                invoice=self.invoice, status=RefundStatusChoices.PENDING
            ).exclude(pk=self.pk)

            if existing_pending.exists():
                raise ValidationError(
                    f"A pending return invoice already exists for invoice {self.invoice.invoice_number}. "
                    "Please complete or cancel the existing return before creating a new one."
                )

    def save(self, *args, **kwargs):
        # Auto-generate financial year
        if not self.financial_year and self.return_date:
            self.financial_year = get_financial_year(self.return_date)

        # Auto-generate return number
        if not self.return_number:
            self.sequence_no, self.return_number = self._get_next_return_number()

        super().save(*args, **kwargs)

    def _get_next_return_number(self):
        """Generate next return number"""
        # Simple implementation - you might want to make this more sophisticated
        last_return = (
            ReturnInvoice.objects.filter(financial_year=self.financial_year)
            .order_by("-sequence_no")
            .first()
        )

        next_seq = (last_return.sequence_no + 1) if last_return else 1
        return_number = f"RET/{self.financial_year}/{str(next_seq).zfill(3)}"

        return next_seq, return_number

    @property
    def is_approved(self):
        """Check if return is approved"""
        return self.status in [
            RefundStatusChoices.APPROVED,
            RefundStatusChoices.PROCESSING,
            RefundStatusChoices.COMPLETED,
        ]

    @property
    def is_completed(self):
        """Check if return is completed"""
        return self.status == RefundStatusChoices.COMPLETED

    @property
    def can_be_processed(self):
        """Check if return can be processed"""
        return self.status == RefundStatusChoices.APPROVED

    def approve(self, user):
        """Approve the return"""
        if self.status != RefundStatusChoices.PENDING:
            raise ValidationError("Only pending returns can be approved")

        self.status = RefundStatusChoices.APPROVED
        self.approved_by = user
        self.approved_date = timezone.now()
        self.save()

    def process(self, user):
        """Process the return"""
        if not self.can_be_processed:
            raise ValidationError("Return must be approved before processing")

        self.status = RefundStatusChoices.COMPLETED
        self.processed_by = user
        self.processed_date = timezone.now()
        self.save()

    def get_absolute_url(self):
        if self.status == RefundStatusChoices.PENDING:
            return reverse("invoice:return_stock_adjustment", kwargs={"pk": self.pk})

        elif self.status == RefundStatusChoices.APPROVED:
            return reverse("invoice:return_detail", kwargs={"pk": self.pk})

        return None

    def __str__(self):
        return f"Return {self.return_number or self.pk} for {self.customer.name}"


class ReturnInvoiceItem(models.Model):
    """
    Model to store return invoice items with detailed tracking
    """

    # Custom manager
    objects = ReturnInvoiceItemManager()

    return_invoice = models.ForeignKey(
        ReturnInvoice, on_delete=models.CASCADE, related_name="return_invoice_items"
    )
    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="return_invoice_items"
    )

    # Reference to original invoice item (if available)
    original_invoice_item = models.ForeignKey(
        InvoiceItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_items",
        help_text="Original invoice item being returned",
    )

    # Return quantities
    quantity_returned = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],  # Allow 0 initially
        help_text="Quantity being returned",
    )
    quantity_original = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Original quantity from invoice",
    )

    # Pricing information
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Unit price at time of return",
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Total amount for this item",
    )

    # Condition and reason
    condition = models.CharField(
        max_length=20,
        choices=ItemConditionChoices.choices,
        default=ItemConditionChoices.NEW,
        help_text="Condition of returned item",
    )
    return_reason = models.CharField(
        max_length=50,
        choices=ItemReturnReasonChoices.choices,
        default=ItemReturnReasonChoices.CUSTOMER_REQUEST,
        help_text="Reason for returning this specific item",
    )

    # Additional information
    notes = models.TextField(
        blank=True, null=True, help_text="Notes about this return item"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["return_invoice", "product_variant"]),
            models.Index(fields=["product_variant"]),
            models.Index(fields=["condition"]),
            models.Index(fields=["return_reason"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity_returned__lte=models.F("quantity_original")),
                name="return_quantity_check",
            ),
        ]

    def save(self, *args, **kwargs):
        # Auto-calculate total amount
        if self.quantity_returned and self.unit_price:
            self.total_amount = self.quantity_returned * self.unit_price

        # Set original quantity from invoice item if available
        if self.original_invoice_item and not self.quantity_original:
            self.quantity_original = self.original_invoice_item.quantity
            self.unit_price = self.original_invoice_item.unit_price

        super().save(*args, **kwargs)

    @property
    def is_full_return(self):
        """Check if this is a full return of the original item"""
        return self.quantity_returned == self.quantity_original

    @property
    def is_partial_return(self):
        """Check if this is a partial return"""
        return self.quantity_returned < self.quantity_original

    @property
    def remaining_quantity(self):
        """Get remaining quantity that can still be returned"""
        return self.quantity_original - self.quantity_returned

    def clean(self):
        """Validate return item data"""
        if self.quantity_returned > self.quantity_original:
            raise ValidationError("Return quantity cannot exceed original quantity")

        # Allow 0 initially - users will select items to return
        # Only validate positive quantity when actually returning items
        if self.quantity_returned < 0:
            raise ValidationError("Return quantity cannot be negative")

        # Check if we're trying to return more than available from the original invoice item
        if self.original_invoice_item and self.quantity_returned > 0:
            available_quantity = (
                self.original_invoice_item.get_return_available_quantity
            )

            # For new return items, check against available quantity
            if not self.pk:  # New item being created
                if self.quantity_returned > available_quantity:
                    raise ValidationError(
                        f"Cannot return {self.quantity_returned} items. "
                        f"Only {available_quantity} items are available for return from this invoice."
                    )
            else:  # Existing item being updated
                # Get current quantity returned (excluding this item)
                current_returned = self.original_invoice_item.return_items.exclude(
                    pk=self.pk
                ).aggregate(total=Sum("quantity_returned"))["total"] or Decimal("0")

                # Available = Original - Current returned (excluding this item)
                available_for_this_item = (
                    self.original_invoice_item.quantity - current_returned
                )

                if self.quantity_returned > available_for_this_item:
                    raise ValidationError(
                        f"Cannot return {self.quantity_returned} items. "
                        f"Only {available_for_this_item} items are available for return."
                    )

    def __str__(self):
        return f"Return {self.quantity_returned} × {self.product_variant.product.name} for {self.return_invoice}"


class InvoiceCancellation(models.Model):
    """
    Audit model to track invoice cancellations.
    Immutable once created - provides complete audit trail.
    """

    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.CASCADE,
        related_name="cancellation_record",
        help_text="The cancelled invoice",
    )

    # Who and when
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="invoice_cancellations",
        help_text="User who cancelled the invoice",
    )
    cancelled_at = models.DateTimeField(
        auto_now_add=True, help_text="When the cancellation occurred"
    )

    # Why
    reason = models.TextField(help_text="Reason for cancellation")

    # Financial snapshot at time of cancellation
    original_amount = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Original invoice amount"
    )
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Discount amount at cancellation"
    )
    advance_amount = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Advance amount at cancellation"
    )
    paid_amount = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Amount paid at cancellation"
    )
    payment_type = models.CharField(
        max_length=20, help_text="Payment type (CASH/CREDIT)"
    )

    class Meta:
        ordering = ["-cancelled_at"]
        indexes = [
            models.Index(fields=["cancelled_by"]),
            models.Index(fields=["cancelled_at"]),
            models.Index(fields=["payment_type"]),
        ]

    def __str__(self):
        return f"Cancellation of {self.invoice.invoice_number} by {self.cancelled_by}"

    @property
    def net_amount_at_cancellation(self):
        """Calculate net amount at time of cancellation"""
        return self.original_amount - self.discount_amount - self.advance_amount
