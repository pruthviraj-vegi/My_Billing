from django.urls import path
from . import views


app_name = "report"

urlpatterns = [
    path("invoice/<int:pk>/", views.createInvoice, name="invoice_pdf"),
    path("estimate/<int:pk>/", views.estimate_invoice, name="estimate_pdf"),
    path("barcode/<int:pk>/", views.generate_barcode, name="barcode"),
    path("invoices/pdf/", views.generate_invoices_pdf, name="invoices_pdf"),
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
]
