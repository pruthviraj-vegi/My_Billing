from django.contrib import messages
from django.shortcuts import redirect

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from .models import ShopDetails, ReportConfiguration, PaymentDetails, BarcodeConfiguration
from .forms import ShopDetailsForm, ReportConfigurationForm, QuickReportConfigForm, PaymentDetailsForm, BarcodeConfigurationForm
import logging

logger = logging.getLogger(__name__)


def shop_details_list(request):
    """List all shop details."""
    shops = ShopDetails.objects.all().order_by("-created_at")

    # Search functionality
    search_query = request.GET.get("search", "")
    if search_query:
        shops = shops.filter(
            Q(shop_name__icontains=search_query)
            | Q(city__icontains=search_query)
            | Q(state__icontains=search_query)
            | Q(phone_number__icontains=search_query)
        )

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
        logger.error(f"Form invalid: {form.errors}")
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
        logger.error(f"Form invalid: {form.errors}")
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
    configs = ReportConfiguration.objects.all().order_by("-is_default", "-created_at")

    # Search functionality
    search_query = request.GET.get("search", "")
    if search_query:
        configs = configs.filter(
            Q(report_type__icontains=search_query)
            | Q(terms_conditions__icontains=search_query)
            | Q(thank_you_message__icontains=search_query)
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


def quick_report_settings(request):
    """Quick report settings page."""
    if request.method == "POST":
        form = QuickReportConfigForm(request.POST)
        if form.is_valid():
            # Get or create default invoice config
            config = ReportConfiguration.get_default_config(
                ReportConfiguration.ReportType.INVOICE
            )

            # Update settings
            config.paper_size = form.cleaned_data["paper_size"]
            config.show_logo = form.cleaned_data["show_logo"]
            config.show_qr_code = form.cleaned_data["show_qr_code"]
            config.show_terms_conditions = form.cleaned_data["show_terms_conditions"]

            if form.cleaned_data["custom_terms"]:
                config.terms_conditions = form.cleaned_data["custom_terms"]

            config.save()
            messages.success(request, "Report settings updated successfully!")
            return redirect("setting:quick_report_settings")
    else:
        # Load current settings
        config = ReportConfiguration.get_default_config(
            ReportConfiguration.ReportType.INVOICE
        )
        form = QuickReportConfigForm(
            initial={
                "paper_size": config.paper_size,
                "show_logo": config.show_logo,
                "show_qr_code": config.show_qr_code,
                "show_terms_conditions": config.show_terms_conditions,
                "custom_terms": config.terms_conditions,
            }
        )

    context = {"form": form, "page_title": "Quick Report Settings"}
    return render(request, "setting/reports/quick_report_settings.html", context)


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
        except ReportConfiguration.DoesNotExist as e:
            logger.error(f"Report configuration not found: {e}")
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
    payments = PaymentDetails.objects.all().order_by("display_order", "-is_default", "-created_at")

    # Search functionality
    search_query = request.GET.get("search", "")
    if search_query:
        payments = payments.filter(
            Q(payment_name__icontains=search_query)
            | Q(upi_id__icontains=search_query)
            | Q(account_number__icontains=search_query)
            | Q(bank_name__icontains=search_query)
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
    configs = BarcodeConfiguration.objects.all().order_by("-is_default", "-created_at")

    # Search functionality
    search_query = request.GET.get("search", "")
    if search_query:
        configs = configs.filter(
            Q(config_name__icontains=search_query)
            | Q(heading_text__icontains=search_query)
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