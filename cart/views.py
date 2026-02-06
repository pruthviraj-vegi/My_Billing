from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from .models import Cart, CartItem
from .forms import CartForm
from django.contrib import messages
from inventory.models import ProductVariant, FavoriteVariant, BarcodeMapping
from inventory.views_variant import get_variants_data
from django.views.generic import CreateView, UpdateView, TemplateView
from django.urls import reverse
from base.utility import render_paginated_response
from decimal import Decimal
import logging
import json

logger = logging.getLogger(__name__)


class CartMainPageView(TemplateView):
    """Template view to render the main cart management page"""

    template_name = "cart/main_page.html"

    def get_context_data(self, **kwargs):
        """Add carts data to context with optimized queries"""
        context = super().get_context_data(**kwargs)
        # Use select_related to avoid N+1 queries
        context["carts"] = (
            Cart.objects.filter(status="OPEN")
            .select_related("created_by")
            .prefetch_related("cart_items__product_variant__product")
            .order_by("-created_at")
        )
        return context


def getCartData(request, pk):
    template_name = "cart/main_page.html"

    try:
        cart = Cart.objects.get(id=pk)
        # Optimize queries with select_related and prefetch_related
        cart_list = (
            CartItem.objects.filter(cart=cart)
            .select_related(
                "product_variant",
                "product_variant__product",
                "product_variant__product__category",
                "product_variant__size",
                "product_variant__color",
            )
            .order_by("-created_at")
        )

        carts = Cart.objects.filter(status="OPEN").order_by("-created_at")

        # Calculate total selling price (sum of all items' MRP * quantity)
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        from decimal import Decimal

        total_selling_price = cart_list.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantity") * F("product_variant__mrp"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )["total"] or Decimal("0.00")

        context = {
            "cart_list": cart_list,
            "cart": cart,
            "carts": carts,
            "total_selling_price": total_selling_price,
        }
    except Cart.DoesNotExist as e:
        # Redirect to main cart page if cart not found
        logger.error(f"Cart not found: {e}")
        return redirect("cart:main_page")

    return render(request, template_name, context)


class CreateCart(CreateView):
    model = Cart
    template_name = "cart/form.html"
    form_class = CartForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Cart"
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("cart:getCartData", kwargs={"pk": self.object.id})

    def form_invalid(self, form):
        return super().form_invalid(form)


class EditCart(UpdateView):
    model = Cart
    template_name = "cart/form.html"
    form_class = CartForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Cart"
        context["cart"] = self.get_object()
        return context

    def get_success_url(self):
        return reverse("cart:getCartData", kwargs={"pk": self.object.id})


def auto_cart_create(request):
    """Auto create cart"""

    carts = Cart.objects.filter(status="OPEN", created_by=request.user).order_by(
        "-created_at"
    )

    for cart in carts:
        if cart.get_item_count() == 0:
            messages.success(request, "Open cart existed, redirecting to it")
            return redirect("cart:getCartData", pk=cart.id)

    cart = Cart.objects.create(name="Walk in", created_by=request.user)
    messages.success(request, "Cart created successfully")
    return redirect("cart:getCartData", pk=cart.id)


def get_favorites(request):
    favorites = (
        FavoriteVariant.objects.filter(user=request.user)
        .select_related("variant")
        .prefetch_related("variant__product")
    )
    return render_paginated_response(request, favorites, "cart/models/favorites.html")


def custom_search(request):
    variants = get_variants_data(request)
    return render_paginated_response(
        request, variants, "cart/models/variants_fetch.html", 15
    )


# API Views for Cart Operations
@require_http_methods(["POST"])
def scan_barcode(request):
    """Scan barcode and add product to cart"""
    action_type = "Create"
    try:
        data = json.loads(request.body.decode("utf-8"))

        # Validate required fields
        barcode = data.get("barcode")
        cart_id = data.get("cart_id")
        quantity = data.get("quantity", 1)

        if not barcode:
            return JsonResponse(
                {"status": "error", "message": "Barcode is required"}, status=400
            )
        if not cart_id:
            return JsonResponse(
                {"status": "error", "message": "Cart ID is required"}, status=400
            )

        # Convert quantity to Decimal
        try:
            quantity = Decimal(str(quantity))
            if quantity <= 0:
                return JsonResponse(
                    {"status": "error", "message": "Quantity must be greater than 0"},
                    status=400,
                )
        except:
            return JsonResponse(
                {"status": "error", "message": "Invalid quantity"}, status=400
            )

        # Check for barcode mapping
        barcode_mapping = BarcodeMapping.objects.filter(barcode=barcode).first()
        if barcode_mapping:
            barcode = barcode_mapping.variant.barcode

        try:
            cart = Cart.objects.get(id=cart_id, status="OPEN")
            product_variant = ProductVariant.objects.get(
                barcode=barcode, status="ACTIVE"
            )

            # Check if item already exists in cart
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product_variant=product_variant,
                price=product_variant.final_price,
                defaults={"quantity": quantity},
            )

            if not created:
                action_type = "Update"
                cart_item.quantity += quantity
                cart_item.save()

            cart_item.refresh_from_db()

            # Build cart item data for response
            cart_item_data = {
                "id": cart_item.id,
                "quantity": float(cart_item.quantity),
                "price": float(cart_item.price),
                "amount": float(cart_item.amount_property),
                "discount_percentage": (
                    float(cart_item.discount_percentage)
                    if cart_item.discount_percentage
                    else 0
                ),
                "product_variant": {
                    "id": product_variant.id,
                    "barcode": product_variant.barcode,
                    "full_name": product_variant.full_name,
                    "mrp": float(product_variant.mrp),
                    "simple_name": product_variant.simple_name,
                    "purchase_price": float(product_variant.purchase_price),
                },
            }

            return JsonResponse(
                {
                    "status": "success",
                    "message": f"Product {product_variant.full_name} added to cart",
                    "cart_item": cart_item_data,
                    "cart_total": float(cart.total_amount),
                    "remaining_stock": float(product_variant.billing_stock),
                    "type": action_type,
                }
            )

        except Cart.DoesNotExist:
            logger.error(f"Cart not found or not open: {cart_id}")
            return JsonResponse(
                {"status": "error", "message": "Cart not found or not open"}, status=404
            )
        except ProductVariant.DoesNotExist:
            logger.error(f"Product not found or inactive: {barcode}")
            return JsonResponse(
                {"status": "error", "message": "Product not found or inactive"},
                status=404,
            )

    except json.JSONDecodeError:
        logger.error("Invalid JSON data")
        return JsonResponse(
            {"status": "error", "message": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        logger.error(f"Server error: {e}")
        return JsonResponse(
            {"status": "error", "message": "Server error occurred"}, status=500
        )


@require_http_methods(["PUT", "DELETE"])
def manage_cart_item(request, item_id):
    """Update or delete cart item"""
    try:
        cart_item = CartItem.objects.get(id=item_id)

        if request.method == "PUT":
            data = json.loads(request.body.decode("utf-8"))

            # Update quantity if provided
            if "quantity" in data:
                try:
                    quantity = Decimal(str(data["quantity"]))
                    if quantity <= 0:
                        return JsonResponse(
                            {
                                "status": "error",
                                "message": "Quantity must be greater than 0",
                            },
                            status=400,
                        )
                    cart_item.quantity = quantity
                except:
                    return JsonResponse(
                        {"status": "error", "message": "Invalid quantity"}, status=400
                    )

            # Update price if provided
            if "price" in data:
                try:
                    price = Decimal(str(data["price"]))
                    if price < 0:
                        return JsonResponse(
                            {"status": "error", "message": "Price cannot be negative"},
                            status=400,
                        )
                    cart_item.price = price
                except:
                    return JsonResponse(
                        {"status": "error", "message": "Invalid price"}, status=400
                    )

            cart_item.save()
            cart_item.refresh_from_db()

            cart_item_data = {
                "id": cart_item.id,
                "quantity": float(cart_item.quantity),
                "price": float(cart_item.price),
                "amount": float(cart_item.amount_property),
                "discount_percentage": (
                    float(cart_item.discount_percentage)
                    if cart_item.discount_percentage
                    else 0
                ),
            }

            return JsonResponse(
                {
                    "status": "success",
                    "message": "Cart item updated successfully",
                    "cart_item": cart_item_data,
                    "cart_total": float(cart_item.cart.total_amount),
                    "remaining_stock": float(cart_item.product_variant.billing_stock),
                }
            )

        elif request.method == "DELETE":
            cart = cart_item.cart
            cart_item.delete()
            return JsonResponse(
                {
                    "status": "success",
                    "message": "Cart item removed successfully",
                    "cart_total": float(cart.total_amount),
                }
            )

    except CartItem.DoesNotExist:
        logger.error(f"Cart item not found: {item_id}")
        return JsonResponse(
            {"status": "error", "message": "Cart item not found"}, status=404
        )
    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "message": "Invalid JSON data"}, status=400
        )
    except Exception as e:
        logger.error(f"Server error: {e}")
        return JsonResponse(
            {"status": "error", "message": f"Server error: {str(e)}"}, status=500
        )


@require_http_methods(["POST"])
def archive_cart(request, cart_id):
    """Archive a cart"""
    try:
        cart = Cart.objects.get(id=cart_id, status="OPEN")
        cart.status = "ARCHIVED"
        cart.save()
        return JsonResponse(
            {"status": "success", "message": "Cart archived successfully"}
        )

    except Cart.DoesNotExist:
        logger.error(f"Cart not found: {cart_id}")
        return JsonResponse(
            {"status": "error", "message": "Cart not found"}, status=404
        )


@require_http_methods(["POST"])
def clear_cart(request, cart_id):
    """Clear all items from a cart"""
    try:
        cart = Cart.objects.get(id=cart_id, status="OPEN")
        cart.cart_items.all().delete()
        return JsonResponse(
            {"status": "success", "message": "Cart cleared successfully"}
        )

    except Cart.DoesNotExist:
        logger.error(f"Cart not found: {cart_id}")
        return JsonResponse(
            {"status": "error", "message": "Cart not found"}, status=404
        )
