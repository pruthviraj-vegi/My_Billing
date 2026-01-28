from django.shortcuts import render
from django.http import JsonResponse
from .models import Invoice, ReturnInvoice
import logging
from base.getDates import getDates
from django.template.loader import render_to_string
from base.utility import render_paginated_response

logger = logging.getLogger(__name__)


def invoice_report(request):
    return render(request, "invoice_report/main.html")


def get_invoice_report_data(date_range):
    invoices = Invoice.objects.select_related("customer").filter(
        invoice_type=Invoice.Invoice_type.GST,
        invoice_date__date__range=date_range,
    )
    return invoices


def get_invoice_cancled_data(date_range):
    invoices = Invoice.objects.select_related("customer").filter(
        invoice_type=Invoice.Invoice_type.GST,
        cancelled_at__date__range=date_range,
        is_cancelled=True,
    )
    return invoices


def get_invoice_return_data(date_range):
    invoices = ReturnInvoice.objects.select_related("invoice__customer").filter(
        invoice__invoice_type=Invoice.Invoice_type.GST,
        updated_at__date__range=date_range,
        invoice__is_cancelled=False,
        status=ReturnInvoice.RefundStatus.APPROVED,
    )
    return invoices


def invoice_report_fetch(request):
    start_date, end_date = getDates(request)
    date_range = [start_date, end_date]
    invoices = get_invoice_report_data(date_range)

    return render_paginated_response(
        request,
        invoices,
        "invoice_report/fetch.html",
        10,
    )


def invoice_cancled_report_fetch(request):
    start_date, end_date = getDates(request)
    date_range = [start_date, end_date]
    invoices = get_invoice_cancled_data(date_range)

    return render_paginated_response(
        request,
        invoices,
        "invoice_report/fetch.html",
        10,
    )


def invoice_return_report_fetch(request):
    start_date, end_date = getDates(request)
    date_range = [start_date, end_date]
    invoices = get_invoice_return_data(date_range)

    return render_paginated_response(
        request,
        invoices,
        "invoice_report/return_fetch.html",
        10,
    )
