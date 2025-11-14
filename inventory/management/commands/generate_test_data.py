"""
Management command to generate random test data for inventory system
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from decimal import Decimal
import random
import string
from datetime import datetime, timedelta

from inventory.models import (
    Category, ClothType, Color, Size, HsnCode, 
    Product, ProductVariant, ProductImage, InventoryLog
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate random test data for inventory system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--products',
            type=int,
            default=100,
            help='Number of products to create (default: 100)'
        )
        parser.add_argument(
            '--variants-per-product',
            type=int,
            default=3,
            help='Average variants per product (default: 3)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing test data before creating new data'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without making changes'
        )

    def handle(self, *args, **options):
        products_count = options['products']
        variants_per_product = options['variants_per_product']
        clear_existing = options['clear_existing']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
            self._show_preview(products_count, variants_per_product)
            return

        if clear_existing:
            self._clear_existing_data()

        # Create base data first
        self._create_base_data()

        # Generate products and variants
        self._generate_products_and_variants(products_count, variants_per_product)

        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated test data!')
        )

    def _show_preview(self, products_count, variants_per_product):
        """Show preview of what will be created"""
        total_variants = products_count * variants_per_product
        
        self.stdout.write(f'Will create:')
        self.stdout.write(f'  - {products_count} Products')
        self.stdout.write(f'  - ~{total_variants} Product Variants')
        self.stdout.write(f'  - Base data (Categories, Colors, Sizes, etc.)')

    def _clear_existing_data(self):
        """Clear existing test data"""
        self.stdout.write('Clearing existing test data...')
        
        with transaction.atomic():
            ProductVariant.objects.all().delete()
            Product.objects.all().delete()
            ProductImage.objects.all().delete()
            InventoryLog.objects.all().delete()
            
        self.stdout.write('Existing data cleared.')

    def _create_base_data(self):
        """Create base data like categories, colors, sizes, etc."""
        self.stdout.write('Creating base data...')

        # Categories
        categories_data = [
            'T-Shirts', 'Jeans', 'Dresses', 'Shirts', 'Pants', 'Skirts',
            'Jackets', 'Sweaters', 'Shorts', 'Blouses', 'Trousers', 'Coats',
            'Hoodies', 'Polo Shirts', 'Leggings', 'Cardigans', 'Tank Tops',
            'Chinos', 'Cargo Pants', 'Blazers'
        ]

        for cat_name in categories_data:
            Category.objects.get_or_create(
                name=cat_name,
                defaults={'description': f'Category for {cat_name.lower()}'}
            )

        # Cloth Types
        cloth_types_data = [
            'Cotton', 'Polyester', 'Denim', 'Silk', 'Wool', 'Linen',
            'Rayon', 'Spandex', 'Nylon', 'Leather', 'Canvas', 'Chiffon',
            'Georgette', 'Crepe', 'Satin', 'Velvet', 'Corduroy', 'Tweed'
        ]

        for cloth_name in cloth_types_data:
            ClothType.objects.get_or_create(
                name=cloth_name,
                defaults={'description': f'{cloth_name} fabric type'}
            )

        # Colors
        colors_data = [
            ('Red', '#FF0000'), ('Blue', '#0000FF'), ('Green', '#008000'),
            ('Yellow', '#FFFF00'), ('Black', '#000000'), ('White', '#FFFFFF'),
            ('Gray', '#808080'), ('Brown', '#A52A2A'), ('Pink', '#FFC0CB'),
            ('Purple', '#800080'), ('Orange', '#FFA500'), ('Navy', '#000080'),
            ('Maroon', '#800000'), ('Olive', '#808000'), ('Teal', '#008080'),
            ('Cyan', '#00FFFF'), ('Magenta', '#FF00FF'), ('Lime', '#00FF00'),
            ('Silver', '#C0C0C0'), ('Gold', '#FFD700')
        ]

        for color_name, hex_code in colors_data:
            Color.objects.get_or_create(
                name=color_name,
                defaults={'hex_code': hex_code}
            )

        # Sizes
        sizes_data = [
            'XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL',
            '28', '30', '32', '34', '36', '38', '40', '42', '44', '46',
            '6', '8', '10', '12', '14', '16', '18', '20', '22', '24',
            'Small', 'Medium', 'Large', 'Extra Large'
        ]

        for size_name in sizes_data:
            Size.objects.get_or_create(
                name=size_name,
                defaults={'description': f'Size {size_name}'}
            )

        # HSN Codes
        hsn_codes_data = [
            ('6109', Decimal('12.00'), 'T-shirts, singlets and other vests'),
            ('6203', Decimal('12.00'), 'Men\'s or boys\' suits, ensembles'),
            ('6204', Decimal('12.00'), 'Women\'s or girls\' suits, ensembles'),
            ('6205', Decimal('12.00'), 'Men\'s or boys\' shirts'),
            ('6206', Decimal('12.00'), 'Women\'s or girls\' blouses'),
            ('6207', Decimal('12.00'), 'Men\'s or boys\' singlets'),
            ('6208', Decimal('12.00'), 'Women\'s or girls\' singlets'),
            ('6209', Decimal('12.00'), 'Babies\' garments'),
            ('6210', Decimal('12.00'), 'Garments made up of fabrics'),
            ('6211', Decimal('12.00'), 'Track suits, ski suits'),
        ]

        for code, gst_percentage, description in hsn_codes_data:
            HsnCode.objects.get_or_create(
                code=code,
                defaults={
                    'gst_percentage': gst_percentage,
                    'description': description
                }
            )

        self.stdout.write('Base data created successfully.')

    def _generate_products_and_variants(self, products_count, variants_per_product):
        """Generate products and their variants"""
        self.stdout.write(f'Generating {products_count} products...')

        # Get base data
        categories = list(Category.objects.all())
        cloth_types = list(ClothType.objects.all())
        hsn_codes = list(HsnCode.objects.all())
        colors = list(Color.objects.all())
        sizes = list(Size.objects.all())

        # Brand names
        brands = [
            'Nike', 'Adidas', 'Puma', 'Reebok', 'Under Armour', 'Champion',
            'Levi\'s', 'Calvin Klein', 'Tommy Hilfiger', 'Ralph Lauren',
            'Gap', 'H&M', 'Zara', 'Uniqlo', 'Forever 21', 'American Eagle',
            'Hollister', 'Abercrombie & Fitch', 'Banana Republic', 'Old Navy',
            'Target', 'Walmart', 'Amazon Essentials', 'Goodthreads', 'Lands\' End'
        ]

        # Product names
        product_names = [
            'Classic T-Shirt', 'Premium Polo', 'Comfort Jeans', 'Elegant Dress',
            'Casual Shirt', 'Formal Pants', 'Summer Skirt', 'Winter Jacket',
            'Cozy Sweater', 'Sport Shorts', 'Business Blouse', 'Smart Trousers',
            'Warm Coat', 'Trendy Hoodie', 'Professional Polo', 'Yoga Leggings',
            'Soft Cardigan', 'Active Tank Top', 'Stylish Chinos', 'Utility Cargo',
            'Sharp Blazer', 'Comfortable Joggers', 'Fashionable Top', 'Classic Denim',
            'Modern Jumpsuit', 'Vintage Tee', 'Contemporary Shirt', 'Timeless Dress'
        ]

        total_variants_created = 0

        with transaction.atomic():
            for i in range(products_count):
                # Create product
                brand = random.choice(brands)
                product_name = random.choice(product_names)
                category = random.choice(categories) if categories else None
                cloth_type = random.choice(cloth_types) if cloth_types else None
                hsn_code = random.choice(hsn_codes) if hsn_codes else None

                product = Product.objects.create(
                    brand=brand,
                    name=f"{product_name} {i+1}",
                    description=f"High-quality {product_name.lower()} from {brand}. "
                               f"Perfect for everyday wear with excellent comfort and style.",
                    category=category,
                    cloth_type=cloth_type,
                    hsn_code=hsn_code,
                    gst_percentage=random.choice([Decimal('5.00'), Decimal('12.00'), Decimal('18.00')]),
                    status=random.choice(['ACTIVE', 'ACTIVE', 'ACTIVE', 'DRAFT'])  # Mostly active
                )

                # Create variants for this product
                num_variants = random.randint(1, variants_per_product * 2)
                
                for j in range(num_variants):
                    # Generate unique barcode
                    barcode = self._generate_unique_barcode()
                    
                    # Try to find a unique combination of size and color
                    size = None
                    color = None
                    max_attempts = 10
                    attempt = 0
                    
                    while attempt < max_attempts:
                        # Random size and color (can be None)
                        size = random.choice(sizes) if random.random() > 0.2 else None
                        color = random.choice(colors) if random.random() > 0.2 else None
                        
                        # Check if this combination already exists for this product
                        existing_variant = ProductVariant.objects.filter(
                            product=product,
                            size=size,
                            color=color
                        ).first()
                        
                        if not existing_variant:
                            break
                        
                        attempt += 1
                    
                    # If we couldn't find a unique combination, skip this variant
                    if attempt >= max_attempts:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Skipping variant after {max_attempts} attempts - too many duplicates for {product}'
                            )
                        )
                        continue
                    
                    # Price ranges
                    base_price = random.randint(200, 2000)
                    purchase_price = Decimal(str(base_price))
                    mrp = purchase_price * Decimal(str(random.uniform(1.5, 3.0)))  # 50-200% markup
                    
                    # Quantities
                    quantity = Decimal(str(random.randint(0, 100)))
                    damaged_quantity = Decimal(str(random.randint(0, 5)))
                    minimum_quantity = Decimal(str(random.randint(5, 20)))
                    
                    # Discount
                    discount_percentage = Decimal(str(random.randint(0, 30)))
                    
                    # Extra attributes
                    extra_attributes = {}
                    if random.random() > 0.7:
                        extra_attributes['Material'] = random.choice(['100% Cotton', 'Cotton Blend', 'Synthetic'])
                    if random.random() > 0.8:
                        extra_attributes['Care'] = random.choice(['Machine Wash', 'Dry Clean Only', 'Hand Wash'])

                    try:
                        variant = ProductVariant.objects.create(
                            product=product,
                            barcode=barcode,
                            size=size,
                            color=color,
                            extra_attributes=extra_attributes,
                            purchase_price=purchase_price,
                            mrp=mrp,
                            quantity=quantity,
                            damaged_quantity=damaged_quantity,
                            minimum_quantity=minimum_quantity,
                            discount_percentage=discount_percentage,
                            status='ACTIVE'
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Error creating variant: {e}')
                        )
                        continue

                    # Create initial inventory log
                    if quantity > 0:
                        InventoryLog.objects.create(
                            variant=variant,
                            transaction_type='INITIAL',
                            quantity_change=quantity,
                            new_quantity=quantity,
                            purchase_price=purchase_price,
                            mrp=mrp,
                            notes=f'Initial stock for {variant}',
                            remaining_quantity=quantity
                        )

                    total_variants_created += 1

                if (i + 1) % 10 == 0:
                    self.stdout.write(f'Created {i + 1} products...')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {products_count} products with {total_variants_created} variants!'
            )
        )

    def _generate_unique_barcode(self):
        """Generate a unique barcode"""
        while True:
            barcode = ''.join(random.choices(string.digits, k=12))
            if not ProductVariant.objects.filter(barcode=barcode).exists():
                return barcode

    def _get_or_create_user(self):
        """Get or create a user for created_by fields"""
        try:
            return User.objects.first()
        except:
            return None
