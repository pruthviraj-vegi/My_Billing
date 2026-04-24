"""
Views for handling cart creation, updates, and checkout processes.

This module provides the necessary views and APIs to manage user shopping carts,
including adding items via barcode, manually updating quantities, and clearing
cart contents.
"""

import json
import logging
from decimal import Decimal, InvalidOperation
from django.db.models import Q

from django.contrib import messages
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, TemplateView, UpdateView

from base.decorators import required_permission, RequiredPermissionMixin

from inventory.models import BarcodeMapping, ProductVariant

from .forms import CartForm
from .models import Cart, CartItem

logger = logging.getLogger(__name__)


class CartMainPageView(RequiredPermissionMixin, TemplateView):
    """Template view to render the main cart management page"""

    template_name = "cart/main_page.html"
    required_permission = "cart.view_cart"

    def get_context_data(self, **kwargs):
        """
        Add open carts to template context with optimized queries.

        Retrieves all carts with 'OPEN' status and prepopulates creator
        and associated items through select_related and prefetch_related
        to eliminate N+1 query redundancy.
        """
        context = super().get_context_data(**kwargs)
        # Use select_related to avoid N+1 queries
        context["carts"] = (
            Cart.objects.filter(status="OPEN", created_by=self.request.user)
            .select_related("created_by")
            .prefetch_related("cart_items__product_variant__product")
            .order_by("-created_at")
        )
        return context


@required_permission("cart.view_cart")
def get_cart_data(request, pk):
    """
    Retrieve and display data for a specific cart along with other open carts.

    Fetches the cart items with related product variant data. Calculates the
    total selling price for the cart items and renders the main cart management
    page template with the acquired context data.
    """
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

        carts = Cart.objects.filter(status="OPEN", created_by=request.user).order_by(
            "-created_at"
        )

        # Calculate total selling price (sum of all items' MRP * quantity)
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
        logger.error("Cart not found: %s", e)
        return redirect("cart:main_page")

    return render(request, template_name, context)


class CreateCart(RequiredPermissionMixin, CreateView):
    """
    View for creating a new Cart instance.

    Provides a form for users to create carts and automatically assigns the
    created cart to the currently authenticated user making the request.
    """

    model = Cart
    template_name = "cart/form.html"
    form_class = CartForm
    required_permission = "cart.add_cart"

    def get_context_data(self, **kwargs):
        """
        Populate the context dictionary with the necessary page title.

        Args:
            **kwargs: Arbitrary keyword arguments extending context data.

        Returns:
            dict: The context dictionary containing "title": "Create Cart".
        """
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Cart"
        return context

    def form_valid(self, form):
        """
        Handle valid form submissions by dictating cart creator assigning.

        Args:
            form (CartForm): The successfully validated form instance.

        Returns:
            HttpResponseRedirect: Overridden form validation response routing.
        """
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        """
        Resolve the target URL to redirect towards post successful cart creation.

        Returns:
            str: Resolved URL string navigating to cart management data page.
        """
        return reverse("cart:get_cart_data", kwargs={"pk": self.object.id})


class EditCart(RequiredPermissionMixin, UpdateView):
    """
    View for editing an existing Cart instance.

    Allows users to update the details of a cart using the provided CartForm.
    """

    model = Cart
    template_name = "cart/form.html"
    form_class = CartForm
    required_permission = "cart.change_cart"

    def get_context_data(self, **kwargs):
        """
        Populate the view context dict comprising the cart targeted for editing.

        Args:
            **kwargs: Arbitrary keyword arguments to populate data.

        Returns:
            dict: Render context loaded with the object map corresponding to cart.
        """
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Cart"
        context["cart"] = self.get_object()
        return context

    def get_success_url(self):
        """
        Compute target post-editing URL to direct users toward their cart listing.

        Returns:
            str: Routing path bridging user straight into cart view endpoints.
        """
        return reverse("cart:get_cart_data", kwargs={"pk": self.object.id})


@required_permission("cart.view_cart")
def auto_cart_create(request):
    """
    Automatically create a new cart or redirect to an existing empty open cart.

    Checks the user's open carts and redirects to the first empty one found.
    If none are empty, it creates a new "Walk in" cart and redirects to it.
    """

    carts = Cart.objects.filter(status="OPEN", created_by=request.user).order_by(
        "-created_at"
    )

    for cart in carts:
        if cart.get_item_count() == 0:
            messages.success(request, "Open cart existed, redirecting to it")
            return redirect("cart:get_cart_data", pk=cart.id)

    cart = Cart.objects.create(name="Walk in", created_by=request.user)
    messages.success(request, "Cart created successfully")
    return redirect("cart:get_cart_data", pk=cart.id)


def barcode_suggestions(request):
    """
    Return JSON list of product variants matching the query string.
    Used for live barcode suggestion dropdown in cart page.
    """
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse([], safe=False)

    filters = Q()
    for term in q.split():
        filters &= (
            Q(barcode__icontains=term)
            | Q(product__name__icontains=term)
            | Q(product__brand__icontains=term)
            | Q(product__description__icontains=term)
            | Q(product__category__name__icontains=term)
            | Q(color__name__icontains=term)
            | Q(size__name__icontains=term)
            | Q(mrp__icontains=term)
        )

    results = (
        ProductVariant.objects.filter(filters)
        .select_related("product", "product__category", "color", "size")
        .values(
            "barcode",
            "product__name",
            "product__brand",
            "color__name",
            "size__name",
            "mrp",
        )[:10]
    )

    data = [
        {
            "barcode": r["barcode"],
            "product": r["product__name"],
            "brand": r["product__brand"] or "",
            "color": r["color__name"] or "",
            "size": r["size__name"] or "",
            "mrp": str(r["mrp"]),
        }
        for r in results
    ]
    return JsonResponse(data, safe=False)


# API Views for Cart Operations


@required_permission("cart.add_cartitem")
@require_http_methods(["POST"])
def scan_barcode(request):
    """
    Scan a barcode and add the corresponding product variant to the cart.

    Accepts JSON containing a barcode, cart ID, and optional quantity. Checks
    alternative barcode mappings, fetches the variant, updates cart item quantities,
    and returns a JSON response with the updated cart totals and product details.
    """
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
        except (ValueError, TypeError, InvalidOperation):
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
                    "product_name": product_variant.product.brand,
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
            logger.error("Cart not found or not open: %s", cart_id)
            return JsonResponse(
                {"status": "error", "message": "Cart not found or not open"}, status=404
            )
        except ProductVariant.DoesNotExist:
            logger.error("Product not found or inactive: %s", barcode)
            return JsonResponse(
                {"status": "error", "message": "Product not found or inactive"},
                status=404,
            )

    except json.JSONDecodeError:
        logger.error("Invalid JSON data")
        return JsonResponse(
            {"status": "error", "message": "Invalid JSON data"}, status=400
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Server error: %s", e)
        return JsonResponse(
            {"status": "error", "message": "Server error occurred"}, status=500
        )


@require_http_methods(["PUT", "DELETE"])
def manage_cart_item(request, item_id):
    """
    Update the quantity or price of a cart item, or remove it completely.

    Handles PUT requests to update an item's quantity or price, returning
    the new totals. Handles DELETE requests to remove the item from its cart.
    """
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
                except (ValueError, TypeError, InvalidOperation):
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
                except (ValueError, TypeError, InvalidOperation):
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
        logger.error("Cart item not found: %s", item_id)
        return JsonResponse(
            {"status": "error", "message": "Cart item not found"}, status=404
        )
    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "message": "Invalid JSON data"}, status=400
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Server error: %s", e)
        return JsonResponse(
            {"status": "error", "message": f"Server error: {str(e)}"}, status=500
        )


@required_permission("cart.change_cart")
@require_http_methods(["POST"])
def archive_cart(request, cart_id):
    """
    Archive a specific open cart.

    Changes the status of an open cart to 'ARCHIVED' so it no longer appears in
    the active cart lists. Allows cart state preservation for owners.
    """
    try:
        cart = Cart.objects.get(id=cart_id, status="OPEN")
        cart.status = "ARCHIVED"
        cart.save()
        return JsonResponse(
            {"status": "success", "message": "Cart archived successfully"}
        )

    except Cart.DoesNotExist:
        logger.error("Cart not found: %s", cart_id)
        return JsonResponse(
            {"status": "error", "message": "Cart not found"}, status=404
        )


@required_permission("cart.delete_cartitem")
@require_http_methods(["POST"])
def clear_cart(request, cart_id):
    """
    Clear all items from a given open cart.

    Removes all associated cart items while keeping the cart object intact.
    Useful for resetting a cart without having to create a new one.
    """
    try:
        cart = Cart.objects.get(id=cart_id, status="OPEN")
        cart.cart_items.all().delete()
        return JsonResponse(
            {"status": "success", "message": "Cart cleared successfully"}
        )

    except Cart.DoesNotExist:
        logger.error("Cart not found: %s", cart_id)
        return JsonResponse(
            {"status": "error", "message": "Cart not found"}, status=404
        )
