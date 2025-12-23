from django.db import models, transaction
from django.conf import settings
from supplier.models import SupplierInvoice
from base.manager import SoftDeleteModel
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from .manager import ProductVariantManager, InventoryLogManager

from base.utility import StringProcessor
from django.urls import reverse

User = settings.AUTH_USER_MODEL


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = StringProcessor(self.name).toTitle()
        self.description = StringProcessor(self.description).toTitle()
        super().save(*args, **kwargs)


class ClothType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = StringProcessor(self.name).toTitle()
        self.description = StringProcessor(self.description).toTitle()
        super().save(*args, **kwargs)


class Color(models.Model):
    """
    Defines a specific color. e.g., Red, Blue, Pink.
    """

    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        help_text="Optional: Hex color code, e.g., #FF0000",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = StringProcessor(self.name).toTitle()
        self.hex_code = StringProcessor(self.hex_code).toUppercase()
        super().save(*args, **kwargs)


class Size(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = StringProcessor(self.name).toUppercase()
        self.description = StringProcessor(self.description).toTitle()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("inventory:size_home")


class UOM(models.Model):
    """
    Unit of Measurement Master Table
    """

    name = models.CharField(
        max_length=50, help_text="Full name of the UOM, e.g., Piece, Dozen, Meter"
    )
    short_code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Abbreviation for the UOM, e.g., pcs, doz, m",
    )
    category = models.CharField(
        max_length=50, help_text="Type of UOM, e.g., Quantity, Weight, Length, Volume"
    )
    base_unit = models.BooleanField(
        default=False, help_text="Marks if this is the base unit for conversions"
    )
    conversion_factor = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=1.0,
        help_text="Factor to convert to base unit (e.g., 1 dozen = 12 pcs)",
    )
    description = models.TextField(
        blank=True, null=True, help_text="Optional notes about this UOM"
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this UOM is active or not"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Unit of Measurement"
        verbose_name_plural = "Units of Measurement"

    def __str__(self):
        return f"{self.name} ({self.short_code})"

    def save(self, *args, **kwargs):
        self.name = StringProcessor(self.name).toTitle()
        self.description = StringProcessor(self.description).toTitle()
        self.short_code = StringProcessor(self.short_code).toUppercase()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("inventory:uom_home")


class GSTHsnCode(models.Model):
    code = models.CharField(max_length=8, unique=True, db_index=True)
    gst_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("40.00")),
        ],
    )

    cess_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("25.00")),
        ],
    )
    effective_from = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} ({self.gst_percentage}% GST + {self.cess_rate}% Cess)"

    def save(self, *args, **kwargs):
        self.code = StringProcessor(self.code).toUppercase()
        self.description = StringProcessor(self.description).toTitle()
        super().save(*args, **kwargs)

    def get_applicable_rate(self, transaction_type="intrastate"):
        if transaction_type == "interstate":
            return {
                "cgst": Decimal("0.00"),
                "sgst": Decimal("0.00"),
                "igst": self.gst_percentage,
                "cess": self.cess_rate,
                "total": self.gst_percentage + self.cess_rate,
            }
        else:
            half = self.gst_percentage / 2
            return {
                "cgst": half,
                "sgst": half,
                "igst": Decimal("0.00"),
                "cess": self.cess_rate,
                "total": self.gst_percentage + self.cess_rate,
            }


class Product(SoftDeleteModel):
    class ProductStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        DISCONTINUED = "DISCONTINUED", "Discontinued"

    brand = models.CharField(max_length=255, help_text="The brand of the product")
    name = models.CharField(max_length=255, help_text="The name of the product")
    description = models.TextField(
        blank=True, null=True, help_text="The description of the product"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )
    cloth_type = models.ForeignKey(
        ClothType,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )
    uom = models.ForeignKey(
        UOM, on_delete=models.PROTECT, related_name="products", null=True, blank=True
    )
    hsn_code = models.ForeignKey(
        GSTHsnCode,
        on_delete=models.PROTECT,
        related_name="products",
    )
    status = models.CharField(
        max_length=20, choices=ProductStatus.choices, default=ProductStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name

    class Meta:
        indexes = [
            models.Index(fields=["brand"]),
            models.Index(fields=["name"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.name = StringProcessor(self.name).toTitle()
        self.brand = StringProcessor(self.brand).toTitle()
        self.description = StringProcessor(self.description).toTitle()
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        if self.name:
            return f"{self.brand} - {self.name}"
        return self.brand


class ProductVariant(SoftDeleteModel):
    class VariantStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DISCONTINUED = "DISCONTINUED", "Discontinued"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size", "color"],
                name="unique_product_size_color",
                condition=models.Q(size__isnull=False, color__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["product", "size"],
                name="unique_product_size_null_color",
                condition=models.Q(size__isnull=False, color__isnull=True),
            ),
            models.UniqueConstraint(
                fields=["product", "color"],
                name="unique_product_color_null_size",
                condition=models.Q(size__isnull=True, color__isnull=False),
            ),
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["barcode"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["product", "status"]),
            models.Index(fields=["quantity", "minimum_quantity"]),
        ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="product_variants"
    )
    barcode = models.CharField(max_length=100, unique=True)
    size = models.ForeignKey(
        Size,
        on_delete=models.PROTECT,
        related_name="product_variants",
        null=True,
        blank=True,
    )
    color = models.ForeignKey(
        Color,
        on_delete=models.PROTECT,
        related_name="product_variants",
        null=True,
        blank=True,
    )
    extra_attributes = models.JSONField(default=dict, blank=True)
    # Price fields
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        validators=[
            MinValueValidator(Decimal("0"), "Purchase price must be greater than 0")
        ],
        help_text="Cost price of the product",
    )
    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        validators=[
            MinValueValidator(Decimal("0"), "Selling price must be greater than 0")
        ],
        help_text="Selling price of the product",
    )
    # Quantity fields
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        validators=[
            MinValueValidator(Decimal("0"), "Quantity cannot be negative"),
        ],
    )
    damaged_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="The quantity of the product that is damaged",
        validators=[
            MinValueValidator(Decimal("0"), "Damaged quantity cannot be negative"),
        ],
    )
    minimum_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Minimum stock level before reorder alert",
        validators=[
            MinValueValidator(Decimal("0"), "Minimum quantity cannot be negative"),
        ],
    )
    # Percentage fields
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        validators=[
            MinValueValidator(Decimal("0"), "Discount cannot be negative"),
            MaxValueValidator(100, "Discount cannot exceed 100%"),
        ],
    )
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0"), "Commission cannot be negative"),
            MaxValueValidator(100, "Commission cannot exceed 100%"),
        ],
    )
    status = models.CharField(
        max_length=20, choices=VariantStatus.choices, default=VariantStatus.ACTIVE
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_variants",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductVariantManager()

    def __str__(self):
        """Simple, bulletproof string representation"""
        try:
            # Get product name safely
            product_name = getattr(self.product, "brand", "Unknown Product")

            # Build variant info safely
            variant_parts = []

            if self.size and hasattr(self.size, "name"):
                variant_parts.append(self.size.name)

            if self.color and hasattr(self.color, "name"):
                variant_parts.append(self.color.name)

            # Add extra attributes safely
            if self.extra_attributes and isinstance(self.extra_attributes, dict):
                for key, value in self.extra_attributes.items():
                    if key and value:
                        variant_parts.append(f"{key}: {value}")

            # Build final string
            if variant_parts:
                variant_info = f" ({', '.join(variant_parts)})"
            else:
                variant_info = ""

            barcode = getattr(self, "barcode", "No Barcode")
            return f"{product_name}{variant_info} - {barcode}"

        except Exception:
            # Fallback if anything goes wrong
            return f"Product Variant #{self.id}"

    def get_name(self, include_barcode=True, include_variants=True):
        """
        Get a clean, formatted name for the product variant

        Args:
            include_barcode (bool): Whether to include barcode in the name
            include_variants (bool): Whether to include size/color info

        Returns:
            str: Formatted product name
        """
        try:
            # Get base product name
            product_name = getattr(self.product, "brand", "Unknown Product")

            # Add product name if available
            if hasattr(self.product, "name") and self.product.name:
                product_name = f"{product_name} - {self.product.name}"

            # Add variant info if requested
            if include_variants:
                variant_parts = []

                if self.size and hasattr(self.size, "name"):
                    variant_parts.append(self.size.name)

                if self.color and hasattr(self.color, "name"):
                    variant_parts.append(self.color.name)

                if variant_parts:
                    product_name = f"{product_name} ({', '.join(variant_parts)})"

            # Add barcode if requested
            if include_barcode and hasattr(self, "barcode") and self.barcode:
                product_name = f"{product_name} - {self.barcode}"

            return product_name

        except Exception:
            return f"Product Variant #{self.id}"

    @property
    def simple_name(self):
        """Simple name without barcode for display purposes"""

        product_name = getattr(self.product, "name", "Unknown Product")

        # Add size if it exists
        if hasattr(self, "size") and self.size:
            product_name += f" - {self.size.name}"

        # Add color if it exists
        if hasattr(self, "color") and self.color:
            product_name += f" - {self.color.name}"

        return product_name

    @property
    def full_name(self):
        """Full name with all details"""
        return self.get_name(include_barcode=True, include_variants=True)

    @property
    def price_name(self):
        """Short name without barcode for display purposes"""
        return self.get_name(include_barcode=False, include_variants=False)

    @property
    def is_low_stock(self):
        return self.quantity <= self.minimum_quantity

    @property
    def total_quantity(self):
        """Total quantity including damaged items"""
        return self.quantity + self.damaged_quantity

    @property
    def available_quantity(self):
        """Quantity available for sale (excluding damaged)"""
        return self.quantity

    @property
    def damage_percentage(self):
        """Percentage of total stock that is damaged"""
        if self.total_quantity > 0:
            return (self.damaged_quantity / self.total_quantity) * 100
        return 0

    @property
    def stock_status(self):
        if self.quantity == 0:
            return "Out of Stock"
        elif self.is_low_stock:
            return "Low Stock"
        return "In Stock"

    @property
    def final_price(self):
        """Calculate final price after discount"""
        if self.discount_percentage > 0:
            return self.mrp * (1 - self.discount_percentage / 100)
        return self.mrp

    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.mrp > 0:
            return ((self.mrp - self.purchase_price) / self.mrp) * 100
        return 0

    @property
    def total_value(self):
        """Calculate total inventory value"""
        return round(self.quantity * self.purchase_price, 2)

    @property
    def damaged_value(self):
        """Calculate value of damaged inventory"""
        return self.damaged_quantity * self.purchase_price

    @property
    def stock_health(self):
        """Get stock health status"""
        if self.quantity == 0:
            return "critical"
        elif self.quantity <= self.minimum_quantity:
            return "low"
        return "healthy"

    @property
    def get_gst_percentage(self):
        """Get GST percentage"""
        if self.product.hsn_code:
            return self.product.hsn_code.gst_percentage
        return Decimal("0")

    @property
    def actual_purchased_price(self):
        """Calculate actual purchased price"""
        return self.purchase_price * (1 + (self.get_gst_percentage / 100))

    @property
    def get_amount(self):
        """Calculate amount"""
        if self.discount_percentage > 0:
            return round(
                self.mrp * (1 - self.discount_percentage / 100) * self.quantity,
                2,
            )
        return round(self.mrp * self.quantity, 2)

    @property
    def get_barcode_qty(self):
        """
        Get the minimum of:
        1. Current quantity (self.quantity)
        2. Quantity change from first INITIAL transaction
        3. Quantity change from first STOCK_IN transaction
        """
        quantities = [self.quantity]

        # Get the first transaction (INITIAL or STOCK_IN) by timestamp
        first_log = (
            self.inventory_logs.filter(
                transaction_type__in=[
                    InventoryLog.TransactionTypes.INITIAL,
                    InventoryLog.TransactionTypes.STOCK_IN,
                ]
            )
            .order_by("-updated_at")
            .first()
        )

        if first_log:
            quantities.append(first_log.quantity_change)

        qty = min(quantities) if quantities else 0
        return max(1, int(qty + 1) // 2) if qty > 0 else 1

    def clean(self):
        """Custom validation"""
        from django.core.exceptions import ValidationError

        # Validate barcode uniqueness
        if self.barcode:
            existing = ProductVariant.objects.filter(barcode=self.barcode)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError("Barcode must be unique")

    def save(self, *args, **kwargs):
        """Override save to include validation"""
        self.clean()

        # If new record and no barcode, generate after getting ID
        if not self.pk and not self.barcode:
            super().save(*args, **kwargs)  # First save to get ID
            self.barcode = f"{self.id:06d}3"  # 6 digits with zero padding
            super().save(update_fields=["barcode"])  # Update only barcode
        else:
            super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(
        upload_to="product_images/", help_text="The product image file."
    )
    image_url = models.URLField(
        max_length=255,
        blank=True,
        null=True,
        help_text="The URL of the product image.",
    )
    color = models.ForeignKey(
        Color,
        on_delete=models.SET_NULL,
        related_name="product_images",
        null=True,
        blank=True,
    )
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Alternative text for the image for accessibility.",
    )
    is_featured = models.BooleanField(
        default=False, help_text="Is this the main image for the product?"
    )

    class Meta:
        ordering = ["-is_featured"]

    def __str__(self):
        return f"Image for {self.product.brand}"


class InventoryLog(SoftDeleteModel):
    class TransactionTypes(models.TextChoices):
        STOCK_IN = "STOCK_IN", "Stock In"
        SALE = "SALE", "Sale"
        RETURN = "RETURN", "Customer Return"
        ADJUSTMENT_IN = "ADJUSTMENT_IN", "Adjustment In"  # More specific
        ADJUSTMENT_OUT = "ADJUSTMENT_OUT", "Adjustment Out"  # More specific
        DAMAGE = "DAMAGE", "Mark as Damaged"
        INITIAL = "INITIAL", "Initial Stock"

    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="inventory_logs"
    )
    supplier_invoice = models.ForeignKey(
        SupplierInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_logs",
    )
    transaction_type = models.CharField(max_length=20, choices=TransactionTypes.choices)
    quantity_change = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0")
    )
    new_quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0")
    )
    purchase_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, default=Decimal("0")
    )
    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Selling price at time of transaction",
        default=Decimal("0"),
    )
    # Sale tracking (for SALE transactions)
    invoice_item = models.ForeignKey(
        "invoice.invoiceitem",  # Adjust app name as needed
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_logs",
        help_text="Customer invoice item for sale transactions",
    )
    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Selling price per unit for sale transactions",
    )
    # FIFO tracking - links sale transactions to their source stock
    source_inventory_log = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="allocated_sales",
        help_text="For SALE transactions: points to the STOCK_IN/INITIAL log this sale is allocated from",
    )

    allocated_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="For SALE transactions: quantity allocated from source_inventory_log",
    )

    # Remaining quantity for FIFO allocation
    remaining_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="For STOCK_IN/INITIAL: remaining quantity available for allocation",
    )

    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total value of the transaction",
        default=Decimal("0"),
    )
    notes = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = InventoryLogManager()

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["variant", "timestamp"]),
            models.Index(fields=["transaction_type", "timestamp"]),
            models.Index(fields=["created_by", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.variant} changed by {self.quantity_change} on {self.timestamp.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        # Auto-calculate total value
        if not self.total_value and self.quantity_change:
            if self.transaction_type in ["STOCK_IN", "INITIAL"] and self.purchase_price:
                self.total_value = abs(self.quantity_change) * self.purchase_price
            elif self.transaction_type == "SALE" and self.selling_price:
                self.total_value = abs(self.quantity_change) * self.selling_price

        # Initialize remaining quantity for stock in transactions
        if (
            self.transaction_type in ["STOCK_IN", "INITIAL"]
            and self.remaining_quantity is None
        ):
            self.remaining_quantity = abs(self.quantity_change)

        super().save(*args, **kwargs)


class FavoriteVariant(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="favorite_variants"
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="favorite_variants"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.full_name} - {self.variant.full_name}"

    class Meta:
        unique_together = ["user", "variant"]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["variant"]),
            models.Index(fields=["created_at"]),
        ]
