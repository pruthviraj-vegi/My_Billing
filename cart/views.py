from email import message
from django.shortcuts import render, redirect
from .models import Cart, CartItem
from .forms import CartForm
from django.contrib import messages
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    BarcodeScanSerializer,
    CartItemUpdateSerializer,
)
from inventory.models import ProductVariant
from django.views.generic import CreateView, UpdateView
from django.urls import reverse

# Template view for the main cart page
from django.views.generic import TemplateView
import logging, json

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


# API Views for Cart Operations
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def scan_barcode(request):
    """Scan barcode and add product to cart"""
    type = "Create"
    try:
        # Handle both JSON and form data
        if request.content_type == "application/json":
            data = request.data
        else:
            # Parse JSON from request body if needed
            data = json.loads(request.body.decode("utf-8"))

        serializer = BarcodeScanSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {
                    "status": "error",
                    "message": "Invalid data",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        barcode = serializer.validated_data["barcode"]
        cart_id = serializer.validated_data["cart_id"]
        quantity = serializer.validated_data["quantity"]

        try:
            cart = Cart.objects.get(id=cart_id, status="OPEN")
            product_variant = ProductVariant.objects.get(
                barcode=barcode, status="ACTIVE"
            )

            # Check if item already exists in cart
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product_variant=product_variant,
                defaults={"quantity": quantity, "price": product_variant.final_price},
            )

            if not created:
                # Update quantity if item already exists
                type = "Update"
                cart_item.quantity += quantity
                cart_item.save()

            # Refresh the cart item to get updated data
            cart_item.refresh_from_db()

            # Ensure related data is loaded
            cart_item.product_variant.refresh_from_db()
            if hasattr(cart_item.product_variant, "product"):
                cart_item.product_variant.product.refresh_from_db()

            # Serialize the cart item for response
            item_serializer = CartItemSerializer(cart_item)

            return Response(
                {
                    "status": "success",
                    "message": f"Product {product_variant.full_name} added to cart",
                    "cart_item": item_serializer.data,
                    "cart_total": cart.total_amount,
                    "type": type,
                },
                status=status.HTTP_200_OK,
            )

        except Cart.DoesNotExist as e:
            logger.error(f"Cart not found or not open: {e}")
            return Response(
                {"status": "error", "message": "Cart not found or not open"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ProductVariant.DoesNotExist as e:
            logger.error(f"Product not found or inactive: {e}")
            return Response(
                {"status": "error", "message": "Product not found or inactive"},
                status=status.HTTP_404_NOT_FOUND,
            )

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON data: {e}")
        return Response(
            {"status": "error", "message": "Invalid JSON data"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.error(f"Server error: {e}")
        return Response(
            {"status": "error", "message": "Server error occurred"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_cart(request):
    """Create a new cart"""
    cart_name = request.data.get("name", f"Cart {Cart.objects.count() + 1}")

    cart = Cart.objects.create(name=cart_name, created_by=request.user)

    serializer = CartSerializer(cart)
    return Response(
        {
            "status": "success",
            "message": "Cart created successfully",
            "cart": serializer.data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def manage_cart_item(request, item_id):
    """Update or delete cart item"""
    try:
        cart_item = CartItem.objects.get(id=item_id)

        if request.method == "PUT":
            serializer = CartItemUpdateSerializer(
                cart_item, data=request.data, partial=True
            )
            if serializer.is_valid():
                # Update the item
                serializer.save()

                # Refresh the cart_item to get updated data
                cart_item.refresh_from_db()

                return Response(
                    {
                        "status": "success",
                        "message": "Cart item updated successfully",
                        "cart_item": CartItemSerializer(cart_item).data,
                        "cart_total": cart_item.cart.total_amount,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {
                        "status": "error",
                        "message": "Invalid data",
                        "errors": serializer.errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        elif request.method == "DELETE":
            cart = cart_item.cart
            cart_item.delete()
            return Response(
                {
                    "status": "success",
                    "message": "Cart item removed successfully",
                    "cart_total": cart.total_amount,
                },
                status=status.HTTP_200_OK,
            )

    except CartItem.DoesNotExist as e:
        logger.error(f"Cart item not found: {e}")
        return Response(
            {"status": "error", "message": "Cart item not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Server error: {e}")
        return Response(
            {"status": "error", "message": f"Server error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def archive_cart(request, cart_id):
    """Archive a cart"""
    try:
        cart = Cart.objects.get(id=cart_id, status="OPEN")
        cart.status = "ARCHIVED"
        cart.save()

        return Response(
            {"status": "success", "message": "Cart archived successfully"},
            status=status.HTTP_200_OK,
        )

    except Cart.DoesNotExist as e:
        logger.error(f"Cart not found: {e}")
        return Response(
            {"status": "error", "message": "Cart not found"},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def clear_cart(request, cart_id):
    """Clear all items from a cart"""
    try:
        cart = Cart.objects.get(id=cart_id, status="OPEN")
        cart.cart_items.all().delete()

        return Response(
            {"status": "success", "message": "Cart cleared successfully"},
            status=status.HTTP_200_OK,
        )

    except Cart.DoesNotExist as e:
        logger.error(f"Cart not found: {e}")
        return Response(
            {"status": "error", "message": "Cart not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
