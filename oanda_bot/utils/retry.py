"""
Retry helpers for OANDA REST and streaming API calls.

Usage example:

    from utils.retry import api_retry

    @api_retry
    def place_order(...):
        ...
"""

from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)
from oandapyV20.exceptions import V20Error


def api_retry(fn):
    """Decorator that retries a function up to five times on V20Error exceptions,
    with exponential back-off (2s → 4s → … capped at 30s).
    """
    return retry(
        wait=wait_exponential(
            multiplier=1,
            min=2,
            max=30,
        ),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(V20Error),
        reraise=True,
    )(fn)
