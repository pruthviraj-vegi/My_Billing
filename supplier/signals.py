# signals.py in your supplier app

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from decimal import Decimal
from .models import SupplierInvoice, SupplierPayment, SupplierPaymentAllocation


@receiver(pre_save, sender=SupplierPayment)
def track_payment_changes(sender, instance, **kwargs):
    """
    Track payment changes before saving to detect amount and is_deleted changes.
    """
    if instance.pk:  # Only for existing payments
        try:
            # Use all_objects to get the instance even if it's soft-deleted
            old_instance = SupplierPayment.all_objects.get(pk=instance.pk)
            instance._old_amount = old_instance.amount
            instance._old_is_deleted = old_instance.is_deleted
        except SupplierPayment.DoesNotExist:
            instance._old_amount = None
            instance._old_is_deleted = None
    else:
        instance._old_amount = None
        instance._old_is_deleted = None


@receiver(post_save, sender=SupplierPayment)
def reallocate_on_payment_change(sender, instance, created, **kwargs):
    """
    When a payment is created, updated, or soft-deleted, reallocate all payments for this supplier.
    """

    """
    for multiple or bulk 
    # In bulk import view
        def bulk_import_payments(request):
            for payment_data in data:
                payment = SupplierPayment(**payment_data)
                payment._skip_reallocation = True  # Skip signal
                payment.save()
            
            # Reallocate once after all imports
            reallocate_supplier_payments(supplier)
    """

    if getattr(instance, "_skip_reallocation", False):
        return

    # Ensure supplier is set before proceeding
    if not instance.supplier_id:
        return

    # Get old values from pre_save
    old_amount = getattr(instance, "_old_amount", None)
    old_is_deleted = getattr(instance, "_old_is_deleted", None)

    # Reallocate if:
    # 1. New payment created (created=True)
    # 2. Amount changed (for existing payments)
    # 3. Payment was soft-deleted (is_deleted changed from False to True)
    # 4. Payment was restored (is_deleted changed from True to False)
    amount_changed = old_amount is not None and old_amount != instance.amount
    deleted_changed = (
        old_is_deleted is not None and old_is_deleted != instance.is_deleted
    )

    # For new payments, always reallocate (created will be True)
    # For existing payments, reallocate if amount or is_deleted changed
    if created or amount_changed or deleted_changed:
        reallocate_supplier_payments(instance.supplier)


@receiver(pre_save, sender=SupplierInvoice)
def track_invoice_changes(sender, instance, **kwargs):
    """
    Track old total_amount before saving to detect changes.
    """
    if instance.pk:  # Only for existing invoices
        try:
            old_instance = SupplierInvoice.objects.get(pk=instance.pk)
            instance._old_total_amount = old_instance.total_amount
        except SupplierInvoice.DoesNotExist:
            instance._old_total_amount = None


@receiver(post_save, sender=SupplierInvoice)
def reallocate_on_invoice_change(sender, instance, created, **kwargs):
    """
    When an invoice is created or its total_amount changes, reallocate.
    """
    old_total = getattr(instance, "_old_total_amount", None)

    # Reallocate if:
    # 1. New invoice created
    # 2. Total amount changed
    if created or (old_total and old_total != instance.total_amount):
        reallocate_supplier_payments(instance.supplier)


@receiver(post_delete, sender=SupplierInvoice)
def reallocate_on_invoice_delete(sender, instance, **kwargs):
    """
    When an invoice is deleted, reallocate remaining invoices.
    """
    reallocate_supplier_payments(instance.supplier)


@receiver(post_delete, sender=SupplierPaymentAllocation)
def reallocate_on_allocation_delete(sender, instance, **kwargs):
    """
    When an allocation is deleted, reallocate payments for the supplier.
    """
    reallocate_supplier_payments(instance.payment.supplier)


@transaction.atomic
def reallocate_supplier_payments(supplier):
    """
    Core reallocation logic using FIFO method.
    This is called by signals automatically.
    """
    # Get all invoices and payments
    invoices = list(
        supplier.invoices.filter(is_deleted=False)
        .select_for_update()
        .order_by("invoice_date", "id")
    )

    payments = list(
        supplier.payments_made.filter(is_deleted=False)
        .select_for_update()
        .order_by("payment_date", "id")
    )

    if not invoices or not payments:
        return

    # Temporarily disconnect the allocation delete signal to prevent recursion
    # when we delete all allocations during reallocation
    post_delete.disconnect(
        reallocate_on_allocation_delete, sender=SupplierPaymentAllocation
    )

    try:
        # Delete all allocations for this supplier
        SupplierPaymentAllocation.objects.filter(
            payment__supplier=supplier, payment__is_deleted=False
        ).delete()
    finally:
        # Always reconnect the signal, even if an error occurs
        post_delete.connect(
            reallocate_on_allocation_delete, sender=SupplierPaymentAllocation
        )

    # Reset invoice states
    for invoice in invoices:
        invoice.paid_amount = Decimal("0")
        invoice.status = "UNPAID"

    # Reset payment states
    for payment in payments:
        payment.unallocated_amount = payment.amount

    # Prepare batch allocations
    allocations_to_create = []
    invoice_idx = 0

    # FIFO allocation logic
    for payment in payments:
        remaining = payment.unallocated_amount

        while invoice_idx < len(invoices) and remaining > 0:
            invoice = invoices[invoice_idx]
            amount_owed = invoice.total_amount - invoice.paid_amount

            if amount_owed <= 0:
                invoice_idx += 1
                continue

            allocation_amount = min(remaining, amount_owed)

            allocations_to_create.append(
                SupplierPaymentAllocation(
                    payment=payment,
                    invoice=invoice,
                    amount_allocated=allocation_amount,
                    created_by=payment.created_by,
                )
            )

            # Update invoice
            invoice.paid_amount += allocation_amount
            if invoice.paid_amount >= invoice.total_amount:
                invoice.status = "PAID"
                invoice_idx += 1
            else:
                invoice.status = "PARTIALLY_PAID"

            # Update payment
            remaining -= allocation_amount
            payment.unallocated_amount = remaining

    # Bulk operations
    if allocations_to_create:
        SupplierPaymentAllocation.objects.bulk_create(allocations_to_create)

    if invoices:
        SupplierInvoice.objects.bulk_update(
            invoices, ["paid_amount", "status"], batch_size=100
        )

    if payments:
        SupplierPayment.objects.bulk_update(
            payments, ["unallocated_amount"], batch_size=100
        )
