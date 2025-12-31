"""
strategy/micro_reversion.py
---------------------------

Microstructure mean reversion strategy for 2-second bars.

This strategy exploits:
1. Price overextension from short-term mean
2. Rapid price moves that typically revert
3. Bollinger Band touches on micro timeframe

The key insight: On 2-second bars, extreme moves often revert within
30-60 seconds as market makers provide liquidity.

Parameters:
    lookback: int = 20            # Bars for mean calculation
    std_mult: float = 2.5         # Standard deviations for entry
    min_extension: float = 1.5    # Minimum ATR extension for entry
    profit_target_std: float = 1.0  # TP at this many std from entry
    stop_loss_std: float = 1.5      # SL at this many std from entry
    max_hold_bars: int = 30         # Time exit (60 seconds)
    cooldown_bars: int = 10         # Cooldown between trades
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any
from collections import deque
import numpy as np

from .base import BaseStrategy


class StrategyMicroReversion(BaseStrategy):
    """
    Mean reversion strategy for micro-timeframe trading.

    Fades extreme price extensions expecting quick reversion.
    """

    name = "MicroReversion"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})

        # Parameters
        self.lookback = int(self.params.get("lookback", 20))
        self.std_mult = float(self.params.get("std_mult", 2.5))
        self.min_extension = float(self.params.get("min_extension", 1.5))
        self.profit_target_std = float(self.params.get("profit_target_std", 1.0))
        self.stop_loss_std = float(self.params.get("stop_loss_std", 1.5))
        self.max_hold_bars = int(self.params.get("max_hold_bars", 30))
        self.cooldown_bars = int(self.params.get("cooldown_bars", 10))

        # Price history
        self.prices: deque = deque(maxlen=100)
        self.highs: deque = deque(maxlen=100)
        self.lows: deque = deque(maxlen=100)

        # State
        self._position: int = 0
        self._entry_price: float = 0.0
        self._entry_mean: float = 0.0
        self._entry_std: float = 0.0
        self._bars_in_position: int = 0
        self._cooldown: int = 0
        self._bar_count: int = 0

    def _extract_price(self, bar) -> Optional[Dict[str, float]]:
        """Extract OHLC from bar."""
        try:
            if isinstance(bar, (int, float)):
                return {"open": float(bar), "high": float(bar),
                        "low": float(bar), "close": float(bar)}

            if isinstance(bar, dict):
                if "mid" in bar and isinstance(bar["mid"], dict):
                    mid = bar["mid"]
                    return {
                        "open": float(mid.get("o", mid.get("open", 0))),
                        "high": float(mid.get("h", mid.get("high", 0))),
                        "low": float(mid.get("l", mid.get("low", 0))),
                        "close": float(mid.get("c", mid.get("close", 0)))
                    }
                if "close" in bar or "c" in bar:
                    return {
                        "open": float(bar.get("open", bar.get("o", 0))),
                        "high": float(bar.get("high", bar.get("h", 0))),
                        "low": float(bar.get("low", bar.get("l", 0))),
                        "close": float(bar.get("close", bar.get("c", 0)))
                    }

            if isinstance(bar, (list, tuple)) and len(bar) >= 4:
                if len(bar) == 4:
                    o, h, l, c = bar
                else:
                    _, o, h, l, c = bar[:5]
                return {"open": float(o), "high": float(h),
                        "low": float(l), "close": float(c)}
        except (TypeError, ValueError):
            pass
        return None

    def _compute_stats(self) -> tuple[float, float, float]:
        """Compute mean, std, and ATR."""
        if len(self.prices) < self.lookback:
            return 0.0, 0.0, 0.0

        prices = list(self.prices)[-self.lookback:]
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std = variance ** 0.5

        # Compute ATR
        if len(self.prices) < self.lookback + 1:
            return mean, std, std

        trs = []
        all_prices = list(self.prices)
        all_highs = list(self.highs)
        all_lows = list(self.lows)

        for i in range(-self.lookback, 0):
            if i - 1 < -len(all_prices):
                continue
            h = all_highs[i]
            l = all_lows[i]
            prev_c = all_prices[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)

        atr = sum(trs) / len(trs) if trs else std

        return mean, std, atr

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """Generate mean reversion signal."""
        if not bars:
            return None

        self._bar_count += 1
        if self._cooldown > 0:
            self._cooldown -= 1

        ohlc = self._extract_price(bars[-1])
        if not ohlc or ohlc["close"] == 0:
            return None

        current_price = ohlc["close"]

        # Update history
        self.prices.append(current_price)
        self.highs.append(ohlc["high"])
        self.lows.append(ohlc["low"])

        # Need enough data
        if len(self.prices) < self.lookback + 1:
            return None

        mean, std, atr = self._compute_stats()
        if std <= 0 or atr <= 0:
            return None

        # Position management
        if self._position != 0:
            self._bars_in_position += 1

            # Calculate distance from entry mean (target mean reversion)
            distance_from_mean = (current_price - self._entry_mean) / self._entry_std

            # For long position, profit when price goes up toward/above mean
            # For short position, profit when price goes down toward/below mean
            pnl_direction = (current_price - self._entry_price) * self._position

            # Take profit - reverted toward mean
            if self._position == 1 and current_price >= self._entry_mean - self.profit_target_std * self._entry_std:
                self._reset_position()
                return "SELL"

            if self._position == -1 and current_price <= self._entry_mean + self.profit_target_std * self._entry_std:
                self._reset_position()
                return "BUY"

            # Stop loss - extended further from mean
            if self._position == 1 and current_price < self._entry_price - self.stop_loss_std * self._entry_std:
                self._reset_position()
                return "SELL"

            if self._position == -1 and current_price > self._entry_price + self.stop_loss_std * self._entry_std:
                self._reset_position()
                return "BUY"

            # Time exit
            if self._bars_in_position >= self.max_hold_bars:
                side = "SELL" if self._position > 0 else "BUY"
                self._reset_position()
                return side

            return None

        # Entry logic
        if self._cooldown > 0:
            return None

        # Calculate z-score (how many std from mean)
        z_score = (current_price - mean) / std

        # Check for sufficient extension from ATR perspective
        extension = abs(current_price - mean) / atr

        # Oversold - go long
        if z_score < -self.std_mult and extension >= self.min_extension:
            self._position = 1
            self._entry_price = current_price
            self._entry_mean = mean
            self._entry_std = std
            self._bars_in_position = 0
            return "BUY"

        # Overbought - go short
        if z_score > self.std_mult and extension >= self.min_extension:
            self._position = -1
            self._entry_price = current_price
            self._entry_mean = mean
            self._entry_std = std
            self._bars_in_position = 0
            return "SELL"

        return None

    def _reset_position(self):
        """Reset position state."""
        self._position = 0
        self._entry_price = 0.0
        self._entry_mean = 0.0
        self._entry_std = 0.0
        self._bars_in_position = 0
        self._cooldown = self.cooldown_bars

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Track results and adapt."""
        super().update_trade_result(win, pnl)

        history = self.params.setdefault("_history", [])
        history.append({"win": win, "pnl": pnl})

        if len(history) > 50:
            history.pop(0)

        # Adaptive std multiplier
        if len(history) >= 20:
            recent = history[-20:]
            win_rate = sum(1 for h in recent if h["win"]) / 20

            if win_rate < 0.4:
                # Be more selective on entries
                self.std_mult = min(3.5, self.std_mult + 0.1)
                self.min_extension = min(2.5, self.min_extension + 0.1)
            elif win_rate > 0.6:
                # Can be less restrictive
                self.std_mult = max(2.0, self.std_mult - 0.05)
                self.min_extension = max(1.0, self.min_extension - 0.05)
