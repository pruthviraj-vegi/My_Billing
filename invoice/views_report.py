from django.shortcuts import render
from django.http import JsonResponse
from .models import Invoice
import logging
from base.getDates import getDates
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def invoice_report(request):
    return render(request, "invoice_report/main.html")


def get_invoice_report_data(date_range):
    invoices = Invoice.objects.select_related("customer").filter(
        invoice_type=Invoice.Invoice_type.GST,
        invoice_date__date__range=date_range,
    )
    return invoices


def invoice_report_fetch(request):
    start_date, end_date = getDates(request)
    date_range = [start_date, end_date]
    invoices = get_invoice_report_data(date_range)
    context = {
        "data": invoices,
    }
    table_html = render_to_string("invoice_report/fetch.html", context, request=request)

    return JsonResponse(
        {
            "success": True,
            "table_html": table_html,
            "start_date": start_date,
            "end_date": end_date,
        }
    )
