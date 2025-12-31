#!/usr/bin/env python3
"""
backtest_edges.py

Comprehensive backtesting script for multiple edge strategies across multiple
currency pairs and timeframes. Generates detailed performance reports.
"""

import json
import time
import logging
from typing import Dict, List, Any
import numpy as np

from oanda_bot.data.core import get_candles
from oanda_bot.backtest import run_backtest
from oanda_bot.strategy.rsi_divergence import StrategyRSIDivergence
from oanda_bot.strategy.macd_histogram import StrategyMACDHistogram
from oanda_bot.strategy.bb_atr_breakout import StrategyBBATRBreakout
from oanda_bot.strategy.ma_confluence import StrategyMAConfluence
from oanda_bot.strategy.atr_channel import StrategyATRChannel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Strategy configurations with optimized parameters
STRATEGY_CONFIGS = {
    "RSIDivergence": {
        "class": StrategyRSIDivergence,
        "params": {
            "rsi_len": 14,
            "divergence_window": 20,
            "min_rsi_oversold": 35,
            "max_rsi_overbought": 65,
            "sl_mult": 1.5,
            "tp_mult": 2.5,
            "max_duration": 50,
        },
        "warmup": 40,
    },
    "MACDHistogram": {
        "class": StrategyMACDHistogram,
        "params": {
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_sig": 9,
            "ema_trend": 50,
            "hist_threshold": 0.0001,
            "sl_mult": 1.2,
            "tp_mult": 2.0,
            "max_duration": 30,
        },
        "warmup": 60,
    },
    "BBATRBreakout": {
        "class": StrategyBBATRBreakout,
        "params": {
            "bb_period": 20,
            "bb_std": 2.0,
            "atr_period": 14,
            "squeeze_ratio": 1.5,
            "breakout_confirm": 3,
            "sl_mult": 1.0,
            "tp_mult": 2.5,
            "max_duration": 40,
        },
        "warmup": 40,
    },
    "MAConfluence": {
        "class": StrategyMAConfluence,
        "params": {
            "ma_periods": [20, 50, 100, 200],
            "ma_type": "EMA",
            "confluence_pct": 0.3,
            "atr_period": 14,
            "bounce_confirm": 2,
            "min_mas_confluent": 3,
            "sl_mult": 1.0,
            "tp_mult": 2.0,
            "max_duration": 35,
        },
        "warmup": 210,
    },
    "ATRChannel": {
        "class": StrategyATRChannel,
        "params": {
            "ema_period": 20,
            "atr_period": 14,
            "atr_mult": 2.0,
            "trend_ema": 50,
            "breakout_confirm": 2,
            "min_atr": 0.0001,
            "sl_mult": 1.5,
            "tp_mult": 3.0,
            "max_duration": 40,
        },
        "warmup": 60,
    },
}

# Currency pairs to test
CURRENCY_PAIRS = [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "AUD_USD",
    "USD_CAD",
    "EUR_GBP",
]

# Timeframes to test
TIMEFRAMES = [
    ("M5", 5000),   # 5-minute bars
    ("M15", 4000),  # 15-minute bars
    ("H1", 3000),   # 1-hour bars
]


def calculate_metrics(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate additional performance metrics."""
    trades = stats.get("trades", 0)
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    win_rate = stats.get("win_rate", 0.0)
    avg_win = stats.get("avg_win", 0.0)
    avg_loss = stats.get("avg_loss", 0.0)
    total_pnl = stats.get("total_pnl", 0.0)
    expectancy = stats.get("expectancy", 0.0)

    # Profit factor
    total_wins = wins * avg_win
    total_losses = losses * avg_loss
    profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

    # Sharpe ratio (simplified - assumes trades are independent)
    if trades > 1:
        pnl_per_trade = [avg_win if i < wins else -avg_loss for i in range(trades)]
        sharpe = (np.mean(pnl_per_trade) / np.std(pnl_per_trade)) * np.sqrt(252) if np.std(pnl_per_trade) > 0 else 0.0
    else:
        sharpe = 0.0

    # Max drawdown (simplified estimate)
    max_drawdown = avg_loss * max(3, losses // 2) if losses > 0 else 0.0

    return {
        **stats,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "total_pips": total_pnl / 0.0001,  # Assuming EUR_USD pip size
    }


def backtest_strategy(strategy_name: str, pair: str, granularity: str, count: int) -> Dict[str, Any]:
    """Backtest a single strategy on a single pair/timeframe."""
    logger.info(f"Backtesting {strategy_name} on {pair} @ {granularity}")

    config = STRATEGY_CONFIGS[strategy_name]
    strategy_class = config["class"]
    params = config["params"].copy()
    warmup = config["warmup"]

    try:
        # Fetch historical data
        candles = get_candles(pair, granularity, count)
        logger.info(f"  Fetched {len(candles)} candles for {pair}")

        if len(candles) < warmup + 100:
            logger.warning(f"  Not enough candles for {pair} @ {granularity}")
            return None

        # Create strategy instance
        strategy = strategy_class(params)

        # Run backtest
        start_time = time.time()
        stats = run_backtest(strategy, candles, warmup)
        duration = time.time() - start_time

        # Calculate extended metrics
        metrics = calculate_metrics(stats)
        metrics["pair"] = pair
        metrics["granularity"] = granularity
        metrics["duration_seconds"] = duration

        logger.info(f"  Completed in {duration:.2f}s - Trades: {metrics['trades']}, "
                   f"Win Rate: {metrics['win_rate']:.2%}, Expectancy: {metrics['expectancy']:.5f}")

        return metrics

    except Exception as e:
        logger.error(f"  Error backtesting {strategy_name} on {pair} @ {granularity}: {e}")
        return None


def run_comprehensive_backtest():
    """Run comprehensive backtest across all strategies, pairs, and timeframes."""
    logger.info("=" * 80)
    logger.info("COMPREHENSIVE EDGE STRATEGY BACKTEST")
    logger.info("=" * 80)

    all_results = {}

    for strategy_name in STRATEGY_CONFIGS.keys():
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing Strategy: {strategy_name}")
        logger.info(f"{'='*80}")

        strategy_results = []

        for pair in CURRENCY_PAIRS:
            for granularity, count in TIMEFRAMES:
                result = backtest_strategy(strategy_name, pair, granularity, count)
                if result:
                    strategy_results.append(result)

                # Rate limiting - OANDA allows 120 req/min
                time.sleep(0.6)

        all_results[strategy_name] = strategy_results

    return all_results


def generate_report(results: Dict[str, List[Dict[str, Any]]]):
    """Generate comprehensive performance report."""
    logger.info("\n" + "=" * 80)
    logger.info("BACKTEST RESULTS SUMMARY")
    logger.info("=" * 80)

    summary = {}

    for strategy_name, strategy_results in results.items():
        if not strategy_results:
            continue

        logger.info(f"\n{strategy_name}:")
        logger.info("-" * 80)

        # Filter results with meaningful trade count
        valid_results = [r for r in strategy_results if r["trades"] >= 10]

        if not valid_results:
            logger.info("  No valid results (need >= 10 trades)")
            continue

        # Sort by expectancy
        sorted_results = sorted(valid_results, key=lambda x: x["expectancy"], reverse=True)

        # Best performance
        best = sorted_results[0]
        logger.info(f"\n  BEST PERFORMANCE: {best['pair']} @ {best['granularity']}")
        logger.info(f"    Trades: {best['trades']}")
        logger.info(f"    Win Rate: {best['win_rate']:.2%}")
        logger.info(f"    Profit Factor: {best['profit_factor']:.2f}")
        logger.info(f"    Expectancy: {best['expectancy']:.5f}")
        logger.info(f"    Sharpe Ratio: {best['sharpe_ratio']:.2f}")
        logger.info(f"    Max Drawdown: {best['max_drawdown']:.5f}")
        logger.info(f"    Total P&L: {best['total_pnl']:.5f} ({best['total_pips']:.1f} pips)")

        # Calculate aggregate stats
        avg_win_rate = np.mean([r["win_rate"] for r in valid_results])
        avg_profit_factor = np.mean([r["profit_factor"] for r in valid_results if r["profit_factor"] > 0])
        avg_expectancy = np.mean([r["expectancy"] for r in valid_results])

        logger.info(f"\n  AGGREGATE STATS (across all pairs/timeframes):")
        logger.info(f"    Average Win Rate: {avg_win_rate:.2%}")
        logger.info(f"    Average Profit Factor: {avg_profit_factor:.2f}")
        logger.info(f"    Average Expectancy: {avg_expectancy:.5f}")

        # Top 5 configurations
        logger.info(f"\n  TOP 5 CONFIGURATIONS:")
        for i, result in enumerate(sorted_results[:5], 1):
            logger.info(f"    {i}. {result['pair']} @ {result['granularity']}: "
                       f"WR={result['win_rate']:.2%}, PF={result['profit_factor']:.2f}, "
                       f"Exp={result['expectancy']:.5f}")

        summary[strategy_name] = {
            "best": best,
            "avg_win_rate": avg_win_rate,
            "avg_profit_factor": avg_profit_factor,
            "avg_expectancy": avg_expectancy,
            "top_configs": sorted_results[:5],
        }

    # Overall comparison
    logger.info("\n" + "=" * 80)
    logger.info("STRATEGY COMPARISON (Best Performance)")
    logger.info("=" * 80)

    comparison = []
    for strategy_name, data in summary.items():
        best = data["best"]
        comparison.append({
            "strategy": strategy_name,
            "pair": best["pair"],
            "timeframe": best["granularity"],
            "win_rate": best["win_rate"],
            "profit_factor": best["profit_factor"],
            "expectancy": best["expectancy"],
            "sharpe": best["sharpe_ratio"],
        })

    # Sort by expectancy
    comparison.sort(key=lambda x: x["expectancy"], reverse=True)

    for i, item in enumerate(comparison, 1):
        logger.info(f"{i}. {item['strategy']:20s} ({item['pair']} @ {item['timeframe']}): "
                   f"WR={item['win_rate']:.2%}, PF={item['profit_factor']:.2f}, "
                   f"Exp={item['expectancy']:.5f}, Sharpe={item['sharpe']:.2f}")

    # Save results to JSON
    output_file = "edge_backtest_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary,
            "comparison": comparison,
            "detailed_results": results,
        }, f, indent=2, default=str)

    logger.info(f"\nDetailed results saved to: {output_file}")

    return summary


if __name__ == "__main__":
    try:
        results = run_comprehensive_backtest()
        summary = generate_report(results)
        logger.info("\nBacktest completed successfully!")
    except KeyboardInterrupt:
        logger.info("\nBacktest interrupted by user")
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
