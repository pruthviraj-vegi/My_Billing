from fuzzywuzzy import process
from datetime import datetime, date
import time
from functools import wraps


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