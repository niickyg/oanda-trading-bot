"""
strategy/macd_histogram.py
---------------------------

MACD Histogram Reversal Strategy - Trades when histogram changes momentum direction.

Theory:
- MACD Histogram = MACD Line - Signal Line
- When histogram bottoms and starts rising → bullish (momentum reversal)
- When histogram tops and starts falling → bearish (momentum reversal)
- Strong edge when combined with trend filter

Parameters (defaults shown)::

    {
        "macd_fast": 12,         # Fast EMA period
        "macd_slow": 26,         # Slow EMA period
        "macd_sig": 9,           # Signal line EMA period
        "ema_trend": 50,         # Trend filter EMA
        "hist_threshold": 0.0001, # Minimum histogram change
        "sl_mult": 1.2,          # Stop loss multiplier (ATR)
        "tp_mult": 2.0,          # Take profit multiplier (ATR)
        "max_duration": 30,      # Maximum bars to hold position
    }
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any, Tuple
import numpy as np
from .base import BaseStrategy


def _ema_series(arr: np.ndarray, span: int) -> np.ndarray:
    """Return full EMA series."""
    alpha = 2.0 / (span + 1)
    ema = np.empty_like(arr)
    ema[0] = arr[0]
    for i in range(1, len(arr)):
        ema[i] = alpha * arr[i] + (1 - alpha) * ema[i - 1]
    return ema


def _macd(arr: np.ndarray, fast: int, slow: int, sig: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculate MACD line, signal line, and histogram."""
    macd_line = _ema_series(arr, fast) - _ema_series(arr, slow)
    sig_line = _ema_series(macd_line, sig)
    histogram = macd_line - sig_line
    return macd_line, sig_line, histogram


class StrategyMACDHistogram(BaseStrategy):
    """Trade MACD histogram momentum reversals with trend filter."""

    name = "MACDHistogram"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})
        self._position: int = 0

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        if not bars:
            return None

        # Extract prices
        first = bars[0]
        if isinstance(first, (int, float, np.floating)):
            closes = np.array(bars, dtype=np.float64)
        else:
            closes = np.array([float(c["mid"]["c"]) for c in bars], dtype=np.float64)

        # Parameters
        fast = self.params.get("macd_fast", 12)
        slow = self.params.get("macd_slow", 26)
        sig = self.params.get("macd_sig", 9)
        trend_len = self.params.get("ema_trend", 50)
        hist_threshold = self.params.get("hist_threshold", 0.0001)

        if len(closes) < max(trend_len, slow) + 5:
            return None

        # Calculate indicators
        macd_line, sig_line, histogram = _macd(closes, fast, slow, sig)
        ema_trend = _ema_series(closes, trend_len)

        # Get recent values
        hist_curr = histogram[-1]
        hist_prev = histogram[-2]
        hist_prev2 = histogram[-3]
        price_curr = closes[-1]
        trend_curr = ema_trend[-1]

        # --- Bullish Histogram Reversal ---
        # Histogram was falling, now rising (bottomed out)
        # Price above trend filter
        if self._position == 0:
            histogram_rising = (hist_prev < hist_prev2) and (hist_curr > hist_prev)
            histogram_negative = hist_curr < 0  # Still below zero (oversold)
            momentum_change = abs(hist_curr - hist_prev) > hist_threshold
            in_uptrend = price_curr > trend_curr

            if histogram_rising and histogram_negative and momentum_change and in_uptrend:
                self._position = 1
                return "BUY"

        # --- Bearish Histogram Reversal ---
        # Histogram was rising, now falling (topped out)
        # Price below trend filter
        if self._position == 0:
            histogram_falling = (hist_prev > hist_prev2) and (hist_curr < hist_prev)
            histogram_positive = hist_curr > 0  # Still above zero (overbought)
            momentum_change = abs(hist_curr - hist_prev) > hist_threshold
            in_downtrend = price_curr < trend_curr

            if histogram_falling and histogram_positive and momentum_change and in_downtrend:
                self._position = -1
                return "SELL"

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Reset position after trade closes."""
        super().update_trade_result(win, pnl)
        self._position = 0
