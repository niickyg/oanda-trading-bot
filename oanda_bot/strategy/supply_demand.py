"""
strategy/supply_demand.py
--------------------------

Supply and demand zone trading strategy.

This strategy identifies zones where institutional orders have previously
caused strong moves, then trades when price returns to these zones.

Key concepts:
1. Supply zones: Areas where selling pressure overwhelmed buyers (strong drops)
2. Demand zones: Areas where buying pressure overwhelmed sellers (strong rallies)
3. Fresh zones: Zones that haven't been retested (higher probability)
4. Zone strength: Based on the speed of the move away

Parameters:
    lookback: int = 50                    # Bars to look for zones
    min_zone_strength: float = 1.5        # Minimum ATR multiplier for move
    max_zone_touches: int = 1             # Max times zone can be tested
    zone_width_atr: float = 0.5           # Zone width in ATR
    sl_mult: float = 1.5                  # Stop loss multiplier
    tp_mult: float = 3.0                  # Take profit multiplier
    require_rejection: bool = True        # Require pin bar at zone
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any, List, Tuple
import numpy as np
from collections import deque

from .base import BaseStrategy


class StrategySupplyDemand(BaseStrategy):
    """
    Supply and demand zone trading strategy.

    Identifies institutional footprints and trades reversals at key zones.
    """

    name = "SupplyDemand"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})

        # Parameters
        self.lookback = int(self.params.get("lookback", 50))
        self.min_zone_strength = float(self.params.get("min_zone_strength", 1.5))
        self.max_zone_touches = int(self.params.get("max_zone_touches", 1))
        self.zone_width_atr = float(self.params.get("zone_width_atr", 0.5))
        self.sl_mult = float(self.params.get("sl_mult", 1.5))
        self.tp_mult = float(self.params.get("tp_mult", 3.0))
        self.require_rejection = bool(self.params.get("require_rejection", True))
        self.atr_period = int(self.params.get("atr_period", 14))

        # Detected zones
        self.demand_zones: List[Dict] = []  # {"low": x, "high": x, "touches": n, "strength": s}
        self.supply_zones: List[Dict] = []

        # History for zone detection
        self.ohlc_history = deque(maxlen=self.lookback + 50)

    def _extract_ohlc(self, bars: Sequence) -> Optional[np.ndarray]:
        """Extract OHLC as numpy array."""
        if not bars:
            return None

        try:
            first = bars[0]
            if isinstance(first, (int, float, np.floating)):
                closes = np.array([float(b) for b in bars])
                return np.column_stack([closes, closes, closes, closes])

            ohlc = []
            for bar in bars:
                if isinstance(bar, dict) and "mid" in bar:
                    mid = bar["mid"]
                    o = float(mid.get("o", mid.get("open", 0)))
                    h = float(mid.get("h", mid.get("high", 0)))
                    l = float(mid.get("l", mid.get("low", 0)))
                    c = float(mid.get("c", mid.get("close", 0)))
                    ohlc.append([o, h, l, c])
                else:
                    return None

            return np.array(ohlc)
        except (ValueError, TypeError, KeyError):
            return None

    def _compute_atr(self, ohlc: np.ndarray) -> float:
        """Compute ATR."""
        if len(ohlc) < self.atr_period + 1:
            return 0.0

        highs = ohlc[-self.atr_period-1:, 1]
        lows = ohlc[-self.atr_period-1:, 2]
        closes = ohlc[-self.atr_period-1:, 3]

        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )

        return float(tr.mean())

    def _is_pin_bar(self, bar: np.ndarray, direction: str) -> bool:
        """Check if bar is a pin bar in given direction."""
        o, h, l, c = bar
        body = abs(c - o)
        total_range = h - l

        if total_range == 0:
            return False

        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l

        if direction == "BUY":
            return lower_wick > body * 2.0 and body / total_range < 0.4
        elif direction == "SELL":
            return upper_wick > body * 2.0 and body / total_range < 0.4

        return False

    def _find_supply_demand_zones(self, ohlc: np.ndarray, atr: float):
        """
        Identify supply and demand zones from price history.

        A demand zone is created when:
        1. Consolidation area (narrow range)
        2. Followed by strong upward move (> min_zone_strength * ATR)
        3. Zone hasn't been tested more than max_zone_touches times

        Supply zone is opposite.
        """
        if len(ohlc) < 20 or atr == 0:
            return

        # Clear old zones
        self.demand_zones = []
        self.supply_zones = []

        # Look for zones
        for i in range(10, len(ohlc) - 5):
            # Get base area (consolidation)
            base_start = i - 5
            base_end = i
            base_bars = ohlc[base_start:base_end]
            base_high = base_bars[:, 1].max()
            base_low = base_bars[:, 2].min()
            base_range = base_high - base_low

            # Must be narrow consolidation
            if base_range > 2 * atr:
                continue

            # Check move away from base
            move_bars = ohlc[base_end:min(base_end + 10, len(ohlc))]
            if len(move_bars) == 0:
                continue

            move_high = move_bars[:, 1].max()
            move_low = move_bars[:, 2].min()

            # Demand zone (strong move up)
            up_move = move_high - base_high
            if up_move > self.min_zone_strength * atr:
                # Count how many times this zone has been touched
                touches = self._count_zone_touches(ohlc[i:], base_low, base_high)

                if touches <= self.max_zone_touches:
                    strength = up_move / atr
                    zone = {
                        "low": base_low,
                        "high": base_high,
                        "touches": touches,
                        "strength": strength,
                        "bar_index": i
                    }
                    self.demand_zones.append(zone)

            # Supply zone (strong move down)
            down_move = base_low - move_low
            if down_move > self.min_zone_strength * atr:
                touches = self._count_zone_touches(ohlc[i:], base_low, base_high)

                if touches <= self.max_zone_touches:
                    strength = down_move / atr
                    zone = {
                        "low": base_low,
                        "high": base_high,
                        "touches": touches,
                        "strength": strength,
                        "bar_index": i
                    }
                    self.supply_zones.append(zone)

        # Keep only strongest zones
        self.demand_zones = sorted(
            self.demand_zones,
            key=lambda z: z["strength"],
            reverse=True
        )[:5]

        self.supply_zones = sorted(
            self.supply_zones,
            key=lambda z: z["strength"],
            reverse=True
        )[:5]

    def _count_zone_touches(self, ohlc: np.ndarray, zone_low: float, zone_high: float) -> int:
        """Count how many times price has touched this zone."""
        touches = 0
        for bar in ohlc:
            h, l = bar[1], bar[2]
            if l <= zone_high and h >= zone_low:
                touches += 1
        return touches

    def _in_zone(self, price: float, zone: Dict) -> bool:
        """Check if price is within zone."""
        return zone["low"] <= price <= zone["high"]

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """Generate trading signal based on supply/demand zones."""
        ohlc = self._extract_ohlc(bars)
        if ohlc is None or len(ohlc) < self.lookback:
            return None

        # Update history
        self.ohlc_history.extend(ohlc)

        atr = self._compute_atr(ohlc)
        if atr == 0:
            return None

        # Find zones
        self._find_supply_demand_zones(ohlc, atr)

        current_bar = ohlc[-1]
        current_close = current_bar[3]
        current_low = current_bar[2]
        current_high = current_bar[1]

        # Check for demand zone entry (BUY)
        for zone in self.demand_zones:
            if self._in_zone(current_low, zone) or self._in_zone(current_close, zone):
                # If we require rejection, check for pin bar
                if self.require_rejection:
                    if self._is_pin_bar(current_bar, "BUY"):
                        # Strong demand zone with rejection
                        return "BUY"
                else:
                    # Enter on touch
                    return "BUY"

        # Check for supply zone entry (SELL)
        for zone in self.supply_zones:
            if self._in_zone(current_high, zone) or self._in_zone(current_close, zone):
                if self.require_rejection:
                    if self._is_pin_bar(current_bar, "SELL"):
                        return "SELL"
                else:
                    return "SELL"

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Track performance."""
        super().update_trade_result(win, pnl)

        history = self.params.setdefault("_history", [])
        history.append({"win": win, "pnl": pnl})

        if len(history) > 30:
            history.pop(0)

        # Adaptive zone strength requirement
        if len(history) >= 20:
            recent = history[-20:]
            win_rate = sum(1 for h in recent if h["win"]) / 20

            if win_rate < 0.45:
                # Be more selective
                self.min_zone_strength = min(2.5, self.min_zone_strength + 0.1)
                self.max_zone_touches = max(0, self.max_zone_touches - 1)
            elif win_rate > 0.65:
                # Can be less restrictive
                self.min_zone_strength = max(1.2, self.min_zone_strength - 0.05)
                self.max_zone_touches = min(2, self.max_zone_touches + 1)


def compute_atr(bars, period: int = 14) -> float:
    """Compute ATR for stop/target placement."""
    if len(bars) < period + 1:
        return 0.0

    try:
        ohlc = []
        for bar in bars[-period-1:]:
            if isinstance(bar, (int, float)):
                return 0.0

            if isinstance(bar, dict) and "mid" in bar:
                mid = bar["mid"]
                h = float(mid.get("h", mid.get("high", 0)))
                l = float(mid.get("l", mid.get("low", 0)))
                c = float(mid.get("c", mid.get("close", 0)))
                ohlc.append([h, l, c])

        ohlc = np.array(ohlc)
        highs = ohlc[:, 0]
        lows = ohlc[:, 1]
        closes = ohlc[:, 2]

        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )

        return float(tr.mean())

    except (ValueError, TypeError, KeyError):
        return 0.0


def sl_tp_levels(bars, side: str, params=None):
    """Calculate stop loss and take profit based on ATR."""
    params = params or {}
    atr_period = params.get("atr_period", 14)
    sl_mult = params.get("sl_mult", 1.5)
    tp_mult = params.get("tp_mult", 3.0)

    atr = compute_atr(bars, period=atr_period)

    last_bar = bars[-1]
    if isinstance(last_bar, (int, float)):
        price = float(last_bar)
    elif isinstance(last_bar, dict) and "mid" in last_bar:
        price = float(last_bar["mid"]["c"])
    else:
        price = 0.0

    if price == 0 or atr == 0:
        if side == "BUY":
            return price * 0.999, price * 1.002
        else:
            return price * 1.001, price * 0.998

    if side == "BUY":
        return (
            price - sl_mult * atr,
            price + tp_mult * atr
        )
    elif side == "SELL":
        return (
            price + sl_mult * atr,
            price - tp_mult * atr
        )
    else:
        raise ValueError("side must be 'BUY' or 'SELL'")
