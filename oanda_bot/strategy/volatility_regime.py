"""
strategy/volatility_regime.py
------------------------------

Volatility regime-based trading strategy exploiting:
1. Volatility clustering (GARCH effects)
2. Volatility breakouts from low-vol regimes
3. Mean reversion after extreme volatility spikes
4. Realized vs expected volatility divergence

Edge: Low volatility periods cluster together and predict upcoming high volatility.
When volatility breaks out from a low regime, momentum follows. When volatility
spikes to extremes, mean reversion occurs.

Parameters::
    {
        "lookback": 100,              # Lookback for volatility calculation
        "vol_window": 20,             # Rolling window for volatility regime
        "regime_threshold": 1.5,      # Std devs for regime classification
        "breakout_mult": 2.0,         # Multiple of recent vol for breakout
        "spike_mult": 3.0,            # Multiple of recent vol for extreme spike
        "mean_revert_mult": 0.5,      # Target reversion level
        "atr_period": 14,             # ATR period for stop/target
        "stop_loss_atr": 2.0,         # Stop loss in ATR multiples
        "profit_target_atr": 3.0,     # Profit target in ATR multiples
        "max_hold_bars": 50,          # Maximum hold period
        "min_vol_ratio": 0.3,         # Minimum volatility ratio to trade
    }
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any
import numpy as np
from .base import BaseStrategy


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Calculate Average True Range."""
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    tr = np.maximum(np.maximum(tr1, tr2), tr3)
    tr[:period] = 0

    # Simple moving average of TR
    atr = np.zeros_like(tr)
    atr[period-1] = tr[:period].mean()
    alpha = 1.0 / period
    for i in range(period, len(tr)):
        atr[i] = (1 - alpha) * atr[i-1] + alpha * tr[i]

    return atr


def _realized_volatility(returns: np.ndarray, window: int) -> np.ndarray:
    """Calculate realized volatility (rolling std of returns)."""
    vol = np.zeros(len(returns))
    for i in range(window, len(returns)):
        vol[i] = np.std(returns[i-window:i])
    return vol


def _garch_regime(vol: np.ndarray, lookback: int) -> tuple:
    """
    Identify volatility regime using GARCH-like approach.
    Returns (current_regime, vol_zscore, vol_percentile)

    Regimes:
    - LOW: volatility < -1 std
    - NORMAL: -1 std <= volatility <= 1 std
    - HIGH: volatility > 1 std
    - EXTREME: volatility > 2 std
    """
    if len(vol) < lookback:
        return "NORMAL", 0.0, 0.5

    recent_vol = vol[-lookback:]
    current_vol = vol[-1]

    mean_vol = np.mean(recent_vol)
    std_vol = np.std(recent_vol)

    if std_vol == 0:
        return "NORMAL", 0.0, 0.5

    # Z-score
    vol_zscore = (current_vol - mean_vol) / std_vol

    # Percentile
    vol_percentile = np.sum(recent_vol < current_vol) / len(recent_vol)

    # Classify regime
    if vol_zscore > 2.0:
        regime = "EXTREME"
    elif vol_zscore > 1.0:
        regime = "HIGH"
    elif vol_zscore < -1.0:
        regime = "LOW"
    else:
        regime = "NORMAL"

    return regime, vol_zscore, vol_percentile


def _volatility_clustering_score(vol: np.ndarray, window: int = 10) -> float:
    """
    Measure volatility clustering using autocorrelation.
    High scores indicate strong clustering (volatility persistence).
    """
    if len(vol) < window * 2:
        return 0.0

    recent = vol[-window*2:-window]
    current = vol[-window:]

    if len(recent) == 0 or len(current) == 0:
        return 0.0

    # Simple correlation between recent and current volatility
    mean_recent = np.mean(recent)
    mean_current = np.mean(current)

    if np.std(recent) == 0 or np.std(current) == 0:
        return 0.0

    correlation = np.corrcoef(recent, current)[0, 1] if len(recent) == len(current) else 0.0

    return correlation if not np.isnan(correlation) else 0.0


class StrategyVolatilityRegime(BaseStrategy):
    """
    Volatility regime trading strategy.

    Entry Logic:
    1. BREAKOUT: Enter in direction of price move when vol breaks from LOW regime
    2. MEAN_REVERT: Fade extreme volatility spikes (counter-trend)
    3. REGIME_SHIFT: Enter when transitioning from LOW to HIGH volatility

    Exit Logic:
    - Profit target: N x ATR
    - Stop loss: M x ATR
    - Time-based: Max hold period
    - Regime reversal: Exit if regime changes against position
    """

    name = "VolatilityRegime"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})
        self._position = 0  # 1=long, -1=short, 0=flat
        self._entry_regime = None
        self._entry_price = None
        self._entry_idx = 0
        self._last_regime = "NORMAL"
        self._regime_history = []

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        if not bars:
            return None

        # Extract OHLC data
        first = bars[0]
        if isinstance(first, (int, float, np.floating)):
            prices = np.array(bars, dtype=np.float64)
            high = low = close = prices
        else:
            high = np.array([float(c["mid"]["h"]) for c in bars], dtype=np.float64)
            low = np.array([float(c["mid"]["l"]) for c in bars], dtype=np.float64)
            close = np.array([float(c["mid"]["c"]) for c in bars], dtype=np.float64)

        # Get parameters
        lookback = self.params.get("lookback", 100)
        vol_window = self.params.get("vol_window", 20)
        regime_threshold = self.params.get("regime_threshold", 1.5)
        breakout_mult = self.params.get("breakout_mult", 2.0)
        spike_mult = self.params.get("spike_mult", 3.0)
        atr_period = self.params.get("atr_period", 14)
        min_vol_ratio = self.params.get("min_vol_ratio", 0.3)

        if len(close) < lookback:
            return None

        # Calculate returns
        returns = np.diff(close) / close[:-1]
        returns = np.concatenate([[0], returns])

        # Calculate realized volatility
        vol = _realized_volatility(returns, vol_window)

        # Calculate ATR
        atr = _atr(high, low, close, atr_period)
        current_atr = atr[-1]

        if current_atr == 0 or vol[-1] == 0:
            return None

        # Identify current regime
        regime, vol_zscore, vol_percentile = _garch_regime(vol, lookback)

        # Track regime history
        self._regime_history.append(regime)
        if len(self._regime_history) > 50:
            self._regime_history.pop(0)

        # Calculate volatility clustering score
        clustering_score = _volatility_clustering_score(vol, window=10)

        # Recent price momentum
        momentum = (close[-1] - close[-5]) / close[-5] if len(close) >= 5 else 0

        # Volatility ratio (current vs recent average)
        avg_vol = np.mean(vol[-vol_window:]) if len(vol) >= vol_window else vol[-1]
        vol_ratio = vol[-1] / avg_vol if avg_vol > 0 else 1.0

        # Don't trade in extremely low volatility (likely to be noise)
        if vol_ratio < min_vol_ratio:
            return None

        # --- ENTRY SIGNALS ---
        if self._position == 0:

            # STRATEGY 1: Volatility Breakout from Low Regime
            # When vol breaks out from LOW regime with strong momentum
            if (self._last_regime == "LOW" and regime in ["HIGH", "EXTREME"] and
                vol_ratio > breakout_mult):

                # Enter in direction of momentum
                if momentum > 0:
                    self._position = 1
                    self._entry_regime = regime
                    self._entry_price = close[-1]
                    return "BUY"
                elif momentum < 0:
                    self._position = -1
                    self._entry_regime = regime
                    self._entry_price = close[-1]
                    return "SELL"

            # STRATEGY 2: Mean Reversion from Extreme Volatility Spike
            # Fade extreme volatility spikes (counter-trend)
            elif regime == "EXTREME" and vol_ratio > spike_mult:

                # Fade the recent move (mean reversion)
                if momentum > 0:
                    self._position = -1  # Fade upward spike
                    self._entry_regime = regime
                    self._entry_price = close[-1]
                    return "SELL"
                elif momentum < 0:
                    self._position = 1  # Fade downward spike
                    self._entry_regime = regime
                    self._entry_price = close[-1]
                    return "BUY"

            # STRATEGY 3: Regime Transition Trading
            # Enter when transitioning from NORMAL to HIGH with clustering
            elif (self._last_regime in ["NORMAL", "LOW"] and regime == "HIGH" and
                  clustering_score > 0.3 and vol_ratio > 1.2):

                # Enter with momentum
                if momentum > 0:
                    self._position = 1
                    self._entry_regime = regime
                    self._entry_price = close[-1]
                    return "BUY"
                elif momentum < 0:
                    self._position = -1
                    self._entry_regime = regime
                    self._entry_price = close[-1]
                    return "SELL"

        # --- EXIT SIGNALS ---
        elif self._position != 0:

            # Exit if regime reverses (e.g., from HIGH back to LOW)
            # This suggests the volatility edge has dissipated
            if self._entry_regime in ["HIGH", "EXTREME"] and regime == "LOW":
                self._position = 0
                self._entry_regime = None
                return "SELL" if self._position == 1 else "BUY"

            # Exit mean reversion trades when volatility normalizes
            if self._entry_regime == "EXTREME" and regime in ["NORMAL", "LOW"]:
                self._position = 0
                self._entry_regime = None
                return "SELL" if self._position == 1 else "BUY"

        # Update regime tracking
        self._last_regime = regime

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """
        Adaptive parameter adjustment based on performance.
        If strategy is losing, adjust thresholds to be more conservative.
        """
        super().update_trade_result(win, pnl)

        history = self.params.setdefault("_trade_history", [])
        history.append({"win": win, "pnl": pnl})

        # Keep last 30 trades
        if len(history) > 30:
            history.pop(0)

        # Adjust parameters based on recent performance
        if len(history) >= 20:
            recent_wins = sum(1 for t in history[-20:] if t["win"])
            win_rate = recent_wins / 20

            # If losing, tighten entry criteria
            if win_rate < 0.4:
                self.params["breakout_mult"] = min(3.0, self.params.get("breakout_mult", 2.0) + 0.1)
                self.params["spike_mult"] = min(4.0, self.params.get("spike_mult", 3.0) + 0.1)
                self.params["min_vol_ratio"] = min(0.5, self.params.get("min_vol_ratio", 0.3) + 0.05)

            # If winning, can be slightly more aggressive
            elif win_rate > 0.6:
                self.params["breakout_mult"] = max(1.5, self.params.get("breakout_mult", 2.0) - 0.05)
                self.params["spike_mult"] = max(2.5, self.params.get("spike_mult", 3.0) - 0.05)
