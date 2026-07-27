"""
Dashboard JSON response builder utility.
"""

from django.http import JsonResponse


def build_dashboard_response(stats: dict, comparison_data: dict, date_range: dict, breakdown: list = None) -> JsonResponse:
    """
    Constructs a standardized JSON response for dashboard fetch endpoints.

    Args:
        stats: Aggregated statistics dict
        comparison_data: Current vs previous period comparison data
        date_range: Date range info dict
        breakdown: Optional list of category/status breakdown dicts

    Returns:
        JsonResponse containing standard payload schema
    """
    payload = {
        "success": True,
        "stats": stats,
        "comparison_data": comparison_data,
        "date_range": date_range,
        "breakdown": breakdown or [],
    }
    return JsonResponse(payload)
