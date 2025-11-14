"""
Management command to debug invoice renumbering issues
"""

from django.core.management.base import BaseCommand, CommandError
from invoice.models import Invoice
from invoice.services import InvoiceRenumberingService


class Command(BaseCommand):
    help = 'Debug invoice renumbering issues to identify problems'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['CASH', 'GST', 'ALL'],
            default='ALL',
            help='Type of invoices to debug (CASH, GST, or ALL)'
        )
        parser.add_argument(
            '--financial-year',
            type=str,
            help='Financial year to debug (e.g., 24-25). If not specified, debugs all years'
        )

    def handle(self, *args, **options):
        invoice_type = options['type']
        financial_year = options['financial_year']

        self.stdout.write(f'Debugging invoice renumbering issues...')
        self.stdout.write(f'Type: {invoice_type}')
        if financial_year:
            self.stdout.write(f'Financial Year: {financial_year}')
        self.stdout.write('-' * 50)

        if invoice_type == 'ALL':
            # Debug both CASH and GST
            self._debug_type('CASH', financial_year)
            self.stdout.write()
            self._debug_type('GST', financial_year)
        else:
            self._debug_type(invoice_type, financial_year)

    def _debug_type(self, invoice_type, financial_year):
        """Debug a specific invoice type"""
        invoice_type_enum = getattr(Invoice.Invoice_type, invoice_type)
        
        self.stdout.write(f'{invoice_type} Invoice Debug:')
        self.stdout.write('-' * 30)
        
        # Get debug info
        debug_info = InvoiceRenumberingService.debug_renumbering_issues(invoice_type_enum, financial_year)
        
        self.stdout.write(f'Total invoices: {debug_info["total_invoices"]}')
        self.stdout.write(f'Financial years: {debug_info["financial_years"]}')
        
        if debug_info['issues']:
            self.stdout.write(self.style.WARNING('Issues found:'))
            for issue in debug_info['issues']:
                self.stdout.write(f'  ❌ {issue}')
        else:
            self.stdout.write(self.style.SUCCESS('No issues found'))
        
        # Show sample invoices
        if debug_info['sample_invoices']:
            self.stdout.write('\nSample invoices:')
            for invoice in debug_info['sample_invoices']:
                self.stdout.write(f'  ID: {invoice["id"]}, Number: {invoice["invoice_number"]}, '
                                f'Seq: {invoice["sequence_no"]}, FY: {invoice["financial_year"]}')
        
        # Check for specific constraint violations
        self._check_constraints(invoice_type_enum, financial_year)

    def _check_constraints(self, invoice_type, financial_year):
        """Check for specific constraint violations"""
        queryset = Invoice.objects.filter(invoice_type=invoice_type)
        if financial_year:
            queryset = queryset.filter(financial_year=financial_year)
        
        self.stdout.write('\nConstraint checks:')
        
        # Check unique constraints
        try:
            # Check for duplicate invoice numbers
            invoice_numbers = list(queryset.values_list('invoice_number', flat=True))
            duplicates = [num for num in set(invoice_numbers) if invoice_numbers.count(num) > 1]
            if duplicates:
                self.stdout.write(f'  ❌ Duplicate invoice numbers: {duplicates}')
            else:
                self.stdout.write('  ✅ No duplicate invoice numbers')
            
            # Check for duplicate sequences
            sequences = list(queryset.values_list('sequence_no', 'financial_year'))
            seq_tuples = [(seq, fy) for seq, fy in sequences if seq is not None]
            duplicates = [t for t in set(seq_tuples) if seq_tuples.count(t) > 1]
            if duplicates:
                self.stdout.write(f'  ❌ Duplicate sequences: {duplicates}')
            else:
                self.stdout.write('  ✅ No duplicate sequences')
                
        except Exception as e:
            self.stdout.write(f'  ❌ Constraint check failed: {e}')
        
        # Check for null/empty values
        null_invoice_numbers = queryset.filter(invoice_number__isnull=True).count()
        null_sequences = queryset.filter(sequence_no__isnull=True).count()
        null_financial_years = queryset.filter(financial_year__isnull=True).count()
        
        if null_invoice_numbers > 0:
            self.stdout.write(f'  ❌ {null_invoice_numbers} invoices with null invoice_number')
        if null_sequences > 0:
            self.stdout.write(f'  ❌ {null_sequences} invoices with null sequence_no')
        if null_financial_years > 0:
            self.stdout.write(f'  ❌ {null_financial_years} invoices with null financial_year')
        
        if null_invoice_numbers == 0 and null_sequences == 0 and null_financial_years == 0:
            self.stdout.write('  ✅ No null values found')
