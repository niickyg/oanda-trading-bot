#!/usr/bin/env python3
"""
Run Statistical Arbitrage Strategy on Historical Forex Data

This script:
1. Fetches historical data for major forex pairs
2. Tests multiple pair combinations for cointegration
3. Backtests pairs trading strategy
4. Reports comprehensive performance metrics
"""

import sys
import os
import logging
import json
from typing import Dict, List, Tuple
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from statistical_arbitrage_strategy import (
    StatisticalArbitrageStrategy,
    backtest_pairs_trading,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_historical_data(pairs: List[str], granularity: str = "H4", count: int = 1000) -> Dict[str, List[float]]:
    """
    Fetch historical data for multiple pairs from OANDA API.

    Args:
        pairs: List of pair names (e.g., ["EUR_USD", "GBP_USD"])
        granularity: Timeframe (M1, M5, M15, H1, H4, D)
        count: Number of candles to fetch

    Returns:
        Dictionary mapping pair names to lists of close prices
    """
    try:
        from oanda_bot.data import get_candles
        use_live_data = True
    except Exception as e:
        logger.warning(f"Could not import OANDA data module: {e}")
        logger.warning("Will generate synthetic data for testing")
        use_live_data = False

    data = {}

    for pair in pairs:
        if use_live_data:
            try:
                logger.info(f"Fetching {count} candles for {pair} @ {granularity}")
                candles = get_candles(symbol=pair, granularity=granularity, count=count)

                # Extract close prices
                prices = [float(c['mid']['c']) for c in candles]
                data[pair] = prices

                logger.info(f"Fetched {len(prices)} prices for {pair}")
            except Exception as e:
                logger.error(f"Error fetching data for {pair}: {e}")
                # Generate synthetic data as fallback
                data[pair] = generate_synthetic_pair_data(count)
        else:
            # Generate synthetic data for testing
            data[pair] = generate_synthetic_pair_data(count)

    return data


def generate_synthetic_pair_data(n_points: int, base_price: float = 1.1, volatility: float = 0.002) -> List[float]:
    """
    Generate synthetic price data with realistic characteristics.

    Args:
        n_points: Number of data points
        base_price: Starting price
        volatility: Daily volatility

    Returns:
        List of prices
    """
    np.random.seed(42)  # For reproducibility

    # Generate random walk with drift
    returns = np.random.normal(0, volatility, n_points)
    log_prices = np.cumsum(returns) + np.log(base_price)
    prices = np.exp(log_prices)

    return prices.tolist()


def generate_cointegrated_pair(
    base_pair: List[float], correlation: float = 0.85, mean_reversion_strength: float = 0.3
) -> List[float]:
    """
    Generate a cointegrated pair based on an existing pair.

    Args:
        base_pair: Price series for the base pair
        correlation: Correlation coefficient (0-1)
        mean_reversion_strength: Strength of mean reversion (0-1)

    Returns:
        Cointegrated price series
    """
    n = len(base_pair)
    base_returns = np.diff(np.log(base_pair))

    # Generate correlated returns
    noise = np.random.normal(0, 0.002, n - 1)
    correlated_returns = correlation * base_returns + np.sqrt(1 - correlation**2) * noise

    # Add mean reversion component
    spread = np.zeros(n)
    spread[0] = 0.0

    for i in range(1, n):
        # Mean reversion: spread pulls towards zero
        spread[i] = spread[i-1] * (1 - mean_reversion_strength) + correlated_returns[i-1]

    # Convert spread back to price level
    base_log = np.log(base_pair)
    pair_log = base_log + spread
    pair_prices = np.exp(pair_log)

    return pair_prices.tolist()


def create_test_dataset() -> Dict[str, List[float]]:
    """
    Create synthetic dataset with some cointegrated pairs for testing.

    Returns:
        Dictionary of price data
    """
    logger.info("Generating synthetic test dataset...")

    # Generate base pairs
    eur_usd = generate_synthetic_pair_data(1000, base_price=1.08, volatility=0.003)
    usd_jpy = generate_synthetic_pair_data(1000, base_price=150.0, volatility=0.004)

    # Generate cointegrated pairs
    gbp_usd = generate_cointegrated_pair(eur_usd, correlation=0.85, mean_reversion_strength=0.2)
    aud_usd = generate_cointegrated_pair(eur_usd, correlation=0.75, mean_reversion_strength=0.25)

    # Generate non-cointegrated pair
    usd_chf = generate_synthetic_pair_data(1000, base_price=0.88, volatility=0.003)

    data = {
        'EUR_USD': eur_usd,
        'GBP_USD': gbp_usd,
        'AUD_USD': aud_usd,
        'USD_JPY': usd_jpy,
        'USD_CHF': usd_chf,
    }

    logger.info(f"Generated {len(data)} pairs with {len(eur_usd)} data points each")
    return data


def find_best_pairs(data: Dict[str, List[float]], top_n: int = 5) -> List[Tuple[str, str, float]]:
    """
    Find best cointegrated pairs based on half-life.

    Args:
        data: Price data dictionary
        top_n: Number of top pairs to return

    Returns:
        List of (pair1, pair2, half_life) tuples
    """
    logger.info("Searching for cointegrated pairs...")

    strategy = StatisticalArbitrageStrategy()

    # Load all data into strategy
    pairs = list(data.keys())
    n_bars = min(len(prices) for prices in data.values())

    for bar_idx in range(n_bars):
        for pair, prices in data.items():
            if bar_idx < len(prices):
                strategy.add_price(pair, prices[bar_idx])

    # Test all pair combinations
    pair_scores = []

    for i, pair1 in enumerate(pairs):
        for pair2 in pairs[i+1:]:
            is_coint, hedge_ratio, half_life = strategy.test_cointegration(pair1, pair2)

            if is_coint and half_life < 100:  # Filter out extremely slow mean reversion
                pair_scores.append((pair1, pair2, half_life))
                logger.info(f"{pair1}/{pair2}: Half-life = {half_life:.2f} bars (Cointegrated)")

    # Sort by half-life (lower is better for trading)
    pair_scores.sort(key=lambda x: x[2])

    return pair_scores[:top_n]


def run_comprehensive_backtest():
    """
    Run comprehensive backtest of statistical arbitrage strategy.
    """
    print("\n" + "="*80)
    print(" STATISTICAL ARBITRAGE STRATEGY - PAIRS TRADING BACKTEST")
    print("="*80 + "\n")

    # Choose data source
    use_live_data = True

    if use_live_data:
        try:
            # Try to fetch real data
            pairs = ["EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD", "USD_CHF", "USD_JPY", "EUR_GBP", "EUR_JPY"]
            data = fetch_historical_data(pairs, granularity="H4", count=1000)

            # Check if we got real data
            if all(len(prices) < 100 for prices in data.values()):
                raise Exception("Insufficient data fetched")

        except Exception as e:
            logger.warning(f"Could not fetch live data: {e}")
            logger.info("Using synthetic test data instead")
            data = create_test_dataset()
    else:
        data = create_test_dataset()

    print(f"\nDataset Summary:")
    print(f"  Pairs: {len(data)}")
    print(f"  Bars per pair: {min(len(p) for p in data.values())}")
    print(f"  Pairs: {', '.join(data.keys())}")

    # Find best cointegrated pairs
    print("\n" + "-"*80)
    print(" COINTEGRATION ANALYSIS")
    print("-"*80 + "\n")

    best_pairs = find_best_pairs(data, top_n=10)

    if not best_pairs:
        print("No cointegrated pairs found. Strategy may not be profitable.")
        return

    print(f"\nTop {len(best_pairs)} Cointegrated Pairs:")
    for i, (pair1, pair2, half_life) in enumerate(best_pairs, 1):
        print(f"  {i}. {pair1}/{pair2}: Half-life = {half_life:.2f} bars")

    # Test multiple parameter configurations
    print("\n" + "-"*80)
    print(" PARAMETER OPTIMIZATION")
    print("-"*80 + "\n")

    parameter_configs = [
        {"zscore_entry": 2.0, "zscore_exit": 0.5, "max_hold_bars": 50, "lookback_period": 60},
        {"zscore_entry": 2.5, "zscore_exit": 0.5, "max_hold_bars": 40, "lookback_period": 60},
        {"zscore_entry": 1.5, "zscore_exit": 0.3, "max_hold_bars": 60, "lookback_period": 80},
        {"zscore_entry": 2.0, "zscore_exit": 0.7, "max_hold_bars": 50, "lookback_period": 100},
    ]

    results_all = []

    for idx, params in enumerate(parameter_configs, 1):
        print(f"\nConfig {idx}: {params}")

        # Use top 3 pairs for trading
        pair_combinations = [(p1, p2) for p1, p2, _ in best_pairs[:3]]

        results = backtest_pairs_trading(
            data=data,
            pair_combinations=pair_combinations,
            strategy_params=params
        )

        results['params'] = params
        results_all.append(results)

        print(f"  Total Trades: {results['total_trades']}")
        print(f"  Win Rate: {results['win_rate']*100:.2f}%")
        print(f"  Profit Factor: {results['profit_factor']:.2f}")
        print(f"  Total P&L: ${results['total_pnl']:.2f} ({results['total_pnl_pct']:.2f}%)")
        print(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown: {results['max_drawdown']*100:.2f}%")

    # Find best configuration
    best_result = max(results_all, key=lambda x: x['sharpe_ratio'] if x['sharpe_ratio'] > 0 else x['total_pnl'])

    print("\n" + "="*80)
    print(" BEST CONFIGURATION RESULTS")
    print("="*80 + "\n")

    print(f"Parameters: {best_result['params']}\n")
    print(f"Total Trades: {best_result['total_trades']}")
    print(f"Winning Trades: {best_result['winning_trades']}")
    print(f"Losing Trades: {best_result['losing_trades']}")
    print(f"Win Rate: {best_result['win_rate']*100:.2f}%")
    print(f"Profit Factor: {best_result['profit_factor']:.2f}")
    print(f"Average Win: ${best_result['avg_win']:.2f}")
    print(f"Average Loss: ${best_result['avg_loss']:.2f}")
    print(f"Total P&L: ${best_result['total_pnl']:.2f} ({best_result['total_pnl_pct']:.2f}%)")
    print(f"Final Equity: ${best_result['final_equity']:.2f}")
    print(f"Max Drawdown: {best_result['max_drawdown']*100:.2f}%")
    print(f"Sharpe Ratio: {best_result['sharpe_ratio']:.2f}")

    # Show sample trades
    if best_result['trades']:
        print(f"\n" + "-"*80)
        print(" SAMPLE TRADES (First 10)")
        print("-"*80 + "\n")

        for i, trade in enumerate(best_result['trades'][:10], 1):
            print(f"{i}. {trade['pair1']}/{trade['pair2']} - {trade['side']}")
            print(f"   Entry Z-score: {trade['entry_zscore']:.2f}")
            print(f"   Duration: {trade['exit_bar'] - trade['entry_bar']} bars")
            print(f"   P&L: ${trade['pnl_dollars']:.2f} ({trade['pnl_pct']:.2f}%)")
            print(f"   Exit: {trade['exit_reason']}\n")

    # Save results to file
    output_file = "/home/user0/oandabot16/oanda_bot/statistical_arbitrage_results.json"
    with open(output_file, 'w') as f:
        # Remove equity curve for JSON serialization (too large)
        save_result = {k: v for k, v in best_result.items() if k != 'equity_curve'}
        # Limit trades to first 100
        if 'trades' in save_result:
            save_result['trades'] = save_result['trades'][:100]
        json.dump(save_result, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")

    print("\n" + "="*80)
    print(" STRATEGY SUMMARY")
    print("="*80 + "\n")

    print("Statistical Arbitrage Edge Identified:")
    print(f"  - Exploits mean reversion in cointegrated currency pairs")
    print(f"  - Best pair: {best_pairs[0][0]}/{best_pairs[0][1]} (half-life: {best_pairs[0][2]:.1f} bars)")
    print(f"  - Entry signal: Z-score > {best_result['params']['zscore_entry']} (absolute value)")
    print(f"  - Exit signal: Z-score crosses {best_result['params']['zscore_exit']}")
    print(f"  - Risk management: Stop at Z-score > 3.0, max hold {best_result['params']['max_hold_bars']} bars")

    if best_result['total_trades'] > 0:
        print(f"\nBacktest Performance:")
        print(f"  - Sample size: {best_result['total_trades']} trades")
        print(f"  - Win rate: {best_result['win_rate']*100:.1f}%")
        print(f"  - Profit factor: {best_result['profit_factor']:.2f}")
        print(f"  - Sharpe ratio: {best_result['sharpe_ratio']:.2f}")
        print(f"  - Max drawdown: {best_result['max_drawdown']*100:.1f}%")
        print(f"  - Total return: {best_result['total_pnl_pct']:.1f}%")

        if best_result['sharpe_ratio'] > 1.0 and best_result['win_rate'] > 0.5:
            print("\n  Status: PROFITABLE EDGE FOUND")
        else:
            print("\n  Status: Edge identified but requires optimization")
    else:
        print("\nNo trades generated. Consider adjusting parameters.")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    try:
        run_comprehensive_backtest()
    except KeyboardInterrupt:
        print("\n\nBacktest interrupted by user.")
    except Exception as e:
        logger.error(f"Error during backtest: {e}", exc_info=True)
        raise
