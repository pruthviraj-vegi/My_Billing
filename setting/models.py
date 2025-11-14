from django.db import models
from django.conf import settings
from base.manager import phone_regex
from base.utility import StringProcessor

User = settings.AUTH_USER_MODEL


class ShopDetails(models.Model):
    """Model to store shop/business information for invoices and reports."""

    shop_name = models.CharField(max_length=255, help_text="Name of the shop/business")
    first_line = models.CharField(
        max_length=255, help_text="First line of address (e.g., Building name, Street)"
    )
    second_line = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Second line of address (e.g., Area, Locality)",
    )
    city = models.CharField(max_length=100, help_text="City name")
    state = models.CharField(max_length=100, help_text="State name")
    pincode = models.CharField(max_length=10, help_text="PIN/ZIP code")
    country = models.CharField(
        max_length=100, default="India", help_text="Country name"
    )
    gst_no = models.CharField(
        max_length=15, blank=True, null=True, help_text="GST Registration Number"
    )
    phone_number = models.CharField(
        max_length=20, validators=[phone_regex], help_text="Primary phone number"
    )
    phone_two = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[phone_regex],
        help_text="Secondary phone number",
    )
    email = models.EmailField(blank=True, null=True, help_text="Business email address")
    website = models.URLField(blank=True, null=True, help_text="Business website URL")
    logo = models.ImageField(
        upload_to="shop_logos/", blank=True, null=True, help_text="Shop logo image"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this shop details is currently active"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shop_details_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Shop Details"
        verbose_name_plural = "Shop Details"
        ordering = ["-created_at"]

    def __str__(self):
        return self.shop_name

    def save(self, *args, **kwargs):
        """Override save to clean and format data."""
        self.shop_name = StringProcessor(self.shop_name).toTitle()
        self.first_line = StringProcessor(self.first_line).toTitle()
        self.second_line = StringProcessor(self.second_line).toTitle()
        self.city = StringProcessor(self.city).toTitle()
        self.state = StringProcessor(self.state).toTitle()
        self.country = StringProcessor(self.country).toTitle()
        self.phone_number = StringProcessor(self.phone_number).cleaned_string
        self.phone_two = StringProcessor(self.phone_two).cleaned_string
        self.email = StringProcessor(self.email).toLowercase()
        self.gst_no = StringProcessor(self.gst_no).toUppercase()

        super().save(*args, **kwargs)

    @property
    def full_address(self):
        """Return complete formatted address."""
        address_parts = [self.first_line]
        if self.second_line:
            address_parts.append(self.second_line)
        address_parts.extend([self.city, self.state, self.pincode])
        if self.country != "India":
            address_parts.append(self.country)
        return ", ".join(address_parts)

    @property
    def address_line_one(self):
        """Return complete formatted address with country."""
        return f"{self.first_line}, {self.second_line}"

    @property
    def address_line_two(self):
        """Return complete formatted address with country."""
        return f"{self.city}, {self.state} - {self.pincode}"

    @property
    def short_address(self):
        """Return shortened address for display."""
        return f"{self.city}, {self.state} - {self.pincode}"

    @property
    def contact_info(self):
        """Return formatted contact information."""
        contacts = [self.phone_number]
        if self.phone_two:
            contacts.append(self.phone_two)
        return ", ".join(contacts)


class ReportConfiguration(models.Model):
    """Model to store report generation preferences and settings."""

    class ReportType(models.TextChoices):
        INVOICE = "INVOICE", "Invoice"
        ESTIMATE = "ESTIMATE", "Estimate"
        QUOTATION = "QUOTATION", "Quotation"
        RECEIPT = "RECEIPT", "Receipt"
        STATEMENT = "STATEMENT", "Account Statement"

    class PaperSize(models.TextChoices):
        A4 = "A4", "A4"
        A5 = "A5", "A5"
        _58mm = "58mm", "58mm"
        LETTER = "LETTER", "Letter"
        LEGAL = "LEGAL", "Legal"

    class Currency(models.TextChoices):
        INR = "INR", "Indian Rupee (₹)"
        USD = "USD", "US Dollar ($)"
        EUR = "EUR", "Euro (€)"
        GBP = "GBP", "British Pound (£)"

    # Basic Settings
    report_type = models.CharField(
        max_length=20, choices=ReportType.choices, default=ReportType.INVOICE
    )
    paper_size = models.CharField(
        max_length=10, choices=PaperSize.choices, default=PaperSize.A5
    )
    currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.INR
    )

    # Header Settings
    show_logo = models.BooleanField(default=True, help_text="Show shop logo in header")
    show_shop_name = models.BooleanField(
        default=True, help_text="Show shop name in header"
    )
    show_address = models.BooleanField(
        default=True, help_text="Show shop address in header"
    )
    show_contact = models.BooleanField(
        default=True, help_text="Show contact information in header"
    )
    show_gst = models.BooleanField(default=True, help_text="Show GST number in header")

    # Invoice/Report Content
    show_invoice_number = models.BooleanField(
        default=True, help_text="Show invoice number"
    )
    show_date = models.BooleanField(default=True, help_text="Show invoice date")
    show_due_date = models.BooleanField(
        default=True, help_text="Show due date (for credit invoices)"
    )
    show_payment_method = models.BooleanField(
        default=True, help_text="Show payment method"
    )
    show_customer_details = models.BooleanField(
        default=True, help_text="Show customer information"
    )

    # Item Details
    show_item_description = models.BooleanField(
        default=True, help_text="Show item descriptions"
    )
    show_quantity = models.BooleanField(default=True, help_text="Show quantities")
    show_unit_price = models.BooleanField(default=True, help_text="Show unit prices")
    show_discount = models.BooleanField(
        default=True, help_text="Show discount information"
    )
    show_tax_breakdown = models.BooleanField(
        default=True, help_text="Show tax breakdown"
    )
    show_total = models.BooleanField(default=True, help_text="Show total amounts")

    # Footer Settings
    show_terms_conditions = models.BooleanField(
        default=True, help_text="Show terms and conditions"
    )
    show_qr_code = models.BooleanField(
        default=True, help_text="Show QR code for payments"
    )
    show_thank_you = models.BooleanField(
        default=True, help_text="Show thank you message"
    )
    show_signature = models.BooleanField(default=False, help_text="Show signature line")

    # Custom Text
    terms_conditions = models.TextField(
        blank=True, null=True, help_text="Custom terms and conditions text"
    )
    thank_you_message = models.TextField(
        blank=True, null=True, help_text="Custom thank you message"
    )
    footer_note = models.TextField(
        blank=True, null=True, help_text="Additional footer note"
    )

    # System Settings
    is_default = models.BooleanField(
        default=False, help_text="Use as default configuration"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this configuration is active"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_configs_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Report Configuration"
        verbose_name_plural = "Report Configurations"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.get_paper_size_display()}"

    def save(self, *args, **kwargs):
        """Override save to ensure only one default config per report type."""
        if self.is_default:
            # Set all other configs of same type to not default
            ReportConfiguration.objects.filter(
                report_type=self.report_type, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)

    @classmethod
    def get_default_config(cls, report_type=ReportType.INVOICE):
        """Get the default configuration for a report type."""
        try:
            return cls.objects.get(
                report_type=report_type, is_default=True, is_active=True
            )
        except cls.DoesNotExist:
            # Create a default config if none exists
            return cls.objects.create(
                report_type=report_type, is_default=True, is_active=True
            )

    @property
    def default_terms_conditions(self):
        """Return default terms and conditions if none set."""
        if self.terms_conditions:
            return self.terms_conditions

        return """1. All Subjects to The Shahapur Juridiction
            2. Goods Once Sold Will Not be taken back
            3. E. & O.E"""

    @property
    def default_thank_you_message(self):
        """Return default thank you message if none set."""
        if self.thank_you_message:
            return self.thank_you_message

        return "Thank You Please Visit Again"
