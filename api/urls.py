from django.urls import path
from . import views

app_name = "api"

urlpatterns = [
    path(
        "last_invoice/<str:phone_number>/", views.get_last_invoice, name="last_invoice"
    ),
    path("balance/<str:phone_number>/", views.get_balance, name="balance"),
    path("statement/<str:phone_number>/", views.get_statement, name="statement"),
    path(
        "last_5_invoices/<str:phone_number>/",
        views.get_last_5_invoices,
        name="last_5_invoices",
    ),
]
