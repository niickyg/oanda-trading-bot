"""
strategy/price_action.py
-------------------------

Pure price action strategies based on candlestick patterns and market structure.

This module implements:
1. Pin bar/hammer patterns
2. Engulfing patterns
3. Support/resistance breakouts and retests
4. Range breakout strategies
5. Supply/demand zone reversals

All patterns are based on multi-timeframe price action with no indicators.

Parameters:
    min_body_ratio: float = 0.3       # Minimum body/range for engulfing
    pin_wick_ratio: float = 2.0       # Wick must be 2x body for pin bars
    lookback_sr: int = 20             # Bars to identify S/R levels
    breakout_confirm: int = 2         # Bars to confirm breakout
    atr_period: int = 14              # ATR for stop placement
    risk_reward: float = 2.0          # Target R:R ratio
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any, List, Tuple
import numpy as np

from .base import BaseStrategy


class StrategyPriceAction(BaseStrategy):
    """
    Multi-pattern price action strategy.

    Combines multiple price action signals:
    - Pin bars at key levels
    - Engulfing patterns
    - Breakout and retest setups
    """

    name = "PriceAction"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})

        # Parameters
        self.min_body_ratio = float(self.params.get("min_body_ratio", 0.3))
        self.pin_wick_ratio = float(self.params.get("pin_wick_ratio", 2.0))
        self.lookback_sr = int(self.params.get("lookback_sr", 20))
        self.breakout_confirm = int(self.params.get("breakout_confirm", 2))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.risk_reward = float(self.params.get("risk_reward", 2.0))
        self.sl_mult = float(self.params.get("sl_mult", 1.5))
        self.tp_mult = float(self.params.get("tp_mult", 3.0))

        # Pattern weights
        self.pin_weight = float(self.params.get("pin_weight", 1.0))
        self.engulf_weight = float(self.params.get("engulf_weight", 1.2))
        self.breakout_weight = float(self.params.get("breakout_weight", 0.8))

        # Minimum signal strength
        self.min_signal_strength = float(self.params.get("min_signal_strength", 1.0))

    def _extract_ohlc(self, bars: Sequence) -> Optional[np.ndarray]:
        """Extract OHLC as numpy array from bars."""
        if not bars:
            return None

        try:
            first = bars[0]
            if isinstance(first, (int, float, np.floating)):
                # Only close prices, create synthetic OHLC
                closes = np.array([float(b) for b in bars])
                return np.column_stack([closes, closes, closes, closes])

            # Extract OHLC from OANDA format
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
        """Compute ATR from OHLC array."""
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

    def _is_pin_bar(self, ohlc_bar: np.ndarray, direction: str) -> Tuple[bool, float]:
        """
        Check if bar is a pin bar (hammer/shooting star).

        Returns (is_pin, strength) where strength is 0-1.
        """
        o, h, l, c = ohlc_bar

        body = abs(c - o)
        total_range = h - l

        if total_range == 0:
            return False, 0.0

        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l

        body_ratio = body / total_range

        # Bullish pin bar (hammer)
        if direction == "BUY":
            if lower_wick > body * self.pin_wick_ratio and body_ratio < 0.4:
                strength = min(1.0, (lower_wick / total_range) * 2.0)
                return True, strength

        # Bearish pin bar (shooting star)
        elif direction == "SELL":
            if upper_wick > body * self.pin_wick_ratio and body_ratio < 0.4:
                strength = min(1.0, (upper_wick / total_range) * 2.0)
                return True, strength

        return False, 0.0

    def _is_engulfing(self, prev_bar: np.ndarray, curr_bar: np.ndarray, direction: str) -> Tuple[bool, float]:
        """
        Check if current bar engulfs previous bar.

        Returns (is_engulfing, strength).
        """
        prev_o, prev_h, prev_l, prev_c = prev_bar
        curr_o, curr_h, curr_l, curr_c = curr_bar

        prev_body = abs(prev_c - prev_o)
        curr_body = abs(curr_c - curr_o)

        if prev_body == 0:
            return False, 0.0

        body_ratio = curr_body / prev_body

        # Bullish engulfing
        if direction == "BUY":
            prev_bearish = prev_c < prev_o
            curr_bullish = curr_c > curr_o

            if prev_bearish and curr_bullish:
                if curr_o <= prev_c and curr_c >= prev_o:
                    # Full engulfing
                    strength = min(1.0, body_ratio)
                    return True, strength

        # Bearish engulfing
        elif direction == "SELL":
            prev_bullish = prev_c > prev_o
            curr_bearish = curr_c < curr_o

            if prev_bullish and curr_bearish:
                if curr_o >= prev_c and curr_c <= prev_o:
                    strength = min(1.0, body_ratio)
                    return True, strength

        return False, 0.0

    def _find_support_resistance(self, ohlc: np.ndarray) -> Tuple[List[float], List[float]]:
        """
        Identify support and resistance levels using swing highs/lows.

        Returns (support_levels, resistance_levels).
        """
        if len(ohlc) < self.lookback_sr:
            return [], []

        highs = ohlc[-self.lookback_sr:, 1]
        lows = ohlc[-self.lookback_sr:, 2]

        support = []
        resistance = []

        # Find swing lows (support)
        for i in range(2, len(lows) - 2):
            if lows[i] == min(lows[i-2:i+3]):
                support.append(float(lows[i]))

        # Find swing highs (resistance)
        for i in range(2, len(highs) - 2):
            if highs[i] == max(highs[i-2:i+3]):
                resistance.append(float(highs[i]))

        return support, resistance

    def _near_level(self, price: float, levels: List[float], tolerance: float) -> bool:
        """Check if price is near any level within tolerance."""
        if not levels:
            return False

        for level in levels:
            if abs(price - level) <= tolerance:
                return True

        return False

    def _detect_breakout(self, ohlc: np.ndarray, direction: str) -> Tuple[bool, float]:
        """
        Detect breakout from range with confirmation.

        Returns (is_breakout, strength).
        """
        if len(ohlc) < self.lookback_sr + self.breakout_confirm:
            return False, 0.0

        # Get recent range
        recent = ohlc[-self.lookback_sr-self.breakout_confirm:-self.breakout_confirm]
        range_high = recent[:, 1].max()
        range_low = recent[:, 2].min()
        range_size = range_high - range_low

        if range_size == 0:
            return False, 0.0

        # Check if we broke out
        confirm_bars = ohlc[-self.breakout_confirm:]

        if direction == "BUY":
            # Bullish breakout
            breakouts = sum(1 for bar in confirm_bars if bar[3] > range_high)
            if breakouts >= self.breakout_confirm:
                # Calculate strength based on how far we've broken
                current_close = ohlc[-1, 3]
                penetration = (current_close - range_high) / range_size
                strength = min(1.0, penetration * 2.0)
                return True, strength

        elif direction == "SELL":
            # Bearish breakout
            breakouts = sum(1 for bar in confirm_bars if bar[3] < range_low)
            if breakouts >= self.breakout_confirm:
                current_close = ohlc[-1, 3]
                penetration = (range_low - current_close) / range_size
                strength = min(1.0, penetration * 2.0)
                return True, strength

        return False, 0.0

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """
        Generate trading signal based on price action patterns.
        """
        ohlc = self._extract_ohlc(bars)
        if ohlc is None or len(ohlc) < max(self.lookback_sr, self.atr_period) + 2:
            return None

        atr = self._compute_atr(ohlc)
        if atr == 0:
            return None

        current_bar = ohlc[-1]
        prev_bar = ohlc[-2]
        current_close = current_bar[3]

        # Find S/R levels
        support, resistance = self._find_support_resistance(ohlc)

        # Calculate signal strength for each direction
        buy_strength = 0.0
        sell_strength = 0.0

        # Pin bar signals
        is_bull_pin, bull_pin_str = self._is_pin_bar(current_bar, "BUY")
        is_bear_pin, bear_pin_str = self._is_pin_bar(current_bar, "SELL")

        if is_bull_pin and self._near_level(current_bar[2], support, atr * 0.5):
            buy_strength += bull_pin_str * self.pin_weight * 1.5  # Bonus for S/R
        elif is_bull_pin:
            buy_strength += bull_pin_str * self.pin_weight

        if is_bear_pin and self._near_level(current_bar[1], resistance, atr * 0.5):
            sell_strength += bear_pin_str * self.pin_weight * 1.5
        elif is_bear_pin:
            sell_strength += bear_pin_str * self.pin_weight

        # Engulfing patterns
        is_bull_engulf, bull_eng_str = self._is_engulfing(prev_bar, current_bar, "BUY")
        is_bear_engulf, bear_eng_str = self._is_engulfing(prev_bar, current_bar, "SELL")

        if is_bull_engulf:
            buy_strength += bull_eng_str * self.engulf_weight

        if is_bear_engulf:
            sell_strength += bear_eng_str * self.engulf_weight

        # Breakout signals
        is_bull_breakout, bull_break_str = self._detect_breakout(ohlc, "BUY")
        is_bear_breakout, bear_break_str = self._detect_breakout(ohlc, "SELL")

        if is_bull_breakout:
            buy_strength += bull_break_str * self.breakout_weight

        if is_bear_breakout:
            sell_strength += bear_break_str * self.breakout_weight

        # Generate signal based on strongest direction
        if buy_strength >= self.min_signal_strength and buy_strength > sell_strength:
            return "BUY"

        if sell_strength >= self.min_signal_strength and sell_strength > buy_strength:
            return "SELL"

        return None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Track performance and adapt parameters."""
        super().update_trade_result(win, pnl)

        history = self.params.setdefault("_history", [])
        history.append({"win": win, "pnl": pnl})

        if len(history) > 50:
            history.pop(0)

        # Adaptive parameter tuning
        if len(history) >= 20:
            recent = history[-20:]
            win_rate = sum(1 for h in recent if h["win"]) / 20

            # Adjust signal threshold based on performance
            if win_rate < 0.4:
                # Be more selective
                self.min_signal_strength = min(2.0, self.min_signal_strength + 0.1)
            elif win_rate > 0.6:
                # Can be less restrictive
                self.min_signal_strength = max(0.5, self.min_signal_strength - 0.05)


def compute_atr(bars, period: int = 14) -> float:
    """
    Return the latest ATR for use in stop/target calculations.
    """
    if len(bars) < period + 1:
        return 0.0

    try:
        ohlc = []
        for bar in bars[-period-1:]:
            if isinstance(bar, (int, float)):
                return 0.0

            if isinstance(bar, dict) and "mid" in bar:
                mid = bar["mid"]
                o = float(mid.get("o", mid.get("open", 0)))
                h = float(mid.get("h", mid.get("high", 0)))
                l = float(mid.get("l", mid.get("low", 0)))
                c = float(mid.get("c", mid.get("close", 0)))
                ohlc.append([o, h, l, c])

        ohlc = np.array(ohlc)
        highs = ohlc[:, 1]
        lows = ohlc[:, 2]
        closes = ohlc[:, 3]

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
    """
    Calculate stop loss and take profit levels based on ATR.
    """
    params = params or {}
    atr_period = params.get("atr_period", 14)
    sl_mult = params.get("sl_mult", 1.5)
    tp_mult = params.get("tp_mult", 3.0)

    atr = compute_atr(bars, period=atr_period)

    # Get current price
    last_bar = bars[-1]
    if isinstance(last_bar, (int, float)):
        price = float(last_bar)
    elif isinstance(last_bar, dict) and "mid" in last_bar:
        price = float(last_bar["mid"]["c"])
    else:
        price = 0.0

    if price == 0 or atr == 0:
        # Fallback
        if side == "BUY":
            return price * 0.999, price * 1.001
        else:
            return price * 1.001, price * 0.999

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
