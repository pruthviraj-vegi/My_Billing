"""
Custom template filters for formatting currency, dates, and other utilities.
"""

import base64
import locale
import logging
from datetime import datetime, timedelta

from django import template
from django.conf import settings
from num2words import num2words

logger = logging.getLogger(__name__)

locale.setlocale(locale.LC_ALL, "en_IN")

register = template.Library()

formate = {
    "grouping": True,  # Enable thousands grouping
    "grouping_threshold": 3,  # Group digits in threes
    "decimal_point": ".",  # Use dot as the decimal separator
    "frac_digits": 2,  # Show 2 digits after the decimal point
}


def _convert_to_numeric(value):
    """
    Bulletproof string-to-number converter that handles various input formats.

    Args:
        value: String, int, float, or other value to convert

    Returns:
        float or int: Converted numeric value, or None if conversion fails
    """
    if value is None:
        return None

    # If already a number, return as-is
    if isinstance(value, (int, float)):
        return value

    # Convert to string and clean
    str_value = str(value).strip()

    if not str_value:
        return None

    # Handle empty string
    if str_value == "":
        return None

    # Remove common currency symbols and whitespace
    cleaned_value = (
        str_value.replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace(",", "")
        .strip()
    )

    # Handle negative numbers
    is_negative = cleaned_value.startswith("-")
    if is_negative:
        cleaned_value = cleaned_value[1:]

    # Handle percentage
    is_percentage = cleaned_value.endswith("%")
    if is_percentage:
        cleaned_value = cleaned_value[:-1]

    try:
        # Try to convert to float first (handles decimals)
        numeric_value = float(cleaned_value)

        # Apply percentage conversion if needed
        if is_percentage:
            numeric_value = numeric_value / 100

        # Apply negative sign if needed
        if is_negative:
            numeric_value = -numeric_value

        # Return as int if it's a whole number and not too large
        if numeric_value.is_integer() and abs(numeric_value) < 1e15:
            return int(numeric_value)

        return numeric_value

    except (ValueError, OverflowError) as e:
        logger.warning("Failed to convert '%s' to numeric: %s", value, e)
        return None


@register.filter(name="currency")
def currency(value, _arg=None):
    """
    Bulletproof currency formatter that handles strings, integers, floats, and None values.
    Converts string inputs to appropriate numeric types before formatting.
    """
    try:
        if value is None or value == "":
            return "0.00"

        # Convert string to number if needed
        numeric_value = _convert_to_numeric(value)

        if numeric_value is None:
            logger.warning("Could not convert value '%s' to numeric format", value)
            return "0.00"

        data = locale.format_string(
            f"%%.{formate['frac_digits']}f",
            numeric_value,
            grouping=formate["grouping"],
            monetary=False,
        )
        return data
    except (TypeError, ValueError, locale.Error) as e:
        logger.error("Currency formatting error for value '%s': %s", value, e)
        return "0.00"


@register.filter(name="currency_nonDecimal")
def currency_non_decimal(value, _arg=None):
    """
    Bulletproof non-decimal currency formatter for integer values.
    """
    try:
        if value is None or value == "":
            return "0"

        # Convert string to number if needed
        numeric_value = _convert_to_numeric(value)

        if numeric_value is None:
            logger.warning("Could not convert value '%s' to numeric format", value)
            return "0"

        # Convert to integer
        value_int = int(numeric_value)

        return locale.format_string(
            "%d",
            value_int,
            grouping=formate["grouping"],
            monetary=False,
        )
    except (TypeError, ValueError, locale.Error) as e:
        logger.error(
            "Currency non-decimal formatting error for value '%s': %s", value, e
        )
        return "0"


@register.filter(name="currency_abbreviation")
def currency_abbreviation(value):
    """
    Bulletproof currency abbreviation formatter that handles strings and various input formats.

    Examples:
    1000 -> 1k
    100000 -> 100,000.00 (or localized equivalent)
    1234567 -> 1.23M
    """
    try:
        if value is None or value == "":
            return "0.00"

        # Convert string to number if needed
        numeric_value = _convert_to_numeric(value)

        if numeric_value is None:
            logger.warning("Could not convert value '%s' to numeric format", value)
            return "0.00"

        # Check for 'k', 'M', 'B' abbreviations
        if numeric_value >= 1_000_000_000:
            return f"{numeric_value / 1_000_000_000:.2f}B"
        elif numeric_value >= 1_000_000:
            return f"{numeric_value / 1_000_000:.2f}M"
        elif numeric_value >= 1000:
            return f"{numeric_value / 1000:.1f}k"

        # Set locale for international formatting (e.g., thousands separators)
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            # Fallback if the system's default locale isn't set
            locale.setlocale(locale.LC_ALL, "en_US.UTF-8")

        # Use locale.format_string for international formatting
        return locale.format_string("%.2f", numeric_value, grouping=True)

    except (TypeError, ValueError, locale.Error) as e:
        logger.error(
            "Currency abbreviation formatting error for value '%s': %s", value, e
        )
        return "0.00"


@register.filter(name="currencyToWord")
def currency_to_word(value, _arg=None):
    """Convert currency value to Indian Rupess text format."""
    try:
        amount = float(value)
        return num2words(amount, lang="en_IN", to="currency", currency="INR").title()
    except (ValueError, TypeError) as e:
        logger.error("Currency to word formatting error for value '%s': %s", value, e)
        return value


@register.filter(name="phone_number")
def phone_number(value):
    """Format a 10-digit phone number with a space in the middle."""
    if value is None:
        return ""
    try:
        numbers = value.replace(" ", "")
        return f"{numbers[:5]} {numbers[5:]}" if len(numbers) == 10 else numbers
    except (TypeError, ValueError) as e:
        logger.error(e)
        return value


@register.filter(name="b64encode")
def base64_encode(value):
    """Encode a string or bytes using base64 and return a UTF-8 string."""
    return base64.b64encode(value).decode("utf-8")


@register.filter(name="sub")
def sub(value, arg):
    """Bulletproof subtraction filter that handles strings and various input formats."""
    try:
        numeric_value = _convert_to_numeric(value)
        numeric_arg = _convert_to_numeric(arg)

        if numeric_value is None or numeric_arg is None:
            logger.warning(
                "Could not convert values '%s' or '%s' to numeric format", value, arg
            )
            return 0

        return numeric_value - numeric_arg
    except (TypeError, ValueError) as e:
        logger.error("Subtraction error for values '%s' and '%s': %s", value, arg, e)
        return 0


@register.filter(name="div")
def div(value, arg):
    """Bulletproof division filter that handles strings and various input formats."""
    try:
        numeric_value = _convert_to_numeric(value)
        numeric_arg = _convert_to_numeric(arg)

        if numeric_value is None or numeric_arg is None:
            logger.warning(
                "Could not convert values '%s' or '%s' to numeric format", value, arg
            )
            return 0

        if numeric_arg == 0:
            logger.warning(
                "Division by zero attempted with values '%s' and '%s'", value, arg
            )
            return 0

        return numeric_value / numeric_arg
    except (TypeError, ValueError, ZeroDivisionError) as e:
        logger.error("Division error for values '%s' and '%s': %s", value, arg, e)
        return 0


@register.filter(name="mul")
def mul(value, arg):
    """Bulletproof multiplication filter that handles strings and various input formats."""
    try:
        numeric_value = _convert_to_numeric(value)
        numeric_arg = _convert_to_numeric(arg)

        if numeric_value is None or numeric_arg is None:
            logger.warning(
                "Could not convert values '%s' or '%s' to numeric format", value, arg
            )
            return 0

        return numeric_value * numeric_arg
    except (TypeError, ValueError) as e:
        logger.error("Multiplication error for values '%s' and '%s': %s", value, arg, e)
        return 0


@register.filter(name="status_badge")
def status_badge(value):
    """Return a bootstrap badge color class based on status string value."""
    if str(value).lower() in ["active", "success", "true", "accepted"]:
        return "badge bg-success"
    elif str(value).lower() in ["inactive", "error", "danger", "false", "rejected"]:
        return "badge bg-danger"
    elif str(value).lower() in ["pending", "warning"]:
        return "badge bg-warning"
    else:
        return "badge bg-secondary"


@register.filter(name="add_class")
def add_class(field, css_class):
    """
    Add a CSS class to a form field
    Usage: {{ form.field|add_class:"form-control" }}
    """
    return field.as_widget(attrs={"class": css_class})


@register.filter(name="to_datetime")
def to_datetime(value):
    """Parse ISO 8601 string to datetime, or pass through datetime.

    Returns None if parsing fails.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        # Normalize Zulu suffix to fromisoformat compatible form
        if text.endswith("Z"):
            text = text[:-1]
        try:
            return datetime.fromisoformat(text)
        except ValueError as e:
            logger.error("Error parsing datetime '%s': %s", text, e)
            return None
    return None


@register.filter(name="expiry")
def expiry(value):
    """Compute expiry datetime by adding INACTIVITY_TIMEOUT_SECONDS to value.

    Accepts datetime or ISO string. Returns datetime or None.
    """
    dt = value if isinstance(value, datetime) else to_datetime(value)
    if dt is None:
        return None
    timeout_seconds = getattr(settings, "INACTIVITY_TIMEOUT_SECONDS", 3 * 60 * 60)
    return dt + timedelta(seconds=timeout_seconds)


@register.filter(name="range")
def range_filter(value):
    """Creates a range from 0 to value-1"""
    try:
        return range(int(value))
    except (ValueError, TypeError):
        return range(0)


@register.filter(name="sale_percentage")
def get_sale_percentage(remaining_quantity, total_quantity):
    """
    Calculate sold percentage and return status badge class.

    Args:
        remaining_quantity: Units still in stock
        total_quantity: Total units received

    Returns:
        - "active" (green): >90% sold - Excellent!
        - "warning" (yellow): 50-90% sold - OK
        - "danger" (red): <50% sold - Poor/Slow moving
        - "secondary" (gray): No stock/invalid
    """
    if total_quantity == 0:
        return "secondary"
    try:
        # Calculate SOLD percentage
        sold_quantity = total_quantity - remaining_quantity
        sold_percentage = (sold_quantity / total_quantity) * 100

        if sold_percentage >= 90:
            return "active"  # Green - Awesome! Almost sold out
        elif sold_percentage >= 50:
            return "warning"  # Yellow - OK, decent sales
        else:
            return "danger"  # Red - Poor, slow moving stock
    except (ValueError, TypeError):
        return "secondary"


# ── Role-based template visibility ────────────────────────────────


@register.filter(name="has_role")
def has_role(user, roles_string):
    """
    Check if user's role matches any of the given roles.

    Usage:
        {% if user|has_role:"OWNER,MANAGER" %}
            <a href="...">Delete</a>
        {% endif %}

    Args:
        user: The user object (must have a `role` attribute)
        roles_string: Comma-separated role names (e.g. "OWNER,MANAGER")
    """
    if not hasattr(user, "role"):
        return False
    allowed = [r.strip() for r in roles_string.split(",")]
    return user.role in allowed


@register.simple_tag
def role_is(user, roles_string):
    """
    Assignment tag to check user role — use with `as` for reusable variables.

    Usage:
        {% role_is user "OWNER,MANAGER" as is_management %}
        {% if is_management %}
            <a href="...">Delete</a>
            <a href="...">Dashboard</a>
        {% endif %}
    """
    if not hasattr(user, "role"):
        return False
    allowed = [r.strip() for r in roles_string.split(",")]
    return user.role in allowed
