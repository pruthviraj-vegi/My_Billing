# signals.py for customer payment allocation

from django.db.models.signals import post_save, post_delete, pre_save, m2m_changed
from django.dispatch import receiver
from django.db import transaction
from decimal import Decimal
from .models import Customer, Payment
from invoice.models import Invoice, PaymentAllocation
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Payment)
def track_payment_changes(sender, instance, **kwargs):
    """
    Track payment changes before saving to detect amount and is_deleted changes.
    """
    if instance.pk:  # Only for existing payments
        try:
            # Use all_objects to get the instance even if it's soft-deleted
            old_instance = Payment.all_objects.get(pk=instance.pk)
            instance._old_amount = old_instance.amount
            instance._old_is_deleted = old_instance.is_deleted
            instance._old_payment_type = old_instance.payment_type
        except Payment.DoesNotExist:
            instance._old_amount = None
            instance._old_is_deleted = None
            instance._old_payment_type = None
    else:
        instance._old_amount = None
        instance._old_is_deleted = None
        instance._old_payment_type = None


@receiver(post_save, sender=Payment)
def reallocate_on_payment_change(sender, instance, created, **kwargs):
    """
    When a payment is created, updated, or soft-deleted, reallocate all payments for this customer.
    """
    if getattr(instance, "_skip_reallocation", False):
        return

    # Ensure customer is set before proceeding
    if not instance.customer_id:
        return

    # Get old values from pre_save
    old_amount = getattr(instance, "_old_amount", None)
    old_is_deleted = getattr(instance, "_old_is_deleted", None)
    old_payment_type = getattr(instance, "_old_payment_type", None)

    # Reallocate if:
    # 1. New payment created (created=True)
    # 2. Amount changed (for existing payments)
    # 3. Payment type changed (Paid <-> Purchased)
    # 4. Payment was soft-deleted (is_deleted changed from False to True)
    # 5. Payment was restored (is_deleted changed from True to False)
    amount_changed = old_amount is not None and old_amount != instance.amount
    deleted_changed = (
        old_is_deleted is not None and old_is_deleted != instance.is_deleted
    )
    type_changed = (
        old_payment_type is not None and old_payment_type != instance.payment_type
    )

    # For new payments, always reallocate (created will be True)
    # For existing payments, reallocate if amount, type, or is_deleted changed
    if created or amount_changed or deleted_changed or type_changed:
        reallocate_customer_payments(instance.customer)


@receiver(pre_save, sender=Invoice)
def track_invoice_changes(sender, instance, **kwargs):
    """
    Track old values before saving to detect changes.
    Only track for CREDIT invoices.
    """
    if instance.pk and instance.payment_type == Invoice.PaymentType.CREDIT:
        try:
            old_instance = Invoice.objects.get(pk=instance.pk)
            instance._old_amount = old_instance.amount
            instance._old_discount_amount = old_instance.discount_amount
            instance._old_advance_amount = old_instance.advance_amount
            instance._old_customer = old_instance.customer
        except Invoice.DoesNotExist:
            instance._old_amount = None
            instance._old_discount_amount = None
            instance._old_advance_amount = None
            instance._old_customer = None
    else:
        instance._old_amount = None
        instance._old_discount_amount = None
        instance._old_advance_amount = None
        instance._old_customer = None


@receiver(post_save, sender=Invoice)
def reallocate_on_invoice_change(sender, instance, created, **kwargs):
    """
    When a CREDIT invoice is created or its financial amounts change, reallocate.
    """
    # Skip if reallocation is being handled elsewhere
    if getattr(instance, "_skip_reallocation", False):
        return

    # Only process CREDIT invoices
    if instance.payment_type != Invoice.PaymentType.CREDIT:
        return

    old_amount = getattr(instance, "_old_amount", None)
    old_discount = getattr(instance, "_old_discount_amount", None)
    old_advance = getattr(instance, "_old_advance_amount", None)
    old_customer = getattr(instance, "_old_customer", None)

    # Reallocate if:
    # 1. New invoice created
    # 2. Amount, discount, or advance changed (affects net_amount_due)
    amount_changed = old_amount is not None and old_amount != instance.amount
    discount_changed = (
        old_discount is not None and old_discount != instance.discount_amount
    )
    advance_changed = old_advance is not None and old_advance != instance.advance_amount
    customer_changed = old_customer is not None and old_customer != instance.customer

    if (
        created
        or amount_changed
        or discount_changed
        or advance_changed
        or customer_changed
    ):
        reallocate_customer_payments(instance.customer)
        if customer_changed:
            reallocate_customer_payments(old_customer)


@receiver(post_delete, sender=Invoice)
def reallocate_on_invoice_delete(sender, instance, **kwargs):
    """
    When a CREDIT invoice is deleted, reallocate remaining invoices.
    """
    if instance.payment_type == Invoice.PaymentType.CREDIT:
        reallocate_customer_payments(instance.customer)


@receiver(post_delete, sender=PaymentAllocation)
def reallocate_on_allocation_delete(sender, instance, **kwargs):
    """
    When an allocation is deleted, reallocate payments for the customer.
    """
    reallocate_customer_payments(instance.payment.customer)


@transaction.atomic
def reallocate_customer_payments(customer, skip_signals=False):
    """
    Core reallocation logic using FIFO method.
    For Paid payments: First covers Purchased payments, then allocates to invoices.
    This is called by signals automatically.

    Args:
        customer: Customer instance to reallocate payments for
        skip_signals: If True, mark payments/invoices to skip signal triggers during updates
    """
    # Get all CREDIT invoices
    # Note: Invoice model doesn't have is_deleted field (not a SoftDeleteModel)
    invoices = list(
        Invoice.objects.filter(
            customer=customer,
            payment_type=Invoice.PaymentType.CREDIT,
            is_cancelled=False,
        )
        .select_for_update()
        .order_by("invoice_date", "id")
    )

    # Get all Paid payments (these allocate to invoices and cover Purchased payments)
    paid_payments = list(
        Payment.objects.filter(
            customer=customer,
            payment_type=Payment.PaymentType.Paid,
            is_deleted=False,
        )
        .select_for_update()
        .order_by("payment_date", "id")
    )

    # Get all Purchased payments (these need to be covered by Paid payments)
    purchased_payments = list(
        Payment.objects.filter(
            customer=customer,
            payment_type=Payment.PaymentType.Purchased,
            is_deleted=False,
        )
        .select_for_update()
        .order_by("payment_date", "id")
    )

    if not paid_payments and not purchased_payments:
        # No payments to allocate, but reset invoice states
        for invoice in invoices:
            invoice.paid_amount = Decimal("0")
            invoice.payment_status = Invoice.PaymentStatus.UNPAID
        if invoices:
            Invoice.objects.bulk_update(
                invoices,
                ["paid_amount", "payment_status", "updated_at"],
                batch_size=100,
            )
        return

    # Temporarily disconnect the allocation delete signal to prevent recursion
    # when we delete all allocations during reallocation
    post_delete.disconnect(reallocate_on_allocation_delete, sender=PaymentAllocation)

    try:
        # Delete all allocations for this customer
        PaymentAllocation.objects.filter(
            payment__customer=customer, payment__is_deleted=False
        ).delete()
    finally:
        # Always reconnect the signal, even if an error occurs
        post_delete.connect(reallocate_on_allocation_delete, sender=PaymentAllocation)

    # Reset invoice states
    for invoice in invoices:
        invoice.paid_amount = Decimal("0")
        invoice.payment_status = Invoice.PaymentStatus.UNPAID
        if skip_signals:
            invoice._skip_reallocation = True

    # Reset payment states
    for payment in paid_payments:
        payment.unallocated_amount = payment.amount
        if skip_signals:
            payment._skip_reallocation = True

    for purchased_payment in purchased_payments:
        purchased_payment.unallocated_amount = purchased_payment.amount
        if skip_signals:
            purchased_payment._skip_reallocation = True

    # Prepare batch allocations
    allocations_to_create = []

    # Create unified FIFO list: combine invoices and purchased payments, sorted by date
    # This ensures oldest items (whether invoice or purchased payment) are handled first
    unified_items = []

    # Add invoices with their date and type
    for invoice in invoices:
        unified_items.append(
            {
                "type": "invoice",
                "date": invoice.invoice_date,
                "id": invoice.id,
                "object": invoice,
                "amount_owed": invoice.remaining_amount,
            }
        )

    # Add purchased payments with their date and type
    for purchased_payment in purchased_payments:
        unified_items.append(
            {
                "type": "purchased_payment",
                "date": purchased_payment.payment_date,
                "id": purchased_payment.id,
                "object": purchased_payment,
                "amount_owed": purchased_payment.unallocated_amount,
            }
        )

    # Sort by date (oldest first), then by id for stability
    unified_items.sort(key=lambda x: (x["date"], x["id"]))

    # FIFO allocation logic for Paid payments
    # Allocate to unified list in chronological order (oldest first)
    for paid_payment in paid_payments:
        remaining = paid_payment.unallocated_amount
        item_idx = 0

        while item_idx < len(unified_items) and remaining > 0:
            item = unified_items[item_idx]
            amount_owed = item["amount_owed"]

            # Skip items that are already fully paid/covered
            if amount_owed <= 0:
                item_idx += 1
                continue

            allocation_amount = min(remaining, amount_owed)

            if item["type"] == "invoice":
                # Allocate to invoice
                invoice = item["object"]

                allocations_to_create.append(
                    PaymentAllocation(
                        payment=paid_payment,
                        invoice=invoice,
                        amount_allocated=allocation_amount,
                        created_by=paid_payment.created_by,
                    )
                )

                # Update invoice
                invoice.paid_amount += allocation_amount
                # Check if fully paid using net_amount_due (amount - discount - advance)
                if invoice.paid_amount >= invoice.net_amount_due:
                    invoice.payment_status = Invoice.PaymentStatus.PAID
                    item["amount_owed"] = Decimal("0")  # Mark as fully paid
                    item_idx += 1
                elif invoice.paid_amount > 0:
                    invoice.payment_status = Invoice.PaymentStatus.PARTIALLY_PAID
                    # Update remaining amount using the property (recalculates automatically)
                    item["amount_owed"] = invoice.remaining_amount

                logger.debug(
                    f"Allocated {allocation_amount} from payment {paid_payment.id} "
                    f"to invoice {invoice.id} (date: {invoice.invoice_date})"
                )

            elif item["type"] == "purchased_payment":
                # Cover purchased payment
                purchased_payment = item["object"]

                # Update purchased payment's unallocated amount
                purchased_payment.unallocated_amount -= allocation_amount
                item["amount_owed"] = (
                    purchased_payment.unallocated_amount
                )  # Update remaining

                # If fully covered, move to next item
                if item["amount_owed"] <= 0:
                    item_idx += 1

                logger.debug(
                    f"Covered purchased payment {purchased_payment.id} "
                    f"(date: {purchased_payment.payment_date}) "
                    f"with {allocation_amount} from paid payment {paid_payment.id}"
                )

            # Update payment
            remaining -= allocation_amount
            paid_payment.unallocated_amount = remaining

    # Bulk operations
    if allocations_to_create:
        PaymentAllocation.objects.bulk_create(allocations_to_create)

    if invoices:
        Invoice.objects.bulk_update(
            invoices, ["paid_amount", "payment_status", "updated_at"], batch_size=100
        )

    if paid_payments:
        Payment.objects.bulk_update(
            paid_payments, ["unallocated_amount", "updated_at"], batch_size=100
        )

    if purchased_payments:
        Payment.objects.bulk_update(
            purchased_payments, ["unallocated_amount", "updated_at"], batch_size=100
        )

    # Update CustomerCreditSummary since bulk_update skips signals
    from customer.models import CustomerCreditSummary

    CustomerCreditSummary.recalculate_for_customer(customer, save=True)


# ============================================
# 2. OPTIMIZED SIGNALS with Bulk Updates
# ============================================
# Create: customer/signals.py

# Thread-local storage for batch updates
_pending_updates = defaultdict(set)


def queue_customer_update(customer_id):
    """Queue customer for batch update"""
    _pending_updates[transaction.get_connection().alias].add(customer_id)


def process_queued_updates():
    """Process all queued updates in a single batch"""
    from customer.models import Customer, CustomerCreditSummary

    connection_alias = transaction.get_connection().alias
    customer_ids = _pending_updates.pop(connection_alias, set())

    if not customer_ids:
        return

    # Bulk recalculate
    customers = Customer.objects.filter(id__in=customer_ids)
    for customer in customers:
        try:
            CustomerCreditSummary.recalculate_for_customer(customer)
        except Exception as e:
            logger.error(f"Failed to update summary for customer {customer.id}: {e}")


@receiver([post_save, post_delete], sender="invoice.ReturnInvoice")
def handle_return_change(sender, instance, **kwargs):
    """Queue credit summary update when return changes"""
    if instance.status in ["APPROVED", "COMPLETED"]:
        queue_customer_update(instance.customer_id)
        transaction.on_commit(process_queued_updates)


@receiver(post_save, sender="customer.Customer")
def create_summary_for_new_customer(sender, instance, created, **kwargs):
    """Create empty summary when customer is created"""
    if created:
        from customer.models import CustomerCreditSummary

        CustomerCreditSummary.objects.get_or_create(customer=instance)
