import logging
from weasyprint import HTML
from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import get_template
from django.contrib.auth.decorators import login_required
import io
import qrcode
from barcode import Code128
from barcode.base import Barcode
from barcode.writer import SVGWriter
import base64
from PIL import Image
from inventory.models import ProductVariant
from invoice.models import Invoice, InvoiceItem
from setting.models import ShopDetails, ReportConfiguration
from cart.models import Cart, CartItem
from datetime import datetime

from customer.views import get_data
from customer.views_credit import credit_customers_data, total_credit_customers_data
from supplier.views import (
    get_suppliers_data,
    get_total_outstanding_balance as supplier_total_outstanding_balance,
)
from inventory.views_variant import get_variants_data

Barcode.default_writer_options["write_text"] = False

logger = logging.getLogger(__name__)


def get_print_count(num):
    return num // 2 if num % 2 == 0 else num // 2 + 1


# general pdf creation values for all data
def generatePdf(template_name, file_name, context, request, report_type="INVOICE"):
    # Get shop details
    shop_details = ShopDetails.objects.filter(is_active=True).first()
    context["shop_details"] = shop_details

    # Get report configuration
    report_config = ReportConfiguration.get_default_config(report_type)
    context["report_config"] = report_config

    template = get_template(f"report/{template_name}")
    html = template.render(context)

    # Insert barcode image into HTML using base64-encoded data URL
    if "qrcode" in context:
        barcode_data = context["qrcode"]
        html = html.replace(
            "{{ qrcode }}", f'<img src="data:image/png;base64, {barcode_data}"/>'
        )

    pdf_file = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf(
        presentational_hints=True
    )

    filename = f"{file_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'filename="{filename}.pdf"'
    response["pdfkit-dpi"] = "800"  # Set the DPI to 300
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

    if report_config.paper_size == ReportConfiguration.PaperSize._58mm:
        template = "report/58mm.html"
    else:
        template = "report/A5.html"

    context = {
        "values": values,
        "details": invoice,
        "shop_details": shop_details,
        "report_config": report_config,
    }

    # Generate QR code if enabled in config
    if report_config and report_config.show_qr_code and shop_details:
        try:
            # Create UPI payment QR code
            qr_data = f"upi://pay?pa={shop_details.phone_number}&pn={shop_details.shop_name}&am={invoice.amount}&tn=Invoice {invoice.invoice_number}&cu=INR"
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

    # Add the barcode image to the context dictionary
    context = {
        "values": variant,
        "print_count": get_print_count(variant.quantity),
        "barcode_svg": barcode_image,
        "shop_details": shop_details,
    }
    return render(request, template, context)


@login_required
def generate_customers_pdf(request):
    """Generate PDF for customers list with search and sort parameters."""

    # Get customers using the same logic as fetch_customers
    customers = get_data(request)

    # Prepare context
    context = {
        "customers": customers,
        "total_count": customers.count(),
    }

    # Render template
    template = "customer_pdf.html"

    filename = "customers"

    return generatePdf(template, filename, context, request)


@login_required
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


@login_required
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


@login_required
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
