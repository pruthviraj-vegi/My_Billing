from django.contrib.auth.views import login_not_required
from customer.models import Customer
from invoice.models import Invoice, InvoiceItem
from django.http import JsonResponse
from django.contrib.auth.decorators import login_not_required
from datetime import datetime
from base.getDates import getDates
from report.views import generatePdf
from customer.views_credit import _build_ledger_rows, get_opening_balance
import io
import qrcode
import base64
import logging
import requests
from setting.models import ReportConfiguration
from setting.models import PaymentDetails
from setting.models import ShopDetails
from api.services import generate_invoice_pdf, generate_statement_pdf
from decouple import config


logger = logging.getLogger(__name__)


# Create your views here.
def number_format(phone_number):
    if not phone_number.isdigit():
        raise Exception("Phone number must contain only digits")
    if len(phone_number) > 13 or len(phone_number) < 10:
        raise Exception("Issue With Phone No, Provide a Valid Phone No")
    if len(phone_number) == 12 and phone_number.startswith("91"):
        phone_number = phone_number[2:]
    return phone_number


@login_not_required
def get_balance(request, phone_number):
    try:
        phone_number = number_format(phone_number)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    customer = Customer.objects.filter(phone_number=phone_number).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    balance = customer.balance_amount
    return JsonResponse(
        {
            "balance": balance,
            "date": datetime.now().strftime("%d-%m-%Y"),
            "name": customer.name,
        },
        status=200,
    )


@login_not_required
def get_last_invoice(request, phone_number):
    try:
        phone_number = number_format(phone_number)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    customer = Customer.objects.filter(phone_number=phone_number).first()

    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    invoice = Invoice.objects.filter(customer=customer).order_by("-created_at").first()

    if not invoice:
        return JsonResponse({"error": "No invoice found"}, status=404)

    try:
        # Use the helper function to generate or retrieve PDF
        pdf_data = generate_invoice_pdf(invoice, request)

        return JsonResponse(
            {
                "name": customer.name,
                "invoice_number": invoice.invoice_number,
                **pdf_data,  # Unpacks url, generated_at, and pdf_status
            },
            status=200,
        )
    except Exception as e:
        logger.error(f"Error generating invoice PDF: {e}")
        return JsonResponse(
            {"error": "Failed to generate or retrieve invoice PDF"}, status=500
        )


@login_not_required
def get_statement(request, phone_number):
    try:
        phone_number = number_format(phone_number)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

    customer = Customer.objects.filter(phone_number=phone_number).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    start_date, end_date = getDates(request)

    try:
        # Use the service function to generate statement PDF
        pdf_data = generate_statement_pdf(customer, start_date, end_date, request)

        return JsonResponse(
            {
                "name": customer.name,
                "from_date": start_date.strftime("%d-%m-%Y"),
                "to_date": end_date.strftime("%d-%m-%Y"),
                **pdf_data,
            },
            status=200,
        )
    except Exception as e:
        logger.error(f"Error generating statement PDF: {e}")
        return JsonResponse(
            {"error": "Failed to generate or retrieve statement PDF"}, status=500
        )


@login_not_required
def get_last_5_invoices(request, phone_number):
    phone_number = number_format(phone_number)

    customer = Customer.objects.filter(phone_number=phone_number).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    invoices = Invoice.objects.filter(customer=customer).order_by("-invoice_date")[:5]

    invoices_data = ""
    for invoice in invoices:
        invoices_data += f"{invoice.invoice_number} - {invoice.invoice_date.strftime('%d-%m-%Y')} - {invoice.amount} \n"

    return JsonResponse(
        {
            "name": customer.name,
            "invoices": invoices_data,
        },
        status=200,
    )


@login_not_required
def send_template(request, phone, template_name, params, url, file_name):
    # Ensure phone number has 91 prefix
    if not phone.startswith("91"):
        phone = f"91{phone}"

    response = requests.post(
        f"{config("WHATSAPP_URL")}/external/send-template",
        json={
            "to": phone,
            "template_name": template_name,
            "params": params,
            "document_url": url,
            "document_filename": file_name,
        },
    )
    return response.json()


@login_not_required
def send_test(request, phone_number, text=""):
    phone_number = number_format(phone_number)

    if not phone_number.startswith("91"):
        phone_number = f"91{phone_number}"

    response = requests.post(
        f"{config("WHATSAPP_URL")}/external/send-text",
        json={"to": phone_number, "text": text},
    )
    return response.json()
