from django.urls import path
from . import views_variant

app_name = "inventory_variant"

urlpatterns = [
    path("", views_variant.variant_home, name="home"),
    path("fetch/", views_variant.fetch_variants, name="fetch"),
    path("<int:variant_id>/", views_variant.variant_details, name="details"),
    path(
        "create/<int:product_id>/",
        views_variant.CreateProductVariant.as_view(),
        name="create",
    ),
    path(
        "edit/<int:pk>/",
        views_variant.EditProductVariant.as_view(),
        name="edit",
    ),
    # Inventory Operations
    path(
        "operations/stock-in/<int:variant_id>/",
        views_variant.StockInCreate.as_view(),
        name="stock_in",
    ),
    path(
        "operations/adjustment-in/<int:variant_id>/",
        views_variant.AdjustmentInCreate.as_view(),
        name="adjustment_in",
    ),
    path(
        "operations/adjustment-out/<int:variant_id>/",
        views_variant.AdjustmentOutCreate.as_view(),
        name="adjustment_out",
    ),
    path(
        "operations/damage/<int:variant_id>/",
        views_variant.DamageCreate.as_view(),
        name="damage_create",
    ),
    # Favorite operations
    path(
        "favorites/",
        views_variant.favorites_home,
        name="favorites_home",
    ),
    path(
        "favorites/fetch/",
        views_variant.fetch_favorites,
        name="fetch_favorites",
    ),
    path(
        "favorites/get-variants/",
        views_variant.get_variants_for_favorites,
        name="get_variants_for_favorites",
    ),
    path(
        "favorites/add-bulk/",
        views_variant.add_favorites_bulk,
        name="add_favorites_bulk",
    ),
]
