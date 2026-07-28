"""
Service layer for Cart operations: item management, price calculations, and barcode processing.
"""

from decimal import Decimal, InvalidOperation
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce

from inventory.models import BarcodeMapping, ProductVariant
from setting.models import ShopDetails
from .models import Cart, CartItem


class CartService:
    """Encapsulates core business logic for shopping carts."""

    @staticmethod
    def get_cart_summary(cart):
        """
        Retrieves cart items with optimized query, category counts, and total MRP selling price.
        """
        cart_items = (
            CartItem.objects.filter(cart=cart)
            .select_related(
                "product_variant",
                "product_variant__product",
                "product_variant__product__category",
                "product_variant__size",
                "product_variant__color",
            )
            .order_by("-created_at")
        )

        category_counts = list(
            cart_items.values(
                category_name=Coalesce(
                    "product_variant__product__category__name", Value("Other")
                )
            ).annotate(total_qty=Sum("quantity")).order_by("-total_qty")
        )

        total_selling_price = cart_items.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("product_variant__mrp"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )["total"] or Decimal("0.00")

        return {
            "cart_items": cart_items,
            "category_counts": category_counts,
            "total_selling_price": total_selling_price,
        }

    @staticmethod
    def add_variant_to_cart(cart, variant, quantity=1, price=None):
        """
        Adds a product variant to a cart or increments existing quantity.
        """
        if price is None:
            price = getattr(variant, "final_price", variant.mrp)

        cart_item = CartItem.objects.filter(
            cart=cart,
            product_variant=variant,
            price=price,
        ).first()

        if cart_item:
            cart_item.quantity += quantity
            cart_item.save(update_fields=["quantity"])
            created = False
        else:
            cart_item = CartItem.objects.create(
                cart=cart,
                product_variant=variant,
                price=price,
                quantity=quantity,
            )
            created = True

        return cart_item, created

    @staticmethod
    def resolve_variant_by_barcode(barcode):
        """
        Resolves a ProductVariant by direct barcode match or BarcodeMapping.
        """
        variant = ProductVariant.objects.filter(barcode=barcode).first()
        if not variant:
            mapping = BarcodeMapping.objects.filter(barcode=barcode).select_related("variant").first()
            if mapping:
                variant = mapping.variant
        return variant
