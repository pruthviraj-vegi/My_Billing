from datetime import datetime, date, timedelta
import time
from functools import wraps
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.loader import render_to_string


def get_financial_year(value):
    """
    Get financial year from a given date.
    Financial year is considered from April (4) to March (3).

    Args:
        value (str | datetime | date): Input date. If string,
                                       accepted formats include "YYYY-MM-DD",
                                       "DD/MM/YYYY", "DD-MM-YYYY".

    Returns:
        str: Financial year in format 'YYYY-YY' (e.g. '2024-25')

    Raises:
        ValueError: If the input cannot be parsed as a valid date.
    """

    # --- Step 1: Parse the input into a datetime.date object ---
    if isinstance(value, str):
        # Try common formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%b %d, %Y"):
            try:
                parsed_date = datetime.strptime(value, fmt).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"Unrecognized date format: {value}")
    elif isinstance(value, datetime):
        parsed_date = value.date()
    elif isinstance(value, date):
        parsed_date = value
    else:
        raise ValueError("Input must be a string, datetime, or date object")

    # --- Step 2: Calculate the financial year ---
    if parsed_date.month >= 4:  # April to Dec
        start_year = parsed_date.year
        end_year = parsed_date.year + 1
    else:  # Jan to March
        start_year = parsed_date.year - 1
        end_year = parsed_date.year

    return f"{str(start_year)[2:]}-{str(end_year)[2:]}"


class StringProcessor:
    """
    This class processes strings by cleaning them (removing spaces, slashes, question marks, and commas)
    and converting them to different cases. It also handles the case where None or an empty string is passed.
    """

    def __init__(self, input_string=None):
        """
        Initializes the StringProcessor object.

        Args:
            input_string (str, optional): The input string to be processed. Defaults to None.
        """
        if input_string is None:
            self.input_string = ""
            self.cleaned_string = ""
        else:
            self.input_string = input_string
            self.clean()

    def clean(self):
        """
        Cleans the input string by removing spaces, slashes, question marks, and commas.
        """
        cleaned_string = " ".join(self.input_string.split())
        cleaned_string = (
            cleaned_string.replace("/", "").replace("?", "").replace(",", "")
        )
        self.cleaned_string = cleaned_string.upper()

    def toUppercase(self):
        """
        Returns the cleaned string in uppercase.

        Returns:
            str: The cleaned string in uppercase.
        """
        return self.cleaned_string

    def toLowercase(self):
        """
        Returns the cleaned string in lowercase.

        Returns:
            str: The cleaned string in lowercase.
        """
        return self.cleaned_string.lower()

    def toTitle(self):
        """
        Returns the cleaned string in title case (first letter of each word capitalized).

        Returns:
            str: The cleaned string in title case.
        """
        return self.cleaned_string.title()

    def toCapitalize(self):
        """
        Returns the cleaned string with only the first letter capitalized.

        Returns:
            str: The cleaned string with the first letter capitalized.
        """
        return self.cleaned_string.capitalize()


def get_periodic_data(date_filter, current_start, current_end):
    """
    Return previous_start, previous_end, period_type for a given date filter.
    Uses the existing DatesManipulation class to avoid code duplication.
    """
    from base.getDates import DatesManipulation

    dates = DatesManipulation()

    # Map date filters to period types and get previous period dates
    period_map = {
        "today": ("daily", dates.yesterday_date),
        "yesterday": (
            "daily",
            (current_start - timedelta(days=1), current_end - timedelta(days=1)),
        ),
        "this_month": ("monthly", dates.last_month),
        "last_month": ("monthly", None),  # Need to calculate 2 months ago
        "this_quarter": ("quarterly", dates.last_quarter),
        "last_quarter": ("quarterly", None),  # Need to calculate 2 quarters ago
        "this_finance": ("yearly", dates.last_finance),
        "last_finance": ("yearly", None),  # Need to calculate 2 FY ago
    }

    if date_filter in period_map:
        period_type, previous_dates = period_map[date_filter]

        if previous_dates:
            previous_start, previous_end = previous_dates
            return (
                (
                    previous_start.date()
                    if hasattr(previous_start, "date")
                    else previous_start
                ),
                previous_end.date() if hasattr(previous_end, "date") else previous_end,
                period_type,
            )

    # Handle special cases that need calculation
    if date_filter == "last_month":
        # Get 2 months ago
        if current_start.month <= 2:
            previous_start = current_start.replace(
                year=current_start.year - 1,
                month=current_start.month + 10 if current_start.month == 2 else 11,
            )
        else:
            previous_start = current_start.replace(month=current_start.month - 2)

        # Calculate end of that month
        if previous_start.month == 12:
            next_month = previous_start.replace(year=previous_start.year + 1, month=1)
        else:
            next_month = previous_start.replace(month=previous_start.month + 1)
        previous_end = next_month - timedelta(days=1)

        return previous_start, previous_end, "monthly"

    elif date_filter == "last_quarter":
        # Get 2 quarters ago (6 months back)
        from base.getDates import quarter_start_end

        last_month = current_start.month - 6
        year = current_start.year
        if last_month <= 0:
            last_month += 12
            year -= 1
        previous_start, previous_end = quarter_start_end(year, last_month)
        return (
            (
                previous_start.date()
                if hasattr(previous_start, "date")
                else previous_start
            ),
            previous_end.date() if hasattr(previous_end, "date") else previous_end,
            "quarterly",
        )

    elif date_filter == "last_finance":
        # Get 2 financial years ago
        if current_start.month >= 4:
            previous_start = current_start.replace(
                year=current_start.year - 2, month=4, day=1
            )
            previous_end = current_start.replace(
                year=current_start.year - 1, month=3, day=31
            )
        else:
            previous_start = current_start.replace(
                year=current_start.year - 3, month=4, day=1
            )
            previous_end = current_start.replace(
                year=current_start.year - 2, month=3, day=31
            )
        return previous_start, previous_end, "yearly"

    # Default: monthly (same as "this_month" case)
    previous_start, previous_end = dates.last_month
    return (
        previous_start.date() if hasattr(previous_start, "date") else previous_start,
        previous_end.date() if hasattr(previous_end, "date") else previous_end,
        "monthly",
    )


def get_period_label(start_date, end_date, period_type):
    if period_type == "daily":
        return start_date.strftime("%B %d, %Y")
    elif period_type == "monthly":
        return f"{start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}"
    elif period_type == "quarterly":
        return f"Q{((start_date.month - 1) // 3) + 1} {start_date.year}"
    else:  # yearly
        return f"FY {start_date.year}-{end_date.year}"


def timed(fn):
    """
    Decorator to measure execution time of a function.
    Stores the last execution time in `fn._last_elapsed_time`.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - start

        print(f"Time taken: {elapsed} seconds")

        # Store timing on the function itself
        wrapper._last_elapsed_time = elapsed
        return result

    wrapper._last_elapsed_time = None  # init attribute
    return wrapper


def render_paginated_response(
    request,
    queryset,
    table_template,
    per_page=20,
    pagination_template="common/_pagination.html",
    **kwargs,
):
    """
    Reusable pagination + HTML rendering helper for HTMX/AJAX.

    Args:
        request: Django request object
        queryset: List/QuerySet to paginate
        table_template: Path to table HTML template
        per_page: Number of items per page
        pagination_template: Path to pagination template (optional)
        **kwargs: Additional context variables to pass to template

    Returns:
        JsonResponse with HTML table + pagination
    """
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "total_count": paginator.count,
    }
    # Merge additional context from kwargs
    context.update(kwargs)

    # Render table
    table_html = render_to_string(table_template, context, request=request)

    # Render pagination if needed
    pagination_html = ""
    if page_obj and page_obj.paginator.num_pages > 1:
        pagination_html = render_to_string(
            pagination_template, context, request=request
        )

    return JsonResponse(
        {
            "html": table_html,
            "pagination": pagination_html,
            "success": True,
        }
    )
