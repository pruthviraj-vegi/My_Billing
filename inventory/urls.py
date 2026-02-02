from django.urls import path
from . import views, _views

app_name = "inventory"

urlpatterns = [
    # Dashboard
    path("dashboard/", views.inventory_dashboard, name="dashboard"),
    path("dashboard/fetch/", views.inventory_dashboard_fetch, name="dashboard_fetch"),
    path("low-stock/", views.low_stock_page, name="low_stock"),
    path("full-product/create/", views.CreateProduct.as_view(), name="product_create"),
    path(
        "variant/<int:pk>/update/",
        views.variant_update,
        name="variant_update",
    ),
    # Cloth Type Management
    path("cloth/", _views.cloth_home, name="cloth_home"),
    path("cloth/create/", _views.CreateClothType.as_view(), name="cloth_create"),
    path("cloth/create-ajax/", _views.create_cloth_type_ajax, name="cloth_create_ajax"),
    path("cloth/<int:pk>/edit/", _views.UpdateClothType.as_view(), name="cloth_edit"),
    path(
        "cloth/<int:pk>/delete/", _views.DeleteClothType.as_view(), name="cloth_delete"
    ),
    # Color Management
    path("color/", _views.color_home, name="color_home"),
    path("color/create/", _views.CreateColor.as_view(), name="color_create"),
    path("color/create-ajax/", _views.create_color_ajax, name="color_create_ajax"),
    path("color/<int:pk>/edit/", _views.UpdateColor.as_view(), name="color_edit"),
    path("color/<int:pk>/delete/", _views.DeleteColor.as_view(), name="color_delete"),
    # Size Management
    path("size/", _views.size_home, name="size_home"),
    path("size/create/", _views.CreateSize.as_view(), name="size_create"),
    path("size/create-ajax/", _views.create_size_ajax, name="size_create_ajax"),
    path("size/<int:pk>/edit/", _views.UpdateSize.as_view(), name="size_edit"),
    path("size/<int:pk>/delete/", _views.DeleteSize.as_view(), name="size_delete"),
    # Category Management
    path("category/", _views.category_home, name="category_home"),
    path("category/fetch/", _views.fetch_categories, name="category_fetch"),
    path(
        "category/suggestions/", _views.search_suggestions, name="category_suggestions"
    ),
    path("category/create/", _views.CreateCategory.as_view(), name="category_create"),
    path(
        "category/create-ajax/",
        _views.create_category_ajax,
        name="category_create_ajax",
    ),
    path(
        "category/<int:pk>/edit/", _views.UpdateCategory.as_view(), name="category_edit"
    ),
    path(
        "category/<int:pk>/delete/",
        _views.DeleteCategory.as_view(),
        name="category_delete",
    ),
    # UOM Management
    path("uom/", _views.uom_home, name="uom_home"),
    path("uom/fetch/", _views.fetch_uoms, name="uom_fetch"),
    path("uom/suggestions/", _views.uom_search_suggestions, name="uom_suggestions"),
    path("uom/create/", _views.CreateUOM.as_view(), name="uom_create"),
    path("uom/create-ajax/", _views.create_uom_ajax, name="uom_create_ajax"),
    path("uom/<int:pk>/edit/", _views.UpdateUOM.as_view(), name="uom_edit"),
    path(
        "uom/<int:pk>/delete/",
        _views.DeleteUOM.as_view(),
        name="uom_delete",
    ),
    # GST HSN Code Management
    path("gst-hsn/", _views.gst_hsn_home, name="gst_hsn_home"),
    path("gst-hsn/fetch/", _views.fetch_gst_hsn_codes, name="gst_hsn_fetch"),
    path(
        "gst-hsn/suggestions/",
        _views.gst_hsn_search_suggestions,
        name="gst_hsn_suggestions",
    ),
    path("gst-hsn/create/", _views.CreateGSTHsnCode.as_view(), name="gst_hsn_create"),
    path(
        "gst-hsn/create-ajax/",
        _views.create_gst_hsn_code_ajax,
        name="gst_hsn_create_ajax",
    ),
    path(
        "gst-hsn/<int:pk>/edit/", _views.UpdateGSTHsnCode.as_view(), name="gst_hsn_edit"
    ),
    path(
        "gst-hsn/<int:pk>/delete/",
        _views.DeleteGSTHsnCode.as_view(),
        name="gst_hsn_delete",
    ),
    # Favorites
    path("favorites/", _views.favorites_home, name="favorites_home"),
    path("favorites/fetch/", _views.fetch_favorites, name="fetch_favorites"),
    path(
        "favorites/get-variants/",
        _views.get_variants_for_favorites,
        name="get_variants_for_favorites",
    ),
    path("favorites/add/<int:variant_id>/", _views.add_favorite, name="add_favorite"),
    path(
        "favorites/remove/<int:variant_id>/",
        _views.remove_favorite,
        name="remove_favorite",
    ),
    # Supplier Invoice Tracking
    path(
        "supplier-invoices/",
        views.supplier_invoice_tracking,
        name="supplier_invoice_tracking",
    ),
    path(
        "supplier-invoices/fetch/",
        views.supplier_invoice_tracking_fetch,
        name="supplier_invoice_tracking_fetch",
    ),
    path(
        "supplier-invoices/<int:invoice_id>/",
        views.supplier_invoice_details,
        name="supplier_invoice_details",
    ),
    # path(
    #     "variant/<int:variant_id>/invoice-analytics/",
    #     views.product_invoice_analytics,
    #     name="product_invoice_analytics",
    # ),
    # path(
    #     "supplier/<int:supplier_id>/analytics/",
    #     views.supplier_analytics,
    #     name="supplier_analytics",
    # ),
]
