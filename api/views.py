"""API views for customer balance, invoices, statements, and WhatsApp messaging."""

import logging
from datetime import datetime

import requests
from decouple import config
from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse

from api.services import generate_invoice_pdf, generate_statement_pdf
from base.getDates import getDates
from customer.models import Customer
from invoice.models import Invoice

logger = logging.getLogger(__name__)


def number_format(phone_number):
    """Validate and normalize a phone number to 10 digits.

    Args:
        phone_number: Raw phone number string.

    Returns:
        str: Normalized 10-digit phone number.

    Raises:
        ValueError: If the phone number is invalid.
    """
    if not phone_number.isdigit():
        raise ValueError("Phone number must contain only digits")
    if len(phone_number) > 13 or len(phone_number) < 10:
        raise ValueError("Issue With Phone No, Provide a Valid Phone No")
    if len(phone_number) == 12 and phone_number.startswith("91"):
        phone_number = phone_number[2:]
    return phone_number


@login_not_required
def get_balance(request, phone_number):
    """Return the current credit balance for a customer by phone number."""
    try:
        phone_number = number_format(phone_number)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    customer = Customer.objects.filter(phone_number=phone_number).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    balance = customer.credit_summary.balance_amount
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
    """Return the last invoice PDF for a customer by phone number."""
    try:
        phone_number = number_format(phone_number)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

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
    except RuntimeError:
        logger.error("Error generating invoice PDF for invoice %s", invoice.pk)
        return JsonResponse(
            {"error": "Failed to generate or retrieve invoice PDF"}, status=500
        )


@login_not_required
def get_statement(request, phone_number):
    """Return a credit statement PDF for a customer by phone number and date range."""
    try:
        phone_number = number_format(phone_number)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

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
    except RuntimeError:
        logger.error("Error generating statement PDF for customer %s", customer.pk)
        return JsonResponse(
            {"error": "Failed to generate or retrieve statement PDF"}, status=500
        )


@login_not_required
def get_last_5_invoices(request, phone_number):
    """Return the last 5 invoices summary for a customer by phone number."""
    phone_number = number_format(phone_number)

    customer = Customer.objects.filter(phone_number=phone_number).first()
    if not customer:
        return JsonResponse({"error": "Customer not found"}, status=404)

    invoices = Invoice.objects.filter(customer=customer).order_by("-invoice_date")[:5]

    invoices_data = ""
    for invoice in invoices:
        invoices_data += (
            f"{invoice.invoice_number} - "
            f"{invoice.invoice_date.strftime('%d-%m-%Y')} - "
            f"{invoice.amount} \n"
        )

    return JsonResponse(
        {
            "name": customer.name,
            "invoices": invoices_data,
        },
        status=200,
    )


@login_not_required
def send_template(request, phone, template_name, params, url, file_name):
    """Send a WhatsApp template message with a document attachment."""
    # Ensure phone number has 91 prefix
    if not phone.startswith("91"):
        phone = f"91{phone}"

    response = requests.post(
        f"{config('WHATSAPP_URL')}/external/send-template",
        json={
            "to": phone,
            "template_name": template_name,
            "params": params,
            "document_url": url,
            "document_filename": file_name,
        },
        timeout=30,
    )
    return response.json()


@login_not_required
def send_test(request, phone_number, text=""):
    """Send a plain text WhatsApp message to the given phone number."""
    phone_number = number_format(phone_number)

    if not phone_number.startswith("91"):
        phone_number = f"91{phone_number}"

    response = requests.post(
        f"{config('WHATSAPP_URL')}/external/send-text",
        json={"to": phone_number, "text": text},
        timeout=30,
    )
    return response.json()
