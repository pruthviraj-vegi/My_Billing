"""
Views for handling settings, shop details, report configs, and barcodes.
"""

import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import (
    BarcodeConfigurationForm,
    PaymentDetailsForm,
    QuickReportConfigForm,
    ReportConfigurationForm,
    ShopDetailsForm,
)
from .models import (
    BarcodeConfiguration,
    PaymentDetails,
    ReportConfiguration,
    ShopDetails,
)

logger = logging.getLogger(__name__)


def shop_details_list(request):
    """List all shop details."""

    # Search functionality
    search_query = request.GET.get("search", "")
    filters = Q()
    if search_query:
        terms = search_query.split()
        for word in terms:
            filters &= (
                Q(shop_name__icontains=word)
                | Q(city__icontains=word)
                | Q(state__icontains=word)
                | Q(phone_number__icontains=word)
            )

    # Base queryset
    shops = ShopDetails.objects.filter(filters).order_by("-created_at")

    # Pagination
    paginator = Paginator(shops, 10)
    page_number = request.GET.get("page")
    shops = paginator.get_page(page_number)

    context = {
        "shops": shops,
        "search_query": search_query,
        "page_title": "Shop Details",
    }
    return render(request, "setting/shop/shop_details_list.html", context)


def shop_details_create(request):
    """Create new shop details."""
    if request.method == "POST":
        form = ShopDetailsForm(request.POST, request.FILES)
        if form.is_valid():
            shop = form.save(commit=False)
            shop.created_by = request.user
            shop.save()
            messages.success(request, "Shop details created successfully!")
            return redirect("setting:shop_details_list")
        logger.error("Form invalid: %s", form.errors)
    else:
        form = ShopDetailsForm()

    context = {"form": form, "page_title": "Add Shop Details", "form_action": "Create"}
    return render(request, "setting/shop/shop_details_form.html", context)


def shop_details_edit(request, pk):
    """Edit existing shop details."""
    shop = get_object_or_404(ShopDetails, pk=pk)

    if request.method == "POST":
        form = ShopDetailsForm(request.POST, request.FILES, instance=shop)
        if form.is_valid():
            form.save()
            messages.success(request, "Shop details updated successfully!")
            return redirect("setting:shop_details_list")
        logger.error("Form invalid: %s", form.errors)
    else:
        form = ShopDetailsForm(instance=shop)

    context = {
        "form": form,
        "shop": shop,
        "page_title": "Edit Shop Details",
        "form_action": "Update",
    }
    return render(request, "setting/shop/shop_details_form.html", context)


def shop_details_detail(request, pk):
    """View shop details."""
    shop = get_object_or_404(ShopDetails, pk=pk)

    context = {"shop": shop, "page_title": f"Shop Details - {shop.shop_name}"}
    return render(request, "setting/shop/shop_details_detail.html", context)


def shop_details_delete(request, pk):
    """Delete shop details."""
    shop = get_object_or_404(ShopDetails, pk=pk)

    if request.method == "POST":
        shop_name = shop.shop_name
        shop.delete()
        messages.success(
            request, f'Shop details for "{shop_name}" deleted successfully!'
        )
        return redirect("setting:shop_details_list")

    context = {"shop": shop, "page_title": f"Delete Shop - {shop.shop_name}"}
    return render(request, "setting/shop/shop_details_delete.html", context)


def report_config_list(request):
    """List all report configurations."""

    # Search functionality
    search_query = request.GET.get("search", "")
    filters = Q()
    if search_query:
        terms = search_query.split()
        for word in terms:
            filters &= (
                Q(report_type__icontains=word)
                | Q(terms_conditions__icontains=word)
                | Q(thank_you_message__icontains=word)
            )

    configs = ReportConfiguration.objects.filter(filters).order_by(
        "-is_default", "-created_at"
    )

    # Pagination
    paginator = Paginator(configs, 10)
    page_number = request.GET.get("page")
    configs = paginator.get_page(page_number)

    context = {
        "configs": configs,
        "search_query": search_query,
        "page_title": "Report Configurations",
    }
    return render(request, "setting/reports/report_config_list.html", context)


def report_config_create(request):
    """Create new report configuration."""
    if request.method == "POST":
        form = ReportConfigurationForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            config.created_by = request.user
            config.save()
            messages.success(request, "Report configuration created successfully!")
            return redirect("setting:report_config_list")
    else:
        form = ReportConfigurationForm()

    context = {
        "form": form,
        "page_title": "Add Report Configuration",
        "form_action": "Create",
    }
    return render(request, "setting/reports/report_config_form.html", context)


def report_config_edit(request, pk):
    """Edit existing report configuration."""
    config = get_object_or_404(ReportConfiguration, pk=pk)

    if request.method == "POST":
        form = ReportConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Report configuration updated successfully!")
            return redirect("setting:report_config_list")
    else:
        form = ReportConfigurationForm(instance=config)

    context = {
        "form": form,
        "config": config,
        "page_title": "Edit Report Configuration",
        "form_action": "Update",
    }
    return render(request, "setting/reports/report_config_form.html", context)


def report_config_detail(request, pk):
    """View report configuration."""
    config = get_object_or_404(ReportConfiguration, pk=pk)

    context = {
        "config": config,
        "page_title": f"Report Configuration - {config.get_report_type_display()}",
    }
    return render(request, "setting/reports/report_config_detail.html", context)


def report_config_delete(request, pk):
    """Delete report configuration."""
    config = get_object_or_404(ReportConfiguration, pk=pk)

    if request.method == "POST":
        config_name = (
            f"{config.get_report_type_display()} - {config.get_paper_size_display()}"
        )
        config.delete()
        messages.success(
            request, f'Report configuration "{config_name}" deleted successfully!'
        )
        return redirect("setting:report_config_list")

    context = {
        "config": config,
        "page_title": f"Delete Configuration - {config.get_report_type_display()}",
    }
    return render(request, "setting/reports/report_config_delete.html", context)


@require_http_methods(["POST"])
def set_default_config(request, pk):
    """Set a configuration as default for its report type."""
    config = get_object_or_404(ReportConfiguration, pk=pk)

    # Set all other configs of same type to not default
    ReportConfiguration.objects.filter(
        report_type=config.report_type, is_default=True
    ).exclude(pk=pk).update(is_default=False)

    # Set this config as default
    config.is_default = True
    config.save()

    return JsonResponse(
        {
            "success": True,
            "message": f"Configuration set as default for {config.get_report_type_display()}",
        }
    )


def shop_settings_dashboard(request):
    """Dashboard for shop and report settings."""
    # Get shop details
    shops = ShopDetails.objects.filter(is_active=True).order_by("-created_at")
    active_shop = shops.first() if shops.exists() else None

    # Get report configurations
    configs = ReportConfiguration.objects.filter(is_active=True).order_by(
        "-is_default", "-created_at"
    )

    # Get default configs by type
    default_configs = {}
    for report_type, _ in ReportConfiguration.ReportType.choices:
        try:
            default_configs[report_type] = ReportConfiguration.objects.get(
                report_type=report_type, is_default=True, is_active=True
            )
        except ReportConfiguration.DoesNotExist:
            default_configs[report_type] = None

    context = {
        "active_shop": active_shop,
        "shops": shops,
        "configs": configs,
        "default_configs": default_configs,
        "page_title": "Shop & Report Settings",
    }
    return render(request, "setting/shop/shop_settings_dashboard.html", context)


def payment_details_list(request):
    """List all payment details."""

    # Search functionality
    search_query = request.GET.get("search", "")
    filters = Q()
    if search_query:
        terms = search_query.split()
        for word in terms:
            filters &= (
                Q(payment_name__icontains=word)
                | Q(upi_id__icontains=word)
                | Q(account_number__icontains=word)
                | Q(bank_name__icontains=word)
            )

    payments = PaymentDetails.objects.filter(filters).order_by(
        "display_order", "-is_default", "-created_at"
    )

    # Pagination
    paginator = Paginator(payments, 10)
    page_number = request.GET.get("page")
    payments = paginator.get_page(page_number)

    context = {
        "payments": payments,
        "search_query": search_query,
        "page_title": "Payment Methods",
    }
    return render(request, "setting/payment/payment_details_list.html", context)


def payment_details_create(request):
    """Create new payment details."""
    if request.method == "POST":
        form = PaymentDetailsForm(request.POST, request.FILES)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.created_by = request.user
            payment.save()
            messages.success(request, "Payment method created successfully!")
            return redirect("setting:payment_details_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        # Pre-select shop if only one exists
        initial_data = {}
        if ShopDetails.objects.count() == 1:
            initial_data["shop"] = ShopDetails.objects.first()

        form = PaymentDetailsForm(initial=initial_data)

    context = {
        "form": form,
        "page_title": "Add Payment Method",
        "form_action": "Create",
    }
    return render(request, "setting/payment/payment_details_form.html", context)


def payment_details_edit(request, pk):
    """Edit existing payment details."""
    payment = get_object_or_404(PaymentDetails, pk=pk)

    if request.method == "POST":
        form = PaymentDetailsForm(request.POST, request.FILES, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(request, "Payment method updated successfully!")
            return redirect("setting:payment_details_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PaymentDetailsForm(instance=payment)

    context = {
        "form": form,
        "payment": payment,
        "page_title": "Edit Payment Method",
        "form_action": "Update",
    }
    return render(request, "setting/payment/payment_details_form.html", context)


def payment_details_detail(request, pk):
    """View payment details."""
    payment = get_object_or_404(PaymentDetails, pk=pk)

    context = {
        "payment": payment,
        "page_title": f"Payment Method - {payment.payment_name}",
    }
    return render(request, "setting/payment/payment_details_detail.html", context)


def payment_details_delete(request, pk):
    """Delete payment details."""
    payment = get_object_or_404(PaymentDetails, pk=pk)

    if request.method == "POST":
        payment_name = payment.payment_name
        payment.delete()
        messages.success(
            request, f'Payment method "{payment_name}" deleted successfully!'
        )
        return redirect("setting:payment_details_list")

    context = {
        "payment": payment,
        "page_title": f"Delete Payment Method - {payment.payment_name}",
    }
    return render(request, "setting/payment/payment_details_delete.html", context)


def barcode_config_list(request):
    """List all barcode configurations."""

    # Search functionality
    search_query = request.GET.get("search", "")
    filters = Q()
    if search_query:
        terms = search_query.split()
        for word in terms:
            filters &= Q(config_name__icontains=word) | Q(heading_text__icontains=word)

    configs = BarcodeConfiguration.objects.filter(filters).order_by(
        "-is_default", "-created_at"
    )

    # Pagination
    paginator = Paginator(configs, 10)
    page_number = request.GET.get("page")
    configs = paginator.get_page(page_number)

    context = {
        "configs": configs,
        "search_query": search_query,
        "page_title": "Barcode Configurations",
    }
    return render(request, "setting/barcode/barcode_config_list.html", context)


def barcode_config_create(request):
    """Create new barcode configuration."""
    if request.method == "POST":
        form = BarcodeConfigurationForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            config.created_by = request.user
            config.save()
            messages.success(request, "Barcode configuration created successfully!")
            return redirect("setting:barcode_config_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        # Pre-select shop if only one exists
        initial_data = {}
        if ShopDetails.objects.count() == 1:
            initial_data["shop"] = ShopDetails.objects.first()

        form = BarcodeConfigurationForm(initial=initial_data)

    context = {
        "form": form,
        "page_title": "Add Barcode Configuration",
        "form_action": "Create",
    }
    return render(request, "setting/barcode/barcode_config_form.html", context)


def barcode_config_edit(request, pk):
    """Edit existing barcode configuration."""
    config = get_object_or_404(BarcodeConfiguration, pk=pk)

    if request.method == "POST":
        form = BarcodeConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Barcode configuration updated successfully!")
            return redirect("setting:barcode_config_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = BarcodeConfigurationForm(instance=config)

    context = {
        "form": form,
        "config": config,
        "page_title": "Edit Barcode Configuration",
        "form_action": "Update",
    }
    return render(request, "setting/barcode/barcode_config_form.html", context)


def barcode_config_detail(request, pk):
    """View barcode configuration."""
    config = get_object_or_404(BarcodeConfiguration, pk=pk)

    context = {
        "config": config,
        "page_title": f"Barcode Configuration - {config.config_name}",
    }
    return render(request, "setting/barcode/barcode_config_detail.html", context)


def barcode_config_delete(request, pk):
    """Delete barcode configuration."""
    config = get_object_or_404(BarcodeConfiguration, pk=pk)

    if request.method == "POST":
        config_name = config.config_name
        config.delete()
        messages.success(
            request, f'Barcode configuration "{config_name}" deleted successfully!'
        )
        return redirect("setting:barcode_config_list")

    context = {
        "config": config,
        "page_title": f"Delete Configuration - {config.config_name}",
    }
    return render(request, "setting/barcode/barcode_config_delete.html", context)
