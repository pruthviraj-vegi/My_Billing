"""Tests for the cart app services."""

from decimal import Decimal

from django.test import TestCase

from cart.services import CartService
from cart.models import Cart, CartItem
from inventory.models import BarcodeMapping
from Billing.tests.helpers import (
    create_test_user,
    create_test_variant,
    create_test_product,
    create_test_cart,
)


class AddVariantToCartTests(TestCase):
    """Tests for CartService.add_variant_to_cart()."""

    def setUp(self):
        self.user = create_test_user()
        self.variant = create_test_variant(user=self.user)
        self.cart = create_test_cart(user=self.user)

    def test_new_item_creates(self):
        cart_item, created = CartService.add_variant_to_cart(
            self.cart, self.variant, quantity=2
        )
        self.assertTrue(created)
        self.assertEqual(cart_item.quantity, 2)
        self.assertEqual(cart_item.cart, self.cart)
        self.assertEqual(cart_item.product_variant, self.variant)

    def test_new_item_with_explicit_price(self):
        cart_item, created = CartService.add_variant_to_cart(
            self.cart, self.variant, quantity=1, price=Decimal("150.00")
        )
        self.assertTrue(created)
        self.assertEqual(cart_item.price, Decimal("150.00"))

    def test_new_item_defaults_price_to_final_price(self):
        cart_item, created = CartService.add_variant_to_cart(
            self.cart, self.variant, quantity=1
        )
        self.assertTrue(created)
        self.assertEqual(cart_item.price, self.variant.final_price)

    def test_existing_item_increments_quantity(self):
        CartService.add_variant_to_cart(self.cart, self.variant, quantity=2, price=Decimal("150.00"))
        cart_item, created = CartService.add_variant_to_cart(
            self.cart, self.variant, quantity=3, price=Decimal("150.00")
        )
        self.assertFalse(created)
        self.assertEqual(cart_item.quantity, 5)

    def test_existing_item_different_price_creates_new(self):
        CartService.add_variant_to_cart(self.cart, self.variant, quantity=2, price=Decimal("150.00"))
        cart_item, created = CartService.add_variant_to_cart(
            self.cart, self.variant, quantity=1, price=Decimal("160.00")
        )
        self.assertTrue(created)
        self.assertEqual(cart_item.quantity, 1)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 2)

    def test_default_quantity_is_one(self):
        cart_item, created = CartService.add_variant_to_cart(
            self.cart, self.variant
        )
        self.assertEqual(cart_item.quantity, 1)


class ResolveVariantByBarcodeTests(TestCase):
    """Tests for CartService.resolve_variant_by_barcode()."""

    def setUp(self):
        self.user = create_test_user()
        self.variant = create_test_variant(
            barcode="SCAN001", user=self.user
        )
        self.other_variant = create_test_variant(
            barcode="SCAN002", user=self.user, mrp=Decimal("200.00")
        )

    def test_direct_match(self):
        result = CartService.resolve_variant_by_barcode("SCAN001")
        self.assertEqual(result, self.variant)

    def test_no_match_returns_none(self):
        result = CartService.resolve_variant_by_barcode("NONEXISTENT")
        self.assertIsNone(result)

    def test_barcode_mapping_match(self):
        BarcodeMapping.objects.create(
            barcode="ALT001",
            variant=self.other_variant,
        )
        result = CartService.resolve_variant_by_barcode("ALT001")
        self.assertEqual(result, self.other_variant)

    def test_barcode_mapping_prefers_direct_variant_match(self):
        variant_with_same_barcode_as_mapping = create_test_variant(
            barcode="CONFLICT", user=self.user, mrp=Decimal("300.00")
        )
        BarcodeMapping.objects.create(
            barcode="CONFLICT",
            variant=self.other_variant,
        )
        result = CartService.resolve_variant_by_barcode("CONFLICT")
        self.assertEqual(result, variant_with_same_barcode_as_mapping)
