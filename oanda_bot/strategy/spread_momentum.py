"""
strategy/spread_momentum.py
---------------------------

Advanced market microstructure strategy exploiting bid-ask spread dynamics
and volume-price patterns on ultra-short timeframes (2-5 second bars).

EDGE DESCRIPTION:
=================
This strategy identifies profitable trading opportunities by analyzing:

1. **Spread Expansion/Contraction** - Spread widening precedes volatility
   - Normal spread: Market makers comfortable with risk
   - Widening spread: Uncertainty/asymmetric information
   - Narrowing spread after expansion: Market makers re-entering

2. **Volume-Price Divergence** - When volume and price action disconnect
   - High volume + small price move = absorption (strong support/resistance)
   - Low volume + large price move = thin liquidity (continuation likely)
   - Volume surge at price extremes = potential reversal

3. **Tick Velocity** - Rate of price change indicates order flow urgency
   - Accelerating tick velocity = aggressive order flow
   - Decelerating tick velocity = order flow exhaustion
   - Velocity divergence from price = early reversal signal

4. **Quote Efficiency Ratio** - Price movement per unit of volume
   - Low ratio = inefficient moves (likely to reverse)
   - High ratio = efficient moves (likely to continue)
   - Ratio change = regime shift detection

THEORETICAL FOUNDATION:
=======================
Based on market microstructure research:
- Glosten & Milgrom (1985): Bid-ask spread reflects asymmetric information
- Kyle (1985): Informed traders impact price through aggressive orders
- Hasbrouck (1991): Order flow imbalance predicts short-term returns
- Engle & Ng (1993): Volume-volatility correlation in high-frequency data

THE EDGE:
=========
Market makers react to order flow with spread adjustments before price moves.
By monitoring spread dynamics with volume patterns, we can anticipate:
- Breakouts (spread widens → volume surge → price move)
- Reversals (spread widens → absorption → reversion)
- False breakouts (large move + low volume = trap)

EXECUTION:
==========
Entry signals combine multiple microstructure indicators:
1. Spread regime classification (normal/wide/narrow)
2. Volume-price efficiency calculation
3. Tick velocity measurement
4. Order flow imbalance detection

Exit via:
- Mean reversion to VWAP
- Tick velocity reversal
- Fixed time limit (60 seconds max hold)

Parameters:
    spread_window: int = 30           # Bars for spread statistics
    volume_window: int = 20           # Bars for volume analysis
    velocity_window: int = 10         # Bars for tick velocity
    spread_expansion_threshold: float = 1.5  # Spread expansion factor
    volume_surge_threshold: float = 2.0      # Volume surge factor
    velocity_accel_threshold: float = 1.3    # Velocity acceleration
    efficiency_threshold: float = 0.7        # Min price/volume efficiency
    max_hold_bars: int = 12          # Max hold time (60 seconds at 5s bars)
    profit_target_atr: float = 1.2   # TP in ATR units
    stop_loss_atr: float = 0.8       # SL in ATR units
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any
from collections import deque
import numpy as np

from .base import BaseStrategy


class StrategySpreadMomentum(BaseStrategy):
    """
    Market microstructure strategy exploiting spread dynamics and volume patterns.

    Designed for 2-5 second bars where microstructure effects are strongest.
    """

    name = "SpreadMomentum"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})

        # Parameters
        self.spread_window = int(self.params.get("spread_window", 30))
        self.volume_window = int(self.params.get("volume_window", 20))
        self.velocity_window = int(self.params.get("velocity_window", 10))
        self.spread_expansion_threshold = float(self.params.get("spread_expansion_threshold", 1.5))
        self.volume_surge_threshold = float(self.params.get("volume_surge_threshold", 2.0))
        self.velocity_accel_threshold = float(self.params.get("velocity_accel_threshold", 1.3))
        self.efficiency_threshold = float(self.params.get("efficiency_threshold", 0.7))
        self.max_hold_bars = int(self.params.get("max_hold_bars", 12))
        self.profit_target_atr = float(self.params.get("profit_target_atr", 1.2))
        self.stop_loss_atr = float(self.params.get("stop_loss_atr", 0.8))

        # Data structures for microstructure analysis
        self.spreads: deque = deque(maxlen=100)
        self.volumes: deque = deque(maxlen=100)
        self.prices: deque = deque(maxlen=100)
        self.highs: deque = deque(maxlen=100)
        self.lows: deque = deque(maxlen=100)
        self.price_changes: deque = deque(maxlen=100)
        self.tick_velocities: deque = deque(maxlen=50)

        # VWAP calculation
        self.vwap_sum_pv: float = 0.0  # Sum of price * volume
        self.vwap_sum_v: float = 0.0   # Sum of volume
        self.vwap_prices: deque = deque(maxlen=100)
        self.vwap_volumes: deque = deque(maxlen=100)

        # State
        self._position: int = 0
        self._entry_price: float = 0.0
        self._entry_vwap: float = 0.0
        self._entry_atr: float = 0.0
        self._bars_in_position: int = 0
        self._cooldown: int = 0
        self._bar_count: int = 0

    def _extract_bar_data(self, bar) -> Optional[Dict[str, float]]:
        """Extract OHLCV and spread from bar."""
        try:
            if isinstance(bar, dict):
                # OANDA format with mid prices
                if "mid" in bar and isinstance(bar["mid"], dict):
                    mid = bar["mid"]
                    volume = float(bar.get("volume", 1))

                    # Extract spread if bid/ask available
                    spread = 0.0
                    if "bid" in bar and "ask" in bar:
                        bid = float(bar["bid"]["c"]) if isinstance(bar["bid"], dict) else float(bar["bid"])
                        ask = float(bar["ask"]["c"]) if isinstance(bar["ask"], dict) else float(bar["ask"])
                        spread = ask - bid
                    else:
                        # Estimate spread from high-low if bid/ask not available
                        h = float(mid.get("h", 0))
                        l = float(mid.get("l", 0))
                        spread = (h - l) * 0.3  # Approximate spread as 30% of bar range

                    return {
                        "open": float(mid.get("o", 0)),
                        "high": float(mid.get("h", 0)),
                        "low": float(mid.get("l", 0)),
                        "close": float(mid.get("c", 0)),
                        "volume": volume,
                        "spread": spread
                    }

                # Generic OHLCV format
                if "close" in bar or "c" in bar:
                    volume = float(bar.get("volume", bar.get("v", 1)))
                    spread = float(bar.get("spread", 0))
                    if spread == 0:
                        h = float(bar.get("high", bar.get("h", 0)))
                        l = float(bar.get("low", bar.get("l", 0)))
                        spread = (h - l) * 0.3

                    return {
                        "open": float(bar.get("open", bar.get("o", 0))),
                        "high": float(bar.get("high", bar.get("h", 0))),
                        "low": float(bar.get("low", bar.get("l", 0))),
                        "close": float(bar.get("close", bar.get("c", 0))),
                        "volume": volume,
                        "spread": spread
                    }

            # Fallback for simple price data
            if isinstance(bar, (int, float)):
                return {
                    "open": float(bar),
                    "high": float(bar),
                    "low": float(bar),
                    "close": float(bar),
                    "volume": 1.0,
                    "spread": 0.0001
                }
        except (TypeError, ValueError, KeyError):
            pass
        return None

    def _compute_vwap(self) -> float:
        """Calculate Volume-Weighted Average Price."""
        if self.vwap_sum_v == 0:
            return 0.0
        return self.vwap_sum_pv / self.vwap_sum_v

    def _update_vwap(self, price: float, volume: float):
        """Update VWAP calculation."""
        self.vwap_prices.append(price)
        self.vwap_volumes.append(volume)

        # Recalculate VWAP from stored data
        self.vwap_sum_pv = sum(p * v for p, v in zip(self.vwap_prices, self.vwap_volumes))
        self.vwap_sum_v = sum(self.vwap_volumes)

    def _compute_atr(self, lookback: int = 14) -> float:
        """Calculate Average True Range."""
        if len(self.prices) < lookback + 1:
            return 0.0

        trs = []
        for i in range(-lookback, 0):
            if i - 1 < -len(self.prices):
                continue
            h = self.highs[i]
            l = self.lows[i]
            prev_c = self.prices[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)

        return sum(trs) / len(trs) if trs else 0.0

    def _analyze_spread_regime(self) -> tuple[str, float]:
        """
        Classify spread regime.
        Returns: (regime, spread_ratio)
        - regime: "normal", "expanding", "contracting"
        - spread_ratio: current_spread / avg_spread
        """
        if len(self.spreads) < self.spread_window:
            return "normal", 1.0

        recent_spreads = list(self.spreads)[-self.spread_window:]
        avg_spread = sum(recent_spreads) / len(recent_spreads)
        current_spread = self.spreads[-1]

        if avg_spread == 0:
            return "normal", 1.0

        spread_ratio = current_spread / avg_spread

        if spread_ratio >= self.spread_expansion_threshold:
            return "expanding", spread_ratio
        elif spread_ratio <= (1.0 / self.spread_expansion_threshold):
            return "contracting", spread_ratio
        else:
            return "normal", spread_ratio

    def _analyze_volume_surge(self) -> tuple[bool, float]:
        """
        Detect volume surge.
        Returns: (is_surge, volume_ratio)
        """
        if len(self.volumes) < self.volume_window:
            return False, 1.0

        recent_volumes = list(self.volumes)[-self.volume_window:]
        avg_volume = sum(recent_volumes[:-1]) / (len(recent_volumes) - 1)
        current_volume = self.volumes[-1]

        if avg_volume == 0:
            return False, 1.0

        volume_ratio = current_volume / avg_volume
        is_surge = volume_ratio >= self.volume_surge_threshold

        return is_surge, volume_ratio

    def _compute_tick_velocity(self) -> tuple[float, bool]:
        """
        Calculate tick velocity and detect acceleration.
        Returns: (velocity, is_accelerating)
        """
        if len(self.price_changes) < self.velocity_window:
            return 0.0, False

        recent_changes = list(self.price_changes)[-self.velocity_window:]

        # Calculate velocity as absolute price change per bar
        velocities = [abs(c) for c in recent_changes]

        if len(velocities) < 4:
            return 0.0, False

        # Current velocity vs previous velocity
        current_velocity = sum(velocities[-3:]) / 3
        previous_velocity = sum(velocities[-6:-3]) / 3

        self.tick_velocities.append(current_velocity)

        if previous_velocity == 0:
            return current_velocity, False

        velocity_ratio = current_velocity / previous_velocity
        is_accelerating = velocity_ratio >= self.velocity_accel_threshold

        return current_velocity, is_accelerating

    def _compute_efficiency_ratio(self) -> float:
        """
        Calculate price efficiency: net price change / sum of absolute changes.
        High ratio = trending, Low ratio = choppy
        """
        if len(self.price_changes) < self.velocity_window:
            return 0.0

        recent_changes = list(self.price_changes)[-self.velocity_window:]
        net_change = abs(sum(recent_changes))
        sum_abs_changes = sum(abs(c) for c in recent_changes)

        if sum_abs_changes == 0:
            return 0.0

        return net_change / sum_abs_changes

    def _compute_volume_price_efficiency(self) -> float:
        """
        Calculate volume-price efficiency: price change / volume.
        High ratio = efficient price discovery
        Low ratio = absorption/accumulation
        """
        if len(self.prices) < 2 or len(self.volumes) < 2:
            return 0.0

        recent_price_change = abs(self.prices[-1] - self.prices[-2])
        recent_volume = self.volumes[-1]

        if recent_volume == 0:
            return 0.0

        # Normalize by typical price
        typical_price = (self.highs[-1] + self.lows[-1] + self.prices[-1]) / 3
        if typical_price == 0:
            return 0.0

        efficiency = (recent_price_change / typical_price) / recent_volume
        return efficiency * 10000  # Scale for readability

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """Generate signal based on microstructure analysis."""
        if not bars:
            return None

        self._bar_count += 1
        if self._cooldown > 0:
            self._cooldown -= 1

        # Extract bar data
        bar_data = self._extract_bar_data(bars[-1])
        if not bar_data or bar_data["close"] == 0:
            return None

        current_price = bar_data["close"]
        current_volume = bar_data["volume"]
        current_spread = bar_data["spread"]

        # Update data structures
        self.prices.append(current_price)
        self.highs.append(bar_data["high"])
        self.lows.append(bar_data["low"])
        self.volumes.append(current_volume)
        self.spreads.append(current_spread)

        if len(self.prices) > 1:
            price_change = current_price - self.prices[-2]
            self.price_changes.append(price_change)

        self._update_vwap(current_price, current_volume)

        # Need minimum data
        if len(self.prices) < max(self.spread_window, self.volume_window, self.velocity_window):
            return None

        # Position management
        if self._position != 0:
            self._bars_in_position += 1

            vwap = self._compute_vwap()
            atr = self._entry_atr if self._entry_atr > 0 else self._compute_atr()

            # Take profit - reversion to VWAP
            if self._position == 1:
                if current_price >= self._entry_vwap + self.profit_target_atr * atr:
                    self._reset_position()
                    return "SELL"
            else:  # Short
                if current_price <= self._entry_vwap - self.profit_target_atr * atr:
                    self._reset_position()
                    return "BUY"

            # Stop loss
            if self._position == 1:
                if current_price < self._entry_price - self.stop_loss_atr * atr:
                    self._reset_position()
                    return "SELL"
            else:  # Short
                if current_price > self._entry_price + self.stop_loss_atr * atr:
                    self._reset_position()
                    return "BUY"

            # Time exit
            if self._bars_in_position >= self.max_hold_bars:
                side = "SELL" if self._position > 0 else "BUY"
                self._reset_position()
                return side

            # Exit on velocity reversal
            velocity, is_accelerating = self._compute_tick_velocity()
            if not is_accelerating and self._bars_in_position >= 3:
                # Velocity slowing down, take profit
                side = "SELL" if self._position > 0 else "BUY"
                self._reset_position()
                return side

            return None

        # Entry logic
        if self._cooldown > 0:
            return None

        # Analyze microstructure conditions
        spread_regime, spread_ratio = self._analyze_spread_regime()
        is_volume_surge, volume_ratio = self._analyze_volume_surge()
        velocity, is_accelerating = self._compute_tick_velocity()
        efficiency_ratio = self._compute_efficiency_ratio()
        vp_efficiency = self._compute_volume_price_efficiency()

        vwap = self._compute_vwap()
        atr = self._compute_atr()

        if atr == 0 or vwap == 0:
            return None

        # Price position relative to VWAP
        price_distance_from_vwap = (current_price - vwap) / atr

        # SIGNAL 1: Spread expansion + volume surge + acceleration = Breakout
        # More selective: require stronger confirmation
        if spread_regime == "expanding" and is_volume_surge and is_accelerating:
            if efficiency_ratio >= self.efficiency_threshold and spread_ratio >= 1.7:
                # Need stronger price movement confirmation
                if len(self.price_changes) >= 3:
                    recent_moves = list(self.price_changes)[-3:]
                    directional_consistency = sum(1 for m in recent_moves if m > 0)

                    # Upward breakout - need 2+ positive moves
                    if directional_consistency >= 2 and recent_moves[-1] > 0:
                        self._position = 1
                        self._entry_price = current_price
                        self._entry_vwap = vwap
                        self._entry_atr = atr
                        self._bars_in_position = 0
                        return "BUY"
                    # Downward breakout - need 2+ negative moves
                    elif directional_consistency <= 1 and recent_moves[-1] < 0:
                        self._position = -1
                        self._entry_price = current_price
                        self._entry_vwap = vwap
                        self._entry_atr = atr
                        self._bars_in_position = 0
                        return "SELL"

        # SIGNAL 2: Volume surge + low efficiency = Absorption/Reversal
        # More stringent filters
        if is_volume_surge and efficiency_ratio < 0.25 and volume_ratio >= 2.5:
            # High volume but price not moving = absorption
            # Also check velocity is NOT accelerating (confirming exhaustion)
            if not is_accelerating:
                if price_distance_from_vwap > 2.0:
                    # Price extended above VWAP, volume absorption = short
                    self._position = -1
                    self._entry_price = current_price
                    self._entry_vwap = vwap
                    self._entry_atr = atr
                    self._bars_in_position = 0
                    return "SELL"
                elif price_distance_from_vwap < -2.0:
                    # Price extended below VWAP, volume absorption = long
                    self._position = 1
                    self._entry_price = current_price
                    self._entry_vwap = vwap
                    self._entry_atr = atr
                    self._bars_in_position = 0
                    return "BUY"

        # SIGNAL 3: Spread contracting after expansion + velocity deceleration = Reversion
        # Best performing signal - focus on this
        if spread_regime == "contracting" and len(self.spreads) >= 8:
            # Check if spread was recently expanded significantly
            recent_spreads = list(self.spreads)[-8:]
            recent_max_spread = max(recent_spreads)
            recent_avg_spread = sum(list(self.spreads)[-self.spread_window:]) / self.spread_window
            current_spread = self.spreads[-1]

            # Require substantial expansion followed by contraction
            if recent_max_spread > recent_avg_spread * 1.8 and current_spread < recent_max_spread * 0.7:
                # Spread contracted after significant expansion
                if not is_accelerating and velocity < np.mean(list(self.tick_velocities)[-10:]) if len(self.tick_velocities) >= 10 else True:
                    # Velocity slowing = reversion trade
                    # More extreme price distance required
                    if price_distance_from_vwap > 1.5:
                        self._position = -1
                        self._entry_price = current_price
                        self._entry_vwap = vwap
                        self._entry_atr = atr
                        self._bars_in_position = 0
                        return "SELL"
                    elif price_distance_from_vwap < -1.5:
                        self._position = 1
                        self._entry_price = current_price
                        self._entry_vwap = vwap
                        self._entry_atr = atr
                        self._bars_in_position = 0
                        return "BUY"

        return None

    def _reset_position(self):
        """Reset position state."""
        self._position = 0
        self._entry_price = 0.0
        self._entry_vwap = 0.0
        self._entry_atr = 0.0
        self._bars_in_position = 0
        self._cooldown = 5

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """Track results and adapt parameters."""
        super().update_trade_result(win, pnl)

        history = self.params.setdefault("_history", [])
        history.append({"win": win, "pnl": pnl})

        if len(history) > 50:
            history.pop(0)

        # Adaptive parameter tuning based on recent performance
        if len(history) >= 20:
            recent = history[-20:]
            win_rate = sum(1 for h in recent if h["win"]) / 20
            avg_pnl = sum(h["pnl"] for h in recent) / 20

            # If losing, be more selective
            if win_rate < 0.45:
                self.spread_expansion_threshold = min(2.0, self.spread_expansion_threshold + 0.05)
                self.volume_surge_threshold = min(3.0, self.volume_surge_threshold + 0.1)
                self.efficiency_threshold = min(0.8, self.efficiency_threshold + 0.02)

            # If winning, can be slightly less restrictive
            elif win_rate > 0.6 and avg_pnl > 0:
                self.spread_expansion_threshold = max(1.3, self.spread_expansion_threshold - 0.02)
                self.volume_surge_threshold = max(1.5, self.volume_surge_threshold - 0.05)
                self.efficiency_threshold = max(0.6, self.efficiency_threshold - 0.01)
