from django.db import models

# Create your models here.
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging
from invoice.models import Invoice
from customer.models import Customer

logger = logging.getLogger(__name__)

User = get_user_model()


class InvoicePDF(models.Model):
    """Stores generated PDF URLs for invoices"""

    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.CASCADE,
        related_name="pdf",
        help_text="Associated invoice",
    )
    pdf_url = models.URLField(
        max_length=500, help_text="Cloudflare R2 URL of the generated PDF"
    )
    filename = models.CharField(max_length=255, help_text="PDF filename in storage")
    generated_at = models.DateTimeField(
        auto_now_add=True, help_text="When the PDF was generated"
    )
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_pdfs",
        help_text="User who triggered PDF generation",
    )
    last_invoice_updated_at = models.DateTimeField(
        help_text="Invoice updated_at timestamp when PDF was generated"
    )
    file_size = models.PositiveIntegerField(
        null=True, blank=True, help_text="PDF file size in bytes"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this PDF is the current active version"
    )

    class Meta:
        db_table = "invoice_pdf"
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["invoice", "is_active"]),
            models.Index(fields=["generated_at"]),
            models.Index(fields=["last_invoice_updated_at"]),
        ]
        verbose_name = "Invoice PDF"
        verbose_name_plural = "Invoice PDFs"

    def __str__(self):
        return f"PDF for {self.invoice.invoice_number}"

    def is_pdf_outdated(self):
        """
        Check if the invoice has been modified since PDF generation.
        Returns True if PDF needs regeneration, False otherwise.
        """
        if not self.last_invoice_updated_at:
            return True

        # Compare invoice's current updated_at with stored timestamp
        return self.invoice.updated_at > self.last_invoice_updated_at

    @classmethod
    def get_valid_pdf(cls, invoice):
        """
        Get existing PDF if valid, return None if needs regeneration.
        A PDF is valid if:
        1. It exists
        2. It's active
        3. Invoice hasn't been modified since PDF generation
        """
        try:
            pdf = cls.objects.get(invoice=invoice, is_active=True)

            # Check if PDF is outdated
            if pdf.is_pdf_outdated():
                logger.info(f"PDF for invoice {invoice.invoice_number} is outdated")
                return None

            return pdf

        except cls.DoesNotExist:
            return None

    @classmethod
    def create_pdf_record(
        cls, invoice, pdf_url, filename, generated_by=None, file_size=None
    ):
        """
        Create or update PDF record with current invoice timestamp.
        Uses update_or_create to avoid duplicate key errors.
        """
        pdf_record, created = cls.objects.update_or_create(
            invoice=invoice,
            defaults={
                "pdf_url": pdf_url,
                "filename": filename,
                "last_invoice_updated_at": invoice.updated_at,
                "generated_by": generated_by,
                "file_size": file_size,
                "is_active": True,
            },
        )

        action = "Created" if created else "Updated"
        logger.info(f"{action} PDF record for invoice {invoice.invoice_number}")

        return pdf_record


class CustomerStatementPDF(models.Model):
    """Stores generated PDF URLs for customer statements"""

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="statement_pdfs",
        help_text="Associated customer",
    )
    from_date = models.DateField(help_text="Statement start date")
    to_date = models.DateField(help_text="Statement end date")
    closing_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Customer's balance at to_date when PDF was generated",
    )
    pdf_url = models.URLField(
        max_length=500, help_text="Cloudflare R2 URL of the generated PDF"
    )
    filename = models.CharField(max_length=255, help_text="PDF filename in storage")
    generated_at = models.DateTimeField(
        auto_now_add=True, help_text="When the PDF was generated"
    )
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_statement_pdfs",
        help_text="User who triggered PDF generation",
    )
    file_size = models.PositiveIntegerField(
        null=True, blank=True, help_text="PDF file size in bytes"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this PDF is the current active version"
    )

    class Meta:
        db_table = "statement_pdf"
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["customer", "from_date", "to_date", "is_active"]),
            models.Index(fields=["customer", "closing_balance"]),
            models.Index(fields=["generated_at"]),
        ]
        # Ensure one active statement per customer per date range
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "from_date", "to_date"],
                condition=models.Q(is_active=True),
                name="unique_active_statement_per_date_range",
            )
        ]
        verbose_name = "Statement PDF"
        verbose_name_plural = "Statement PDFs"

    def __str__(self):
        return f"Statement for {self.customer} ({self.from_date} to {self.to_date})"

    def is_balance_outdated(self, current_balance):
        """
        Check if the customer's balance has changed since PDF generation.
        Returns True if PDF needs regeneration, False otherwise.
        """
        return self.closing_balance != current_balance

    @classmethod
    def get_valid_pdf(cls, customer, from_date, to_date, current_balance):
        """
        Get existing PDF if valid, return None if needs regeneration.
        A PDF is valid if:
        1. It exists for this customer and date range
        2. It's active
        3. Balance hasn't changed since PDF generation
        """
        try:
            pdf = cls.objects.get(
                customer=customer,
                from_date=from_date,
                to_date=to_date,
                is_active=True,
            )

            # Check if balance has changed
            if pdf.is_balance_outdated(current_balance):
                logger.info(
                    f"Statement PDF for customer {customer.id} is outdated "
                    f"(balance changed from {pdf.closing_balance} to {current_balance})"
                )
                # Delete ALL cached PDFs for this customer since balance changed
                cls.invalidate_all_customer_pdfs(customer)
                return None

            logger.info(
                f"Using cached statement PDF for customer {customer.id} "
                f"({from_date} to {to_date})"
            )
            return pdf

        except cls.DoesNotExist:
            return None

    @classmethod
    def invalidate_all_customer_pdfs(cls, customer):
        """
        Delete all cached PDFs for a customer when balance changes.
        This ensures no outdated statements exist.
        """
        deleted_count = cls.objects.filter(customer=customer).delete()[0]
        if deleted_count > 0:
            logger.info(
                f"Invalidated {deleted_count} cached statement PDFs for customer {customer.id}"
            )
        return deleted_count

    @classmethod
    def create_pdf_record(
        cls,
        customer,
        from_date,
        to_date,
        closing_balance,
        pdf_url,
        filename,
        generated_by=None,
        file_size=None,
    ):
        """
        Create PDF record with current balance.
        Uses update_or_create to handle the date range uniqueness.
        """
        pdf_record, created = cls.objects.update_or_create(
            customer=customer,
            from_date=from_date,
            to_date=to_date,
            defaults={
                "closing_balance": closing_balance,
                "pdf_url": pdf_url,
                "filename": filename,
                "generated_by": generated_by,
                "file_size": file_size,
                "is_active": True,
            },
        )

        action = "Created" if created else "Updated"
        logger.info(
            f"{action} statement PDF record for customer {customer.id} "
            f"({from_date} to {to_date}, balance: {closing_balance})"
        )

        return pdf_record
