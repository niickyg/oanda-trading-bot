from __future__ import annotations
from typing import Sequence, Optional, Tuple
import numpy as np

import logging

logger = logging.getLogger(__name__)

from .base import BaseStrategy

# --------------------------------------------------------------------------- #
# Helper functions (pure NumPy, no pandas)                                    #
# --------------------------------------------------------------------------- #
def _ema_series(arr: np.ndarray, span: int) -> np.ndarray:
    """Return full EMA series (single-pass, no pandas)."""
    alpha = 2.0 / (span + 1)
    ema = np.empty_like(arr)
    ema[0] = arr[0]
    for i in range(1, len(arr)):
        ema[i] = alpha * arr[i] + (1 - alpha) * ema[i - 1]
    return ema

def _macd(arr: np.ndarray, fast: int, slow: int, sig: int) -> Tuple[np.ndarray, np.ndarray]:
    macd_line = _ema_series(arr, fast) - _ema_series(arr, slow)
    sig_line  = _ema_series(macd_line, sig)
    return macd_line, sig_line

# --------------------------------------------------------------------------- #
# Strategy                                                                    #
# --------------------------------------------------------------------------- #
class MACDTrendStrategy(BaseStrategy):
    """MACD + EMA trend-following strategy."""
    name = "MACDTrend"

    def __init__(self, params=None):
        # Pass params up to BaseStrategy so they live in self.params
        super().__init__(params or {})
        # Helpful trace to make sure optimiser values get here
        logger.debug("STRATEGY INIT — params = %s", self.params)

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        # Extract close prices: bars may be raw floats or OANDA candle dicts
        if not bars:
            return None
        # Determine bar type
        if isinstance(bars[0], (int, float, np.floating)):
            closes = np.array(bars, dtype=np.float64)
        else:
            # bars are dicts with price under ["mid"]["c"]
            closes = np.array([float(c["mid"]["c"]) for c in bars], dtype=np.float64)

        # Need enough bars for EMA trend
        trend_len = self.params.get("ema_trend", 200)
        if len(closes) < trend_len + 2:  # need prev bar for crossover
            return None

        # Parameters (fallback to defaults)
        fast = self.params.get("macd_fast", 12)
        slow = self.params.get("macd_slow", 26)
        sig  = self.params.get("macd_sig", 9)

        # Compute indicators
        ema_trend = _ema_series(closes, trend_len)[-1]
        macd_line, sig_line = _macd(closes, fast, slow, sig)

        macd_prev, sig_prev = macd_line[-2], sig_line[-2]
        macd_curr, sig_curr = macd_line[-1], sig_line[-1]
        price_curr = closes[-1]

        # Up-trend long entry
        if price_curr > ema_trend and macd_prev < sig_prev and macd_curr > sig_curr:
            return "BUY"

        # Down-trend short entry
        if price_curr < ema_trend and macd_prev > sig_prev and macd_curr < sig_curr:
            return "SELL"

        return None

StrategyMACDTrend = MACDTrendStrategy

# Convenience function to generate entry/exit signals using MACDTrendStrategy
def generate_signal(bars, params=None):
    """
    Run MACDTrendStrategy.next_signal using provided bars list and params dict.
    """
    strategy = MACDTrendStrategy(params or {})
    return strategy.next_signal(bars)

# Stub for compute_atr (to be implemented)
def compute_atr(bars, period: int = 14) -> float:
    """
    Return the latest Average True Range (ATR) over the given bars.

    Bars may be either:
    • plain floats (close prices) – in which case ATR is undefined and we return 0
    • OANDA candle dicts with ["mid"]["h"], ["mid"]["l"], ["mid"]["c"] keys.
    """
    if len(bars) < period + 1:
        return 0.0

    # Extract high/low/close series as NumPy arrays
    if isinstance(bars[0], (int, float, np.floating)):
        # Cannot compute ATR with only closes
        return 0.0

    highs = np.array([float(b["mid"]["h"]) for b in bars[-period - 1 :]], dtype=np.float64)
    lows  = np.array([float(b["mid"]["l"]) for b in bars[-period - 1 :]], dtype=np.float64)
    closes_prev = np.array([float(b["mid"]["c"]) for b in bars[-period - 1 :]], dtype=np.float64)

    # True range: max( high - low,
    #                  abs(high - prev_close),
    #                  abs(low  - prev_close) )
    tr = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(
            np.abs(highs[1:] - closes_prev[:-1]),
            np.abs(lows[1:] - closes_prev[:-1]),
        ),
    )

    return float(tr.mean())

# Stub for sl_tp_levels (to be implemented)
def sl_tp_levels(bars, side: str, params=None):
    """
    Given a list of bars and a trade side ("BUY" or "SELL"),
    return tuple (stop_loss, take_profit).

    Uses ATR‑based offsets with multipliers supplied in params.
    """
    params = params or {}
    atr_period = params.get("atr_period", 14)
    sl_mult    = params.get("sl_mult", 1.0)
    tp_mult    = params.get("tp_mult", 1.0)

    price = float(bars[-1]["mid"]["c"]) if not isinstance(bars[-1], (int, float, np.floating)) else float(bars[-1])
    atr   = compute_atr(bars, period=atr_period)

    if side == "BUY":
        return price - sl_mult * atr, price + tp_mult * atr
    elif side == "SELL":
        return price + sl_mult * atr, price - tp_mult * atr
    else:
        raise ValueError("side must be 'BUY' or 'SELL'")