from django.db import models
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
