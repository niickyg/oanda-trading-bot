#!/usr/bin/env python3
"""
Improved Statistical Arbitrage Strategy - Mean Reversion with Correlation

This strategy uses a simpler, more robust approach:
1. Identifies highly correlated pairs (correlation > 0.8)
2. Calculates normalized spread (ratio-based)
3. Trades mean reversion when spread deviates from historical average
4. Uses strict risk management with position sizing

This is more suitable for forex markets than pure cointegration.
"""

import sys
import os
import logging
import json
import numpy as np
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ImprovedStatArb:
    """
    Simplified statistical arbitrage using correlation and mean reversion.
    """

    def __init__(
        self,
        lookback: int = 50,
        entry_threshold: float = 1.5,  # Standard deviations
        exit_threshold: float = 0.5,
        stop_loss_threshold: float = 2.5,
        min_correlation: float = 0.75,
        position_size_pct: float = 0.02,  # 2% risk per trade
    ):
        self.lookback = lookback
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.stop_loss_threshold = stop_loss_threshold
        self.min_correlation = min_correlation
        self.position_size_pct = position_size_pct

    def calculate_correlation(self, prices1: np.ndarray, prices2: np.ndarray) -> float:
        """Calculate correlation coefficient"""
        if len(prices1) < 2 or len(prices2) < 2:
            return 0.0

        returns1 = np.diff(np.log(prices1))
        returns2 = np.diff(np.log(prices2))

        if len(returns1) < 2:
            return 0.0

        corr_matrix = np.corrcoef(returns1, returns2)
        return corr_matrix[0, 1]

    def calculate_spread_ratio(self, prices1: np.ndarray, prices2: np.ndarray) -> np.ndarray:
        """Calculate spread as price ratio"""
        return prices1 / prices2

    def calculate_zscore(self, spread: np.ndarray) -> float:
        """Calculate z-score of current spread"""
        if len(spread) < 2:
            return 0.0

        mean = np.mean(spread[:-1])  # Use all but current for mean
        std = np.std(spread[:-1])

        if std < 1e-10:
            return 0.0

        return (spread[-1] - mean) / std


def backtest_improved_strategy(
    data: Dict[str, List[float]],
    params: Dict = None,
) -> Dict:
    """
    Backtest the improved statistical arbitrage strategy.
    """
    if params is None:
        params = {}

    strategy = ImprovedStatArb(**params)

    # Find best correlated pairs
    pairs = list(data.keys())
    correlations = []

    for i, pair1 in enumerate(pairs):
        for pair2 in pairs[i+1:]:
            prices1 = np.array(data[pair1])
            prices2 = np.array(data[pair2])

            corr = strategy.calculate_correlation(prices1, prices2)

            if abs(corr) >= strategy.min_correlation:
                correlations.append((pair1, pair2, corr))

    correlations.sort(key=lambda x: abs(x[2]), reverse=True)

    logger.info(f"Found {len(correlations)} correlated pairs (threshold: {strategy.min_correlation})")

    if not correlations:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'total_pnl': 0.0,
        }

    # Trade the top 3 most correlated pairs
    trading_pairs = correlations[:3]

    for pair1, pair2, corr in trading_pairs:
        logger.info(f"Trading pair: {pair1}/{pair2}, Correlation: {corr:.3f}")

    # Backtest
    n_bars = min(len(data[p]) for p in pairs)
    equity = 10000.0
    equity_curve = [equity]
    trades = []
    positions = {}  # pair_key: position_info

    for bar in range(strategy.lookback, n_bars):
        # Check exits
        for pair_key in list(positions.keys()):
            pos = positions[pair_key]
            pair1, pair2 = pos['pair1'], pos['pair2']

            # Get current prices
            p1 = np.array(data[pair1][bar - strategy.lookback:bar + 1])
            p2 = np.array(data[pair2][bar - strategy.lookback:bar + 1])

            spread = strategy.calculate_spread_ratio(p1, p2)
            zscore = strategy.calculate_zscore(spread)

            should_exit = False
            exit_reason = ""

            # Stop loss
            if abs(zscore) > strategy.stop_loss_threshold:
                should_exit = True
                exit_reason = "STOP_LOSS"

            # Profit target
            elif pos['side'] == 'LONG' and zscore > -strategy.exit_threshold:
                should_exit = True
                exit_reason = "PROFIT_TARGET"
            elif pos['side'] == 'SHORT' and zscore < strategy.exit_threshold:
                should_exit = True
                exit_reason = "PROFIT_TARGET"

            # Max hold
            elif bar - pos['entry_bar'] >= 100:
                should_exit = True
                exit_reason = "MAX_HOLD"

            if should_exit:
                # Calculate P&L
                current_spread = p1[-1] / p2[-1]
                entry_spread = pos['entry_spread']

                if pos['side'] == 'LONG':
                    # Bought spread (long p1, short p2)
                    pnl_pct = (current_spread - entry_spread) / entry_spread
                else:
                    # Sold spread (short p1, long p2)
                    pnl_pct = (entry_spread - current_spread) / entry_spread

                pnl_dollars = equity * strategy.position_size_pct * pnl_pct
                equity += pnl_dollars

                trades.append({
                    'pair1': pair1,
                    'pair2': pair2,
                    'side': pos['side'],
                    'entry_bar': pos['entry_bar'],
                    'exit_bar': bar,
                    'entry_zscore': pos['entry_zscore'],
                    'exit_zscore': zscore,
                    'pnl_pct': pnl_pct * 100,
                    'pnl_dollars': pnl_dollars,
                    'exit_reason': exit_reason,
                })

                del positions[pair_key]

        # Look for entries
        if len(positions) < 3:
            for pair1, pair2, corr in trading_pairs:
                pair_key = f"{pair1}_{pair2}"

                if pair_key in positions:
                    continue

                # Get prices
                p1 = np.array(data[pair1][bar - strategy.lookback:bar + 1])
                p2 = np.array(data[pair2][bar - strategy.lookback:bar + 1])

                spread = strategy.calculate_spread_ratio(p1, p2)
                zscore = strategy.calculate_zscore(spread)

                signal = None

                if zscore < -strategy.entry_threshold:
                    signal = 'LONG'  # Spread too low, buy it
                elif zscore > strategy.entry_threshold:
                    signal = 'SHORT'  # Spread too high, sell it

                if signal:
                    positions[pair_key] = {
                        'pair1': pair1,
                        'pair2': pair2,
                        'side': signal,
                        'entry_bar': bar,
                        'entry_spread': spread[-1],
                        'entry_zscore': zscore,
                    }
                    break

        equity_curve.append(equity)

    # Close remaining positions
    for pair_key, pos in positions.items():
        pair1, pair2 = pos['pair1'], pos['pair2']
        p1 = np.array(data[pair1][-strategy.lookback:])
        p2 = np.array(data[pair2][-strategy.lookback:])

        current_spread = p1[-1] / p2[-1]
        entry_spread = pos['entry_spread']

        if pos['side'] == 'LONG':
            pnl_pct = (current_spread - entry_spread) / entry_spread
        else:
            pnl_pct = (entry_spread - current_spread) / entry_spread

        pnl_dollars = equity * strategy.position_size_pct * pnl_pct
        equity += pnl_dollars

        trades.append({
            'pair1': pair1,
            'pair2': pair2,
            'side': pos['side'],
            'entry_bar': pos['entry_bar'],
            'exit_bar': n_bars - 1,
            'entry_zscore': pos['entry_zscore'],
            'pnl_pct': pnl_pct * 100,
            'pnl_dollars': pnl_dollars,
            'exit_reason': 'END_OF_DATA',
        })

    # Calculate metrics
    if not trades:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'total_pnl': 0.0,
        }

    winning_trades = [t for t in trades if t['pnl_dollars'] > 0]
    losing_trades = [t for t in trades if t['pnl_dollars'] <= 0]

    total_wins = sum(t['pnl_dollars'] for t in winning_trades)
    total_losses = abs(sum(t['pnl_dollars'] for t in losing_trades))

    win_rate = len(winning_trades) / len(trades)
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

    # Calculate max drawdown
    peak = equity_curve[0]
    max_dd = 0.0

    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio
    returns = np.diff(equity_curve) / equity_curve[:-1]
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if len(returns) > 0 and np.std(returns) > 0 else 0.0

    return {
        'total_trades': len(trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe,
        'total_pnl': equity - 10000.0,
        'total_pnl_pct': (equity - 10000.0) / 10000.0 * 100,
        'final_equity': equity,
        'avg_win': total_wins / len(winning_trades) if winning_trades else 0.0,
        'avg_loss': total_losses / len(losing_trades) if losing_trades else 0.0,
        'trades': trades,
        'equity_curve': equity_curve,
        'correlated_pairs': correlations,
    }


def fetch_data(pairs: List[str], granularity: str = "H4", count: int = 1000) -> Dict[str, List[float]]:
    """Fetch historical data"""
    try:
        from oanda_bot.data import get_candles
        data = {}

        for pair in pairs:
            logger.info(f"Fetching {count} candles for {pair} @ {granularity}")
            candles = get_candles(symbol=pair, granularity=granularity, count=count)
            prices = [float(c['mid']['c']) for c in candles]
            data[pair] = prices
            logger.info(f"Fetched {len(prices)} prices for {pair}")

        return data
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        raise


def run_improved_backtest():
    """Run improved statistical arbitrage backtest"""

    print("\n" + "="*80)
    print(" IMPROVED STATISTICAL ARBITRAGE - CORRELATION TRADING")
    print("="*80 + "\n")

    # Fetch data
    pairs = ["EUR_USD", "GBP_USD", "AUD_USD", "NZD_USD", "USD_CHF", "USD_JPY", "EUR_GBP", "EUR_JPY"]
    data = fetch_data(pairs, granularity="H4", count=1000)

    print(f"\nDataset: {len(data)} pairs, {min(len(p) for p in data.values())} bars each\n")

    # Test multiple configurations
    configs = [
        {"lookback": 40, "entry_threshold": 1.5, "exit_threshold": 0.3, "min_correlation": 0.70},
        {"lookback": 50, "entry_threshold": 2.0, "exit_threshold": 0.5, "min_correlation": 0.75},
        {"lookback": 60, "entry_threshold": 2.0, "exit_threshold": 0.5, "min_correlation": 0.80},
        {"lookback": 80, "entry_threshold": 1.8, "exit_threshold": 0.4, "min_correlation": 0.75},
    ]

    all_results = []

    print("="*80)
    print(" PARAMETER OPTIMIZATION")
    print("="*80 + "\n")

    for idx, config in enumerate(configs, 1):
        print(f"Config {idx}: {config}")
        results = backtest_improved_strategy(data, config)
        results['params'] = config
        all_results.append(results)

        print(f"  Trades: {results['total_trades']}")
        print(f"  Win Rate: {results['win_rate']*100:.1f}%")
        print(f"  Profit Factor: {results['profit_factor']:.2f}")
        print(f"  Total P&L: ${results['total_pnl']:.2f} ({results['total_pnl_pct']:.2f}%)")
        print(f"  Sharpe: {results['sharpe_ratio']:.2f}")
        print(f"  Max DD: {results['max_drawdown']*100:.1f}%\n")

    # Find best
    best = max(all_results, key=lambda x: x['total_pnl'] if x['total_trades'] > 10 else -999999)

    print("="*80)
    print(" BEST CONFIGURATION")
    print("="*80 + "\n")

    print(f"Parameters: {best['params']}\n")
    print(f"Total Trades: {best['total_trades']}")
    print(f"Win Rate: {best['win_rate']*100:.2f}%")
    print(f"Profit Factor: {best['profit_factor']:.2f}")
    print(f"Sharpe Ratio: {best['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {best['max_drawdown']*100:.2f}%")
    print(f"Total P&L: ${best['total_pnl']:.2f} ({best['total_pnl_pct']:.2f}%)")
    print(f"Final Equity: ${best['final_equity']:.2f}")

    if 'correlated_pairs' in best and best['correlated_pairs']:
        print(f"\nTop Correlated Pairs:")
        for pair1, pair2, corr in best['correlated_pairs'][:5]:
            print(f"  {pair1}/{pair2}: {corr:.3f}")

    if best['trades']:
        print(f"\n" + "-"*80)
        print(" SAMPLE TRADES")
        print("-"*80 + "\n")

        for i, trade in enumerate(best['trades'][:10], 1):
            print(f"{i}. {trade['pair1']}/{trade['pair2']} - {trade['side']}")
            print(f"   Entry Z: {trade['entry_zscore']:.2f}, Duration: {trade['exit_bar'] - trade['entry_bar']} bars")
            print(f"   P&L: ${trade['pnl_dollars']:.2f} ({trade['pnl_pct']:.2f}%) - {trade['exit_reason']}\n")

    # Save results
    output_file = "/home/user0/oandabot16/oanda_bot/improved_stat_arb_results.json"
    save_data = {k: v for k, v in best.items() if k not in ['equity_curve', 'trades']}
    save_data['sample_trades'] = best['trades'][:50]

    with open(output_file, 'w') as f:
        json.dump(save_data, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")

    print("\n" + "="*80)
    print(" FINAL SUMMARY")
    print("="*80 + "\n")

    if best['total_trades'] > 0 and best['total_pnl'] > 0:
        print("PROFITABLE EDGE FOUND!")
        print(f"  Strategy: Correlation-based mean reversion")
        print(f"  Total Return: {best['total_pnl_pct']:.2f}%")
        print(f"  Risk-Adjusted Return (Sharpe): {best['sharpe_ratio']:.2f}")
        print(f"  Win Rate: {best['win_rate']*100:.1f}%")
        print(f"  Profit Factor: {best['profit_factor']:.2f}")
    else:
        print("Strategy requires further optimization.")
        print("Consider: lower entry thresholds, different lookback periods,")
        print("or alternative pair combinations.")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    run_improved_backtest()
