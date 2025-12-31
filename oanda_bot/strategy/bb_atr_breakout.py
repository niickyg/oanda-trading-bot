"""
strategy/bb_atr_breakout.py
----------------------------

Bollinger Band + ATR Volatility Breakout Strategy

Theory:
- Bollinger Band squeeze indicates low volatility (consolidation)
- When BB width < threshold × ATR, volatility is compressed
- Breakout from squeeze with volume/momentum confirmation = high probability trade
- ATR-based filters prevent false breakouts in low volatility

Parameters (defaults shown)::

    {
        "bb_period": 20,         # Bollinger Band period
        "bb_std": 2.0,           # Standard deviation multiplier
        "atr_period": 14,        # ATR calculation period
        "squeeze_ratio": 1.5,    # BB width must be < (squeeze_ratio × ATR)
        "breakout_confirm": 3,   # Bars to confirm breakout
        "sl_mult": 1.0,          # Stop loss multiplier (ATR)
        "tp_mult": 2.5,          # Take profit multiplier (ATR)
        "max_duration": 40,      # Maximum bars to hold position
    }
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any
import numpy as np
from .base import BaseStrategy


def _sma(arr: np.ndarray, period: int) -> np.ndarray:
    """Calculate simple moving average."""
    result = np.empty_like(arr)
    result[:period-1] = np.nan
    for i in range(period-1, len(arr)):
        result[i] = arr[i-period+1:i+1].mean()
    return result


def _std(arr: np.ndarray, period: int) -> np.ndarray:
    """Calculate rolling standard deviation."""
    result = np.empty_like(arr)
    result[:period-1] = np.nan
    for i in range(period-1, len(arr)):
        result[i] = arr[i-period+1:i+1].std()
    return result


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    """Calculate Average True Range."""
    # True Range components
    high_low = highs - lows
    high_close = np.abs(highs - np.concatenate([[closes[0]], closes[:-1]]))
    low_close = np.abs(lows - np.concatenate([[closes[0]], closes[:-1]]))

    true_range = np.maximum(high_low, np.maximum(high_close, low_close))

    # ATR is simple moving average of TR
    atr = np.empty_like(true_range)
    atr[:period-1] = np.nan
    for i in range(period-1, len(true_range)):
        atr[i] = true_range[i-period+1:i+1].mean()

    return atr


class StrategyBBATRBreakout(BaseStrategy):
    """Bollinger Band squeeze breakout with ATR confirmation."""

    name = "BBATRBreakout"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})
        self._position: int = 0
        self._squeeze_detected: bool = False
        self._squeeze_bars: int = 0

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        if not bars:
            return None

        # Extract OHLC data
        first = bars[0]
        if isinstance(first, (int, float, np.floating)):
            # Only close prices available - cannot compute full strategy
            return None
        else:
            highs = np.array([float(c["mid"]["h"]) for c in bars], dtype=np.float64)
            lows = np.array([float(c["mid"]["l"]) for c in bars], dtype=np.float64)
            closes = np.array([float(c["mid"]["c"]) for c in bars], dtype=np.float64)

        # Parameters
        bb_period = self.params.get("bb_period", 20)
        bb_std_mult = self.params.get("bb_std", 2.0)
        atr_period = self.params.get("atr_period", 14)
        squeeze_ratio = self.params.get("squeeze_ratio", 1.5)
        breakout_confirm = self.params.get("breakout_confirm", 3)

        if len(closes) < max(bb_period, atr_period) + 10:
            return None

        # Calculate Bollinger Bands
        sma = _sma(closes, bb_period)
        std = _std(closes, bb_period)
        bb_upper = sma + (bb_std_mult * std)
        bb_lower = sma - (bb_std_mult * std)
        bb_width = bb_upper - bb_lower

        # Calculate ATR
        atr_vals = _atr(highs, lows, closes, atr_period)

        # Get current values
        curr_close = closes[-1]
        curr_bb_upper = bb_upper[-1]
        curr_bb_lower = bb_lower[-1]
        curr_bb_width = bb_width[-1]
        curr_atr = atr_vals[-1]
        curr_sma = sma[-1]

        # Check for NaN
        if np.isnan(curr_bb_width) or np.isnan(curr_atr):
            return None

        # --- Detect Squeeze ---
        in_squeeze = curr_bb_width < (squeeze_ratio * curr_atr)

        if in_squeeze:
            self._squeeze_detected = True
            self._squeeze_bars += 1
        else:
            self._squeeze_bars = 0

        # --- Detect Breakout from Squeeze ---
        if self._squeeze_detected and not in_squeeze and self._position == 0:
            # Squeeze just released - check for breakout direction

            # Bullish breakout: close above upper band
            if curr_close > curr_bb_upper and curr_close > curr_sma:
                # Confirm with multiple bars above breakout
                if self._squeeze_bars >= breakout_confirm:
                    self._position = 1
                    self._squeeze_detected = False
                    self._squeeze_bars = 0
                    return "BUY"

            # Bearish breakout: close below lower band
            if curr_close < curr_bb_lower and curr_close < curr_sma:
                # Confirm with multiple bars in squeeze
                if self._squeeze_bars >= breakout_confirm:
                    self._position = -1
                    self._squeeze_detected = False
                    self._squeeze_bars = 0
                    return "SELL"

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Reset position after trade closes."""
        super().update_trade_result(win, pnl)
        self._position = 0
        self._squeeze_detected = False
        self._squeeze_bars = 0
