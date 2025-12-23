from django.db import models
from django.db.models import Sum, Case, When, F, Value, DecimalField
from django.db.models.functions import Coalesce

from base.manager import SoftDeleteManager


class ProductVariantManager(SoftDeleteManager):
    """Custom manager for ProductVariant with common queries"""

    def active(self):
        """Get only active variants"""
        return self.filter(status="ACTIVE")

    def low_stock(self):
        """Get variants with low stock (at or below minimum quantity)"""
        return self.filter(
            quantity__lte=models.F("minimum_quantity"),
            status="ACTIVE",
        )

    def out_of_stock(self):
        """Get variants that are out of stock"""
        return self.filter(quantity=0, status="ACTIVE")

    def with_damage(self):
        """Get variants with damaged items"""
        return self.filter(damaged_quantity__gt=0)

    def by_category(self, category):
        """Get variants by product category"""
        return self.filter(product__category=category)

    def by_brand(self, brand):
        """Get variants by product brand"""
        return self.filter(product__brand__icontains=brand)

    def by_status(self, status):
        """Get variants by status"""
        return self.filter(status=status)

    def in_stock(self):
        """Get variants that are in stock"""
        return self.filter(quantity__gt=0, status="ACTIVE")

    def by_price_range(self, min_price=None, max_price=None):
        """Get variants within a price range"""
        queryset = self.filter(status="ACTIVE")
        if min_price is not None:
            queryset = queryset.filter(mrp__gte=min_price)
        if max_price is not None:
            queryset = queryset.filter(mrp__lte=max_price)
        return queryset

    def with_discount(self):
        """Get variants that have discounts applied"""
        return self.filter(discount_percentage__gt=0, status="ACTIVE")

    def by_product(self, product):
        """Get variants by specific product"""
        return self.filter(product=product, status="ACTIVE")

    def by_size(self, size):
        """Get variants by size"""
        return self.filter(size=size, status="ACTIVE")

    def by_color(self, color):
        """Get variants by color"""
        return self.filter(color=color, status="ACTIVE")


class InventoryLogQuerySet(models.QuerySet):
    """Custom queryset helpers for InventoryLog aggregations."""

    def with_stock_summary(self):
        """
        Annotate the queryset with stock in/sales/damage totals so callers
        can simply chain `.with_stock_summary()` after filters/values().
        """

        quantity_field = DecimalField(max_digits=16, decimal_places=3)

        return self.annotate(
            stock_in_quantity=Coalesce(
                Sum(
                    Case(
                        When(
                            transaction_type__in=[
                                "STOCK_IN",
                                "INITIAL",
                                "ADJUSTMENT_IN",
                            ],
                            then=F("quantity_change"),
                        ),
                        default=Value(0),
                        output_field=quantity_field,
                    )
                ),
                Value(0),
                output_field=quantity_field,
            ),
            sales_quantity=Coalesce(
                Sum(
                    Case(
                        When(
                            transaction_type__in=["SALE", "RETURN"],
                            then=F("quantity_change"),
                        ),
                        default=Value(0),
                        output_field=quantity_field,
                    )
                ),
                Value(0),
                output_field=quantity_field,
            ),
            damage_quantity=Coalesce(
                Sum(
                    Case(
                        When(
                            transaction_type__in=["DAMAGE", "ADJUSTMENT_OUT"],
                            then=F("quantity_change"),
                        ),
                        default=Value(0),
                        output_field=quantity_field,
                    )
                ),
                Value(0),
                output_field=quantity_field,
            ),
        )


class InventoryLogManager(SoftDeleteManager.from_queryset(InventoryLogQuerySet)):
    """Manager that keeps soft-delete filtering while exposing queryset helpers."""

    pass
