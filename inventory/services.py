"""
Services module for complex inventory operations like stock in, out, sale, return,
cancellation, and damage tracking.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import DamagedItemRecord, InventoryLog
from supplier.models import SupplierInvoice

logger = logging.getLogger(__name__)


class InventoryService:
    """Service class for inventory operations"""

    @staticmethod
    def apply_discount(variant, percentage, user=None):
        """Apply discount and log the change"""
        if 0 <= percentage <= 100:
            with transaction.atomic():
                variant.discount_percentage = percentage
                variant.save()

                InventoryLog.objects.create(
                    variant=variant,
                    created_by=user,
                    quantity_change=0,
                    new_quantity=variant.quantity,
                    transaction_type=InventoryLog.TransactionTypes.ADJUSTMENT_IN,
                    notes=f"Discount applied: {percentage}%",
                )

    @staticmethod
    def update_quantity(variant, change, user=None, notes="", supplier_invoice=None):
        """Safely update quantity and create log entry"""
        with transaction.atomic():
            new_quantity = variant.quantity + change
            variant.quantity = new_quantity
            variant.save()

            InventoryLog.objects.create(
                variant=variant,
                created_by=user,
                quantity_change=change,
                new_quantity=new_quantity,
                transaction_type=InventoryLog.TransactionTypes.STOCK_IN,
                total_value=change * variant.purchase_price,
                notes=notes or f"Stock In: {change} units",
                supplier_invoice=supplier_invoice,
            )

    @staticmethod
    def adjust_in_quantity(variant, change, user=None, notes=""):
        """Adjust quantity and create log entry"""
        with transaction.atomic():
            if change == 0:
                raise ValueError("Quantity change cannot be zero")

            new_quantity = variant.quantity + change
            variant.quantity = new_quantity
            variant.save()

            InventoryLog.objects.create(
                variant=variant,
                created_by=user,
                quantity_change=change,
                new_quantity=new_quantity,
                transaction_type=InventoryLog.TransactionTypes.ADJUSTMENT_IN,
                total_value=change * variant.purchase_price,
                notes=notes or f"Adjustment In: {change} units",
            )

    @staticmethod
    def adjust_out_quantity(variant, change, user=None, notes=""):
        """Adjust quantity and create log entry"""
        with transaction.atomic():
            if change == 0:
                raise ValueError("Quantity change cannot be zero")

            new_quantity = variant.quantity - change
            variant.quantity = new_quantity
            variant.save()

            InventoryLog.objects.create(
                variant=variant,
                created_by=user,
                quantity_change=-change,
                new_quantity=new_quantity,
                transaction_type=InventoryLog.TransactionTypes.ADJUSTMENT_OUT,
                total_value=change * variant.purchase_price,
                notes=notes or f"Adjustment Out: {change} units",
            )

    @staticmethod
    def create_initial_log(variant, user=None, notes="", supplier_invoice=None):
        """Create initial log entry for a new variant"""
        try:
            with transaction.atomic():
                inventory_log = InventoryLog.objects.create(
                    variant=variant,
                    created_by=user,
                    quantity_change=variant.quantity,
                    new_quantity=variant.quantity,
                    purchase_price=variant.purchase_price,
                    remaining_quantity=variant.quantity,
                    mrp=variant.mrp,
                    total_value=variant.quantity * variant.purchase_price,
                    transaction_type=InventoryLog.TransactionTypes.INITIAL,
                    notes=notes or f"Initial Stock: {variant.quantity} units",
                    supplier_invoice=supplier_invoice,
                )
                return inventory_log

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Failed to create initial log: %s", e)
            return None

    _SENTINEL = object()

    @staticmethod
    def update_initial_log(variant, user=None, notes="", supplier_invoice=_SENTINEL):
        """Update the initial inventory log entry for a variant"""
        log_data = InventoryLog.objects.filter(
            variant=variant,
            transaction_type=InventoryLog.TransactionTypes.INITIAL,
        ).first()
        if log_data:
            has_other_transactions = InventoryLog.objects.filter(
                variant=variant
            ).exclude(id=log_data.id).exists()

            if not has_other_transactions:
                if variant.quantity >= 0:
                    log_data.quantity_change = variant.quantity
                    log_data.new_quantity = variant.quantity
                    log_data.remaining_quantity = variant.quantity
                    log_data.total_value = variant.quantity * variant.purchase_price
                    log_data.notes = notes or f"Initial Stock: {variant.quantity} units"
                else:
                    # Negative quantity: preserve existing initial log quantity_change
                    if notes:
                        log_data.notes = notes
            else:
                # Stock movements have occurred — if present quantity >= 0, adjust initial quantity calculation
                if variant.quantity >= 0:
                    other_logs = InventoryLog.objects.filter(variant=variant).exclude(id=log_data.id)
                    stock_out_total = Decimal("0")
                    stock_in_total = Decimal("0")
                    for l in other_logs:
                        if l.transaction_type in [
                            InventoryLog.TransactionTypes.SALE,
                            InventoryLog.TransactionTypes.DAMAGE,
                            InventoryLog.TransactionTypes.ADJUSTMENT_OUT,
                        ]:
                            stock_out_total += abs(l.quantity_change)
                        elif l.transaction_type in [
                            InventoryLog.TransactionTypes.STOCK_IN,
                            InventoryLog.TransactionTypes.ADJUSTMENT_IN,
                            InventoryLog.TransactionTypes.RETURN,
                            InventoryLog.TransactionTypes.CANCEL,
                        ]:
                            stock_in_total += abs(l.quantity_change)

                    calculated_initial = variant.quantity + stock_out_total - stock_in_total
                    if calculated_initial >= 0:
                        log_data.quantity_change = calculated_initial
                        allocated = (
                            InventoryLog.objects.filter(source_inventory_log=log_data)
                            .aggregate(total=Sum("allocated_quantity"))["total"]
                            or Decimal("0")
                        )
                        log_data.remaining_quantity = max(calculated_initial - allocated, Decimal("0"))

                log_data.total_value = log_data.quantity_change * variant.purchase_price
                if notes:
                    log_data.notes = notes

            log_data.purchase_price = variant.purchase_price
            log_data.mrp = variant.mrp
            if supplier_invoice is not InventoryService._SENTINEL:
                log_data.supplier_invoice = supplier_invoice
            log_data.created_by = user
            log_data.save()

    @staticmethod
    def update_stock_in_log(
        variant,
        quantity_change,
        user=None,
        notes="",
        supplier_invoice=None,
        purchase_price=None,
        mrp=None,
    ):
        """Update stock in log for a variant"""
        try:
            with transaction.atomic():
                new_quantity = variant.quantity + quantity_change
                variant.quantity = new_quantity

                if purchase_price != variant.purchase_price:
                    variant.purchase_price = purchase_price

                if mrp != variant.mrp:
                    variant.mrp = mrp

                variant.save()

                inventory_log = InventoryLog.objects.create(
                    variant=variant,
                    supplier_invoice=supplier_invoice,
                    transaction_type=InventoryLog.TransactionTypes.STOCK_IN,
                    created_by=user,
                    quantity_change=quantity_change,
                    remaining_quantity=quantity_change,
                    new_quantity=variant.quantity,
                    total_value=quantity_change
                    * (purchase_price or variant.purchase_price),
                    purchase_price=purchase_price or variant.purchase_price,
                    mrp=mrp or variant.mrp,
                    notes=notes or f"Stock In: {quantity_change} units",
                )

                return inventory_log

        except Exception as e:  # pylint: disable=broad-except
            logger.error("Error updating stock in log: %s", e)
            return None

    @staticmethod
    def sale(variant, quantity_sold, user=None, invoice_item="", notes=""):
        """Process a sale and automatically update inventory

        Args:
            variant: The variant being sold
            quantity_sold: Amount sold
            user: User performing sale
            invoice_item: Associated invoice item
            notes: Sale notes

        Returns:
            dict: Result of sale process
        """
        with transaction.atomic():
            if quantity_sold <= 0:
                raise ValueError("Sale quantity must be positive")

            # Use selling price from invoice_item if available, otherwise variant's final_price
            unit_price = (
                invoice_item.unit_price if invoice_item else variant.final_price
            )

            # Perform FIFO allocation FIRST
            allocation_result = InventoryService._allocate_fifo(
                variant=variant,
                quantity_to_allocate=quantity_sold,
                invoice_item=invoice_item,
                unit_price=unit_price,
                user=user,
                notes=notes,
            )

            # Update variant quantity AFTER FIFO allocation
            new_quantity = variant.quantity - quantity_sold
            variant.quantity = new_quantity
            variant.save()

            return {
                "success": True,
                "quantity_sold": quantity_sold,
                "remaining_stock": new_quantity,
                "total_amount": quantity_sold * unit_price,
                "cogs": allocation_result["total_cogs"],
                "gross_profit": (quantity_sold * unit_price)
                - allocation_result["total_cogs"],
                "allocation_logs": allocation_result["logs"],
                "insufficient_stock_warning": allocation_result.get(
                    "insufficient_stock", False
                ),
            }

    @staticmethod
    def _allocate_fifo(
        variant,
        quantity_to_allocate,
        invoice_item=None,
        unit_price=None,
        user=None,
        notes="",
    ):
        """Internal method to perform FIFO allocation

        Args:
            variant: The product variant to allocate stock from
            quantity_to_allocate: Amount of stock to allocate
            invoice_item: The associated invoice item (optional)
            unit_price: Selling price per unit (optional)
            user: The user performing the action (optional)
            notes: Additional notes for the log (optional)

        Returns:
            dict: Allocation results including logs, COGS, and insufficient stock flag
        """
        remaining_to_allocate = Decimal(str(quantity_to_allocate))
        allocation_logs = []
        total_cogs = Decimal("0")
        insufficient_stock = False

        # Get available stock logs in FIFO order (oldest first)
        available_logs = InventoryLog.objects.filter(
            variant=variant,
            transaction_type__in=[
                InventoryLog.TransactionTypes.STOCK_IN,
                InventoryLog.TransactionTypes.INITIAL,
                InventoryLog.TransactionTypes.RETURN,
            ],
            remaining_quantity__gt=0,
        ).order_by("timestamp")

        # Allocate from available stock logs
        current_variant_quantity = variant.quantity
        updated_logs = []  # Track logs for batch update

        for stock_log in available_logs:
            if remaining_to_allocate <= 0:
                break

            allocatable = min(stock_log.remaining_quantity, remaining_to_allocate)

            new_quantity_after_allocation = current_variant_quantity - allocatable

            sale_log = InventoryLog.objects.create(
                variant=variant,
                transaction_type=InventoryLog.TransactionTypes.SALE,
                quantity_change=-allocatable,
                new_quantity=new_quantity_after_allocation,
                invoice_item=invoice_item,
                selling_price=unit_price,
                source_inventory_log=stock_log,
                allocated_quantity=allocatable,
                purchase_price=stock_log.purchase_price,
                total_value=allocatable * unit_price if unit_price else None,
                supplier_invoice=stock_log.supplier_invoice,
                created_by=user,
                notes=notes
                or f"FIFO Sale: {allocatable} from {stock_log.timestamp.date()}",
            )

            # Track remaining quantity locally instead of F() + refresh_from_db()
            new_remaining = stock_log.remaining_quantity - allocatable
            stock_log.remaining_quantity = new_remaining
            updated_logs.append(stock_log)

            if stock_log.purchase_price:
                total_cogs += allocatable * stock_log.purchase_price

            allocation_logs.append(sale_log)
            remaining_to_allocate -= allocatable
            current_variant_quantity -= allocatable

        # Batch update remaining quantities
        if updated_logs:
            InventoryLog.objects.bulk_update(updated_logs, ["remaining_quantity"])

        # Handle insufficient stock (negative inventory)
        if remaining_to_allocate > 0:
            insufficient_stock = True

            # Create sale log for the unallocated quantity
            sale_log = InventoryLog.objects.create(
                variant=variant,
                transaction_type=InventoryLog.TransactionTypes.SALE,
                quantity_change=-remaining_to_allocate,
                new_quantity=current_variant_quantity
                - remaining_to_allocate,  # Correct final quantity
                invoice_item=invoice_item,
                selling_price=unit_price,
                total_value=remaining_to_allocate * unit_price if unit_price else None,
                created_by=user,
                notes=(
                    f"INSUFFICIENT STOCK: {remaining_to_allocate} units - {notes}"
                    if notes
                    else f"INSUFFICIENT STOCK: {remaining_to_allocate} units"
                ),
            )
            allocation_logs.append(sale_log)

        return {
            "logs": allocation_logs,
            "total_cogs": total_cogs,
            "insufficient_stock": insufficient_stock,
        }

    @staticmethod
    def return_sale(
        variant,
        quantity_returned,
        user=None,
        invoice_item=None,
        notes="",
    ):
        """Process a customer return and restore inventory

        Args:
            variant: The returned variant
            quantity_returned: Amount returned
            user: User processing return
            invoice_item: Associated invoice item
            notes: Return notes

        Returns:
            dict: Return processing results
        """
        with transaction.atomic():
            if quantity_returned <= 0:
                raise ValueError("Return quantity must be positive")

            new_quantity = variant.quantity + quantity_returned
            variant.quantity = new_quantity
            variant.save()

            inventory_log = InventoryLog.objects.filter(
                variant=variant,
                transaction_type=InventoryLog.TransactionTypes.SALE,
                quantity_change__lt=quantity_returned,
                invoice_item=invoice_item,
            ).first()

            supplier_invoice = None
            if inventory_log:
                supplier_invoice = inventory_log.supplier_invoice

            InventoryLog.objects.create(
                variant=variant,
                transaction_type=InventoryLog.TransactionTypes.RETURN,
                quantity_change=quantity_returned,  # Positive for returns
                invoice_item=invoice_item,
                remaining_quantity=quantity_returned,
                created_by=user,
                new_quantity=new_quantity,
                supplier_invoice=supplier_invoice,
                selling_price=invoice_item.unit_price,
                total_value=quantity_returned * invoice_item.unit_price,
                purchase_price=variant.purchase_price,
                notes=notes
                or f"Customer return: {quantity_returned} units{f' for {invoice_item}' if invoice_item else ''}",
            )

            return {
                "success": True,
                "quantity_returned": quantity_returned,
                "new_stock": new_quantity,
                "refund_amount": quantity_returned * variant.final_price,
            }

    @staticmethod
    def cancelled_sale(
        variant,
        quantity_cancelled,
        user=None,
        invoice_item=None,
        notes="",
    ):
        """Process a customer cancellation and restore inventory

        Args:
            variant: The cancelled variant
            quantity_cancelled: Amount cancelled
            user: User processing cancellation
            invoice_item: Associated invoice item
            notes: Cancellation notes

        Returns:
            dict: Cancellation processing results
        """
        with transaction.atomic():
            if quantity_cancelled <= 0:
                raise ValueError("Return quantity must be positive")

            new_quantity = variant.quantity + quantity_cancelled
            variant.quantity = new_quantity
            variant.save()

            inventory_log = InventoryLog.objects.filter(
                variant=variant,
                transaction_type=InventoryLog.TransactionTypes.SALE,
                quantity_change__lt=quantity_cancelled,
                invoice_item=invoice_item,
            ).first()

            supplier_invoice = None
            if inventory_log:
                supplier_invoice = inventory_log.supplier_invoice

            InventoryLog.objects.create(
                variant=variant,
                transaction_type=InventoryLog.TransactionTypes.CANCEL,
                quantity_change=quantity_cancelled,  # Positive for returns
                invoice_item=invoice_item,
                remaining_quantity=quantity_cancelled,
                created_by=user,
                new_quantity=new_quantity,
                supplier_invoice=supplier_invoice,
                selling_price=invoice_item.unit_price,
                total_value=quantity_cancelled * invoice_item.unit_price,
                purchase_price=variant.purchase_price,
                notes=notes
                or f"Customer cancle: {quantity_cancelled} units{f' for {invoice_item}' if invoice_item else ''}",
            )

            return {
                "success": True,
                "quantity_cancelled": quantity_cancelled,
                "new_stock": new_quantity,
                "refund_amount": quantity_cancelled * variant.final_price,
            }

    @staticmethod
    def damage_log(
        variant,
        quantity_damaged,
        user=None,
        notes="",
        damage_type="General",
        supplier_invoice=None,
    ):
        """Mark items as damaged and move them to damaged inventory"""
        with transaction.atomic():
            if quantity_damaged <= 0:
                raise ValueError("Damaged quantity must be positive")

            if quantity_damaged > variant.quantity:
                raise ValueError(
                    f"Insufficient stock to mark as damaged. Available stock: {variant.quantity}"
                )

            # Move from available to damaged
            variant.quantity -= quantity_damaged
            variant.damaged_quantity += quantity_damaged
            variant.save()

            formatted_notes = f"Marked as damaged: {quantity_damaged} units - {damage_type}. {notes}".strip()

            # Create inventory log
            InventoryLog.objects.create(
                variant=variant,
                created_by=user,
                quantity_change=-quantity_damaged,  # Negative for available stock
                new_quantity=variant.quantity,
                total_value=quantity_damaged * variant.purchase_price,
                transaction_type=InventoryLog.TransactionTypes.DAMAGE,
                supplier_invoice=supplier_invoice,
                notes=formatted_notes,
            )

            # Create pending damage record for lifecycle tracking
            supplier = (
                supplier_invoice.supplier if supplier_invoice else None
            )
            reason = (
                "TRANSIT" if damage_type == "Transit" else
                "WATER" if damage_type == "Water" else
                "GENERAL"
            )
            DamageResolutionService.create_damage_record(
                variant=variant,
                quantity=quantity_damaged,
                user=user,
                reason=reason,
                notes=notes,
                supplier=supplier,
                supplier_invoice=supplier_invoice,
            )

            return {
                "success": True,
                "quantity_damaged": quantity_damaged,
                "remaining_available": variant.quantity,
                "total_damaged": variant.damaged_quantity,
                "damage_type": damage_type,
            }

    @staticmethod
    def get_suggested_supplier_invoices(inventory_log, limit=5):
        """Get suggested supplier invoices for an inventory log scored by weighted probability signals.

        Weights & Signals:
        1. Exact Variant Match (40 pts) / Product Match (25 pts) in candidate Supplier Invoice
        2. Adjacent Log Context (Neighboring Cluster Match: 30 pts for immediate neighbors, 20 pts for +/-5 cluster)
        3. Date Proximity (20 pts for 0-7 days before log, scaling down to 5 pts)
        4. Purchase Price Match (10 pts for matching price)

        Returns list of dicts with score, confidence level, and match reasons.
        """
        import datetime
        from supplier.models import SupplierInvoice

        log_time = inventory_log.timestamp or inventory_log.created_at
        variant = inventory_log.variant
        product = variant.product if variant else None

        min_date = log_time - datetime.timedelta(days=60)
        max_date = log_time + datetime.timedelta(days=7)

        candidates = list(
            SupplierInvoice.objects.filter(
                is_deleted=False,
                invoice_date__range=(min_date, max_date),
            ).select_related("supplier")
        )

        if len(candidates) < limit:
            existing_ids = {inv.id for inv in candidates}
            fallback = list(
                SupplierInvoice.objects.filter(is_deleted=False)
                .exclude(id__in=existing_ids)
                .select_related("supplier")
                .order_by("-invoice_date")[: limit - len(candidates)]
            )
            candidates.extend(fallback)

        # 1. Variant & Product linked invoices map
        variant_linked_invoice_ids = set()
        product_linked_invoice_ids = set()
        if variant:
            from inventory.models import InventoryLog

            variant_linked_invoice_ids = set(
                InventoryLog.objects.filter(
                    variant=variant,
                    supplier_invoice__isnull=False,
                    is_deleted=False,
                ).values_list("supplier_invoice_id", flat=True)
            )
            if product:
                product_linked_invoice_ids = set(
                    InventoryLog.objects.filter(
                        variant__product=product,
                        supplier_invoice__isnull=False,
                        is_deleted=False,
                    ).values_list("supplier_invoice_id", flat=True)
                )

        # 2. Adjacent Log Context (Neighboring cluster)
        from inventory.models import InventoryLog

        adjacent_before = list(
            InventoryLog.objects.filter(
                created_at__lt=log_time,
                is_deleted=False,
            )
            .order_by("-created_at")[:5]
        )
        adjacent_after = list(
            InventoryLog.objects.filter(
                created_at__gt=log_time,
                is_deleted=False,
            )
            .order_by("created_at")[:5]
        )

        adjacent_invoice_dist = {}
        for idx, adj in enumerate(adjacent_before):
            if adj.supplier_invoice_id:
                dist = idx + 1
                if (
                    adj.supplier_invoice_id not in adjacent_invoice_dist
                    or dist < adjacent_invoice_dist[adj.supplier_invoice_id]
                ):
                    adjacent_invoice_dist[adj.supplier_invoice_id] = dist

        for idx, adj in enumerate(adjacent_after):
            if adj.supplier_invoice_id:
                dist = idx + 1
                if (
                    adj.supplier_invoice_id not in adjacent_invoice_dist
                    or dist < adjacent_invoice_dist[adj.supplier_invoice_id]
                ):
                    adjacent_invoice_dist[adj.supplier_invoice_id] = dist

        # Score candidates
        scored_results = []
        for inv in candidates:
            score = 0
            reasons = []

            # 1. Variant / Product score
            if inv.id in variant_linked_invoice_ids:
                score += 40
                reasons.append("Exact product variant exists in invoice")
            elif inv.id in product_linked_invoice_ids:
                score += 25
                if product:
                    reasons.append(f"Product '{product.name}' items exist in invoice")
                else:
                    reasons.append("Product items exist in invoice")

            # 2. Adjacent log score
            if inv.id in adjacent_invoice_dist:
                dist = adjacent_invoice_dist[inv.id]
                if dist == 1:
                    score += 30
                    reasons.append("Immediately adjacent stock log linked to this invoice")
                else:
                    score += 20
                    reasons.append(f"Nearby stock log (distance {dist}) linked to this invoice")

            # 3. Date proximity
            days_diff = (log_time - inv.invoice_date).total_seconds() / 86400.0
            if 0 <= days_diff <= 7:
                score += 20
                reasons.append(f"Invoice dated {int(days_diff)} days before stock log")
            elif 7 < days_diff <= 14:
                score += 15
                reasons.append(f"Invoice dated {int(days_diff)} days before stock log")
            elif 14 < days_diff <= 30:
                score += 10
                reasons.append(f"Invoice dated {int(days_diff)} days before stock log")
            elif 30 < days_diff <= 60 or -7 <= days_diff < 0:
                score += 5
                reasons.append("Invoice dated within 60-day stock log window")
            else:
                score += 2
                reasons.append("Active supplier invoice")

            # 4. Purchase price match
            if inventory_log.purchase_price and inventory_log.purchase_price > 0:
                if variant and variant.purchase_price == inventory_log.purchase_price:
                    score += 10
                    reasons.append(f"Purchase price match ({inventory_log.purchase_price:.2f})")

            confidence_score = min(99 if score < 100 else 100, max(15, score))

            if confidence_score >= 75:
                confidence_level = "HIGH"
            elif confidence_score >= 45:
                confidence_level = "MEDIUM"
            else:
                confidence_level = "LOW"

            scored_results.append({
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "invoice_date": inv.invoice_date.strftime("%d %b %Y"),
                "supplier_name": inv.supplier.name if inv.supplier else "N/A",
                "supplier_contact": inv.supplier.contact_person if inv.supplier and inv.supplier.contact_person else "",
                "supplier_phone": inv.supplier.phone if inv.supplier and inv.supplier.phone else "",
                "supplier_gstin": inv.supplier.gstin if inv.supplier and inv.supplier.gstin else "",
                "sub_total": float(inv.sub_total),
                "total_amount": float(inv.total_amount),
                "confidence_score": int(confidence_score),
                "confidence_level": confidence_level,
                "match_reasons": reasons,
            })

        scored_results.sort(key=lambda x: (x["confidence_score"], x["id"]), reverse=True)
        return scored_results[:limit]

    @staticmethod
    def link_supplier_invoice_and_propagate_fifo(
        inventory_log, supplier_invoice, user=None, purchase_price=None, notes=""
    ):
        """Link supplier invoice to initial/stock-in inventory log and propagate to child logs."""
        with transaction.atomic():
            if inventory_log.transaction_type not in [
                InventoryLog.TransactionTypes.INITIAL,
                InventoryLog.TransactionTypes.STOCK_IN,
            ]:
                raise ValueError(
                    "Can only link supplier invoice to Initial or Stock In logs."
                )

            inventory_log.supplier_invoice = supplier_invoice
            if purchase_price is not None and purchase_price >= 0:
                inventory_log.purchase_price = Decimal(str(purchase_price))
                inventory_log.total_value = (
                    inventory_log.quantity_change * inventory_log.purchase_price
                )

            if notes:
                clean_notes = inventory_log.notes or ""
                inventory_log.notes = (
                    f"{clean_notes} | Linked Invoice #{supplier_invoice.invoice_number}".strip(
                        " |"
                    )
                )

            inventory_log.save()

            # Update purchase price on variant if log is initial or stock-in and price changed
            variant = inventory_log.variant
            if purchase_price is not None and purchase_price > 0:
                variant.purchase_price = Decimal(str(purchase_price))
                variant.save()

            # Propagate supplier invoice & purchase price to directly allocated child SALE and DAMAGE logs
            child_logs = InventoryLog.objects.filter(source_inventory_log=inventory_log)
            child_count = 0
            for child in child_logs:
                child.supplier_invoice = supplier_invoice
                if purchase_price is not None and purchase_price > 0:
                    child.purchase_price = Decimal(str(purchase_price))
                child.save()
                child_count += 1

            # Update DamagedItemRecord if unlinked
            DamagedItemRecord.objects.filter(
                variant=variant, supplier_invoice__isnull=True
            ).update(
                supplier_invoice=supplier_invoice,
                supplier=supplier_invoice.supplier,
            )

            # Re-run FIFO allocation for any unallocated stock-out logs (SALE, DAMAGE, ADJUSTMENT_OUT) of this variant
            unallocated_stock_outs = InventoryLog.objects.filter(
                variant=variant,
                transaction_type__in=[
                    InventoryLog.TransactionTypes.SALE,
                    InventoryLog.TransactionTypes.DAMAGE,
                    InventoryLog.TransactionTypes.ADJUSTMENT_OUT,
                ],
                source_inventory_log__isnull=True,
            )

            reallocated_count = 0
            if unallocated_stock_outs.exists():
                available_logs = InventoryLog.objects.filter(
                    variant=variant,
                    transaction_type__in=[
                        InventoryLog.TransactionTypes.STOCK_IN,
                        InventoryLog.TransactionTypes.INITIAL,
                        InventoryLog.TransactionTypes.RETURN,
                    ],
                    remaining_quantity__gt=0,
                ).order_by("timestamp")

                for stock_out in unallocated_stock_outs:
                    needed = abs(stock_out.quantity_change)
                    for stock_log in available_logs:
                        if needed <= 0 or stock_log.remaining_quantity <= 0:
                            continue
                        allocatable = min(stock_log.remaining_quantity, needed)
                        stock_out.source_inventory_log = stock_log
                        stock_out.supplier_invoice = stock_log.supplier_invoice
                        stock_out.purchase_price = stock_log.purchase_price
                        stock_out.allocated_quantity = allocatable
                        stock_out.save()

                        stock_log.remaining_quantity -= allocatable
                        stock_log.save()
                        reallocated_count += 1
                        needed -= allocatable

            return {
                "success": True,
                "log_id": inventory_log.id,
                "variant_name": variant.full_name,
                "supplier_invoice_number": supplier_invoice.invoice_number,
                "child_logs_updated": child_count,
                "reallocated_sales_count": reallocated_count,
            }


class DamageResolutionService:
    """Service for managing the lifecycle of damaged items."""

    @staticmethod
    def create_damage_record(variant, quantity, user, reason="GENERAL",
                              notes="", supplier=None, supplier_invoice=None):
        with transaction.atomic():
            record = DamagedItemRecord.objects.create(
                variant=variant,
                quantity=quantity,
                reason=reason,
                notes=notes,
                supplier=supplier,
                supplier_invoice=supplier_invoice,
                created_by=user if (user and getattr(user, "is_authenticated", True)) else None,
                status=DamagedItemRecord.Status.PENDING,
            )
            return record

    @staticmethod
    def return_to_supplier(record, supplier, user, notes="",
                            supplier_invoice=None):
        """Return damaged items to supplier by linking supplier/invoice and reducing damaged stock."""
        with transaction.atomic():
            if record.status != DamagedItemRecord.Status.PENDING:
                raise ValueError(f"Cannot return — record is {record.get_status_display()}")

            variant = record.variant
            if record.quantity > variant.damaged_quantity:
                raise ValueError(
                    f"Cannot return {record.quantity} units — only {variant.damaged_quantity} damaged units currently available."
                )

            variant.damaged_quantity -= record.quantity
            variant.save()

            resolved_user = user if (user and getattr(user, "is_authenticated", True)) else None
            record.supplier = supplier or (supplier_invoice.supplier if supplier_invoice else None)
            if supplier_invoice:
                record.supplier_invoice = supplier_invoice
            record.status = DamagedItemRecord.Status.RETURNED
            record.resolved_at = timezone.now()
            record.resolved_by = resolved_user
            record.resolution_notes = notes
            record.save()

            return record

    @staticmethod
    def write_off(record, user, notes=""):
        """Write off damaged items as a loss."""
        with transaction.atomic():
            if record.status != DamagedItemRecord.Status.PENDING:
                raise ValueError(f"Cannot write off — record is {record.get_status_display()}")

            variant = record.variant
            if record.quantity > variant.damaged_quantity:
                raise ValueError(
                    f"Cannot write off {record.quantity} units — only {variant.damaged_quantity} damaged units currently available."
                )

            variant.damaged_quantity -= record.quantity
            variant.save()

            resolved_user = user if (user and getattr(user, "is_authenticated", True)) else None
            record.status = DamagedItemRecord.Status.WRITTEN_OFF
            record.resolved_at = timezone.now()
            record.resolved_by = resolved_user
            record.resolution_notes = notes
            record.save()

            if resolved_user:
                try:
                    from user.models import Transaction as UserTransaction
                    loss = record.quantity * (variant.purchase_price or Decimal("0.01"))
                    UserTransaction.objects.create(
                        user=resolved_user,
                        transaction_type=UserTransaction.TransactionType.EXPENSE,
                        amount=loss,
                        payment_method=UserTransaction.PaymentMethod.OTHER,
                        description=(
                            f"Write-off: {variant.full_name} x{record.quantity}"
                        ),
                    )
                except Exception as e:
                    logger.error("Failed to create expense transaction for write-off: %s", e)

            return record

    @staticmethod
    def repair(record, user, notes="", repair_cost=None):
        """Repair damaged items and restore them to sellable stock with an InventoryLog audit entry."""
        with transaction.atomic():
            if record.status != DamagedItemRecord.Status.PENDING:
                raise ValueError(f"Cannot repair — record is {record.get_status_display()}")

            variant = record.variant
            if record.quantity > variant.damaged_quantity:
                raise ValueError(
                    f"Cannot repair {record.quantity} units — only {variant.damaged_quantity} damaged units currently available."
                )

            variant.damaged_quantity -= record.quantity
            variant.quantity += record.quantity
            variant.save()

            resolved_user = user if (user and getattr(user, "is_authenticated", True)) else None

            # Create inventory log for restored sellable stock
            InventoryLog.objects.create(
                variant=variant,
                created_by=resolved_user,
                quantity_change=record.quantity,
                new_quantity=variant.quantity,
                purchase_price=variant.purchase_price,
                total_value=record.quantity * variant.purchase_price,
                transaction_type=InventoryLog.TransactionTypes.ADJUSTMENT_IN,
                notes=f"Repaired & restored from damaged stock (Record #{record.id}). {notes}".strip(),
            )

            record.status = DamagedItemRecord.Status.REPAIRED
            record.resolved_at = timezone.now()
            record.resolved_by = resolved_user
            record.resolution_notes = notes
            if repair_cost is not None:
                record.repair_cost = repair_cost
            record.save()

            if repair_cost and repair_cost > 0 and resolved_user:
                try:
                    from user.models import Transaction as UserTransaction
                    UserTransaction.objects.create(
                        user=resolved_user,
                        transaction_type=UserTransaction.TransactionType.EXPENSE,
                        amount=repair_cost,
                        payment_method=UserTransaction.PaymentMethod.OTHER,
                        description=(
                            f"Repair cost: {variant.full_name} x{record.quantity}"
                        ),
                    )
                except Exception as e:
                    logger.error("Failed to create expense transaction for repair cost: %s", e)

            return record

    @staticmethod
    def suggest_resolution(variant):
        if variant.damaged_quantity <= 0:
            return []

        price = variant.purchase_price or variant.mrp or Decimal("0")
        total_qty = variant.quantity + variant.damaged_quantity
        damage_pct = (variant.damaged_quantity / total_qty * 100) if total_qty > 0 else 0

        suggestions = []

        if price > 500 and damage_pct < 50:
            suggestions.append({
                "action": "return_supplier",
                "priority": 1,
                "reasoning": (
                    f"High value item ({price:,.0f}) with "
                    f"{damage_pct:.0f}% damage — "
                    "supplier may accept return for credit."
                ),
                "financial_impact": (
                    f"Potential credit: "
                    f"{variant.damaged_quantity * price:,.0f}"
                ),
            })

        if price > 200 and damage_pct < 70:
            suggestions.append({
                "action": "repair",
                "priority": 2,
                "reasoning": (
                    f"Item at {price:,.0f} with {damage_pct:.0f}% damage — "
                    "repair may be cost-effective."
                ),
                "financial_impact": (
                    f"Restore {variant.damaged_quantity} units to sellable stock."
                ),
            })

        suggestions.append({
            "action": "write_off",
            "priority": 3,
            "reasoning": (
                "Low value or heavily damaged — most practical to "
                "write off as loss."
            ),
            "financial_impact": (
                f"Loss: "
                f"{variant.damaged_quantity * (price or Decimal('0.01')):,.0f}"
            ),
        })

        return sorted(suggestions, key=lambda s: s["priority"])
