from rest_framework import serializers
from .models import Cart, CartItem
from inventory.models import ProductVariant
from decimal import Decimal


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for ProductVariant model"""

    full_name = serializers.CharField(read_only=True)
    brand = serializers.CharField(source="product.brand", read_only=True)
    simple_name = serializers.CharField(read_only=True)
    discount_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "barcode",
            "full_name",
            "mrp",
            "purchase_price",
            "brand",
            "simple_name",
            "discount_percentage",
        ]


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for CartItem model"""

    product_variant = ProductVariantSerializer(read_only=True)
    product_variant_id = serializers.IntegerField(write_only=True)
    amount = serializers.SerializerMethodField()
    product_name = serializers.CharField(read_only=True)
    discount_percentage = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "cart",
            "product_variant",
            "product_variant_id",
            "quantity",
            "price",
            "amount",
            "product_name",
            "discount_percentage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "cart",
            "amount",
            "product_name",
            "discount_percentage",
            "created_at",
            "updated_at",
        ]

    def get_amount(self, obj):
        """Calculate the amount based on quantity and price"""
        return obj.amount_property

    def get_discount_percentage(self, obj):
        """Get the discount percentage for this item"""
        return obj.discount_percentage

    def validate_quantity(self, value):
        """Validate quantity is positive"""
        from decimal import Decimal

        if value <= Decimal("0"):
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def validate_price(self, value):
        """Validate price is positive"""
        from decimal import Decimal

        if value < Decimal("0"):
            raise serializers.ValidationError("Price cannot be negative")
        return value


class CartSerializer(serializers.ModelSerializer):
    """Serializer for Cart model"""

    cart_items = CartItemSerializer(many=True, read_only=True)
    total_amount = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "name",
            "status",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
            "cart_items",
            "total_amount",
            "item_count",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def get_total_amount(self, obj):
        """Get the total amount from the cart"""
        return obj.total_amount

    def get_item_count(self, obj):
        """Get the count of items in the cart"""
        return obj.get_item_count()

    def to_representation(self, instance):
        """Optimize representation by using cached values when available"""
        data = super().to_representation(instance)

        # Use cached summary if available
        if hasattr(instance, "get_cart_summary"):
            summary = instance.get_cart_summary()
            data["total_amount"] = summary["total_amount"]
            data["item_count"] = summary["item_count"]

        return data


class CartListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing carts"""

    total_amount = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "name", "status", "total_amount", "item_count", "created_at"]

    def get_total_amount(self, obj):
        """Get the total amount from the cart"""
        return obj.total_amount

    def get_item_count(self, obj):
        """Get the count of items in the cart"""
        return obj.cart_items.count()


class BarcodeScanSerializer(serializers.Serializer):
    """Serializer for barcode scan requests"""

    barcode = serializers.CharField(max_length=100)
    cart_id = serializers.IntegerField()
    quantity = serializers.DecimalField(
        max_digits=10, decimal_places=2, default=1, min_value=Decimal("0.01")
    )

    def validate_barcode(self, value):
        """Validate that the barcode exists"""
        if not ProductVariant.objects.filter(barcode=value, status="ACTIVE").exists():
            raise serializers.ValidationError(
                "Product with this barcode not found or inactive"
            )
        return value

    def validate_cart_id(self, value):
        """Validate that the cart exists and is open"""
        if not value:
            raise serializers.ValidationError("Cart ID is required")

        try:
            cart = Cart.objects.get(id=value, status="OPEN")
        except Cart.DoesNotExist:
            raise serializers.ValidationError("Cart not found or not open")
        return value


class CartItemUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating CartItem quantities"""

    amount = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", "quantity", "price", "amount", "discount_percentage"]

    def get_amount(self, obj):
        """Calculate the amount based on quantity and price"""
        return obj.amount_property

    def get_discount_percentage(self, obj):
        """Get the discount percentage for this item"""
        return obj.discount_percentage

    def validate_quantity(self, value):
        """Validate quantity is positive"""
        from decimal import Decimal

        if value <= Decimal("0"):
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def validate_price(self, value):
        """Validate price is positive"""
        from decimal import Decimal

        if value < Decimal("0"):
            raise serializers.ValidationError("Price cannot be negative")
        return value
