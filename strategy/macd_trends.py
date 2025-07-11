"""
strategy/macd_trends.py
-----------------------

Trend‑following strategy using a configurable EMA filter period and MACD crossover
for entries.  Designed to be loaded dynamically by manager.py via the
BaseStrategy interface.

Parameters accepted via ``params`` dict (defaults shown)::

    {
        "ema_trend": 200,   # Configurable EMA period for major trend (default 200)
        "macd_fast": 12,    # MACD fast EMA
        "macd_slow": 26,    # MACD slow EMA
        "macd_sig":  9,     # MACD signal line
    }

"""

from __future__ import annotations
from typing import Sequence, Optional, Tuple
import numpy as np

from strategy.base import BaseStrategy


# --------------------------------------------------------------------------- #
# Helper functions (pure NumPy, no pandas)                                    #
# --------------------------------------------------------------------------- #
def _ema_series(arr: np.ndarray, span: int) -> np.ndarray:
    """Return full EMA series (single‑pass, no pandas)."""
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
class StrategyMACDTrend(BaseStrategy):
    """MACD + EMA trend‑following strategy."""

    name = "MACDTrend"

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:  # noqa: D401
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

        # Up‑trend long entry
        if price_curr > ema_trend and macd_prev < sig_prev and macd_curr > sig_curr:
            return "BUY"

        # Down‑trend short entry
        if price_curr < ema_trend and macd_prev > sig_prev and macd_curr < sig_curr:
            return "SELL"

        return None

    # Optional adaptive feedback (just forward to BaseStrategy default)
    # You can override update_trade_result here if you want strategy‑level
    # learning in addition to the global adaptive module.</file>