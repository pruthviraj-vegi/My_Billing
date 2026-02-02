from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from customer.models import Customer
from invoice.models import Invoice
from inventory.models import Product, ProductVariant
from supplier.models import Supplier
from base.suggestions import (
    invalidate_cache,
    get_instance_tokens,
    CUSTOMER_SEARCH_FIELDS,
    INVOICE_SEARCH_FIELDS,
    PRODUCT_SEARCH_FIELDS,
    PRODUCT_VARIANT_SEARCH_FIELDS,
    SUPPLIER_SEARCH_FIELDS,
)
import logging

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
        logger.info(f"Tokens changed for {instance} ({cache_key}). Invalidating.")
        invalidate_cache(cache_key)
    else:
        logger.info(f"No token changes for {instance}. Cache preserved.")


# --- Customer ---
@receiver(pre_save, sender=Customer)
def capture_customer_tokens(sender, instance, **kwargs):
    # If it's an update (pk exists), capture old tokens
    if instance.pk:
        try:
            old_inst = Customer.objects.get(pk=instance.pk)
            instance._old_tokens = get_instance_tokens(old_inst, CUSTOMER_SEARCH_FIELDS)
        except Customer.DoesNotExist:
            instance._old_tokens = set()
    else:
        instance._old_tokens = set()


@receiver(post_save, sender=Customer)
def invalidate_customer_cache(sender, instance, **kwargs):
    check_and_invalidate(
        instance,
        CUSTOMER_SEARCH_FIELDS,
        "customer_search_words",
        getattr(instance, "_old_tokens", set()),
    )


@receiver(post_delete, sender=Customer)
def delete_customer_cache(sender, instance, **kwargs):
    invalidate_cache("customer_search_words")


# --- Invoice ---
@receiver(pre_save, sender=Invoice)
def capture_invoice_tokens(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_inst = Invoice.objects.get(pk=instance.pk)
            instance._old_tokens = get_instance_tokens(old_inst, INVOICE_SEARCH_FIELDS)
        except Invoice.DoesNotExist:
            instance._old_tokens = set()
    else:
        instance._old_tokens = set()


@receiver(post_save, sender=Invoice)
def invalidate_invoice_cache(sender, instance, **kwargs):
    check_and_invalidate(
        instance,
        INVOICE_SEARCH_FIELDS,
        "invoice_search_words",
        getattr(instance, "_old_tokens", set()),
    )


@receiver(post_delete, sender=Invoice)
def delete_invoice_cache(sender, instance, **kwargs):
    invalidate_cache("invoice_search_words")


# --- Product ---
@receiver(pre_save, sender=Product)
def capture_product_tokens(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_inst = Product.objects.get(pk=instance.pk)
            instance._old_tokens = get_instance_tokens(old_inst, PRODUCT_SEARCH_FIELDS)
        except Product.DoesNotExist:
            instance._old_tokens = set()
    else:
        instance._old_tokens = set()


@receiver(post_save, sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    check_and_invalidate(
        instance,
        PRODUCT_SEARCH_FIELDS,
        "product_search_words",
        getattr(instance, "_old_tokens", set()),
    )


@receiver(post_delete, sender=Product)
def delete_product_cache(sender, instance, **kwargs):
    invalidate_cache("product_search_words")


# --- Product Variant ---
@receiver(pre_save, sender=ProductVariant)
def capture_variant_tokens(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_inst = ProductVariant.objects.get(pk=instance.pk)
            instance._old_tokens = get_instance_tokens(
                old_inst, PRODUCT_VARIANT_SEARCH_FIELDS
            )
        except ProductVariant.DoesNotExist:
            instance._old_tokens = set()
    else:
        instance._old_tokens = set()


@receiver(post_save, sender=ProductVariant)
def invalidate_product_variant_cache(sender, instance, **kwargs):
    old_tokens = getattr(instance, "_old_tokens", set())
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
    invalidate_cache("product_variant_search_words")
    invalidate_cache("product_search_words")


# --- Supplier ---
@receiver(pre_save, sender=Supplier)
def capture_supplier_tokens(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_inst = Supplier.objects.get(pk=instance.pk)
            instance._old_tokens = get_instance_tokens(old_inst, SUPPLIER_SEARCH_FIELDS)
        except Supplier.DoesNotExist:
            instance._old_tokens = set()
    else:
        instance._old_tokens = set()


@receiver(post_save, sender=Supplier)
def invalidate_supplier_cache(sender, instance, **kwargs):
    check_and_invalidate(
        instance,
        SUPPLIER_SEARCH_FIELDS,
        "supplier_search_words",
        getattr(instance, "_old_tokens", set()),
    )


@receiver(post_delete, sender=Supplier)
def delete_supplier_cache(sender, instance, **kwargs):
    invalidate_cache("supplier_search_words")
