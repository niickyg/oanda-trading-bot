"""
strategy/atr_channel.py
------------------------

ATR Channel Breakout with Trend Confirmation

Theory:
- ATR channels adapt to volatility (better than fixed Bollinger Bands)
- Channel = EMA ± (multiplier × ATR)
- Breakouts from ATR channels with trend confirmation = strong momentum trades
- Works well in trending markets, filters out noise in ranging markets

Parameters (defaults shown)::

    {
        "ema_period": 20,        # Base EMA for channel
        "atr_period": 14,        # ATR calculation period
        "atr_mult": 2.0,         # Channel width multiplier
        "trend_ema": 50,         # Longer EMA for trend filter
        "breakout_confirm": 2,   # Bars to confirm breakout
        "min_atr": 0.0001,       # Minimum ATR to trade (avoid low volatility)
        "sl_mult": 1.5,          # Stop loss multiplier (ATR)
        "tp_mult": 3.0,          # Take profit multiplier (ATR)
        "max_duration": 40,      # Maximum bars to hold position
    }
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any
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


def _atr_series(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    """Calculate ATR series."""
    high_low = highs - lows
    high_close = np.abs(highs - np.concatenate([[closes[0]], closes[:-1]]))
    low_close = np.abs(lows - np.concatenate([[closes[0]], closes[:-1]]))

    true_range = np.maximum(high_low, np.maximum(high_close, low_close))

    # Simple moving average of TR
    atr = np.empty_like(true_range)
    atr[:period-1] = np.nan
    for i in range(period-1, len(true_range)):
        atr[i] = true_range[i-period+1:i+1].mean()

    return atr


class StrategyATRChannel(BaseStrategy):
    """ATR Channel breakout with trend confirmation."""

    name = "ATRChannel"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})
        self._position: int = 0
        self._breakout_count: int = 0
        self._last_signal: Optional[str] = None

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
        ema_period = self.params.get("ema_period", 20)
        atr_period = self.params.get("atr_period", 14)
        atr_mult = self.params.get("atr_mult", 2.0)
        trend_ema = self.params.get("trend_ema", 50)
        breakout_confirm = self.params.get("breakout_confirm", 2)
        min_atr = self.params.get("min_atr", 0.0001)

        max_period = max(ema_period, atr_period, trend_ema)
        if len(closes) < max_period + 10:
            return None

        # Calculate indicators
        ema = _ema_series(closes, ema_period)
        atr = _atr_series(highs, lows, closes, atr_period)
        trend = _ema_series(closes, trend_ema)

        # Get current values
        curr_ema = ema[-1]
        curr_atr = atr[-1]
        curr_trend = trend[-1]
        curr_close = closes[-1]
        prev_close = closes[-2]

        # Check for valid ATR
        if np.isnan(curr_atr) or curr_atr < min_atr:
            return None

        # Calculate ATR channel
        upper_channel = curr_ema + (atr_mult * curr_atr)
        lower_channel = curr_ema - (atr_mult * curr_atr)

        # Previous channel values
        prev_ema = ema[-2]
        prev_atr = atr[-2]
        prev_upper = prev_ema + (atr_mult * prev_atr)
        prev_lower = prev_ema - (atr_mult * prev_atr)

        # --- Bullish Breakout Detection ---
        if self._position == 0:
            # Price breaks above upper channel
            breakout_up = prev_close <= prev_upper and curr_close > upper_channel
            in_uptrend = curr_close > curr_trend
            strong_move = curr_close > curr_ema  # Price above EMA

            if breakout_up and in_uptrend and strong_move:
                if self._last_signal == "BUY":
                    self._breakout_count += 1
                else:
                    self._breakout_count = 1
                    self._last_signal = "BUY"

                if self._breakout_count >= breakout_confirm:
                    self._position = 1
                    self._breakout_count = 0
                    self._last_signal = None
                    return "BUY"

        # --- Bearish Breakout Detection ---
        if self._position == 0:
            # Price breaks below lower channel
            breakout_down = prev_close >= prev_lower and curr_close < lower_channel
            in_downtrend = curr_close < curr_trend
            strong_move = curr_close < curr_ema  # Price below EMA

            if breakout_down and in_downtrend and strong_move:
                if self._last_signal == "SELL":
                    self._breakout_count += 1
                else:
                    self._breakout_count = 1
                    self._last_signal = "SELL"

                if self._breakout_count >= breakout_confirm:
                    self._position = -1
                    self._breakout_count = 0
                    self._last_signal = None
                    return "SELL"

        # Reset breakout count if conditions no longer met
        if self._position == 0:
            if self._last_signal == "BUY" and not (curr_close > upper_channel and curr_close > curr_trend):
                self._breakout_count = 0
                self._last_signal = None
            elif self._last_signal == "SELL" and not (curr_close < lower_channel and curr_close < curr_trend):
                self._breakout_count = 0
                self._last_signal = None

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Reset position after trade closes."""
        super().update_trade_result(win, pnl)
        self._position = 0
        self._breakout_count = 0
        self._last_signal = None
