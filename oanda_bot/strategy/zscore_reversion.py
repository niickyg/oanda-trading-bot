"""
strategy/zscore_reversion.py
----------------------------

Z-Score based mean reversion strategy.

Entry when price deviates >N standard deviations from moving average.
Exit when price returns to mean (z-score crosses zero).

Optimized for Asia session (low volatility, range-bound conditions).

Parameters::

    {
        "lookback": 20,           # Moving average period
        "z_threshold": 2.0,       # Entry threshold (std deviations)
        "z_exit": 0.5,            # Exit threshold (return toward mean)
        "session_filter": True,   # Only trade during Asia session
        "sl_mult": 2.5,           # Stop loss multiplier (ATR)
        "tp_mult": 1.5,           # Take profit multiplier (ATR)
        "max_duration": 50,       # Max bars to hold position
    }
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any
from datetime import datetime
import numpy as np

from .base import BaseStrategy


# --------------------------------------------------------------------------- #
# Helper: Z-Score calculation                                                 #
# --------------------------------------------------------------------------- #
def _calculate_zscore(prices: np.ndarray, lookback: int) -> float:
    """
    Calculate z-score of latest price vs. lookback period.

    Z-Score = (current_price - mean) / std_dev

    Returns
    -------
    float
        Z-score value. Positive = above mean, negative = below mean.
    """
    if len(prices) < lookback:
        return 0.0

    recent = prices[-lookback:]
    mean = recent.mean()
    std = recent.std()

    if std == 0:
        return 0.0

    z_score = (prices[-1] - mean) / std
    return z_score


# --------------------------------------------------------------------------- #
# Session filter helper                                                       #
# --------------------------------------------------------------------------- #
def _is_asia_session(hour: Optional[int] = None) -> bool:
    """
    Check if current time is Asia trading session (23:00-08:00 UTC).

    Parameters
    ----------
    hour : int, optional
        Hour in UTC (0-23). If None, uses current UTC hour.

    Returns
    -------
    bool
        True if Asia session, False otherwise.
    """
    if hour is None:
        hour = datetime.utcnow().hour

    # Asia session: 23:00-08:00 UTC
    return (23 <= hour) or (hour < 8)


def _is_favorable_session(hour: Optional[int] = None,
                         strategy_type: str = "mean_reversion") -> bool:
    """
    Check if current time is favorable for the strategy type.

    Parameters
    ----------
    hour : int, optional
        Hour in UTC (0-23). If None, uses current UTC hour.
    strategy_type : str
        "mean_reversion" or "trend"

    Returns
    -------
    bool
        True if favorable session, False otherwise.
    """
    if hour is None:
        hour = datetime.utcnow().hour

    if strategy_type == "mean_reversion":
        # Asia session best for mean reversion
        return (23 <= hour) or (hour < 8)
    elif strategy_type == "trend":
        # London + NY sessions best for trends
        return 8 <= hour < 21
    else:
        return True  # No filter


# --------------------------------------------------------------------------- #
# Strategy                                                                    #
# --------------------------------------------------------------------------- #
class StrategyZScoreReversion(BaseStrategy):
    """
    Statistical mean reversion using z-scores.

    Entry Signals
    -------------
    - BUY when z-score < -threshold (price too low vs. mean)
    - SELL when z-score > +threshold (price too high vs. mean)

    Exit Signals
    ------------
    - Close when z-score crosses back toward mean (abs(z) < z_exit)
    - Or via SL/TP/max_duration from backtest engine

    Best Performance
    ----------------
    - Asia session (low volatility)
    - 20-period lookback
    - 2.0 std dev threshold
    - EUR/USD, GBP/USD, AUD/USD
    """

    name = "ZScoreReversion"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})

        # Internal state tracking
        self._position: Optional[str] = None  # "BUY", "SELL", or None
        self._entry_zscore: float = 0.0       # Z-score at entry
        self._trade_count: int = 0             # Total trades taken

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """
        Generate trading signal based on z-score deviation.

        Parameters
        ----------
        bars : Sequence[dict]
            List of OANDA candle dictionaries.

        Returns
        -------
        str or None
            "BUY", "SELL", or None
        """
        if not bars:
            return None

        # Extract close prices
        first = bars[0]
        if isinstance(first, (int, float, np.floating)):
            prices = np.array(bars, dtype=np.float64)
        else:
            prices = np.array([float(c["mid"]["c"]) for c in bars], dtype=np.float64)

        # Get parameters
        lookback = self.params.get("lookback", 20)
        z_threshold = self.params.get("z_threshold", 2.0)
        z_exit = self.params.get("z_exit", 0.5)
        session_filter = self.params.get("session_filter", True)

        # Need enough data
        if len(prices) < lookback + 1:
            return None

        # Session filter (optional)
        if session_filter:
            if not _is_asia_session():
                return None

        # Calculate current z-score
        z_score = _calculate_zscore(prices, lookback)

        # ------------------------------------------------------------------- #
        # Entry Logic                                                         #
        # ------------------------------------------------------------------- #
        if self._position is None:
            # Oversold: buy
            if z_score < -z_threshold:
                self._position = "BUY"
                self._entry_zscore = z_score
                self._trade_count += 1
                return "BUY"

            # Overbought: sell
            elif z_score > z_threshold:
                self._position = "SELL"
                self._entry_zscore = z_score
                self._trade_count += 1
                return "SELL"

        # ------------------------------------------------------------------- #
        # Exit Logic                                                          #
        # ------------------------------------------------------------------- #
        else:
            # Exit long when z-score returns to mean
            if self._position == "BUY":
                if z_score > -z_exit:  # Price recovered toward mean
                    self._position = None
                    return None  # Signal flat (backtest handles exit)

            # Exit short when z-score returns to mean
            elif self._position == "SELL":
                if z_score < z_exit:  # Price recovered toward mean
                    self._position = None
                    return None

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """
        Optional: Adaptive parameter adjustment based on performance.

        Parameters
        ----------
        win : bool
            True if trade was profitable, False if loss.
        pnl : float
            Profit or loss in account currency.
        """
        super().update_trade_result(win, pnl)

        # Adaptive logic: widen thresholds if losing, tighten if winning
        history = self.params.setdefault("_win_history", [])
        history.append(win)

        # Keep last 20 trades
        if len(history) > 20:
            history.pop(0)

        # Only adapt after 20 trades
        if len(history) >= 20:
            win_rate = sum(history) / len(history)

            # Win rate too low: widen entry threshold (wait for more extreme)
            if win_rate < 0.45:
                self.params["z_threshold"] = min(3.0, self.params.get("z_threshold", 2.0) + 0.1)

            # Win rate very high: can tighten threshold (take more trades)
            elif win_rate > 0.70:
                self.params["z_threshold"] = max(1.5, self.params.get("z_threshold", 2.0) - 0.1)


# ============================================================================
# Convenience Functions for External Use
# ============================================================================

def generate_signal(bars: Sequence[dict], params: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Convenience function to generate z-score reversion signal.

    Parameters
    ----------
    bars : Sequence[dict]
        List of OANDA candle dicts.
    params : dict, optional
        Strategy parameters.

    Returns
    -------
    str or None
        "BUY", "SELL", or None
    """
    strategy = StrategyZScoreReversion(params)
    return strategy.next_signal(bars)


def backtest_zscore_strategy(candles: list, params: Optional[Dict[str, Any]] = None) -> dict:
    """
    Quick backtest helper for z-score strategy.

    Parameters
    ----------
    candles : list
        OANDA historical candles.
    params : dict, optional
        Strategy parameters.

    Returns
    -------
    dict
        Backtest statistics (trades, win_rate, expectancy, etc.)
    """
    from oanda_bot.backtest import run_backtest

    strategy = StrategyZScoreReversion(params or {
        "lookback": 20,
        "z_threshold": 2.0,
        "z_exit": 0.5,
        "session_filter": True,
        "sl_mult": 2.5,
        "tp_mult": 1.5,
        "max_duration": 50,
    })

    warmup = params.get("lookback", 20) + 10 if params else 30
    stats = run_backtest(strategy, candles, warmup=warmup)

    return stats


# ============================================================================
# Optimal Parameters by Instrument (Based on Research)
# ============================================================================

OPTIMAL_PARAMS = {
    "EUR_USD": {
        "lookback": 20,
        "z_threshold": 2.0,
        "z_exit": 0.5,
        "session_filter": True,
        "sl_mult": 2.5,
        "tp_mult": 1.5,
        "max_duration": 50,
    },
    "GBP_USD": {
        "lookback": 20,
        "z_threshold": 2.5,  # More volatile, need wider threshold
        "z_exit": 0.5,
        "session_filter": True,
        "sl_mult": 3.0,
        "tp_mult": 1.8,
        "max_duration": 50,
    },
    "USD_JPY": {
        "lookback": 25,
        "z_threshold": 2.2,
        "z_exit": 0.5,
        "session_filter": True,
        "sl_mult": 2.8,
        "tp_mult": 1.6,
        "max_duration": 50,
    },
    "AUD_USD": {
        "lookback": 20,
        "z_threshold": 2.0,
        "z_exit": 0.5,
        "session_filter": True,
        "sl_mult": 2.5,
        "tp_mult": 1.5,
        "max_duration": 50,
    },
}


def get_optimal_params(instrument: str) -> Dict[str, Any]:
    """
    Get optimized parameters for specific instrument.

    Parameters
    ----------
    instrument : str
        Instrument name (e.g., "EUR_USD")

    Returns
    -------
    dict
        Optimal parameters for that instrument
    """
    return OPTIMAL_PARAMS.get(instrument, OPTIMAL_PARAMS["EUR_USD"])
