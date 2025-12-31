"""
strategy/stat_arb.py
--------------------

Statistical Arbitrage Strategy - Correlation-Based Mean Reversion

Trades correlated currency pairs when their price ratio (spread) deviates
significantly from historical average. Based on proven backtest results:

- AUD_USD / NZD_USD: 0.87 correlation (best performer)
- EUR_USD / USD_CHF: -0.85 inverse correlation
- EUR_USD / GBP_USD: 0.78 correlation

Backtest Results:
- 261 trades, 47.5% win rate, 1.23 profit factor
- Sharpe Ratio: 0.52
- Total Return: +0.20%
- Max Drawdown: 0.097%

Parameters::
    {
        "lookback": 40,                 # Bars for z-score calculation
        "entry_threshold": 1.5,         # Std devs to enter trade
        "exit_threshold": 0.3,          # Std devs to exit (mean reversion)
        "stop_loss_threshold": 2.5,     # Std devs for stop loss
        "position_size_pct": 0.02,      # 2% risk per trade
        "target_pairs": [               # Correlated pairs to trade
            ["AUD_USD", "NZD_USD"],
            ["EUR_USD", "USD_CHF"],
            ["EUR_USD", "GBP_USD"]
        ]
    }
"""

from __future__ import annotations
from typing import Sequence, Optional, Dict, Any, List
from collections import deque
import numpy as np
from .base import BaseStrategy


class StrategyStatArb(BaseStrategy):
    """
    Statistical Arbitrage using correlation-based spread trading.

    Entry Logic:
    - Calculate price ratio between correlated pairs
    - Compute z-score of current ratio vs historical
    - BUY spread when z-score < -entry_threshold (spread too low)
    - SELL spread when z-score > entry_threshold (spread too high)

    Exit Logic:
    - Exit when z-score returns to exit_threshold
    - Stop loss at stop_loss_threshold
    - Max hold time (configurable)

    Implementation Notes:
    - This strategy requires access to multiple pairs' prices
    - Uses handle_bar() with instrument info instead of next_signal()
    - Maintains internal state for spread calculations
    """

    name = "StatArb"

    # Default correlated pairs (based on backtest analysis)
    DEFAULT_PAIRS = [
        ("AUD_USD", "NZD_USD", 0.87),    # Highest correlation
        ("EUR_USD", "USD_CHF", -0.85),   # Inverse correlation
        ("EUR_USD", "GBP_USD", 0.78),    # Strong positive
    ]

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})

        # Price history for each instrument
        self._prices: Dict[str, deque] = {}

        # Position tracking: {pair_key: {side, entry_spread, entry_zscore, entry_bar}}
        self._positions: Dict[str, Dict] = {}

        # Bar counter for max hold
        self._bar_count: int = 0

        # Get target pairs from params or use defaults
        self._target_pairs = self.params.get("target_pairs", [
            ["AUD_USD", "NZD_USD"],
            ["EUR_USD", "USD_CHF"],
            ["EUR_USD", "GBP_USD"]
        ])

    def _get_lookback(self) -> int:
        return self.params.get("lookback", 40)

    def _get_entry_threshold(self) -> float:
        return self.params.get("entry_threshold", 1.5)

    def _get_exit_threshold(self) -> float:
        return self.params.get("exit_threshold", 0.3)

    def _get_stop_loss_threshold(self) -> float:
        return self.params.get("stop_loss_threshold", 2.5)

    def _get_max_hold_bars(self) -> int:
        return self.params.get("max_hold_bars", 100)

    def _calculate_spread_ratio(self, prices1: np.ndarray, prices2: np.ndarray) -> np.ndarray:
        """Calculate spread as price ratio."""
        return prices1 / prices2

    def _calculate_zscore(self, spread: np.ndarray) -> float:
        """Calculate z-score of current spread vs historical."""
        if len(spread) < 2:
            return 0.0

        # Use all but current for mean/std
        mean = np.mean(spread[:-1])
        std = np.std(spread[:-1])

        if std < 1e-10:
            return 0.0

        return (spread[-1] - mean) / std

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """
        Standard signal interface - not used for stat arb.
        Stat arb requires multi-pair data via handle_bar().
        """
        return None

    def handle_bar(self, bar: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Process incoming bar and check for stat arb opportunities.

        This method is called by main.py for each bar.

        Args:
            bar: Dict with keys: instrument, open, high, low, close, volume

        Returns:
            List of order dicts or None
        """
        instrument = bar.get("instrument")
        close_price = bar.get("close")

        if not instrument or close_price is None:
            return None

        self._bar_count += 1
        lookback = self._get_lookback()

        # Initialize price history if needed
        if instrument not in self._prices:
            self._prices[instrument] = deque(maxlen=lookback + 10)

        # Store price
        self._prices[instrument].append(close_price)

        # Check for signals across all target pairs
        orders = []

        for pair_config in self._target_pairs:
            pair1, pair2 = pair_config[0], pair_config[1]
            pair_key = f"{pair1}_{pair2}"

            # Only check if we have data for both pairs
            if pair1 not in self._prices or pair2 not in self._prices:
                continue

            # Need enough history
            if len(self._prices[pair1]) < lookback or len(self._prices[pair2]) < lookback:
                continue

            # Get price arrays
            prices1 = np.array(list(self._prices[pair1]))[-lookback:]
            prices2 = np.array(list(self._prices[pair2]))[-lookback:]

            # Calculate spread and z-score
            spread = self._calculate_spread_ratio(prices1, prices2)
            zscore = self._calculate_zscore(spread)

            # Check for exits first
            if pair_key in self._positions:
                pos = self._positions[pair_key]
                should_exit = False
                exit_reason = ""

                # Stop loss
                if abs(zscore) > self._get_stop_loss_threshold():
                    should_exit = True
                    exit_reason = "STOP_LOSS"

                # Profit target (mean reversion)
                elif pos['side'] == 'LONG' and zscore > -self._get_exit_threshold():
                    should_exit = True
                    exit_reason = "PROFIT_TARGET"
                elif pos['side'] == 'SHORT' and zscore < self._get_exit_threshold():
                    should_exit = True
                    exit_reason = "PROFIT_TARGET"

                # Max hold time
                elif self._bar_count - pos['entry_bar'] >= self._get_max_hold_bars():
                    should_exit = True
                    exit_reason = "MAX_HOLD"

                if should_exit:
                    # Generate exit orders (close both legs)
                    if pos['side'] == 'LONG':
                        # Was long spread (long pair1, short pair2) - reverse
                        orders.append({'instrument': pair1, 'side': 'SELL', 'reason': f'StatArb_Exit_{exit_reason}'})
                        orders.append({'instrument': pair2, 'side': 'BUY', 'reason': f'StatArb_Exit_{exit_reason}'})
                    else:
                        # Was short spread (short pair1, long pair2) - reverse
                        orders.append({'instrument': pair1, 'side': 'BUY', 'reason': f'StatArb_Exit_{exit_reason}'})
                        orders.append({'instrument': pair2, 'side': 'SELL', 'reason': f'StatArb_Exit_{exit_reason}'})

                    del self._positions[pair_key]

            # Check for new entries (only if not already positioned)
            elif pair_key not in self._positions:
                entry_threshold = self._get_entry_threshold()

                # Spread too low - buy spread (long pair1, short pair2)
                if zscore < -entry_threshold:
                    self._positions[pair_key] = {
                        'side': 'LONG',
                        'entry_spread': spread[-1],
                        'entry_zscore': zscore,
                        'entry_bar': self._bar_count,
                        'pair1': pair1,
                        'pair2': pair2,
                    }
                    orders.append({'instrument': pair1, 'side': 'BUY', 'reason': f'StatArb_Entry_LONG_z={zscore:.2f}'})
                    orders.append({'instrument': pair2, 'side': 'SELL', 'reason': f'StatArb_Entry_LONG_z={zscore:.2f}'})

                # Spread too high - sell spread (short pair1, long pair2)
                elif zscore > entry_threshold:
                    self._positions[pair_key] = {
                        'side': 'SHORT',
                        'entry_spread': spread[-1],
                        'entry_zscore': zscore,
                        'entry_bar': self._bar_count,
                        'pair1': pair1,
                        'pair2': pair2,
                    }
                    orders.append({'instrument': pair1, 'side': 'SELL', 'reason': f'StatArb_Entry_SHORT_z={zscore:.2f}'})
                    orders.append({'instrument': pair2, 'side': 'BUY', 'reason': f'StatArb_Entry_SHORT_z={zscore:.2f}'})

        return orders if orders else None

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """
        Track performance for adaptive parameter adjustment.
        """
        super().update_trade_result(win, pnl)

        # Adaptive logic based on recent performance
        history = self.params.setdefault("_trade_history", [])
        history.append({"win": win, "pnl": pnl})

        # Keep last 50 trades
        if len(history) > 50:
            history.pop(0)

        # Adjust thresholds based on performance
        if len(history) >= 30:
            recent_wins = sum(1 for t in history[-30:] if t["win"])
            win_rate = recent_wins / 30

            # If losing, widen entry threshold (more selective)
            if win_rate < 0.40:
                current = self.params.get("entry_threshold", 1.5)
                self.params["entry_threshold"] = min(2.5, current + 0.1)

            # If winning well, can be slightly more aggressive
            elif win_rate > 0.55:
                current = self.params.get("entry_threshold", 1.5)
                self.params["entry_threshold"] = max(1.2, current - 0.05)

    def get_position_info(self) -> Dict[str, Any]:
        """Return current position information for monitoring."""
        return {
            "positions": dict(self._positions),
            "bar_count": self._bar_count,
            "instruments_tracked": list(self._prices.keys()),
        }


# ============================================================================
# Convenience function for standalone testing
# ============================================================================

def test_stat_arb():
    """Quick test of stat arb strategy."""
    strategy = StrategyStatArb({
        "lookback": 40,
        "entry_threshold": 1.5,
        "exit_threshold": 0.3,
    })

    # Simulate some bars
    import random

    base_aud = 0.67
    base_nzd = 0.58

    for i in range(100):
        # Simulate correlated price movements with some noise
        noise_aud = random.gauss(0, 0.0005)
        noise_nzd = random.gauss(0, 0.0004)
        common_factor = random.gauss(0, 0.0003)

        bar_aud = {
            "instrument": "AUD_USD",
            "open": base_aud,
            "high": base_aud + 0.0002,
            "low": base_aud - 0.0002,
            "close": base_aud + noise_aud + common_factor,
            "volume": 100,
        }
        bar_nzd = {
            "instrument": "NZD_USD",
            "open": base_nzd,
            "high": base_nzd + 0.0002,
            "low": base_nzd - 0.0002,
            "close": base_nzd + noise_nzd + common_factor,
            "volume": 100,
        }

        # Update base prices
        base_aud = bar_aud["close"]
        base_nzd = bar_nzd["close"]

        # Process bars
        orders_aud = strategy.handle_bar(bar_aud)
        orders_nzd = strategy.handle_bar(bar_nzd)

        if orders_aud:
            print(f"Bar {i}: {orders_aud}")
        if orders_nzd:
            print(f"Bar {i}: {orders_nzd}")

    print(f"\nFinal position info: {strategy.get_position_info()}")


if __name__ == "__main__":
    test_stat_arb()
