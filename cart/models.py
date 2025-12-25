# Create your models here.
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from inventory.models import ProductVariant
from base.utility import StringProcessor
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from decimal import Decimal


User = settings.AUTH_USER_MODEL


class Cart(models.Model):
    class CartStatus(models.TextChoices):
        OPEN = "OPEN", "Open"
        ARCHIVED = "ARCHIVED", "Archived"

    name = models.CharField(max_length=255, help_text="Cart name")
    status = models.CharField(
        max_length=20,
        choices=CartStatus.choices,
        default=CartStatus.OPEN,
    )
    advance_payment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Advance payment received from customer",
    )
    notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="carts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["name"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        if self.advance_payment > 0:
            return f"Cart #{self.id} - {self.name} - ({self.advance_payment})"
        else:
            return f"Cart #{self.id} - {self.name}"

    def save(self, *args, **kwargs):
        self.name = StringProcessor(self.name).toTitle()
        super().save(*args, **kwargs)

    @property
    def total_amount(self):
        """Calculate total amount using database aggregation for better performance"""
        # Use database aggregation to calculate total in a single query
        total = self.cart_items.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("price"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )["total"] or Decimal(0)

        return round(total, 2)

    @property
    def total_quantity(self):
        """Calculate total quantity using database aggregation for better performance"""
        # Use database aggregation to calculate total Quantity in a single query
        total = self.cart_items.aggregate(total=Sum("quantity"))["total"] or Decimal(0)

        return round(total, 2)

    def get_item_count(self):
        """Get item count with database optimization"""
        return self.cart_items.count()

    def get_cart_summary(self):
        """Get cart summary in a single query"""
        from django.db.models import Sum, Count

        summary = self.cart_items.aggregate(
            total_items=Count("id"), total_amount=Sum("price")
        )

        return {
            "item_count": summary["total_items"] or 0,
            "total_amount": summary["total_amount"] or 0,
        }


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="cart_items")
    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name="cart_items"
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["cart"]),
            models.Index(fields=["product_variant"]),
        ]

    def __str__(self):
        return f"{self.cart.name} - {self.product_variant.full_name}"

    def amount(self):
        """Calculate the total for this item with caching"""
        if not hasattr(self, "_amount_cache"):
            self._amount_cache = round(self.quantity * self.price, 2)
        return self._amount_cache

    @property
    def amount_property(self):
        """Property to access amount for templates"""
        return self.amount()

    @property
    def product_name(self):
        """Get product name with caching"""
        if not hasattr(self, "_product_name_cache"):
            self._product_name_cache = self.product_variant.full_name
        return self._product_name_cache

    @property
    def discount_percentage(self):
        """Calculate discount percentage with caching"""
        if not hasattr(self, "_discount_cache"):
            if not self.product_variant.mrp or self.product_variant.mrp <= 0:
                self._discount_cache = 0
            else:
                discount = (
                    (self.product_variant.mrp - self.price) / self.product_variant.mrp
                ) * 100
                self._discount_cache = round(max(0, discount), 2)
        return self._discount_cache

    def save(self, *args, **kwargs):
        """Clear cache on save"""
        if hasattr(self, "_amount_cache"):
            delattr(self, "_amount_cache")
        if hasattr(self, "_product_name_cache"):
            delattr(self, "_product_name_cache")
        if hasattr(self, "_discount_cache"):
            delattr(self, "_discount_cache")
        super().save(*args, **kwargs)
