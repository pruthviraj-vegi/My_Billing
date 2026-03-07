"""
URL patterns for the report app.
"""

from django.urls import path
from . import statements, views

app_name = "report"

urlpatterns = [
    path("invoice/<int:pk>/", views.create_invoice, name="invoice_pdf"),
    path("estimate/<int:pk>/", views.estimate_invoice, name="estimate_pdf"),
    path("barcode/<int:pk>/", views.generate_barcode, name="barcode"),
    path("customers/pdf/", views.generate_customers_pdf, name="customers_pdf"),
    path(
        "credit/customers/pdf/", views.generate_credit_pdf, name="credit_customers_pdf"
    ),
    path(
        "credit/individual/<int:pk>/",
        views.generate_credit_ind_pdf,
        name="credit_ind_pdf",
    ),
    path("suppliers/pdf/", views.generate_suppliers_pdf, name="suppliers_pdf"),
    path("variants/pdf/", views.generate_variants_pdf, name="variants_pdf"),
    path(
        "purchase-orders/pdf/",
        views.generate_purchase_orders_pdf,
        name="purchase_orders_pdf",
    ),
    path(
        "supplier/individual/<int:pk>/",
        views.generate_supplier_ind_pdf,
        name="supplier_ind_pdf",
    ),
    path(
        "invoice/report/pdf/",
        views.generate_invoice_report_pdf,
        name="invoice_report_pdf",
    ),
    path("send-invoice/<int:pk>/", statements.send_invoice, name="send_invoice"),
    path(
        "send-statement/<int:pk>/", statements.send_statement, name="send_pdf_statement"
    ),
    path("send-text/<int:pk>/", statements.send_text, name="send_text"),
]
