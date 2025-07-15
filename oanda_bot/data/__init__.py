"""
data package initializer.
Expose core data functions and news helpers.
"""

from .core import (
    stream_bars,
    get_candles,
    build_active_list,
    get_last_volume,
    api,
    OANDA_ACCOUNT_ID,
)
from .news import (
    fetch_forex_news_from_twitter,
    interpret_news_signals,
)

__all__ = [
    "stream_bars",
    "get_candles",
    "build_active_list",
    "get_last_volume",
    "api",
    "OANDA_ACCOUNT_ID",
    "fetch_forex_news_from_twitter",
    "interpret_news_signals",
]
