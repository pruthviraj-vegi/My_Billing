from django.http import JsonResponse
from invoice.models import Invoice
from api.services import generate_invoice_pdf, generate_statement_pdf
from api.views import send_template, send_test
from customer.models import Customer, Payment
from base.getDates import getDates
from django.shortcuts import get_object_or_404

import logging

logger = logging.getLogger(__name__)


def send_invoice(request, pk):

    invoice = Invoice.objects.get(pk=pk)
    try:
        # Use the helper function to generate or retrieve PDF
        pdf_data = generate_invoice_pdf(invoice, request)

        response = send_template(
            request,
            invoice.customer.phone_number,
            "invoice_template",
            [invoice.customer.name, str(float(invoice.amount))],
            pdf_data["url"],
            pdf_data["filename"],
        )

        if response.get("success") == True:
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

    except Exception as e:
        logger.error(f"Error generating invoice PDF: {e}")
        return JsonResponse(
            {
                "success": False,
                "message": "Failed to send invoice",
            },
            status=500,
        )


def send_statement(request, pk):
    customer = get_object_or_404(Customer, id=pk)
    start_date, end_date = getDates(request)

    try:
        pdf_data = generate_statement_pdf(customer, start_date, end_date, request)
        response = send_template(
            request,
            customer.phone_number,
            "statement",
            [
                customer.name,
                start_date.strftime("%d-%m-%Y"),
                end_date.strftime("%d-%m-%Y"),
            ],
            pdf_data["url"],
            pdf_data["filename"],
        )
        if response.get("success") == True:
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

    except Exception as e:
        logger.error(f"Error generating statement PDF: {e}")
        return JsonResponse(
            {
                "success": False,
                "message": "Failed to send statement",
            },
            status=500,
        )


def send_text(request, pk):
    payment = get_object_or_404(Payment, id=pk)
    try:
        response = send_template(
            request,
            payment.customer.phone_number,
            "payment_recived",
            [
                payment.customer.name,
                str(float(payment.amount)),
                payment.created_at.strftime("%d-%m-%Y"),
                f"#{payment.id}",
            ],
            "",
            "",
        )

        if response.get("success") == True:
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

    except Exception as e:
        logger.error(f"Error generating payment text: {e}")
        return JsonResponse(
            {
                "success": False,
                "message": "Failed to send payment",
            },
            status=500,
        )
