from django.core.management.base import BaseCommand
from setting.models import ReportConfiguration, ShopDetails


class Command(BaseCommand):
    help = "Create sample report configurations for testing"

    def handle(self, *args, **options):
        # Create sample shop details
        shop, created = ShopDetails.objects.get_or_create(
            shop_name="Sample Shop",
            defaults={
                "first_line": "123 Main Street",
                "second_line": "Downtown Area",
                "city": "Mumbai",
                "state": "Maharashtra",
                "pincode": "400001",
                "phone_number": "+91-9876543210",
                "email": "shop@example.com",
                "is_active": True,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created shop: {shop.shop_name}"))
        else:
            self.stdout.write(f"Shop already exists: {shop.shop_name}")

        # Create sample report configurations
        configs_data = [
            {
                "report_type": ReportConfiguration.ReportType.INVOICE,
                "paper_size": ReportConfiguration.PaperSize.A5,
                "currency": ReportConfiguration.Currency.INR,
                "is_default": True,
                "is_active": True,
                "terms_conditions": "1. All subjects to local jurisdiction\n2. Goods once sold will not be taken back\n3. E. & O.E",
                "thank_you_message": "Thank You Please Visit Again",
            },
            {
                "report_type": ReportConfiguration.ReportType.INVOICE,
                "paper_size": ReportConfiguration.PaperSize._58mm,
                "currency": ReportConfiguration.Currency.INR,
                "is_default": False,
                "is_active": True,
                "terms_conditions": "1. All subjects to local jurisdiction\n2. Goods once sold will not be taken back\n3. E. & O.E",
                "thank_you_message": "Thank You Please Visit Again",
            },
            {
                "report_type": ReportConfiguration.ReportType.ESTIMATE,
                "paper_size": ReportConfiguration.PaperSize.A4,
                "currency": ReportConfiguration.Currency.INR,
                "is_default": True,
                "is_active": True,
                "terms_conditions": "This is an estimate. Valid for 30 days.",
                "thank_you_message": "Thank you for your interest",
            },
        ]

        for config_data in configs_data:
            config, created = ReportConfiguration.objects.get_or_create(
                report_type=config_data["report_type"],
                paper_size=config_data["paper_size"],
                defaults=config_data,
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created config: {config.get_report_type_display()} - {config.get_paper_size_display()}"
                    )
                )
            else:
                self.stdout.write(
                    f"Config already exists: {config.get_report_type_display()} - {config.get_paper_size_display()}"
                )

        self.stdout.write(self.style.SUCCESS("Sample data creation completed!"))
