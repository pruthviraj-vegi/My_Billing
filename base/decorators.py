import time
from functools import wraps
from django.db import connection
from django.conf import settings


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


def query_debugger(func):
    """Decorator to count queries and execution time"""

    def wrapper(*args, **kwargs):
        # Only run in debug mode
        if not settings.DEBUG:
            return func(*args, **kwargs)

        # Reset queries
        connection.queries_log.clear()

        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        query_count = len(connection.queries)
        execution_time = (end_time - start_time) * 1000

        print(f"\n{'='*60}")
        print(f"Function: {func.__name__}")
        print(f"Queries: {query_count}")
        print(f"Time: {execution_time:.2f}ms")
        print(f"{'='*60}\n")

        return result

    return wrapper
