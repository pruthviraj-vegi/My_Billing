# pylint: disable=invalid-name
"""
Utility module for handling date ranges and date calculations.
"""
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


# ---------- Helpers ----------
def start_of_day(dt):
    """Return the datetime representing the start of the given day."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt):
    """Return the datetime representing the end of the given day."""
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def parse_date(date_str, fallback=None):
    """Parse date string in multiple formats: dd-mm-yyyy or yyyy-mm-dd"""
    if not date_str:
        return fallback
    try:
        # Try dd-mm-yyyy format first (original format)
        return datetime.strptime(date_str, "%d-%m-%Y")
    except (ValueError, TypeError):
        try:
            # Try yyyy-mm-dd format (ISO format)
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError) as e:
            logger.error("Failed to parse date '%s': %s", date_str, e)
            return fallback


# ---------- Dates Logic ----------
def quarter_start_end(year, month):
    """Calculate the start and end datetimes for a quarter given a year and month."""
    q_start_month = ((month - 1) // 3) * 3 + 1
    start = datetime(year, q_start_month, 1)
    if q_start_month + 3 > 12:
        end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = datetime(year, q_start_month + 3, 1) - timedelta(days=1)
    return start_of_day(start), end_of_day(end)


class DatesManipulation:
    """Helper class to calculate common date ranges relative to today."""

    def __init__(self):
        self.today = datetime.now()
        self.year = self.today.year
        self.month = self.today.month

    @property
    def today_date(self):
        """Return the start and end datetime for today."""
        return start_of_day(self.today), end_of_day(self.today)

    @property
    def yesterday_date(self):
        """Return the start and end datetime for yesterday."""
        y = self.today - timedelta(days=1)
        return start_of_day(y), end_of_day(y)

    @property
    def this_month(self):
        """Return the start and end datetime for the current month."""
        start = self.today.replace(day=1)
        return start_of_day(start), end_of_day(self.today)

    @property
    def last_month(self):
        """Return the start and end datetime for the previous month."""
        last_month_end = self.today.replace(day=1) - timedelta(days=1)
        start = last_month_end.replace(day=1)
        return start_of_day(start), end_of_day(last_month_end)

    @property
    def this_finance(self):
        """Return the start and end datetime for the current financial year (April-March)."""
        year = self.today.year if self.month > 3 else self.today.year - 1
        start = datetime(year, 4, 1)
        return start_of_day(start), end_of_day(self.today)

    @property
    def last_finance(self):
        """Return the start and end datetime for the previous financial year."""
        year = self.today.year if self.month > 3 else self.today.year - 1
        start = datetime(year - 1, 4, 1)
        end = datetime(year, 3, 31)
        return start_of_day(start), end_of_day(end)

    @property
    def this_quarter(self):
        """Return the start and end datetime for the current quarter."""
        return quarter_start_end(self.today.year, self.today.month)

    @property
    def last_quarter(self):
        """Return the start and end datetime for the previous quarter."""
        last_month = self.month - 3
        year = self.year
        if last_month <= 0:
            last_month += 12
            year -= 1
        return quarter_start_end(year, last_month)


# ---------- Main Wrapper ----------
class DatesRange:
    """Wrapper class to map date preset strings to actual datetime ranges."""

    def __init__(self, value):
        self.dates = DatesManipulation()
        ranges = {
            "today": self.dates.today_date,
            "yesterday": self.dates.yesterday_date,
            "this_month": self.dates.this_month,
            "last_month": self.dates.last_month,
            "this_finance": self.dates.this_finance,
            "last_finance": self.dates.last_finance,
            "this_quarter": self.dates.this_quarter,
            "last_quarter": self.dates.last_quarter,
            "full_date": (
                start_of_day(datetime(2023, 1, 1)),
                end_of_day(self.dates.today),
            ),
        }
        self.from_date, self.to_date = ranges.get(value, self.dates.last_month)


# ---------- Public Function ----------
def getDates(request):
    """
    Get date range from request. Accepts multiple parameter formats:
    - date_filter or date_range: "this_month", "last_month", "custom", etc.
    - For custom dates: from_date/to_date (dd-mm-yyyy) or start_date/end_date (yyyy-mm-dd)
    Supports both GET query parameters and POST JSON body.
    """
    import json

    today = datetime.now()

    # Try to parse JSON body for POST requests
    data = {}
    if request.method == "POST" and request.body:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            pass

    # Accept both 'date_filter' and 'date_range' parameter names from GET or POST
    type_of = (
        request.GET.get("date_filter")
        or request.GET.get("date_range")
        or data.get("date_filter")
        or data.get("date_range")
        or "this_month"
    )

    if type_of == "custom":
        # Accept both 'from_date'/'to_date' and 'start_date'/'end_date' parameter names
        from_date_str = (
            request.GET.get("from_date")
            or request.GET.get("start_date")
            or data.get("from_date")
            or data.get("start_date")
        )
        to_date_str = (
            request.GET.get("to_date")
            or request.GET.get("end_date")
            or data.get("to_date")
            or data.get("end_date")
        )

        from_date = parse_date(from_date_str, today)
        to_date = parse_date(to_date_str, today)
        return start_of_day(from_date), end_of_day(to_date)

    date_range = DatesRange(type_of)
    return date_range.from_date, date_range.to_date
