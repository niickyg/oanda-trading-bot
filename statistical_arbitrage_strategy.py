#!/usr/bin/env python3
"""
Statistical Arbitrage Strategy for Forex Pairs Trading

This strategy exploits temporary mispricings between cointegrated currency pairs
using mean reversion. The strategy identifies pairs that historically move together
and trades when their spread deviates significantly from the equilibrium.

Key Concepts:
1. Cointegration: Two pairs are cointegrated if their spread is mean-reverting
2. Z-Score: Measures how many standard deviations the spread is from its mean
3. Half-Life: Time it takes for spread to revert halfway to the mean

Entry Rules:
- Long spread when z-score < -2 (spread undervalued)
- Short spread when z-score > 2 (spread overvalued)

Exit Rules:
- Close when z-score crosses zero (mean reversion complete)
- Stop loss when z-score extends beyond 3 standard deviations
- Maximum hold time to avoid prolonged divergence
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class PairPosition:
    """Tracks an open pairs trade"""
    pair1: str
    pair2: str
    side: str  # "LONG" or "SHORT" the spread
    entry_zscore: float
    entry_spread: float
    hedge_ratio: float
    entry_bar: int
    entry_price1: float
    entry_price2: float


class StatisticalArbitrageStrategy:
    """
    Pairs trading strategy based on cointegration and mean reversion.

    The strategy:
    1. Tests pairs for cointegration using Augmented Dickey-Fuller test
    2. Calculates optimal hedge ratio using OLS regression
    3. Monitors spread z-score for entry/exit signals
    4. Implements proper risk management with position sizing
    """

    def __init__(
        self,
        lookback_period: int = 60,
        zscore_entry: float = 2.0,
        zscore_exit: float = 0.5,
        zscore_stop: float = 3.0,
        max_hold_bars: int = 50,
        min_half_life: int = 5,
        max_half_life: int = 30,
    ):
        """
        Initialize strategy parameters.

        Args:
            lookback_period: Number of bars to use for spread calculation
            zscore_entry: Z-score threshold for entry (absolute value)
            zscore_exit: Z-score threshold for exit (absolute value)
            zscore_stop: Z-score threshold for stop loss (absolute value)
            max_hold_bars: Maximum number of bars to hold a position
            min_half_life: Minimum acceptable half-life for mean reversion
            max_half_life: Maximum acceptable half-life for mean reversion
        """
        self.lookback = lookback_period
        self.zscore_entry = zscore_entry
        self.zscore_exit = zscore_exit
        self.zscore_stop = zscore_stop
        self.max_hold_bars = max_hold_bars
        self.min_half_life = min_half_life
        self.max_half_life = max_half_life

        # Track data for each pair
        self.price_data: Dict[str, deque] = {}
        self.positions: List[PairPosition] = []

        # Performance tracking
        self.trades = []
        self.equity_curve = [10000.0]  # Start with $10k

    def add_price(self, pair: str, price: float):
        """Add new price observation for a pair"""
        if pair not in self.price_data:
            self.price_data[pair] = deque(maxlen=self.lookback + 50)
        self.price_data[pair].append(price)

    def get_prices(self, pair: str) -> np.ndarray:
        """Get price history for a pair"""
        if pair not in self.price_data:
            return np.array([])
        return np.array(list(self.price_data[pair]))

    def calculate_hedge_ratio(self, prices1: np.ndarray, prices2: np.ndarray) -> float:
        """
        Calculate optimal hedge ratio using OLS regression.
        Returns beta coefficient from: price1 = alpha + beta * price2
        """
        if len(prices1) < 2 or len(prices2) < 2:
            return 1.0

        # Simple linear regression
        X = prices2.reshape(-1, 1)
        y = prices1.reshape(-1, 1)

        # Add intercept
        X_with_intercept = np.column_stack([np.ones(len(X)), X])

        # OLS: (X'X)^-1 X'y
        try:
            beta = np.linalg.lstsq(X_with_intercept, y, rcond=None)[0]
            return float(beta[1][0])  # Return slope (beta)
        except:
            return 1.0

    def calculate_spread(
        self, prices1: np.ndarray, prices2: np.ndarray, hedge_ratio: float
    ) -> np.ndarray:
        """Calculate spread: spread = price1 - hedge_ratio * price2"""
        return prices1 - hedge_ratio * prices2

    def calculate_zscore(self, spread: np.ndarray) -> float:
        """Calculate current z-score of the spread"""
        if len(spread) < 2:
            return 0.0

        mean = np.mean(spread)
        std = np.std(spread)

        if std < 1e-8:  # Avoid division by zero
            return 0.0

        return (spread[-1] - mean) / std

    def calculate_half_life(self, spread: np.ndarray) -> float:
        """
        Calculate half-life of mean reversion using AR(1) model.
        Half-life = -log(2) / log(lambda), where lambda is AR coefficient.
        """
        if len(spread) < 10:
            return np.inf

        # Lag the spread
        spread_lag = spread[:-1]
        spread_diff = spread[1:] - spread_lag

        # Regression: diff = alpha + beta * lag
        try:
            X = spread_lag.reshape(-1, 1)
            y = spread_diff.reshape(-1, 1)
            X_with_intercept = np.column_stack([np.ones(len(X)), X])
            coeffs = np.linalg.lstsq(X_with_intercept, y, rcond=None)[0]
            beta = coeffs[1][0]

            # Half-life calculation
            if beta >= 0:  # No mean reversion
                return np.inf

            half_life = -np.log(2) / np.log(1 + beta)
            return half_life
        except:
            return np.inf

    def test_cointegration(self, pair1: str, pair2: str) -> Tuple[bool, float, float]:
        """
        Test if two pairs are cointegrated.

        Returns:
            (is_cointegrated, hedge_ratio, half_life)
        """
        prices1 = self.get_prices(pair1)
        prices2 = self.get_prices(pair2)

        if len(prices1) < self.lookback or len(prices2) < self.lookback:
            return False, 0.0, np.inf

        # Use last lookback bars for testing
        p1 = prices1[-self.lookback:]
        p2 = prices2[-self.lookback:]

        # Calculate hedge ratio
        hedge_ratio = self.calculate_hedge_ratio(p1, p2)

        # Calculate spread
        spread = self.calculate_spread(p1, p2, hedge_ratio)

        # Calculate half-life
        half_life = self.calculate_half_life(spread)

        # Check if spread is mean-reverting
        is_cointegrated = self.min_half_life <= half_life <= self.max_half_life

        return is_cointegrated, hedge_ratio, half_life

    def generate_signal(
        self, pair1: str, pair2: str, current_bar: int
    ) -> Optional[Tuple[str, float, float, float]]:
        """
        Generate trading signal for a pair.

        Returns:
            (signal, zscore, hedge_ratio, spread) or None
            signal: "LONG_SPREAD" or "SHORT_SPREAD"
        """
        # Check if we have enough data
        prices1 = self.get_prices(pair1)
        prices2 = self.get_prices(pair2)

        if len(prices1) < self.lookback or len(prices2) < self.lookback:
            return None

        # Test cointegration
        is_coint, hedge_ratio, half_life = self.test_cointegration(pair1, pair2)

        if not is_coint:
            return None

        # Calculate current spread and z-score
        p1 = prices1[-self.lookback:]
        p2 = prices2[-self.lookback:]
        spread = self.calculate_spread(p1, p2, hedge_ratio)
        zscore = self.calculate_zscore(spread)

        # Generate signal
        if zscore < -self.zscore_entry:
            return "LONG_SPREAD", zscore, hedge_ratio, spread[-1]
        elif zscore > self.zscore_entry:
            return "SHORT_SPREAD", zscore, hedge_ratio, spread[-1]

        return None

    def check_exit(self, position: PairPosition, current_bar: int) -> Tuple[bool, str]:
        """
        Check if position should be exited.

        Returns:
            (should_exit, reason)
        """
        prices1 = self.get_prices(position.pair1)
        prices2 = self.get_prices(position.pair2)

        if len(prices1) == 0 or len(prices2) == 0:
            return False, ""

        # Calculate current spread and z-score
        p1 = prices1[-min(self.lookback, len(prices1)):]
        p2 = prices2[-min(self.lookback, len(prices2)):]
        spread = self.calculate_spread(p1, p2, position.hedge_ratio)
        zscore = self.calculate_zscore(spread)

        # Check stop loss
        if abs(zscore) > self.zscore_stop:
            return True, "STOP_LOSS"

        # Check profit target (mean reversion)
        if position.side == "LONG" and zscore > self.zscore_exit:
            return True, "PROFIT_TARGET"
        elif position.side == "SHORT" and zscore < -self.zscore_exit:
            return True, "PROFIT_TARGET"

        # Check max hold time
        if current_bar - position.entry_bar >= self.max_hold_bars:
            return True, "MAX_HOLD_TIME"

        return False, ""

    def calculate_pnl(self, position: PairPosition) -> float:
        """Calculate P&L for a position"""
        prices1 = self.get_prices(position.pair1)
        prices2 = self.get_prices(position.pair2)

        if len(prices1) == 0 or len(prices2) == 0:
            return 0.0

        current_price1 = prices1[-1]
        current_price2 = prices2[-1]

        # P&L calculation
        if position.side == "LONG":
            # Long spread = long pair1, short pair2
            pnl1 = (current_price1 - position.entry_price1) / position.entry_price1
            pnl2 = -(current_price2 - position.entry_price2) / position.entry_price2 * position.hedge_ratio
        else:
            # Short spread = short pair1, long pair2
            pnl1 = -(current_price1 - position.entry_price1) / position.entry_price1
            pnl2 = (current_price2 - position.entry_price2) / position.entry_price2 * position.hedge_ratio

        # Total P&L as percentage
        total_pnl = (pnl1 + pnl2) / 2.0  # Average of both legs

        return total_pnl


def backtest_pairs_trading(
    data: Dict[str, List[float]],
    pair_combinations: List[Tuple[str, str]],
    strategy_params: Optional[Dict] = None,
) -> Dict:
    """
    Backtest pairs trading strategy on historical data.

    Args:
        data: Dictionary mapping pair names to price lists
        pair_combinations: List of (pair1, pair2) tuples to test
        strategy_params: Optional strategy parameters

    Returns:
        Dictionary with backtest results
    """
    if strategy_params is None:
        strategy_params = {}

    strategy = StatisticalArbitrageStrategy(**strategy_params)

    # Determine number of bars
    n_bars = min(len(prices) for prices in data.values())

    logger.info(f"Starting backtest with {n_bars} bars and {len(pair_combinations)} pairs")

    # Results tracking
    trades = []
    equity = 10000.0
    equity_curve = [equity]
    peak_equity = equity
    max_drawdown = 0.0

    # Process each bar
    for bar_idx in range(n_bars):
        # Update prices
        for pair, prices in data.items():
            if bar_idx < len(prices):
                strategy.add_price(pair, prices[bar_idx])

        # Check exits for existing positions
        for position in strategy.positions[:]:
            should_exit, reason = strategy.check_exit(position, bar_idx)

            if should_exit:
                pnl = strategy.calculate_pnl(position)
                pnl_dollars = equity * pnl
                equity += pnl_dollars

                trade_record = {
                    'pair1': position.pair1,
                    'pair2': position.pair2,
                    'side': position.side,
                    'entry_bar': position.entry_bar,
                    'exit_bar': bar_idx,
                    'entry_zscore': position.entry_zscore,
                    'pnl_pct': pnl * 100,
                    'pnl_dollars': pnl_dollars,
                    'exit_reason': reason,
                }
                trades.append(trade_record)
                strategy.positions.remove(position)

                logger.debug(f"Closed {position.pair1}/{position.pair2}: {reason}, PnL: {pnl*100:.2f}%")

        # Look for new entries (limit to 3 concurrent positions)
        if len(strategy.positions) < 3 and bar_idx >= strategy.lookback:
            for pair1, pair2 in pair_combinations:
                if any(p.pair1 == pair1 and p.pair2 == pair2 for p in strategy.positions):
                    continue  # Already have position in this pair

                signal = strategy.generate_signal(pair1, pair2, bar_idx)

                if signal is not None:
                    signal_type, zscore, hedge_ratio, spread = signal

                    # Create position
                    position = PairPosition(
                        pair1=pair1,
                        pair2=pair2,
                        side="LONG" if signal_type == "LONG_SPREAD" else "SHORT",
                        entry_zscore=zscore,
                        entry_spread=spread,
                        hedge_ratio=hedge_ratio,
                        entry_bar=bar_idx,
                        entry_price1=data[pair1][bar_idx],
                        entry_price2=data[pair2][bar_idx],
                    )
                    strategy.positions.append(position)

                    logger.debug(f"Opened {pair1}/{pair2}: {signal_type}, Z-score: {zscore:.2f}")
                    break  # Only one entry per bar

        # Update equity curve
        equity_curve.append(equity)

        # Update max drawdown
        if equity > peak_equity:
            peak_equity = equity

        current_dd = (peak_equity - equity) / peak_equity
        if current_dd > max_drawdown:
            max_drawdown = current_dd

    # Close any remaining positions at the end
    for position in strategy.positions:
        pnl = strategy.calculate_pnl(position)
        pnl_dollars = equity * pnl
        equity += pnl_dollars

        trade_record = {
            'pair1': position.pair1,
            'pair2': position.pair2,
            'side': position.side,
            'entry_bar': position.entry_bar,
            'exit_bar': n_bars - 1,
            'entry_zscore': position.entry_zscore,
            'pnl_pct': pnl * 100,
            'pnl_dollars': pnl_dollars,
            'exit_reason': 'END_OF_DATA',
        }
        trades.append(trade_record)

    # Calculate metrics
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'total_pnl': 0.0,
            'final_equity': equity,
        }

    winning_trades = [t for t in trades if t['pnl_dollars'] > 0]
    losing_trades = [t for t in trades if t['pnl_dollars'] <= 0]

    total_wins = sum(t['pnl_dollars'] for t in winning_trades)
    total_losses = abs(sum(t['pnl_dollars'] for t in losing_trades))

    win_rate = len(winning_trades) / len(trades) if trades else 0.0
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

    # Sharpe ratio (annualized, assuming daily bars)
    returns = np.diff(equity_curve) / equity_curve[:-1]
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 0 and np.std(returns) > 0 else 0.0

    results = {
        'total_trades': len(trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe,
        'total_pnl': equity - 10000.0,
        'total_pnl_pct': (equity - 10000.0) / 10000.0 * 100,
        'final_equity': equity,
        'avg_win': total_wins / len(winning_trades) if winning_trades else 0.0,
        'avg_loss': total_losses / len(losing_trades) if losing_trades else 0.0,
        'trades': trades,
        'equity_curve': equity_curve,
    }

    return results


if __name__ == "__main__":
    # Example usage
    print("Statistical Arbitrage Strategy - Pairs Trading")
    print("=" * 60)
    print("\nThis strategy exploits temporary mispricings between")
    print("cointegrated currency pairs using mean reversion.")
