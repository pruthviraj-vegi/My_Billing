from django.core.management.base import BaseCommand
from setting.models import ReportConfiguration


class Command(BaseCommand):
    help = "Create a simple test report configuration"

    def handle(self, *args, **options):
        # Create a simple test configuration
        config = ReportConfiguration.objects.create(
            report_type=ReportConfiguration.ReportType.INVOICE,
            paper_size=ReportConfiguration.PaperSize.A5,
            currency=ReportConfiguration.Currency.INR,
            is_default=True,
            is_active=True,
            terms_conditions="Test terms and conditions",
            thank_you_message="Thank you for your business",
        )

        self.stdout.write(self.style.SUCCESS(f"Created test config: {config}"))
