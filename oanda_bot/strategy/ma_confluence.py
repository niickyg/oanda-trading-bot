"""
strategy/ma_confluence.py
--------------------------

Moving Average Confluence Zone Strategy

Theory:
- When multiple MAs (EMA/SMA) cluster together, it creates a strong support/resistance zone
- Price bounces off confluence zones provide high-probability trade setups
- Works best in trending markets
- Confluence = 3+ MAs within tight range (% of ATR)

Parameters (defaults shown)::

    {
        "ma_periods": [20, 50, 100, 200],  # MA periods to track
        "ma_type": "EMA",                   # "EMA" or "SMA"
        "confluence_pct": 0.3,              # MAs must be within (confluence_pct × ATR)
        "atr_period": 14,                   # ATR calculation period
        "bounce_confirm": 2,                # Bars to confirm bounce
        "min_mas_confluent": 3,             # Minimum MAs that must be confluent
        "sl_mult": 1.0,                     # Stop loss multiplier (ATR)
        "tp_mult": 2.0,                     # Take profit multiplier (ATR)
        "max_duration": 35,                 # Maximum bars to hold position
    }
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any, List
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


def _sma_series(arr: np.ndarray, period: int) -> np.ndarray:
    """Return full SMA series."""
    result = np.empty_like(arr)
    result[:period-1] = np.nan
    for i in range(period-1, len(arr)):
        result[i] = arr[i-period+1:i+1].mean()
    return result


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
    """Calculate current ATR value."""
    if len(highs) < period + 1:
        return 0.0

    high_low = highs[1:] - lows[1:]
    high_close = np.abs(highs[1:] - closes[:-1])
    low_close = np.abs(lows[1:] - closes[:-1])

    true_range = np.maximum(high_low, np.maximum(high_close, low_close))
    return float(true_range[-period:].mean())


class StrategyMAConfluence(BaseStrategy):
    """Trade bounces from moving average confluence zones."""

    name = "MAConfluence"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})
        self._position: int = 0
        self._bounce_count: int = 0

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        if not bars:
            return None

        # Extract OHLC data
        first = bars[0]
        if isinstance(first, (int, float, np.floating)):
            # Only close prices available
            closes = np.array(bars, dtype=np.float64)
            highs = closes.copy()
            lows = closes.copy()
        else:
            highs = np.array([float(c["mid"]["h"]) for c in bars], dtype=np.float64)
            lows = np.array([float(c["mid"]["l"]) for c in bars], dtype=np.float64)
            closes = np.array([float(c["mid"]["c"]) for c in bars], dtype=np.float64)

        # Parameters
        ma_periods = self.params.get("ma_periods", [20, 50, 100, 200])
        ma_type = self.params.get("ma_type", "EMA")
        confluence_pct = self.params.get("confluence_pct", 0.3)
        atr_period = self.params.get("atr_period", 14)
        bounce_confirm = self.params.get("bounce_confirm", 2)
        min_mas = self.params.get("min_mas_confluent", 3)

        max_period = max(ma_periods)
        if len(closes) < max_period + 10:
            return None

        # Calculate all MAs
        ma_values = []
        if ma_type == "EMA":
            for period in ma_periods:
                ma = _ema_series(closes, period)[-1]
                if not np.isnan(ma):
                    ma_values.append(ma)
        else:  # SMA
            for period in ma_periods:
                ma = _sma_series(closes, period)[-1]
                if not np.isnan(ma):
                    ma_values.append(ma)

        if len(ma_values) < min_mas:
            return None

        # Calculate ATR
        curr_atr = _atr(highs, lows, closes, atr_period)
        if curr_atr == 0:
            return None

        # Get current price data
        curr_close = closes[-1]
        prev_close = closes[-2]
        curr_high = highs[-1]
        curr_low = lows[-1]

        # Check for MA confluence
        ma_values_sorted = sorted(ma_values)
        ma_range = ma_values_sorted[-1] - ma_values_sorted[0]
        confluence_threshold = confluence_pct * curr_atr

        is_confluent = ma_range < confluence_threshold

        if not is_confluent:
            self._bounce_count = 0
            return None

        # Find confluence zone center
        confluence_center = np.mean(ma_values)

        # --- Bullish Bounce Detection ---
        # Price was below confluence, now bouncing up
        if self._position == 0:
            # Check if price touched/crossed confluence from below
            price_below_before = prev_close < confluence_center
            price_touching = curr_low <= confluence_center <= curr_high
            price_above_now = curr_close > confluence_center

            if price_below_before and (price_touching or price_above_now):
                self._bounce_count += 1
                if self._bounce_count >= bounce_confirm:
                    self._position = 1
                    self._bounce_count = 0
                    return "BUY"

        # --- Bearish Bounce Detection ---
        # Price was above confluence, now bouncing down
        if self._position == 0:
            # Check if price touched/crossed confluence from above
            price_above_before = prev_close > confluence_center
            price_touching = curr_low <= confluence_center <= curr_high
            price_below_now = curr_close < confluence_center

            if price_above_before and (price_touching or price_below_now):
                self._bounce_count += 1
                if self._bounce_count >= bounce_confirm:
                    self._position = -1
                    self._bounce_count = 0
                    return "SELL"

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Reset position after trade closes."""
        super().update_trade_result(win, pnl)
        self._position = 0
        self._bounce_count = 0
