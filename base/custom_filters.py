from django import template
import locale
import base64
from datetime import datetime, timedelta
from django.conf import settings
import logging
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
        logger.warning(f"Failed to convert '{value}' to numeric: {e}")
        return None


@register.filter(name="currency")
def currency(value, arg=None):
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
            logger.warning(f"Could not convert value '{value}' to numeric format")
            return "0.00"

        data = locale.format_string(
            "%%.%df" % formate["frac_digits"],
            numeric_value,
            grouping=formate["grouping"],
            monetary=False,
        )
        return data
    except (TypeError, ValueError, locale.Error) as e:
        logger.error(f"Currency formatting error for value '{value}': {e}")
        return "0.00"


@register.filter(name="currency_nonDecimal")
def currency_nonDecimal(value, arg=None):
    """
    Bulletproof non-decimal currency formatter for integer values.
    """
    try:
        if value is None or value == "":
            return "0"

        # Convert string to number if needed
        numeric_value = _convert_to_numeric(value)

        if numeric_value is None:
            logger.warning(f"Could not convert value '{value}' to numeric format")
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
        logger.error(f"Currency non-decimal formatting error for value '{value}': {e}")
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
            logger.warning(f"Could not convert value '{value}' to numeric format")
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
        logger.error(f"Currency abbreviation formatting error for value '{value}': {e}")
        return "0.00"


@register.filter(name="currencyToWord")
def currencyToyWord(value, arg=None):
    try:
        amount = float(value)
        return num2words(amount, lang="en_IN", to="currency", currency="INR").title()
    except BaseException as e:
        logger.error(f"Currency to word formatting error for value '{value}': {e}")
        return value


@register.filter(name="phone_number")
def phone_number(value):
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
    return base64.b64encode(value).decode("utf-8")


@register.filter(name="sub")
def sub(value, arg):
    """Bulletproof subtraction filter that handles strings and various input formats."""
    try:
        numeric_value = _convert_to_numeric(value)
        numeric_arg = _convert_to_numeric(arg)

        if numeric_value is None or numeric_arg is None:
            logger.warning(
                f"Could not convert values '{value}' or '{arg}' to numeric format"
            )
            return 0

        return numeric_value - numeric_arg
    except (TypeError, ValueError) as e:
        logger.error(f"Subtraction error for values '{value}' and '{arg}': {e}")
        return 0


@register.filter(name="div")
def div(value, arg):
    """Bulletproof division filter that handles strings and various input formats."""
    try:
        numeric_value = _convert_to_numeric(value)
        numeric_arg = _convert_to_numeric(arg)

        if numeric_value is None or numeric_arg is None:
            logger.warning(
                f"Could not convert values '{value}' or '{arg}' to numeric format"
            )
            return 0

        if numeric_arg == 0:
            logger.warning(
                f"Division by zero attempted with values '{value}' and '{arg}'"
            )
            return 0

        return numeric_value / numeric_arg
    except (TypeError, ValueError, ZeroDivisionError) as e:
        logger.error(f"Division error for values '{value}' and '{arg}': {e}")
        return 0


@register.filter(name="mul")
def mul(value, arg):
    """Bulletproof multiplication filter that handles strings and various input formats."""
    try:
        numeric_value = _convert_to_numeric(value)
        numeric_arg = _convert_to_numeric(arg)

        if numeric_value is None or numeric_arg is None:
            logger.warning(
                f"Could not convert values '{value}' or '{arg}' to numeric format"
            )
            return 0

        return numeric_value * numeric_arg
    except (TypeError, ValueError) as e:
        logger.error(f"Multiplication error for values '{value}' and '{arg}': {e}")
        return 0


@register.filter(name="status_badge")
def status_badge(value):
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
        except Exception as e:
            logger.error(e)
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
