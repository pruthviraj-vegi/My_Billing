"""
Views for handling statement and invoice related endpoints.
"""

import logging

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from api.services import generate_invoice_pdf, generate_statement_pdf
from api.views import send_template
from base.getDates import getDates
from customer.models import Customer, Payment
from invoice.models import Invoice

logger = logging.getLogger(__name__)


def send_invoice(request, pk):
    """
    Generate and send an invoice PDF to the customer via WhatsApp.
    """
    invoice = Invoice.objects.select_related("customer").get(pk=pk)
    try:
        # Use the helper function to generate or retrieve PDF
        pdf_data = generate_invoice_pdf(invoice, request)

        response = send_template(
            request,
            invoice.customer.phone_number,
            settings.WA_INVOICE_TEMPLATE,
            {
                "customer_name": invoice.customer.name,
                "invoice_number": invoice.invoice_number,
            },
            pdf_data["url"],
            pdf_data["filename"],
        )

        if response.get("success") is True:
            return JsonResponse(
                {
                    "success": True,
                    "message": "Invoice sent successfully",
                },
                status=200,
            )
        return JsonResponse(
            {
                "success": False,
                "message": response.get("detail")
                or response.get("message")
                or "Failed to send invoice",
            },
            status=200,
        )

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error generating invoice PDF: %s", e)
        return JsonResponse(
            {
                "success": False,
                "message": "Failed to send invoice",
            },
            status=500,
        )


def send_statement(request, pk):
    """
    Generate and send a statement PDF to the customer via WhatsApp.
    """
    customer = get_object_or_404(Customer, id=pk)
    start_date, end_date = getDates(request)

    try:
        pdf_data = generate_statement_pdf(customer, start_date, end_date, request)
        response = send_template(
            request,
            customer.phone_number,
            settings.WA_STATEMENT_TEMPLATE,
            {
                "customer_name": customer.name,
                "from_date": start_date.strftime("%d-%m-%Y"),
                "to_date": end_date.strftime("%d-%m-%Y"),
            },
            pdf_data["url"],
            pdf_data["filename"],
        )
        if response.get("success") is True:
            return JsonResponse(
                {
                    "success": True,
                    "message": "Statement sent successfully",
                },
                status=200,
            )
        return JsonResponse(
            {
                "success": False,
                "message": response.get("detail")
                or response.get("message")
                or "Failed to send statement",
            },
            status=200,
        )

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error generating statement PDF: %s", e)
        return JsonResponse(
            {
                "success": False,
                "message": "Failed to send statement",
            },
            status=500,
        )


def send_text(request, pk):
    """
    Send a payment receipt text to the customer via WhatsApp.
    """
    payment = get_object_or_404(Payment, id=pk)
    try:
        response = send_template(
            request,
            payment.customer.phone_number,
            settings.WA_PAYMENT_TEMPLATE,
            {
                "customer_name": payment.customer.name,
                "amount": str(float(payment.amount)),
                "date": payment.created_at.strftime("%d-%m-%Y"),
                "payment_id": str(payment.id),
            },
            "",
            "",
        )

        if response.get("success") is True:
            return JsonResponse(
                {
                    "success": True,
                    "message": "Payment sent successfully",
                },
                status=200,
            )
        return JsonResponse(
            {
                "success": False,
                "message": response.get("detail")
                or response.get("message")
                or "Failed to send payment",
            },
            status=200,
        )

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error generating payment text: %s", e)
        return JsonResponse(
            {
                "success": False,
                "message": "Failed to send payment",
            },
            status=500,
        )


def balance(request, pk):
    """
    Send the current balance details to a customer via WhatsApp.

    Fetches the customer by pk, retrieves their current outstanding balance,
    and sends it using the WhatsApp balance template.

    Args:
        request: The HTTP request object.
        pk (int): The primary key of the customer.

    Returns:
        JsonResponse: Indicating whether the message was sent successfully.
    """
    customer = get_object_or_404(Customer, id=pk)
    try:
        try:
            balance_amount = customer.credit_summary.balance_amount
        except Exception:
            balance_amount = 0.0

        today_str = timezone.now().strftime("%d-%m-%Y")

        response = send_template(
            request,
            customer.phone_number,
            settings.WA_BALANCE_TEMPLATE,
            {
                "customer_name": customer.name,
                "balance": str(float(balance_amount)),
                "date": today_str,
            },
            "",
            "",
        )

        if response.get("success") is True:
            return JsonResponse(
                {
                    "success": True,
                    "message": "Balance sent successfully",
                },
                status=200,
            )
        return JsonResponse(
            {
                "success": False,
                "message": response.get("detail")
                or response.get("message")
                or "Failed to send balance",
            },
            status=200,
        )

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error sending balance: %s", e)
        return JsonResponse(
            {
                "success": False,
                "message": "Failed to send balance",
            },
            status=500,
        )
