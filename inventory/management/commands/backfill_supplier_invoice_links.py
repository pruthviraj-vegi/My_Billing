"""
Django management command to backfill supplier_invoice links using FIFO allocation.

This command links old InventoryLog entries to their supplier invoices using
First-In-First-Out (FIFO) logic, matching how the system tracks inventory.

Usage:
    python manage.py backfill_supplier_invoice_links --dry-run
    python manage.py backfill_supplier_invoice_links --execute
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from inventory.models import InventoryLog, ProductVariant
from supplier.models import SupplierInvoice
from datetime import datetime
from decimal import Decimal
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill supplier_invoice links using FIFO allocation"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without applying them",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Execute the backfill operation",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of records to process in each batch (default: 1000)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        execute = options["execute"]
        batch_size = options["batch_size"]

        if not dry_run and not execute:
            self.stdout.write(
                self.style.ERROR("Please specify either --dry-run or --execute")
            )
            return

        mode = "DRY RUN" if dry_run else "EXECUTE"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\nFIFO Backfill Supplier Invoice Links - {mode}\n{'='*60}\n"
            )
        )

        # Get all variants that have unlinked logs
        variants_with_unlinked = ProductVariant.objects.filter(
            inventory_logs__supplier_invoice__isnull=True
        ).distinct()

        total_variants = variants_with_unlinked.count()
        self.stdout.write(f"Variants with unlinked logs: {total_variants}\n")

        if total_variants == 0:
            self.stdout.write(
                self.style.SUCCESS("No unlinked logs found. Nothing to do!")
            )
            return

        # Statistics
        stats = {
            "variants_processed": 0,
            "logs_linked": 0,
            "logs_skipped": 0,
            "variants_no_stock": 0,
            "variants_successful": 0,
        }

        # Report data
        linked_logs = []
        skipped_variants = []
        errors = []

        # Process each variant
        for variant in variants_with_unlinked.iterator(chunk_size=100):
            stats["variants_processed"] += 1

            try:
                result = self._process_variant_fifo(variant, dry_run, batch_size)

                stats["logs_linked"] += result["linked_count"]
                stats["logs_skipped"] += result["skipped_count"]

                if result["linked_count"] > 0:
                    stats["variants_successful"] += 1
                    linked_logs.extend(result["linked_logs"])

                if result["no_stock"]:
                    stats["variants_no_stock"] += 1
                    skipped_variants.append(
                        {
                            "variant": str(variant),
                            "reason": "No stock batches with supplier_invoice found",
                        }
                    )

            except Exception as e:
                errors.append(
                    {
                        "variant": str(variant),
                        "error": str(e),
                    }
                )
                logger.error(f"Error processing variant {variant.id}: {e}")

            # Progress indicator
            if stats["variants_processed"] % 50 == 0:
                self.stdout.write(
                    f"Processed {stats['variants_processed']}/{total_variants} variants..."
                )

        # Print summary
        self._print_summary(stats, dry_run)

        # Generate report
        self._generate_report(linked_logs, skipped_variants, errors, stats, dry_run)

    def _process_variant_fifo(self, variant, dry_run, batch_size):
        """
        Process a single variant using FIFO allocation.

        Returns dict with:
            - linked_count: number of logs linked
            - skipped_count: number of logs skipped
            - linked_logs: list of log info
            - no_stock: True if no stock batches found
        """
        result = {
            "linked_count": 0,
            "skipped_count": 0,
            "linked_logs": [],
            "no_stock": False,
        }

        # STEP 1: Get stock batches (INITIAL/STOCK_IN) WITH supplier_invoice
        stock_batches = list(
            InventoryLog.objects.filter(
                variant=variant,
                transaction_type__in=[
                    InventoryLog.TransactionTypes.INITIAL,
                    InventoryLog.TransactionTypes.STOCK_IN,
                ],
                supplier_invoice__isnull=False,
            )
            .select_related("supplier_invoice")
            .order_by("timestamp")
        )

        if not stock_batches:
            result["no_stock"] = True
            return result

        # Track available quantity per batch
        batch_availability = {
            batch.id: abs(batch.quantity_change) for batch in stock_batches
        }

        # STEP 2: Get unlinked transactions (SALE, DAMAGE, RETURN, CANCEL)
        unlinked_logs = list(
            InventoryLog.objects.filter(
                variant=variant,
                supplier_invoice__isnull=True,
                transaction_type__in=[
                    InventoryLog.TransactionTypes.SALE,
                    InventoryLog.TransactionTypes.DAMAGE,
                    InventoryLog.TransactionTypes.RETURN,
                    InventoryLog.TransactionTypes.CANCEL,
                ],
            ).order_by("timestamp")
        )

        if not unlinked_logs:
            return result

        # STEP 3: FIFO Allocation
        logs_to_update = []
        batch_index = 0

        for log in unlinked_logs:
            if batch_index >= len(stock_batches):
                # No more batches available, skip remaining logs
                result["skipped_count"] += 1
                continue

            current_batch = stock_batches[batch_index]
            quantity = abs(log.quantity_change)

            # Check transaction type
            if log.transaction_type in [
                InventoryLog.TransactionTypes.SALE,
                InventoryLog.TransactionTypes.DAMAGE,
            ]:
                # Reduces stock - consume from batch
                quantity_remaining = abs(log.quantity_change)
                allocated = False

                while quantity_remaining > 0 and batch_index < len(stock_batches):
                    current_batch = stock_batches[batch_index]
                    available = batch_availability[current_batch.id]

                    if available > 0:
                        if available >= quantity_remaining:
                            # This batch can fulfill the entire transaction
                            batch_availability[current_batch.id] -= quantity_remaining
                            log.supplier_invoice = current_batch.supplier_invoice
                            logs_to_update.append(log)

                            result["linked_logs"].append(
                                {
                                    "log_id": log.id,
                                    "variant": str(variant),
                                    "type": log.transaction_type,
                                    "quantity": log.quantity_change,
                                    "timestamp": log.timestamp,
                                    "supplier_invoice": str(
                                        current_batch.supplier_invoice
                                    ),
                                }
                            )
                            result["linked_count"] += 1
                            quantity_remaining = 0
                            allocated = True
                        else:
                            # Batch doesn't have enough stock, try next batch
                            quantity_remaining -= available
                            batch_availability[current_batch.id] = 0
                            batch_index += 1
                    else:
                        # Current batch exhausted, move to next
                        batch_index += 1

                # If we couldn't allocate the entire sale, skip it
                if not allocated:
                    result["skipped_count"] += 1

            elif log.transaction_type in [
                InventoryLog.TransactionTypes.RETURN,
                InventoryLog.TransactionTypes.CANCEL,
            ]:
                # Adds stock back - restore to current batch
                batch_availability[current_batch.id] += quantity
                log.supplier_invoice = current_batch.supplier_invoice
                logs_to_update.append(log)

                result["linked_logs"].append(
                    {
                        "log_id": log.id,
                        "variant": str(variant),
                        "type": log.transaction_type,
                        "quantity": log.quantity_change,
                        "timestamp": log.timestamp,
                        "supplier_invoice": str(current_batch.supplier_invoice),
                    }
                )
                result["linked_count"] += 1

        # Save updates if executing
        if not dry_run and logs_to_update:
            InventoryLog.objects.bulk_update(
                logs_to_update,
                ["supplier_invoice"],
                batch_size=batch_size,
            )

        return result

    def _print_summary(self, stats, dry_run):
        """Print summary statistics."""
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("SUMMARY")
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"Variants processed:       {stats['variants_processed']}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Variants with links:      {stats['variants_successful']}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                f"Variants without stock:   {stats['variants_no_stock']}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(f"Total logs linked:        {stats['logs_linked']}")
        )
        self.stdout.write(f"Logs skipped:             {stats['logs_skipped']}")
        self.stdout.write(f"{'='*60}\n")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n[!] DRY RUN MODE - No changes were made to the database"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n[OK] Changes have been applied to the database")
            )

    def _generate_report(self, linked_logs, skipped_variants, errors, stats, dry_run):
        """Generate detailed report file."""
        timestamp = timezone.now().strftime("%Y-%m-%d_%H-%M-%S")
        mode = "dry_run" if dry_run else "executed"
        filename = f"fifo_backfill_report_{mode}_{timestamp}.txt"

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write(f"FIFO Supplier Invoice Backfill Report - {timezone.now()}\n")
                f.write(f"Mode: {'DRY RUN' if dry_run else 'EXECUTED'}\n")
                f.write("=" * 80 + "\n\n")

                # Summary
                f.write("SUMMARY\n")
                f.write("-" * 80 + "\n")
                f.write(f"Variants processed:       {stats['variants_processed']}\n")
                f.write(f"Variants with links:      {stats['variants_successful']}\n")
                f.write(f"Variants without stock:   {stats['variants_no_stock']}\n")
                f.write(f"Total logs linked:        {stats['logs_linked']}\n")
                f.write(f"Logs skipped:             {stats['logs_skipped']}\n\n")

                # Linked logs (show first 100)
                if linked_logs:
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("SUCCESSFULLY LINKED LOGS (First 100)\n")
                    f.write("=" * 80 + "\n")
                    for log in linked_logs[:100]:
                        f.write(f"\nLog ID: {log['log_id']}\n")
                        f.write(f"  Variant: {log['variant']}\n")
                        f.write(f"  Type: {log['type']}\n")
                        f.write(f"  Quantity: {log['quantity']}\n")
                        f.write(f"  Timestamp: {log['timestamp']}\n")
                        f.write(f"  Linked to: {log['supplier_invoice']}\n")

                    if len(linked_logs) > 100:
                        f.write(
                            f"\n... and {len(linked_logs) - 100} more linked logs\n"
                        )

                # Skipped variants
                if skipped_variants:
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("SKIPPED VARIANTS (No Stock Batches)\n")
                    f.write("=" * 80 + "\n")
                    for entry in skipped_variants[:50]:
                        f.write(f"\nVariant: {entry['variant']}\n")
                        f.write(f"  Reason: {entry['reason']}\n")

                    if len(skipped_variants) > 50:
                        f.write(
                            f"\n... and {len(skipped_variants) - 50} more skipped variants\n"
                        )

                # Errors
                if errors:
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("ERRORS\n")
                    f.write("=" * 80 + "\n")
                    for entry in errors:
                        f.write(f"\nVariant: {entry['variant']}\n")
                        f.write(f"  Error: {entry['error']}\n")

            self.stdout.write(
                self.style.SUCCESS(f"\n[REPORT] Detailed report saved to: {filename}")
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error generating report: {e}"))
