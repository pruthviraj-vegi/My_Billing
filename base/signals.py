"""
Signals for cache invalidation across models.
"""

import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from base.suggestions import (
    CUSTOMER_SEARCH_FIELDS,
    INVOICE_SEARCH_FIELDS,
    PRODUCT_SEARCH_FIELDS,
    PRODUCT_VARIANT_SEARCH_FIELDS,
    SUPPLIER_SEARCH_FIELDS,
    get_instance_tokens,
    invalidate_cache,
)
from customer.models import Customer
from inventory.models import Product, ProductVariant
from invoice.models import Invoice
from supplier.models import Supplier

logger = logging.getLogger(__name__)


def check_and_invalidate(instance, fields, cache_key, old_tokens=None):
    """
    Compares old tokens (from pre_save) with new tokens (current instance).
    Invalidates cache ONLY if tokens have changed.
    For new instances (created=True), old_tokens will be None/Empty.
    """
    new_tokens = get_instance_tokens(instance, fields)

    if old_tokens is None:
        # Case: Created (Post-Save where we didn't have pre-save state? No, pre-save always runs)
        # Actually, for new objects, old_tokens should be empty set.
        pass

    # If sets are different, invalidate
    if old_tokens != new_tokens:
        logger.info("Tokens changed for %s (%s). Invalidating.", instance, cache_key)
        invalidate_cache(cache_key)
    else:
        logger.info("No token changes for %s. Cache preserved.", instance)


# --- Customer ---
@receiver(pre_save, sender=Customer)
def capture_customer_tokens(sender, instance, **kwargs):
    """Capture tokens for Customer before saving."""
    if instance.pk:
        try:
            old_inst = Customer.objects.get(pk=instance.pk)
            setattr(
                instance,
                "old_tokens",
                get_instance_tokens(old_inst, CUSTOMER_SEARCH_FIELDS),
            )
        except Customer.DoesNotExist:
            setattr(instance, "old_tokens", set())
    else:
        setattr(instance, "old_tokens", set())


@receiver(post_save, sender=Customer)
def invalidate_customer_cache(sender, instance, **kwargs):
    """Invalidate Customer cache if search tokens have changed."""
    check_and_invalidate(
        instance,
        CUSTOMER_SEARCH_FIELDS,
        "customer_search_words",
        getattr(instance, "old_tokens", set()),
    )


@receiver(post_delete, sender=Customer)
def delete_customer_cache(sender, instance, **kwargs):
    """Invalidate Customer cache when a Customer is deleted."""
    invalidate_cache("customer_search_words")


# --- Invoice ---
@receiver(pre_save, sender=Invoice)
def capture_invoice_tokens(sender, instance, **kwargs):
    """Capture tokens for Invoice before saving."""
    if instance.pk:
        try:
            old_inst = Invoice.objects.get(pk=instance.pk)
            setattr(
                instance,
                "old_tokens",
                get_instance_tokens(old_inst, INVOICE_SEARCH_FIELDS),
            )
        except Invoice.DoesNotExist:
            setattr(instance, "old_tokens", set())
    else:
        setattr(instance, "old_tokens", set())


@receiver(post_save, sender=Invoice)
def invalidate_invoice_cache(sender, instance, **kwargs):
    """Invalidate Invoice cache if search tokens have changed."""
    check_and_invalidate(
        instance,
        INVOICE_SEARCH_FIELDS,
        "invoice_search_words",
        getattr(instance, "old_tokens", set()),
    )


@receiver(post_delete, sender=Invoice)
def delete_invoice_cache(sender, instance, **kwargs):
    """Invalidate Invoice cache when an Invoice is deleted."""
    invalidate_cache("invoice_search_words")


# --- Product ---
@receiver(pre_save, sender=Product)
def capture_product_tokens(sender, instance, **kwargs):
    """Capture tokens for Product before saving."""
    if instance.pk:
        try:
            old_inst = Product.objects.get(pk=instance.pk)
            setattr(
                instance,
                "old_tokens",
                get_instance_tokens(old_inst, PRODUCT_SEARCH_FIELDS),
            )
        except Product.DoesNotExist:
            setattr(instance, "old_tokens", set())
    else:
        setattr(instance, "old_tokens", set())


@receiver(post_save, sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    """Invalidate Product cache if search tokens have changed."""
    check_and_invalidate(
        instance,
        PRODUCT_SEARCH_FIELDS,
        "product_search_words",
        getattr(instance, "old_tokens", set()),
    )


@receiver(post_delete, sender=Product)
def delete_product_cache(sender, instance, **kwargs):
    """Invalidate Product cache when a Product is deleted."""
    invalidate_cache("product_search_words")


# --- Product Variant ---
@receiver(pre_save, sender=ProductVariant)
def capture_variant_tokens(sender, instance, **kwargs):
    """Capture tokens for ProductVariant before saving."""
    if instance.pk:
        try:
            old_inst = ProductVariant.objects.get(pk=instance.pk)
            setattr(
                instance,
                "old_tokens",
                get_instance_tokens(old_inst, PRODUCT_VARIANT_SEARCH_FIELDS),
            )
        except ProductVariant.DoesNotExist:
            setattr(instance, "old_tokens", set())
    else:
        setattr(instance, "old_tokens", set())


@receiver(post_save, sender=ProductVariant)
def invalidate_product_variant_cache(sender, instance, **kwargs):
    """Invalidate ProductVariant and potentially Product cache if search tokens change."""
    old_tokens = getattr(instance, "old_tokens", set())
    # Variant affects its own cache AND Product cache (potentially)
    # We check basic variant tokens
    check_and_invalidate(
        instance,
        PRODUCT_VARIANT_SEARCH_FIELDS,
        "product_variant_search_words",
        old_tokens,
    )

    # NOTE: Changing a variant might implies Product search change?
    # Current logic: Variant has "product__name" in fields.
    # If valid logic mandates, we invalidate product too.
    # For now, let's keep it simple: if variant tokens change, invalidate product too safely?
    # Or just check changes.
    if old_tokens != get_instance_tokens(instance, PRODUCT_VARIANT_SEARCH_FIELDS):
        invalidate_cache("product_search_words")


@receiver(post_delete, sender=ProductVariant)
def delete_product_variant_cache(sender, instance, **kwargs):
    """Invalidate ProductVariant and Product caches when a variant is deleted."""
    invalidate_cache("product_variant_search_words")
    invalidate_cache("product_search_words")


# --- Supplier ---
@receiver(pre_save, sender=Supplier)
def capture_supplier_tokens(sender, instance, **kwargs):
    """Capture tokens for Supplier before saving."""
    if instance.pk:
        try:
            old_inst = Supplier.objects.get(pk=instance.pk)
            setattr(
                instance,
                "old_tokens",
                get_instance_tokens(old_inst, SUPPLIER_SEARCH_FIELDS),
            )
        except Supplier.DoesNotExist:
            setattr(instance, "old_tokens", set())
    else:
        setattr(instance, "old_tokens", set())


@receiver(post_save, sender=Supplier)
def invalidate_supplier_cache(sender, instance, **kwargs):
    """Invalidate Supplier cache if search tokens have changed."""
    check_and_invalidate(
        instance,
        SUPPLIER_SEARCH_FIELDS,
        "supplier_search_words",
        getattr(instance, "old_tokens", set()),
    )


@receiver(post_delete, sender=Supplier)
def delete_supplier_cache(sender, instance, **kwargs):
    """Invalidate Supplier cache when a Supplier is deleted."""
    invalidate_cache("supplier_search_words")
