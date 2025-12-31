"""
correlation.py
--------------

Strategy correlation analysis and portfolio optimization.

Tracks signal correlation between strategies to:
- Identify redundant strategies
- Optimize strategy portfolio for diversification
- Recommend strategy weights based on low correlation
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from collections import defaultdict, deque
import json
import logging

logger = logging.getLogger(__name__)


class StrategyCorrelationAnalyzer:
    """Analyze and track correlation between trading strategies."""

    def __init__(self, window_size: int = 500):
        """
        Initialize correlation analyzer.

        Args:
            window_size: Number of recent signals to track per strategy
        """
        self.window_size = window_size

        # Track signals: {(pair, strategy): deque of signals}
        # Signal encoding: 1=BUY, -1=SELL, 0=NONE
        self.signal_history: Dict[Tuple[str, str], deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

        # Track when each signal was generated (for time-series analysis)
        self.signal_timestamps: Dict[Tuple[str, str], deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

        # Track actual trade outcomes for each strategy
        self.trade_outcomes: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )

        # Cache correlation matrix (recalculate periodically)
        self.correlation_matrix: Optional[np.ndarray] = None
        self.strategy_names: Optional[List[str]] = None
        self.last_correlation_calc = 0

    def log_signal(
        self,
        pair: str,
        strategy_name: str,
        signal: Optional[str],
        timestamp: float,
    ) -> None:
        """
        Log a strategy signal for correlation tracking.

        Args:
            pair: Currency pair (e.g., "EUR_USD")
            strategy_name: Name of the strategy
            signal: "BUY", "SELL", or None
            timestamp: Unix timestamp when signal was generated
        """
        key = (pair, strategy_name)

        # Encode signal: 1=BUY, -1=SELL, 0=NONE
        if signal == "BUY":
            encoded = 1
        elif signal == "SELL":
            encoded = -1
        else:
            encoded = 0

        self.signal_history[key].append(encoded)
        self.signal_timestamps[key].append(timestamp)

    def log_trade_outcome(
        self,
        strategy_name: str,
        win: bool,
        pnl: float,
    ) -> None:
        """
        Log trade outcome for a strategy.

        Args:
            strategy_name: Name of the strategy
            win: True if trade was profitable
            pnl: Profit/loss amount
        """
        self.trade_outcomes[strategy_name].append({
            "win": win,
            "pnl": pnl,
        })

    def calculate_correlation_matrix(
        self,
        min_samples: int = 50,
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Calculate correlation matrix between all strategies.

        Args:
            min_samples: Minimum number of samples required

        Returns:
            Tuple of (correlation_matrix, strategy_names)
        """
        # Get unique strategies that have enough data
        strategy_pairs = [
            (pair, strat) for (pair, strat) in self.signal_history.keys()
            if len(self.signal_history[(pair, strat)]) >= min_samples
        ]

        if len(strategy_pairs) < 2:
            logger.warning("Insufficient data for correlation analysis")
            return np.array([]), []

        # Get unique strategy names
        strategies = sorted(list(set(strat for _, strat in strategy_pairs)))
        n = len(strategies)

        # Build correlation matrix
        corr_matrix = np.zeros((n, n))

        for i, strat1 in enumerate(strategies):
            for j, strat2 in enumerate(strategies):
                if i == j:
                    corr_matrix[i, j] = 1.0
                elif i > j:
                    # Use symmetry
                    corr_matrix[i, j] = corr_matrix[j, i]
                else:
                    # Calculate correlation across all pairs
                    correlations = []

                    for pair in set(p for p, _ in strategy_pairs):
                        key1 = (pair, strat1)
                        key2 = (pair, strat2)

                        if key1 in self.signal_history and key2 in self.signal_history:
                            signals1 = np.array(self.signal_history[key1])
                            signals2 = np.array(self.signal_history[key2])

                            # Align lengths
                            min_len = min(len(signals1), len(signals2))
                            if min_len >= min_samples:
                                s1 = signals1[-min_len:]
                                s2 = signals2[-min_len:]

                                # Calculate correlation
                                if s1.std() > 0 and s2.std() > 0:
                                    corr = np.corrcoef(s1, s2)[0, 1]
                                    correlations.append(corr)

                    # Average correlation across pairs
                    if correlations:
                        corr_matrix[i, j] = np.mean(correlations)
                    else:
                        corr_matrix[i, j] = 0.0

        self.correlation_matrix = corr_matrix
        self.strategy_names = strategies
        self.last_correlation_calc = len(self.signal_history)

        logger.info(f"Calculated correlation matrix for {n} strategies")
        return corr_matrix, strategies

    def get_highly_correlated_pairs(
        self,
        threshold: float = 0.7,
    ) -> List[Tuple[str, str, float]]:
        """
        Find pairs of strategies with high correlation.

        Args:
            threshold: Correlation threshold (default 0.7)

        Returns:
            List of (strategy1, strategy2, correlation) tuples
        """
        if self.correlation_matrix is None or self.strategy_names is None:
            self.calculate_correlation_matrix()

        if self.correlation_matrix is None:
            return []

        high_corr = []
        n = len(self.strategy_names)

        for i in range(n):
            for j in range(i + 1, n):
                corr = self.correlation_matrix[i, j]
                if abs(corr) >= threshold:
                    high_corr.append((
                        self.strategy_names[i],
                        self.strategy_names[j],
                        float(corr),
                    ))

        # Sort by absolute correlation
        high_corr.sort(key=lambda x: abs(x[2]), reverse=True)
        return high_corr

    def recommend_strategy_portfolio(
        self,
        max_strategies: int = 5,
        min_correlation: float = 0.5,
    ) -> List[Tuple[str, float]]:
        """
        Recommend optimal strategy portfolio with low correlation.

        Uses greedy selection to maximize diversification.

        Args:
            max_strategies: Maximum number of strategies to include
            min_correlation: Avoid strategies with correlation above this

        Returns:
            List of (strategy_name, weight) tuples
        """
        if self.correlation_matrix is None or self.strategy_names is None:
            self.calculate_correlation_matrix()

        if self.correlation_matrix is None or len(self.strategy_names) == 0:
            return []

        # Calculate performance score for each strategy
        strategy_scores = {}
        for strategy in self.strategy_names:
            if strategy in self.trade_outcomes:
                outcomes = list(self.trade_outcomes[strategy])
                if outcomes:
                    win_rate = sum(1 for o in outcomes if o["win"]) / len(outcomes)
                    avg_pnl = np.mean([o["pnl"] for o in outcomes])
                    # Simple score: weighted average of win rate and average PnL
                    strategy_scores[strategy] = win_rate * 0.5 + avg_pnl * 0.5
                else:
                    strategy_scores[strategy] = 0.0
            else:
                strategy_scores[strategy] = 0.0

        # Greedy selection: start with best performing strategy
        selected = []
        selected_indices = []

        # Sort strategies by score
        sorted_strategies = sorted(
            enumerate(self.strategy_names),
            key=lambda x: strategy_scores.get(x[1], 0.0),
            reverse=True,
        )

        for idx, strategy in sorted_strategies:
            if len(selected) >= max_strategies:
                break

            # Check correlation with already selected strategies
            if not selected_indices:
                # First strategy - always add
                selected.append(strategy)
                selected_indices.append(idx)
            else:
                # Check average correlation with selected strategies
                correlations = [
                    abs(self.correlation_matrix[idx, sel_idx])
                    for sel_idx in selected_indices
                ]
                avg_corr = np.mean(correlations)

                if avg_corr < min_correlation:
                    selected.append(strategy)
                    selected_indices.append(idx)

        # Calculate weights (equal weight for now, could be optimized)
        if selected:
            weight = 1.0 / len(selected)
            portfolio = [(strat, weight) for strat in selected]
        else:
            portfolio = []

        logger.info(f"Recommended portfolio: {len(portfolio)} strategies")
        return portfolio

    def get_signal_agreement_rate(
        self,
        strategy1: str,
        strategy2: str,
        pair: Optional[str] = None,
    ) -> float:
        """
        Calculate what percentage of time two strategies agree.

        Args:
            strategy1: First strategy name
            strategy2: Second strategy name
            pair: Optional pair to filter (if None, use all pairs)

        Returns:
            Agreement rate (0.0 to 1.0)
        """
        agreements = 0
        total = 0

        pairs_to_check = [pair] if pair else set(p for p, _ in self.signal_history.keys())

        for p in pairs_to_check:
            key1 = (p, strategy1)
            key2 = (p, strategy2)

            if key1 in self.signal_history and key2 in self.signal_history:
                signals1 = list(self.signal_history[key1])
                signals2 = list(self.signal_history[key2])

                min_len = min(len(signals1), len(signals2))
                if min_len > 0:
                    s1 = signals1[-min_len:]
                    s2 = signals2[-min_len:]

                    for sig1, sig2 in zip(s1, s2):
                        total += 1
                        # Agreement: both buy, both sell, or both none
                        if (sig1 == sig2) or (sig1 == 0 and sig2 == 0):
                            agreements += 1

        if total == 0:
            return 0.0

        return agreements / total

    def export_correlation_report(self, filepath: str) -> None:
        """
        Export correlation analysis to JSON file.

        Args:
            filepath: Path to save JSON report
        """
        if self.correlation_matrix is None or self.strategy_names is None:
            self.calculate_correlation_matrix()

        if self.correlation_matrix is None:
            logger.warning("No correlation data to export")
            return

        report = {
            "strategies": self.strategy_names,
            "correlation_matrix": self.correlation_matrix.tolist(),
            "highly_correlated_pairs": [
                {
                    "strategy1": s1,
                    "strategy2": s2,
                    "correlation": corr,
                }
                for s1, s2, corr in self.get_highly_correlated_pairs(threshold=0.7)
            ],
            "recommended_portfolio": [
                {"strategy": s, "weight": w}
                for s, w in self.recommend_strategy_portfolio()
            ],
            "signal_counts": {
                f"{pair}_{strat}": len(signals)
                for (pair, strat), signals in self.signal_history.items()
            },
        }

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Exported correlation report to {filepath}")

    def print_correlation_matrix(self) -> str:
        """
        Generate a formatted string representation of the correlation matrix.

        Returns:
            Formatted correlation matrix as string
        """
        if self.correlation_matrix is None or self.strategy_names is None:
            self.calculate_correlation_matrix()

        if self.correlation_matrix is None:
            return "Insufficient data for correlation matrix"

        # Build formatted table
        n = len(self.strategy_names)
        col_width = 12

        # Header
        output = " " * col_width
        for name in self.strategy_names:
            output += f"{name[:col_width-1]:>{col_width}}"
        output += "\n"

        # Rows
        for i, name in enumerate(self.strategy_names):
            output += f"{name[:col_width-1]:<{col_width}}"
            for j in range(n):
                corr = self.correlation_matrix[i, j]
                output += f"{corr:>{col_width}.3f}"
            output += "\n"

        return output
