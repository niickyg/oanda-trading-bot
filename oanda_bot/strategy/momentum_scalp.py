"""
strategy/momentum_scalp.py
--------------------------

High-frequency momentum scalping strategy optimized for 2-second bars.

This strategy exploits:
1. Short-term momentum bursts (price acceleration)
2. Volume-weighted price moves
3. Quick mean reversion after overextension

Designed to overcome OANDA spread costs (1-2 pips) by:
- Only trading when momentum is strong (>2x ATR move)
- Using tight time-based exits (max 30 bars = 1 minute)
- Targeting 1.5:1 reward-to-risk minimum

Parameters:
    momentum_period: int = 5      # Bars to measure momentum
    atr_period: int = 20          # ATR lookback
    momentum_threshold: float = 2.0  # Multiple of ATR for entry
    profit_target_atr: float = 1.5   # TP as multiple of ATR
    stop_loss_atr: float = 1.0       # SL as multiple of ATR
    max_hold_bars: int = 30          # Max bars before time exit
    cooldown_bars: int = 10          # Min bars between trades
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any, List
from collections import deque
import numpy as np

from .base import BaseStrategy


class StrategyMomentumScalp(BaseStrategy):
    """
    Momentum scalping strategy for micro-timeframes.

    Enters on strong momentum bursts, exits quickly on profit target or stop.
    """

    name = "MomentumScalp"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})

        # Strategy parameters
        self.momentum_period = int(self.params.get("momentum_period", 5))
        self.atr_period = int(self.params.get("atr_period", 20))
        self.momentum_threshold = float(self.params.get("momentum_threshold", 2.0))
        self.profit_target_atr = float(self.params.get("profit_target_atr", 1.5))
        self.stop_loss_atr = float(self.params.get("stop_loss_atr", 1.0))
        self.max_hold_bars = int(self.params.get("max_hold_bars", 30))
        self.cooldown_bars = int(self.params.get("cooldown_bars", 10))

        # Price history
        self.prices: deque = deque(maxlen=100)
        self.highs: deque = deque(maxlen=100)
        self.lows: deque = deque(maxlen=100)

        # State tracking
        self._position: int = 0  # 1=long, -1=short, 0=flat
        self._entry_price: float = 0.0
        self._entry_bar: int = 0
        self._bars_since_entry: int = 0
        self._bars_since_exit: int = 0
        self._bar_count: int = 0

    def _extract_price(self, bar) -> Optional[Dict[str, float]]:
        """Extract OHLC prices from various bar formats."""
        try:
            if isinstance(bar, (int, float)):
                return {"open": float(bar), "high": float(bar),
                        "low": float(bar), "close": float(bar)}

            if isinstance(bar, dict):
                # OANDA nested format
                if "mid" in bar and isinstance(bar["mid"], dict):
                    mid = bar["mid"]
                    return {
                        "open": float(mid.get("o", mid.get("open", 0))),
                        "high": float(mid.get("h", mid.get("high", 0))),
                        "low": float(mid.get("l", mid.get("low", 0))),
                        "close": float(mid.get("c", mid.get("close", 0)))
                    }
                # Flat format
                if "close" in bar or "c" in bar:
                    return {
                        "open": float(bar.get("open", bar.get("o", 0))),
                        "high": float(bar.get("high", bar.get("h", 0))),
                        "low": float(bar.get("low", bar.get("l", 0))),
                        "close": float(bar.get("close", bar.get("c", 0)))
                    }

            # Tuple format
            if isinstance(bar, (list, tuple)):
                if len(bar) >= 4:
                    if len(bar) == 4:
                        o, h, l, c = bar
                    elif len(bar) >= 5:
                        _, o, h, l, c = bar[:5]
                    return {"open": float(o), "high": float(h),
                            "low": float(l), "close": float(c)}
        except (TypeError, ValueError, KeyError):
            pass
        return None

    def _compute_atr(self) -> float:
        """Calculate ATR from price history."""
        if len(self.prices) < self.atr_period + 1:
            return 0.0

        trs = []
        prices = list(self.prices)
        highs = list(self.highs)
        lows = list(self.lows)

        for i in range(-self.atr_period, 0):
            h = highs[i]
            l = lows[i]
            prev_c = prices[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)

        return sum(trs) / len(trs) if trs else 0.0

    def _compute_momentum(self) -> float:
        """Calculate momentum as price change over momentum_period."""
        if len(self.prices) < self.momentum_period + 1:
            return 0.0

        prices = list(self.prices)
        return prices[-1] - prices[-self.momentum_period - 1]

    def _compute_momentum_acceleration(self) -> float:
        """Calculate momentum acceleration (second derivative)."""
        if len(self.prices) < self.momentum_period * 2 + 1:
            return 0.0

        prices = list(self.prices)
        current_momentum = prices[-1] - prices[-self.momentum_period - 1]
        prev_momentum = prices[-self.momentum_period - 1] - prices[-self.momentum_period * 2 - 1]

        return current_momentum - prev_momentum

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """Generate trading signal based on momentum."""
        if not bars:
            return None

        # Extract latest bar data
        ohlc = self._extract_price(bars[-1])
        if not ohlc or ohlc["close"] == 0:
            return None

        self._bar_count += 1
        self._bars_since_exit += 1

        # Update price history
        self.prices.append(ohlc["close"])
        self.highs.append(ohlc["high"])
        self.lows.append(ohlc["low"])

        # Need enough data
        if len(self.prices) < max(self.atr_period, self.momentum_period * 2) + 1:
            return None

        atr = self._compute_atr()
        if atr <= 0:
            return None

        current_price = ohlc["close"]

        # Position management
        if self._position != 0:
            self._bars_since_entry += 1

            # Check exit conditions
            pnl = (current_price - self._entry_price) * self._position

            # Take profit
            if pnl >= atr * self.profit_target_atr:
                side = "SELL" if self._position > 0 else "BUY"
                self._reset_position()
                return side

            # Stop loss
            if pnl <= -atr * self.stop_loss_atr:
                side = "SELL" if self._position > 0 else "BUY"
                self._reset_position()
                return side

            # Time exit
            if self._bars_since_entry >= self.max_hold_bars:
                side = "SELL" if self._position > 0 else "BUY"
                self._reset_position()
                return side

            return None

        # Entry logic - only if not in cooldown
        if self._bars_since_exit < self.cooldown_bars:
            return None

        momentum = self._compute_momentum()
        momentum_accel = self._compute_momentum_acceleration()

        # Strong momentum signal with acceleration
        momentum_strength = abs(momentum) / atr

        if momentum_strength >= self.momentum_threshold:
            # Momentum burst detected
            if momentum > 0 and momentum_accel > 0:
                # Bullish momentum with acceleration - go long
                self._position = 1
                self._entry_price = current_price
                self._entry_bar = self._bar_count
                self._bars_since_entry = 0
                return "BUY"

            elif momentum < 0 and momentum_accel < 0:
                # Bearish momentum with acceleration - go short
                self._position = -1
                self._entry_price = current_price
                self._entry_bar = self._bar_count
                self._bars_since_entry = 0
                return "SELL"

        return None

    def _reset_position(self):
        """Reset position state after exit."""
        self._position = 0
        self._entry_price = 0.0
        self._bars_since_entry = 0
        self._bars_since_exit = 0

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Track trade results for adaptive behavior."""
        super().update_trade_result(win, pnl)

        # Adaptive parameter adjustment
        history = self.params.setdefault("_trade_history", [])
        history.append({"win": win, "pnl": pnl})

        if len(history) > 50:
            history.pop(0)

        # Adjust momentum threshold based on win rate
        if len(history) >= 20:
            recent_wins = sum(1 for t in history[-20:] if t["win"])
            win_rate = recent_wins / 20

            if win_rate < 0.4:
                # Too many losses - be more selective
                self.momentum_threshold = min(3.5, self.momentum_threshold + 0.1)
            elif win_rate > 0.65:
                # Strong performance - can be slightly less selective
                self.momentum_threshold = max(1.5, self.momentum_threshold - 0.05)
