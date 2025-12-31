"""
strategy/rsi_divergence.py
---------------------------

RSI Divergence Strategy - Identifies bullish/bearish divergences between price and RSI.

Theory:
- Bullish divergence: Price makes lower lows, RSI makes higher lows (reversal signal)
- Bearish divergence: Price makes higher highs, RSI makes lower highs (reversal signal)

Parameters (defaults shown)::

    {
        "rsi_len": 14,          # RSI lookback period
        "divergence_window": 20, # Window to search for divergence
        "min_rsi_oversold": 35,  # RSI threshold for bullish divergence
        "max_rsi_overbought": 65, # RSI threshold for bearish divergence
        "sl_mult": 1.5,          # Stop loss multiplier (ATR)
        "tp_mult": 2.5,          # Take profit multiplier (ATR)
        "max_duration": 50,      # Maximum bars to hold position
    }
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any
import numpy as np
from .base import BaseStrategy


def _rsi(arr: np.ndarray, length: int = 14) -> np.ndarray:
    """Return RSI series (numpy)."""
    delta = np.diff(arr)
    up = np.maximum(delta, 0.0)
    down = np.maximum(-delta, 0.0)

    roll_up = np.empty_like(arr)
    roll_down = np.empty_like(arr)
    roll_up[:length] = 0.0
    roll_down[:length] = 0.0
    roll_up[length] = up[:length].mean()
    roll_down[length] = down[:length].mean()
    alpha = 1.0 / length
    for i in range(length + 1, len(arr)):
        roll_up[i] = (1 - alpha) * roll_up[i - 1] + alpha * up[i - 1]
        roll_down[i] = (1 - alpha) * roll_down[i - 1] + alpha * down[i - 1]

    rs = np.divide(roll_up, roll_down, out=np.zeros_like(roll_up), where=roll_down != 0)
    rsi = 100 - (100 / (1 + rs))
    rsi[:length] = 50.0
    return rsi


def _find_peaks_troughs(arr: np.ndarray, window: int = 5) -> tuple:
    """Find local peaks and troughs in an array."""
    peaks = []
    troughs = []

    for i in range(window, len(arr) - window):
        # Check if this is a peak
        if all(arr[i] >= arr[i-j] for j in range(1, window+1)) and \
           all(arr[i] >= arr[i+j] for j in range(1, window+1)):
            peaks.append(i)
        # Check if this is a trough
        if all(arr[i] <= arr[i-j] for j in range(1, window+1)) and \
           all(arr[i] <= arr[i+j] for j in range(1, window+1)):
            troughs.append(i)

    return peaks, troughs


class StrategyRSIDivergence(BaseStrategy):
    """Detect and trade RSI divergences."""

    name = "RSIDivergence"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})
        self._position: int = 0  # 1=long, -1=short, 0=flat

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        if not bars:
            return None

        # Extract prices
        first = bars[0]
        if isinstance(first, (int, float, np.floating)):
            prices = np.array(bars, dtype=np.float64)
        else:
            prices = np.array([float(c["mid"]["c"]) for c in bars], dtype=np.float64)

        rsi_len = self.params.get("rsi_len", 14)
        div_window = self.params.get("divergence_window", 20)

        if len(prices) < rsi_len + div_window + 5:
            return None

        rsi_series = _rsi(prices, rsi_len)

        # Get parameters
        min_oversold = self.params.get("min_rsi_oversold", 35)
        max_overbought = self.params.get("max_rsi_overbought", 65)

        # Look for divergence in recent window
        recent_prices = prices[-div_window:]
        recent_rsi = rsi_series[-div_window:]

        # Find peaks and troughs
        price_peaks, price_troughs = _find_peaks_troughs(recent_prices, window=3)
        rsi_peaks, rsi_troughs = _find_peaks_troughs(recent_rsi, window=3)

        # --- Bullish Divergence Detection ---
        # Price makes lower low, RSI makes higher low
        if len(price_troughs) >= 2 and len(rsi_troughs) >= 2 and self._position == 0:
            last_price_trough_idx = price_troughs[-1]
            prev_price_trough_idx = price_troughs[-2]

            # Check if we have corresponding RSI troughs
            if rsi_troughs:
                last_rsi_trough_idx = rsi_troughs[-1]
                prev_rsi_trough_idx = rsi_troughs[-2] if len(rsi_troughs) >= 2 else rsi_troughs[-1]

                price_lower_low = recent_prices[last_price_trough_idx] < recent_prices[prev_price_trough_idx]
                rsi_higher_low = recent_rsi[last_rsi_trough_idx] > recent_rsi[prev_rsi_trough_idx]
                rsi_oversold = recent_rsi[last_rsi_trough_idx] < min_oversold

                if price_lower_low and rsi_higher_low and rsi_oversold:
                    # Bullish divergence detected
                    self._position = 1
                    return "BUY"

        # --- Bearish Divergence Detection ---
        # Price makes higher high, RSI makes lower high
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2 and self._position == 0:
            last_price_peak_idx = price_peaks[-1]
            prev_price_peak_idx = price_peaks[-2]

            if rsi_peaks:
                last_rsi_peak_idx = rsi_peaks[-1]
                prev_rsi_peak_idx = rsi_peaks[-2] if len(rsi_peaks) >= 2 else rsi_peaks[-1]

                price_higher_high = recent_prices[last_price_peak_idx] > recent_prices[prev_price_peak_idx]
                rsi_lower_high = recent_rsi[last_rsi_peak_idx] < recent_rsi[prev_rsi_peak_idx]
                rsi_overbought = recent_rsi[last_rsi_peak_idx] > max_overbought

                if price_higher_high and rsi_lower_high and rsi_overbought:
                    # Bearish divergence detected
                    self._position = -1
                    return "SELL"

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Reset position after trade closes."""
        super().update_trade_result(win, pnl)
        self._position = 0
