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
    """Return previous_start, previous_end, period_type for a given date filter."""

    # ---------------- DAILY ----------------
    if date_filter in ["today", "yesterday"]:
        return (
            current_start - timedelta(days=1),
            current_end - timedelta(days=1),
            "daily",
        )

    # ---------------- MONTHLY ----------------
    if date_filter in ["this_month", "last_month"]:
        if current_start.month == 1:
            previous_start = current_start.replace(
                year=current_start.year - 1, month=12
            )
        else:
            previous_start = current_start.replace(month=current_start.month - 1)

        # Next month of previous_start
        if previous_start.month == 12:
            next_month = previous_start.replace(year=previous_start.year + 1, month=1)
        else:
            next_month = previous_start.replace(month=previous_start.month + 1)

        previous_end = next_month - timedelta(days=1)

        return previous_start, previous_end, "monthly"

    # ---------------- QUARTERLY ----------------
    if date_filter in ["this_quarter", "last_quarter"]:
        quarter_start_month = ((current_start.month - 1) // 3) * 3 + 1
        current_q_start = current_start.replace(month=quarter_start_month, day=1)

        # Determine previous quarter start
        if quarter_start_month == 1:
            prev_start = current_q_start.replace(
                year=current_q_start.year - 1, month=10
            )
        else:
            prev_start = current_q_start.replace(month=quarter_start_month - 3)

        # Determine previous quarter end
        prev_end = prev_start.replace(month=prev_start.month + 3, day=1) - timedelta(
            days=1
        )

        return prev_start, prev_end, "quarterly"

    # ---------------- FINANCIAL YEAR ----------------
    if date_filter in ["this_finance", "last_finance"]:
        if current_start.month >= 4:  # FY: Apr 1 – Mar 31
            previous_start = current_start.replace(
                year=current_start.year - 1, month=4, day=1
            )
            previous_end = current_start.replace(
                year=current_start.year, month=3, day=31
            )
        else:
            previous_start = current_start.replace(
                year=current_start.year - 2, month=4, day=1
            )
            previous_end = current_start.replace(
                year=current_start.year - 1, month=3, day=31
            )

        return previous_start, previous_end, "yearly"

    # ---------------- DEFAULT: MONTHLY ----------------
    if current_start.month == 1:
        previous_start = current_start.replace(year=current_start.year - 1, month=12)
    else:
        previous_start = current_start.replace(month=current_start.month - 1)

    if previous_start.month == 12:
        next_month = previous_start.replace(year=previous_start.year + 1, month=1)
    else:
        next_month = previous_start.replace(month=previous_start.month + 1)

    previous_end = next_month - timedelta(days=1)

    return previous_start, previous_end, "monthly"


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
