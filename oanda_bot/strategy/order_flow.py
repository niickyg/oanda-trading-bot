"""
strategy/order_flow.py
----------------------

Order flow imbalance strategy for forex scalping.

This strategy detects:
1. Aggressive buying/selling pressure from tick data
2. Spread widening as a volatility signal
3. Price rejection patterns (wicks)

Key edge: When many ticks move in one direction quickly, it signals
aggressive order flow that often continues short-term.

Parameters:
    tick_window: int = 10         # Recent ticks to analyze
    imbalance_threshold: float = 0.7  # Min % of ticks in one direction
    min_tick_count: int = 5       # Min ticks in window to generate signal
    wick_ratio: float = 0.6       # Wick size as % of bar for rejection
    profit_target_pips: float = 3.0   # TP in pips
    stop_loss_pips: float = 2.0       # SL in pips
    max_spread_pips: float = 2.0      # Max spread to trade
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any, List
from collections import deque
import numpy as np

from .base import BaseStrategy


class StrategyOrderFlow(BaseStrategy):
    """
    Order flow imbalance strategy.

    Detects aggressive buying/selling and trades in direction of flow.
    """

    name = "OrderFlow"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})

        # Parameters
        self.tick_window = int(self.params.get("tick_window", 10))
        self.imbalance_threshold = float(self.params.get("imbalance_threshold", 0.7))
        self.min_tick_count = int(self.params.get("min_tick_count", 5))
        self.wick_ratio = float(self.params.get("wick_ratio", 0.6))
        self.profit_target_pips = float(self.params.get("profit_target_pips", 3.0))
        self.stop_loss_pips = float(self.params.get("stop_loss_pips", 2.0))
        self.max_spread_pips = float(self.params.get("max_spread_pips", 2.0))

        # Price history for tick analysis
        self.tick_prices: deque = deque(maxlen=50)
        self.tick_directions: deque = deque(maxlen=50)  # 1=up, -1=down, 0=unchanged
        self.spreads: deque = deque(maxlen=20)

        # Bar data for wick analysis
        self.bars: deque = deque(maxlen=20)

        # State
        self._position: int = 0
        self._entry_price: float = 0.0
        self._pip_size: float = 0.0001
        self._cooldown: int = 0
        self._bar_count: int = 0

    def _extract_ohlc(self, bar) -> Optional[Dict[str, float]]:
        """Extract OHLC from various bar formats."""
        try:
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
            if isinstance(bar, (int, float)):
                return {"open": float(bar), "high": float(bar),
                        "low": float(bar), "close": float(bar)}
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

    def _analyze_tick_flow(self) -> tuple[float, int]:
        """
        Analyze recent tick flow.
        Returns (imbalance_ratio, dominant_direction).
        imbalance_ratio: 0-1, where 1 = all ticks in same direction
        dominant_direction: 1=bullish, -1=bearish, 0=neutral
        """
        if len(self.tick_directions) < self.min_tick_count:
            return 0.0, 0

        recent = list(self.tick_directions)[-self.tick_window:]
        if not recent:
            return 0.0, 0

        up_count = sum(1 for d in recent if d > 0)
        down_count = sum(1 for d in recent if d < 0)
        total = len(recent)

        if total == 0:
            return 0.0, 0

        up_ratio = up_count / total
        down_ratio = down_count / total

        if up_ratio > down_ratio:
            return up_ratio, 1
        elif down_ratio > up_ratio:
            return down_ratio, -1
        else:
            return 0.0, 0

    def _detect_wick_rejection(self, bar: Dict[str, float]) -> int:
        """
        Detect price rejection via wicks.
        Returns: 1 for bullish rejection (long wick down), -1 for bearish, 0 for none
        """
        if not bar:
            return 0

        o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]
        bar_range = h - l

        if bar_range == 0:
            return 0

        body_top = max(o, c)
        body_bottom = min(o, c)

        upper_wick = h - body_top
        lower_wick = body_bottom - l

        upper_wick_ratio = upper_wick / bar_range
        lower_wick_ratio = lower_wick / bar_range

        # Long lower wick = bullish rejection
        if lower_wick_ratio >= self.wick_ratio and lower_wick > upper_wick:
            return 1

        # Long upper wick = bearish rejection
        if upper_wick_ratio >= self.wick_ratio and upper_wick > lower_wick:
            return -1

        return 0

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """Generate signal based on order flow analysis."""
        if not bars:
            return None

        self._bar_count += 1
        if self._cooldown > 0:
            self._cooldown -= 1

        # Extract current bar
        ohlc = self._extract_ohlc(bars[-1])
        if not ohlc or ohlc["close"] == 0:
            return None

        current_price = ohlc["close"]

        # Detect pip size from instrument (if available)
        if len(bars) > 0 and isinstance(bars[-1], dict):
            instrument = bars[-1].get("instrument", "")
            self._pip_size = 0.01 if "JPY" in instrument else 0.0001

        # Track tick direction
        if len(self.tick_prices) > 0:
            prev_price = self.tick_prices[-1]
            if current_price > prev_price:
                self.tick_directions.append(1)
            elif current_price < prev_price:
                self.tick_directions.append(-1)
            else:
                self.tick_directions.append(0)

        self.tick_prices.append(current_price)
        self.bars.append(ohlc)

        # Position management
        if self._position != 0:
            pnl_pips = (current_price - self._entry_price) * self._position / self._pip_size

            # Take profit
            if pnl_pips >= self.profit_target_pips:
                side = "SELL" if self._position > 0 else "BUY"
                self._position = 0
                self._entry_price = 0
                self._cooldown = 5
                return side

            # Stop loss
            if pnl_pips <= -self.stop_loss_pips:
                side = "SELL" if self._position > 0 else "BUY"
                self._position = 0
                self._entry_price = 0
                self._cooldown = 5
                return side

            return None

        # Entry logic
        if self._cooldown > 0:
            return None

        # Analyze order flow
        imbalance, direction = self._analyze_tick_flow()

        # Check for wick rejection confirmation
        wick_signal = self._detect_wick_rejection(ohlc) if ohlc else 0

        # Strong order flow imbalance
        if imbalance >= self.imbalance_threshold:
            if direction == 1:
                # Strong buying flow - go long
                self._position = 1
                self._entry_price = current_price
                return "BUY"
            elif direction == -1:
                # Strong selling flow - go short
                self._position = -1
                self._entry_price = current_price
                return "SELL"

        # Wick rejection with moderate flow confirmation
        if abs(wick_signal) > 0 and imbalance >= 0.5 and direction == wick_signal:
            if wick_signal == 1:
                self._position = 1
                self._entry_price = current_price
                return "BUY"
            elif wick_signal == -1:
                self._position = -1
                self._entry_price = current_price
                return "SELL"

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Track results for adaptation."""
        super().update_trade_result(win, pnl)

        history = self.params.setdefault("_results", [])
        history.append(win)

        if len(history) > 30:
            history.pop(0)

        # Adapt imbalance threshold
        if len(history) >= 20:
            win_rate = sum(history[-20:]) / 20
            if win_rate < 0.45:
                self.imbalance_threshold = min(0.85, self.imbalance_threshold + 0.02)
            elif win_rate > 0.6:
                self.imbalance_threshold = max(0.6, self.imbalance_threshold - 0.01)
