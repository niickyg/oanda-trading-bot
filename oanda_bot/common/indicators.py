

"""
Common technical indicator utilities.

All functions take `pandas.Series` inputs and return a `pandas.Series`
indexed exactly like the inputs so they can be joined back to a price
DataFrame without alignment headaches.
"""

from __future__ import annotations

import pandas as pd


def ATR(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
) -> pd.Series:
    """
    Compute the Average True Range (ATR).

    Parameters
    ----------
    high, low, close : pd.Series
        Series of high, low and closing prices for the same instrument and timeframe.
    window : int, default 14
        Rolling window length used for the simple moving average of True Range.

    Returns
    -------
    pd.Series
        The ATR values aligned with the original index.

    Notes
    -----
    * True Range (TR) is the max of:
        1. High - Low
        2. abs(High - Previous Close)
        3. abs(Low  - Previous Close)
    * ATR is the simple moving average of TR.
    """
    # Calculate the three components of True Range
    high_low = high - low
    high_prev_close = (high - close.shift()).abs()
    low_prev_close = (low - close.shift()).abs()

    true_range = pd.concat(
        [high_low, high_prev_close, low_prev_close], axis=1
    ).max(axis=1)

    # Simple moving average of True Range
    atr = true_range.rolling(window=window, min_periods=window).mean()

    return atr
