"""
strategy/rsi_reversion.py
-------------------------

Mean‑reversion strategy with configurable RSI length and thresholds.
Fades overbought/oversold RSI levels; meant to be loaded via BaseStrategy.

Parameters (defaults shown)::

    {
        "rsi_len": 14,       # RSI lookback period (configurable)
        "overbought": 70,    # RSI above this triggers short entry
        "oversold": 30,      # RSI below this triggers long entry
        "exit_mid": 50,      # RSI crosses this for exit
    }

"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any
import numpy as np

from strategy.base import BaseStrategy


# --------------------------------------------------------------------------- #
# Helper: vectorised RSI (NumPy)                                              #
# --------------------------------------------------------------------------- #
def _rsi(arr: np.ndarray, length: int = 14) -> np.ndarray:
    """Return RSI series (numpy)."""
    delta = np.diff(arr)
    up   = np.maximum(delta, 0.0)
    down = np.maximum(-delta, 0.0)

    # Wilder's smoothing
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
    rsi[: length] = 50.0  # neutral until enough data
    return rsi


# --------------------------------------------------------------------------- #
# Strategy                                                                    #
# --------------------------------------------------------------------------- #
class StrategyRSIReversion(BaseStrategy):
    """Fade extreme RSI levels and exit near the mid‑line."""

    name = "RSIReversion"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})
        # cache previous position side to avoid multiple entries
        self._position: int = 0  # 1=long, -1=short, 0=flat

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        if not bars:
            return None

        # Extract prices: bars may be raw floats or OANDA candle dicts
        first = bars[0]
        if isinstance(first, (int, float, np.floating)):
            prices = np.array(bars, dtype=np.float64)
        else:
            prices = np.array([float(c["mid"]["c"]) for c in bars], dtype=np.float64)

        rsi_len = self.params.get("rsi_len", 14)
        if len(prices) < rsi_len + 2:
            return None

        rsi_series = _rsi(prices, rsi_len)
        rsi_prev, rsi_curr = rsi_series[-2], rsi_series[-1]

        overbought = self.params.get("overbought", 70)
        oversold = self.params.get("oversold", 30)
        exit_mid = self.params.get("exit_mid", 50)

        # --- Entry signals ---
        if self._position == 0:
            if rsi_prev > overbought and rsi_curr < overbought:
                self._position = -1
                return "SELL"
            if rsi_prev < oversold and rsi_curr > oversold:
                self._position = 1
                return "BUY"

        # --- Exit signals ---
        if self._position == 1 and rsi_curr >= exit_mid:
            self._position = 0
            return "SELL"  # close long
        if self._position == -1 and rsi_curr <= exit_mid:
            self._position = 0
            return "BUY"   # close short

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """
        Simple adaptive tweak: if rolling win-rate < 40%, widen RSI bands by 2; 
        if rolling win-rate > 65%, narrow bands by 2.
        """
        history = self.params.setdefault("_hist", [])
        history.append(win)
        hist_len = 20
        if len(history) > hist_len:
            history.pop(0)

        if len(history) == hist_len:
            win_rate = sum(history) / hist_len
            if win_rate < 0.40:
                self.params["overbought"] += 2
                self.params["oversold"] -= 2
            elif win_rate > 0.65:
                self.params["overbought"] = max(55, self.params["overbought"] - 2)
                self.params["oversold"]   = min(45, self.params["oversold"] + 2)