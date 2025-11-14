import re, json, os
from django.core.cache import cache
from django.conf import settings
from fuzzywuzzy import process
from django.http import JsonResponse
from customer.models import Customer
from invoice.models import Invoice
from inventory.models import Product, ProductVariant
from rapidfuzz import process
from supplier.models import Supplier


# Precompiled regex for speed
TOKENIZER = re.compile(r"[a-zA-Z0-9]+")


def get_related_words(query, list_of_words, limit=10, score_cutoff=60):
    """
    Returns top fuzzy-matched words for a query.
    - Uses rapidfuzz for speed.
    - Avoids redundant deduplication.
    - Limits results early for efficiency.
    """

    if not query or len(query) < 2 or not list_of_words:
        return []

    # rapidfuzz can handle iterables directly (no need to force list)
    matches = process.extract(
        query.lower(), list_of_words, limit=limit, score_cutoff=score_cutoff
    )

    # Extract only words (discard scores)
    return [word for word, score, _ in matches]


def get_search_words(
    query,
    model,
    fields,
    cache_key,
    cache_timeout=3600,
    max_words=50000,
):
    """
    Optimized helper to build/search word lists from model fields.
    - Uses cache to avoid rebuilding.
    - Minimizes memory overhead by streaming.
    - Tokenizes with set comprehension instead of nested loops.
    - Limits max_words to avoid huge cache payloads.
    """

    # 1. Try cache first
    searchable_items = cache.get(cache_key)
    if searchable_items is not None:
        return get_related_words(query, searchable_items)

    # 2. Stream from DB efficiently (iterator avoids full memory load)
    queryset = model.objects.values_list(*fields).iterator()

    all_words = set()
    for row in queryset:
        # Flatten row → tokenize in one go
        tokens = {
            token
            for field in row
            if field
            for token in TOKENIZER.findall(str(field).lower())
            if len(token) > 2
        }
        all_words.update(tokens)

        # Optional: early cutoff if dataset is massive
        if len(all_words) >= max_words:
            break

    # 3. Convert to list once
    searchable_items = list(all_words)

    # 4. Save in cache
    cache.set(cache_key, searchable_items, cache_timeout)

    # 5. Get suggestions
    return get_related_words(query, searchable_items)


def customer_all_suggestions(request):
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"success": True, "data": []})

    suggestions = get_search_words(
        query=query,
        model=Customer,
        fields=("name", "phone_number", "email", "address"),
        cache_key="customer_search_words",
        cache_timeout=3600,
    )

    return JsonResponse({"success": True, "data": suggestions})


def invoice_all_suggestions(request):
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"success": True, "data": []})

    suggestions = get_search_words(
        query=query,
        model=Invoice,
        fields=("invoice_number", "customer__name", "customer__phone_number", "notes"),
        cache_key="invoice_search_words",
        cache_timeout=3600,
    )

    return JsonResponse({"success": True, "data": suggestions})


def product_all_suggestions(request):

    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"success": True, "data": []})

    suggestions = get_search_words(
        query=query,
        model=Product,
        fields=("brand", "name", "category__name"),
        cache_key="product_search_words",
        cache_timeout=3600,
    )

    return JsonResponse({"success": True, "data": suggestions})


def product_variant_all_suggestions(request):
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"success": True, "data": []})

    suggestions = get_search_words(
        query=query,
        model=ProductVariant,
        fields=(
            "barcode",
            "product__name",
            "product__brand",
            "product__category__name",
        ),
        cache_key="product_variant_search_words",
        cache_timeout=3600,
    )

    return JsonResponse({"success": True, "data": suggestions})


def supplier_all_suggestions(request):
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"success": True, "data": []})

    suggestions = get_search_words(
        query=query,
        model=Supplier,
        fields=(
            "name",
            "phone",
            "email",
            "gstin",
            "first_line",
            "second_line",
            "city",
            "state",
            "pincode",
            "country",
        ),
        cache_key="supplier_search_words",
        cache_timeout=3600,
    )

    return JsonResponse({"success": True, "data": suggestions})
