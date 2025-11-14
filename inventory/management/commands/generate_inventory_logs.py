"""
Management command to generate realistic inventory logs for existing products
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from decimal import Decimal
import random
from datetime import datetime, timedelta

from inventory.models import ProductVariant, InventoryLog

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate realistic inventory logs for existing products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to simulate (default: 90)'
        )
        parser.add_argument(
            '--transactions-per-day',
            type=int,
            default=10,
            help='Average transactions per day (default: 10)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing inventory logs before creating new ones'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without making changes'
        )

    def handle(self, *args, **options):
        days = options['days']
        transactions_per_day = options['transactions_per_day']
        clear_existing = options['clear_existing']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
            self._show_preview(days, transactions_per_day)
            return

        variants = ProductVariant.objects.all()
        if not variants.exists():
            self.stdout.write(
                self.style.ERROR('No product variants found. Please create products first.')
            )
            return

        if clear_existing:
            self._clear_existing_logs()

        self._generate_inventory_logs(variants, days, transactions_per_day)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated inventory logs!')
        )

    def _show_preview(self, days, transactions_per_day):
        """Show preview of what will be created"""
        total_transactions = days * transactions_per_day
        
        self.stdout.write(f'Will create:')
        self.stdout.write(f'  - {total_transactions} inventory transactions')
        self.stdout.write(f'  - Over {days} days')
        self.stdout.write(f'  - {transactions_per_day} transactions per day average')

    def _clear_existing_logs(self):
        """Clear existing inventory logs"""
        self.stdout.write('Clearing existing inventory logs...')
        
        with transaction.atomic():
            InventoryLog.objects.all().delete()
            
        self.stdout.write('Existing logs cleared.')

    def _generate_inventory_logs(self, variants, days, transactions_per_day):
        """Generate realistic inventory logs"""
        self.stdout.write(f'Generating inventory logs for {days} days...')

        # Transaction type probabilities
        transaction_types = {
            'STOCK_IN': 0.3,      # 30% stock in
            'SALE': 0.4,          # 40% sales
            'ADJUSTMENT_IN': 0.1, # 10% adjustments in
            'ADJUSTMENT_OUT': 0.1, # 10% adjustments out
            'DAMAGE': 0.05,       # 5% damage
            'RETURN': 0.05        # 5% returns
        }

        start_date = datetime.now() - timedelta(days=days)
        user = self._get_or_create_user()

        total_transactions = 0

        with transaction.atomic():
            for day in range(days):
                current_date = start_date + timedelta(days=day)
                
                # Random number of transactions for this day
                daily_transactions = random.randint(
                    max(1, transactions_per_day - 5),
                    transactions_per_day + 5
                )

                for _ in range(daily_transactions):
                    variant = random.choice(variants)
                    transaction_type = self._weighted_choice(transaction_types)
                    
                    # Generate transaction based on type
                    log = self._create_transaction_log(
                        variant, transaction_type, current_date, user
                    )
                    
                    if log:
                        total_transactions += 1

                if (day + 1) % 10 == 0:
                    self.stdout.write(f'Generated logs for {day + 1} days...')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {total_transactions} inventory transactions!'
            )
        )

    def _create_transaction_log(self, variant, transaction_type, timestamp, user):
        """Create a specific transaction log"""
        try:
            if transaction_type == 'STOCK_IN':
                return self._create_stock_in_log(variant, timestamp, user)
            elif transaction_type == 'SALE':
                return self._create_sale_log(variant, timestamp, user)
            elif transaction_type == 'ADJUSTMENT_IN':
                return self._create_adjustment_in_log(variant, timestamp, user)
            elif transaction_type == 'ADJUSTMENT_OUT':
                return self._create_adjustment_out_log(variant, timestamp, user)
            elif transaction_type == 'DAMAGE':
                return self._create_damage_log(variant, timestamp, user)
            elif transaction_type == 'RETURN':
                return self._create_return_log(variant, timestamp, user)
        except Exception as e:
            self.stdout.write(f'Error creating log: {e}')
            return None

    def _create_stock_in_log(self, variant, timestamp, user):
        """Create stock in transaction"""
        quantity = Decimal(str(random.randint(10, 100)))
        purchase_price = variant.purchase_price * Decimal(str(random.uniform(0.8, 1.2)))
        
        # Update variant quantity
        variant.quantity += quantity
        variant.save()

        return InventoryLog.objects.create(
            variant=variant,
            transaction_type='STOCK_IN',
            quantity_change=quantity,
            new_quantity=variant.quantity,
            purchase_price=purchase_price,
            mrp=variant.mrp,
            notes=f'Stock received - {quantity} units',
            timestamp=timestamp,
            created_by=user,
            remaining_quantity=quantity
        )

    def _create_sale_log(self, variant, timestamp, user):
        """Create sale transaction"""
        if variant.quantity <= 0:
            return None

        max_quantity = min(variant.quantity, 10)
        quantity = Decimal(str(random.randint(1, max_quantity)))
        selling_price = variant.mrp * Decimal(str(random.uniform(0.8, 1.0)))
        
        # Update variant quantity
        variant.quantity -= quantity
        variant.save()

        return InventoryLog.objects.create(
            variant=variant,
            transaction_type='SALE',
            quantity_change=-quantity,
            new_quantity=variant.quantity,
            selling_price=selling_price,
            notes=f'Sale - {quantity} units',
            timestamp=timestamp,
            created_by=user
        )

    def _create_adjustment_in_log(self, variant, timestamp, user):
        """Create adjustment in transaction"""
        quantity = Decimal(str(random.randint(1, 20)))
        
        # Update variant quantity
        variant.quantity += quantity
        variant.save()

        return InventoryLog.objects.create(
            variant=variant,
            transaction_type='ADJUSTMENT_IN',
            quantity_change=quantity,
            new_quantity=variant.quantity,
            notes=f'Stock adjustment +{quantity} units',
            timestamp=timestamp,
            created_by=user
        )

    def _create_adjustment_out_log(self, variant, timestamp, user):
        """Create adjustment out transaction"""
        if variant.quantity <= 0:
            return None

        max_quantity = min(variant.quantity, 10)
        quantity = Decimal(str(random.randint(1, max_quantity)))
        
        # Update variant quantity
        variant.quantity -= quantity
        variant.save()

        return InventoryLog.objects.create(
            variant=variant,
            transaction_type='ADJUSTMENT_OUT',
            quantity_change=-quantity,
            new_quantity=variant.quantity,
            notes=f'Stock adjustment -{quantity} units',
            timestamp=timestamp,
            created_by=user
        )

    def _create_damage_log(self, variant, timestamp, user):
        """Create damage transaction"""
        if variant.quantity <= 0:
            return None

        max_quantity = min(variant.quantity, 5)
        quantity = Decimal(str(random.randint(1, max_quantity)))
        
        # Move from quantity to damaged_quantity
        variant.quantity -= quantity
        variant.damaged_quantity += quantity
        variant.save()

        return InventoryLog.objects.create(
            variant=variant,
            transaction_type='DAMAGE',
            quantity_change=-quantity,
            new_quantity=variant.quantity,
            notes=f'Marked as damaged - {quantity} units',
            timestamp=timestamp,
            created_by=user
        )

    def _create_return_log(self, variant, timestamp, user):
        """Create return transaction"""
        quantity = Decimal(str(random.randint(1, 5)))
        
        # Update variant quantity
        variant.quantity += quantity
        variant.save()

        return InventoryLog.objects.create(
            variant=variant,
            transaction_type='RETURN',
            quantity_change=quantity,
            new_quantity=variant.quantity,
            notes=f'Customer return +{quantity} units',
            timestamp=timestamp,
            created_by=user
        )

    def _weighted_choice(self, choices):
        """Make a weighted random choice"""
        rand = random.random()
        cumulative = 0
        for choice, weight in choices.items():
            cumulative += weight
            if rand <= cumulative:
                return choice
        return list(choices.keys())[-1]

    def _get_or_create_user(self):
        """Get or create a user for created_by fields"""
        try:
            return User.objects.first()
        except:
            return None
