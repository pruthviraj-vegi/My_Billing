import re
import logging
from django.core.cache import cache
from django.core.cache.backends.base import InvalidCacheBackendError
from django.http import JsonResponse
from customer.models import Customer
from invoice.models import Invoice
from inventory.models import Product, ProductVariant
from rapidfuzz import process, fuzz
from supplier.models import Supplier

logger = logging.getLogger(__name__)


# Precompiled regex for speed
TOKENIZER = re.compile(r"[a-zA-Z0-9]+")

CUSTOMER_SEARCH_FIELDS = ("name", "phone_number", "email", "address")
INVOICE_SEARCH_FIELDS = (
    "invoice_number",
    "customer__name",
    "customer__phone_number",
    "notes",
)
PRODUCT_SEARCH_FIELDS = ("brand", "name", "category__name")
PRODUCT_VARIANT_SEARCH_FIELDS = (
    "barcode",
    "product__name",
    "product__brand",
    "product__category__name",
)
SUPPLIER_SEARCH_FIELDS = (
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
)


def get_instance_tokens(instance, fields):
    """
    Helper to extract tokens from a single model instance.
    Used by signals to check if cache invalidation is actually needed.
    """
    tokens = set()
    for field_path in fields:
        # Handle related fields (e.g., 'customer__name')
        value = instance
        parts = field_path.split("__")
        try:
            for part in parts:
                if value is None:
                    break
                value = getattr(value, part)
        except AttributeError:
            continue  # Field might not exist or be accessible

        if value:
            # Tokenize
            found = TOKENIZER.findall(str(value).lower())
            tokens.update(t for t in found if len(t) > 2)
    return tokens


def invalidate_cache(cache_key):
    """
    Clears the specific cache key.
    Used by signals to invalidate cache on model changes.
    """
    try:
        cache.delete(cache_key)
        logger.info(f"Cache invalidated for key: {cache_key}")
    except Exception as e:
        logger.error(f"Failed to invalidate cache for key {cache_key}: {e}")


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
        query.lower(),
        list_of_words,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=score_cutoff,
    )

    # Extract only words (discard scores)
    return [word for word, score, _ in matches]


def get_search_words(
    query,
    model,
    fields,
    cache_key,
    cache_timeout=None,
    max_words=50000,
):
    """
    Optimized helper to build/search word lists from model fields.
    - Uses Redis/DB cache to avoid rebuilding.
    - Minimizes memory overhead by streaming.
    - Tokenizes with set comprehension instead of nested loops.
    - Limits max_words to avoid huge cache payloads.
    - Handles cache connection errors gracefully.
    """

    # 1. Try cache first (Redis-compatible)
    try:
        searchable_items = cache.get(cache_key)
        if searchable_items is not None:
            return get_related_words(query, searchable_items)
    except (InvalidCacheBackendError, Exception) as e:
        # Redis might be down or misconfigured - log and continue without cache
        logger.warning(
            f"Cache read failed for key '{cache_key}': {e}. Proceeding without cache."
        )

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

    # 4. Save in cache (Redis-compatible - Django handles serialization)
    try:
        cache.set(cache_key, searchable_items, cache_timeout)
    except (InvalidCacheBackendError, Exception) as e:
        # Redis might be down - log but don't fail the request
        logger.warning(
            f"Cache write failed for key '{cache_key}': {e}. Results returned without caching."
        )

    # 5. Get suggestions
    return get_related_words(query, searchable_items)


def customer_all_suggestions(request):
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"success": True, "data": []})

    suggestions = get_search_words(
        query=query,
        model=Customer,
        fields=CUSTOMER_SEARCH_FIELDS,
        cache_key="customer_search_words",
    )

    return JsonResponse({"success": True, "data": suggestions})


def invoice_all_suggestions(request):
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"success": True, "data": []})

    suggestions = get_search_words(
        query=query,
        model=Invoice,
        fields=INVOICE_SEARCH_FIELDS,
        cache_key="invoice_search_words",
    )

    return JsonResponse({"success": True, "data": suggestions})


def product_all_suggestions(request):

    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"success": True, "data": []})

    suggestions = get_search_words(
        query=query,
        model=Product,
        fields=PRODUCT_SEARCH_FIELDS,
        cache_key="product_search_words",
    )

    return JsonResponse({"success": True, "data": suggestions})


def product_variant_all_suggestions(request):
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"success": True, "data": []})

    suggestions = get_search_words(
        query=query,
        model=ProductVariant,
        fields=PRODUCT_VARIANT_SEARCH_FIELDS,
        cache_key="product_variant_search_words",
    )

    return JsonResponse({"success": True, "data": suggestions})


def supplier_all_suggestions(request):
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"success": True, "data": []})

    suggestions = get_search_words(
        query=query,
        model=Supplier,
        fields=SUPPLIER_SEARCH_FIELDS,
        cache_key="supplier_search_words",
    )

    return JsonResponse({"success": True, "data": suggestions})
