from django.core.management.base import BaseCommand
from customer.models import Customer
from customer.signals import reallocate_customer_payments
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Auto allot all payments using FIFO method for all customers. One-time command."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes to see what would be processed',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
        
        self.stdout.write(self.style.WARNING("Starting auto allotment for all customers..."))

        customers = Customer.objects.filter(is_deleted=False)
        total_customers = customers.count()
        success_count = 0
        error_count = 0

        self.stdout.write(f"Found {total_customers} customers to process")

        for customer in customers:
            try:
                self.stdout.write(f"Processing customer: {customer.name} (ID: {customer.id})")
                
                if not dry_run:
                    logger.info(f"Auto allotting payments for {customer.name}")
                    reallocate_customer_payments(customer, skip_signals=True)
                    success_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Successfully processed {customer.name}")
                    )
                else:
                    success_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Would process {customer.name}")
                    )
            except Exception as e:
                logger.error(f"Error auto allotting payments for {customer.name}: {e}")
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"✗ Error processing {customer.name}: {str(e)}")
                )
                continue

        # Summary
        self.stdout.write("\n" + "=" * 50)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN completed. Would process: {success_count} customers. "
                    f"Would fail: {error_count}."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Auto allotment completed. "
                    f"Successfully processed: {success_count} customers. "
                    f"Errors: {error_count}."
                )
            )
        self.stdout.write("=" * 50)

