from decimal import Decimal
import logging
from weasyprint import HTML
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template
import io
import qrcode
from barcode import Code128
from barcode.base import Barcode
from barcode.writer import SVGWriter
import base64
from PIL import Image
from inventory.models import ProductVariant
from invoice.models import Invoice, InvoiceItem
from setting.models import (
    ShopDetails,
    ReportConfiguration,
    PaymentDetails,
    BarcodeConfiguration,
)
from cart.models import Cart, CartItem
from customer.models import Customer
from customer.views_credit import _build_ledger_rows
from datetime import datetime
from django.db.models import Sum
from django.db.models.functions import Coalesce
from base.getDates import getDates
from customer.views import get_data as get_customers_data
from customer.views_credit import (
    credit_customers_data,
    total_credit_customers_data,
    get_opening_balance,
)
from supplier.views import (
    get_suppliers_data,
    get_total_outstanding_balance as supplier_total_outstanding_balance,
    Supplier,
    SupplierInvoice,
    get_supplier_report_data,
)
from inventory.views_variant import get_variants_data
from invoice.views_report import get_invoice_report_data
from django.conf import settings

Barcode.default_writer_options["write_text"] = False

logger = logging.getLogger(__name__)


# general pdf creation values for all data
def generatePdf(
    template_name,
    file_name,
    context,
    request,
    report_type="INVOICE",
    upload_to_r2=False,
):
    """
    Generate PDF and optionally upload to R2 storage.

    Args:
        upload_to_r2: Set to True when you want to upload this specific PDF
    """
    # Get shop details
    shop_details = ShopDetails.objects.filter(is_active=True).first()
    context["shop_details"] = shop_details

    # Get report configuration
    report_config = ReportConfiguration.get_default_config(report_type)
    context["report_config"] = report_config

    template = get_template(f"report/{template_name}")
    html = template.render(context)

    # Insert barcode image into HTML
    if "qrcode" in context:
        barcode_data = context["qrcode"]
        html = html.replace(
            "{{ qrcode }}", f'<img src="data:image/png;base64, {barcode_data}"/>'
        )

    # Generate PDF
    pdf_file = HTML(string=html, base_url=settings.STATIC_ROOT).write_pdf(
        presentational_hints=True
    )

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    # Upload to R2 only if requested
    if upload_to_r2:
        try:
            from io import BytesIO
            from api.cloudflare import upload_pdf_to_r2, BucketType, R2StorageError

            pdf_buffer = BytesIO(pdf_file)
            bucket_type = (
                BucketType.INVOICE if report_type == "INVOICE" else BucketType.STATEMENT
            )

            r2_url = upload_pdf_to_r2(
                file_obj=pdf_buffer, filename=filename, bucket_type=bucket_type
            )

            logger.info(f"PDF uploaded to R2: {r2_url}")
            return r2_url

        except R2StorageError as e:
            logger.error(f"Failed to upload PDF to R2: {str(e)}")
            return None

    # Return HTTP response
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'filename="{filename}"'
    response["pdfkit-dpi"] = "800"
    return response


# create invoice page
def createInvoice(request, pk):
    template = None

    invoice = Invoice.objects.select_related("customer", "created_by").get(id=pk)
    values = (
        InvoiceItem.objects.filter(invoice__id=pk)
        .select_related(
            "product_variant__product__category",
            "product_variant__product__uom",
            "product_variant__size",
            "product_variant__color",
        )
        .prefetch_related("return_items__return_invoice")
    )

    # Get shop details and report configuration
    shop_details = ShopDetails.objects.filter(is_active=True).first()
    report_config = ReportConfiguration.get_default_config(
        ReportConfiguration.ReportType.INVOICE
    )
    payment_details = (
        PaymentDetails.get_active_payments(shop=shop_details)
        .order_by("display_order")
        .first()
    )

    if report_config.paper_size == ReportConfiguration.PaperSize._58mm:
        template = "report/58mm.html"
    else:
        template = "report/A5.html"

    context = {
        "values": values,
        "details": invoice,
        "shop_details": shop_details,
        "report_config": report_config,
        "payment_details": payment_details,
    }

    # Generate QR code if enabled in config
    if (
        report_config
        and report_config.show_qr_code
        and payment_details
        and payment_details.upi_id
    ):
        try:
            # Create UPI payment QR code
            qr_data = f"upi://pay?pa={payment_details.upi_id}&pn={shop_details.shop_name}&am={invoice.net_amount_due}&tn=for bill no {invoice.invoice_number}&cu=INR"
            qr_code = qrcode.make(qr_data)
            image_bytes = io.BytesIO()
            qr_code.save(image_bytes, format="PNG")
            context["qrcode"] = base64.b64encode(image_bytes.getvalue()).decode()
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")

    return render(request, template, context)


def estimate_invoice(request, pk):
    template = "report/estimate.html"
    estimate = Cart.objects.get(id=pk)
    values = CartItem.objects.filter(cart__id=pk)
    shop_details = ShopDetails.objects.filter(is_active=True).first()
    report_config = ReportConfiguration.get_default_config(
        ReportConfiguration.ReportType.ESTIMATE
    )
    context = {
        "values": values,
        "details": estimate,
        "shop_details": shop_details,
        "report_config": report_config,
    }
    return render(request, template, context)


# crate barcode
def generate_barcode(request, pk):
    template = "report/barcode.html"
    variant = ProductVariant.objects.get(id=pk)
    shop_details = ShopDetails.objects.filter(is_active=True).first()
    code128 = Code128(variant.barcode, writer=SVGWriter())
    buffer = io.BytesIO()
    code128.write(buffer)
    buffer.seek(0)
    barcode_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

    barcode_config = BarcodeConfiguration.get_active_barcodes(shop_details).first()

    # Add the barcode image to the context dictionary
    context = {
        "values": variant,
        "print_count": variant.get_barcode_qty,
        "barcode_svg": barcode_image,
        "shop_details": shop_details,
        "barcode_config": barcode_config,
    }
    return render(request, template, context)


def generate_invoices_pdf(request):
    start_date, end_date = getDates(request)
    invoices = Invoice.objects.filter(
        invoice_type=Invoice.Invoice_type.GST,
        invoice_date__range=(start_date, end_date),
    ).order_by("invoice_date")

    total_count = invoices.count()

    total_tax_value = 0
    total_gst_amount = 0
    total_payable = 0
    for invoice in invoices:
        total_tax_value += invoice.total_tax_value
        total_gst_amount += invoice.total_gst_amount
        total_payable += invoice.total_payable

    # Handle invoice numbers range
    if total_count == 0:
        invoice_numbers = 0
    elif total_count == 1:
        invoice_numbers = str(invoices.first().invoice_number)
    else:
        first_invoice = invoices.first()
        last_invoice = invoices.last()
        invoice_numbers = (
            f"{first_invoice.invoice_number} to {last_invoice.invoice_number}"
        )

    context = {
        "data": invoices,
        "total_count": total_count,
        "start_date": start_date,
        "end_date": end_date,
        "total_tax_value": total_tax_value,
        "total_gst_amount": total_gst_amount,
        "total_payable": total_payable,
        "invoice_numbers": invoice_numbers,
    }

    template = "invoice_report.html"
    filename = f"invoices_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    return generatePdf(template, filename, context, request)


def generate_customers_pdf(request):
    """Generate PDF for customers list with search and sort parameters."""

    # Get customers using the same logic as fetch_customers
    customers = get_customers_data(request)

    # Prepare context
    context = {
        "customers": customers,
        "total_count": customers.count(),
    }

    # Render template
    template = "customer_pdf.html"

    filename = "customers"

    return generatePdf(template, filename, context, request)


def generate_credit_pdf(request):
    """Generate PDF for credit customers list with search and sort parameters."""
    customers = credit_customers_data(request)
    total_outstanding = total_credit_customers_data(request)

    if isinstance(customers, list):
        count = len(customers)
    else:
        count = customers.count()

    # Prepare context
    context = {
        "customers": customers,
        "total_count": count,
        "total_outstanding": total_outstanding,
    }

    # Render template
    template = "customer_credit.html"
    filename = "credit_customers"

    return generatePdf(template, filename, context, request)


def generate_credit_ind_pdf(request, pk):
    """Generate PDF for credit individual customer with search and sort parameters."""
    customer = get_object_or_404(Customer, pk=pk)
    start_date, end_date = getDates(request)
    ledger = _build_ledger_rows(customer, start_date, end_date)
    opening_balance = get_opening_balance(customer, start_date)

    ledger.sort(key=lambda r: (r["date"] or datetime.min, r["type"]))

    balance = opening_balance
    for i in ledger:
        balance += i["credit"] - i["debit"]
        i["balance"] = balance

    context = {
        "customer": customer,
        "ledger": ledger,
        "start_date": start_date,
        "end_date": end_date,
        "opening_balance": opening_balance,
    }
    template = "customer_credit_ind.html"
    filename = "credit_individual_customer"
    return generatePdf(template, filename, context, request)


def generate_suppliers_pdf(request):
    """Generate PDF for suppliers list with search and sort parameters."""
    suppliers = get_suppliers_data(request)
    total_outstanding = supplier_total_outstanding_balance()

    if isinstance(suppliers, list):
        count = len(suppliers)
    else:
        count = suppliers.count()

    # Prepare context
    context = {
        "suppliers": suppliers,
        "total_count": count,
        "total_outstanding": total_outstanding,
    }

    # Render template
    template = "suppliers_pdf.html"
    filename = "suppliers"

    return generatePdf(template, filename, context, request)


def generate_variants_pdf(request):
    """Generate PDF for variants list with search and sort parameters."""
    variants = get_variants_data(request)
    total_count = variants.count()

    # Prepare context
    context = {
        "variants": variants,
        "total_count": total_count,
    }

    # Render template
    template = "variants_pdf.html"
    filename = "variants"

    return generatePdf(template, filename, context, request)


def generate_purchase_orders_pdf(request):
    """Generate PDF for purchase order list with search and sort parameters."""

    start_date, end_date = getDates(request)

    purchase_orders = SupplierInvoice.objects.filter(
        is_deleted=False,
        invoice_type=SupplierInvoice.InvoiceType.GST_APPLICABLE,
        invoice_date__range=(start_date, end_date),
    )

    total_count = purchase_orders.count()

    # Use Coalesce to handle NULL values properly
    aggregates = purchase_orders.aggregate(
        total_subtotal=Coalesce(Sum("sub_total"), Decimal("0.00")),
        total_cgst=Coalesce(Sum("cgst_amount"), Decimal("0.00")),
        total_igst=Coalesce(Sum("igst_amount"), Decimal("0.00")),
        total_amount=Coalesce(Sum("total_amount"), Decimal("0.00")),
        total_adjustment=Coalesce(Sum("adjustment_amount"), Decimal("0.00")),
    )

    context = {
        "data": purchase_orders,
        "total_count": total_count,
        "total_subtotal": aggregates["total_subtotal"],
        "total_cgst": aggregates["total_cgst"] * 2,  # CGST + SGST
        "total_igst": aggregates["total_igst"],
        "total_amount": aggregates["total_amount"],
        "total_adjustment": aggregates["total_adjustment"],
        "start_date": start_date,
        "end_date": end_date,
    }

    template = "supplier_purchased_pdf.html"
    filename = "purchase_orders"
    return generatePdf(template, filename, context, request)


def generate_supplier_ind_pdf(request, pk):
    """Generate PDF for individual supplier purchase order with search and sort parameters."""
    supplier = get_object_or_404(Supplier, pk=pk)
    start_date, end_date = getDates(request)
    date_range = [start_date, end_date]
    report_data = get_supplier_report_data(supplier, date_range)

    context = {
        "supplier": supplier,
        "transactions": report_data["transactions"],
        "total_invoiced": report_data["total_invoiced"],
        "total_paid": report_data["total_paid"],
        "outstanding_balance": report_data["outstanding_balance"],
        "opening_balance": report_data["opening_balance"],
        "start_date": start_date,
        "end_date": end_date,
    }
    template = "supplier_ind_report_pdf.html"
    filename = "supplier_individual_report"

    return generatePdf(template, filename, context, request)


def generate_invoice_report_pdf(request):
    start_date, end_date = getDates(request)
    date_range = [start_date, end_date]
    invoices = get_invoice_report_data(date_range)
    total_count = invoices.count()
    total_net = Decimal("0")
    total_cgst_amount = Decimal("0")
    total_gst = Decimal("0")
    total_amount = Decimal("0")

    if invoices:
        for invoice in invoices:
            total_net += invoice.total_tax_value
            total_cgst_amount += invoice.cgst_amount
            total_gst += invoice.total_gst_amount
            total_amount += invoice.total_payable

    context = {
        "data": invoices,
        "start_date": start_date,
        "end_date": end_date,
        "total_count": total_count,
        "total_net": total_net,
        "total_cgst_amount": total_cgst_amount,
        "total_gst": total_gst,
        "total_amount": total_amount,
    }
    template = "invoice_report_pdf.html"
    filename = (
        f"invoice_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    )
    return generatePdf(template, filename, context, request)
