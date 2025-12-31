#!/usr/bin/env python3
"""
Quick Price Action Edge Test

Tests price action strategies on a smaller dataset for faster results.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oanda_bot.data.core import get_candles
from oanda_bot.backtest import run_backtest
from oanda_bot.strategy.price_action import StrategyPriceAction


def test_quick():
    """Quick test of price action strategies."""

    print("=" * 60)
    print("QUICK PRICE ACTION EDGE TEST")
    print("=" * 60)

    # Test configurations
    configs = [
        {
            "name": "PinBar_Conservative",
            "params": {
                "pin_wick_ratio": 2.5,
                "lookback_sr": 20,
                "sl_mult": 1.0,
                "tp_mult": 2.5,
                "pin_weight": 1.5,
                "engulf_weight": 0.5,
                "breakout_weight": 0.3,
                "min_signal_strength": 1.5
            }
        },
        {
            "name": "Engulfing_Primary",
            "params": {
                "pin_wick_ratio": 2.5,
                "lookback_sr": 20,
                "sl_mult": 1.2,
                "tp_mult": 2.5,
                "pin_weight": 0.5,
                "engulf_weight": 2.0,
                "breakout_weight": 0.3,
                "min_signal_strength": 1.5
            }
        },
        {
            "name": "Combined_Balanced",
            "params": {
                "pin_wick_ratio": 2.2,
                "lookback_sr": 20,
                "sl_mult": 1.3,
                "tp_mult": 2.8,
                "pin_weight": 1.0,
                "engulf_weight": 1.0,
                "breakout_weight": 1.0,
                "min_signal_strength": 1.3
            }
        }
    ]

    pairs = ["EUR_USD", "GBP_USD"]
    timeframes = [("M5", 500), ("H1", 300)]

    results = []

    for pair in pairs:
        print(f"\n{'='*60}")
        print(f"Testing {pair}")
        print(f"{'='*60}")

        for tf, count in timeframes:
            print(f"\n--- {tf} ({count} candles) ---")

            try:
                candles = get_candles(pair, tf, count)
                print(f"Fetched {len(candles)} candles")

                for config in configs:
                    print(f"\n  {config['name']}:")

                    strategy = StrategyPriceAction(config["params"])
                    warmup = 30

                    stats = run_backtest(strategy, candles, warmup=warmup)

                    trades = stats.get("trades", 0)
                    win_rate = stats.get("win_rate", 0) * 100
                    pnl = stats.get("total_pnl", 0)
                    expectancy = stats.get("expectancy", 0)
                    avg_win = stats.get("avg_win", 0)
                    avg_loss = stats.get("avg_loss", 0)

                    # Convert to pips
                    pips = pnl / 0.0001 if "JPY" not in pair else pnl / 0.01

                    status = "PROFIT" if pnl > 0 else "LOSS" if pnl < 0 else "NEUTRAL"

                    result = {
                        "config": config["name"],
                        "pair": pair,
                        "timeframe": tf,
                        "trades": trades,
                        "win_rate": win_rate,
                        "pnl": pnl,
                        "pips": pips,
                        "expectancy": expectancy,
                        "avg_win": avg_win,
                        "avg_loss": avg_loss,
                        "risk_reward": avg_win / avg_loss if avg_loss > 0 else 0
                    }
                    results.append(result)

                    print(f"    Trades: {trades}")
                    print(f"    Win Rate: {win_rate:.1f}%")
                    print(f"    PnL: {pnl:.5f} ({pips:.1f} pips)")
                    print(f"    Expectancy: {expectancy:.6f}")
                    if avg_loss > 0:
                        print(f"    Risk:Reward: 1:{avg_win/avg_loss:.2f}")
                    print(f"    Status: {status}")

            except Exception as e:
                print(f"  ERROR: {e}")

    # Summary
    print("\n\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    # Best overall
    profitable = [r for r in results if r["pnl"] > 0 and r["trades"] >= 3]
    if profitable:
        best = max(profitable, key=lambda x: x["pnl"])
        print(f"\nBest Setup:")
        print(f"  {best['config']} on {best['pair']} {best['timeframe']}")
        print(f"  {best['trades']} trades, {best['win_rate']:.1f}% win rate")
        print(f"  {best['pips']:.1f} pips profit")
        print(f"  Expectancy: {best['expectancy']:.6f}")

    # By strategy
    print("\nBy Strategy:")
    strategy_totals = {}
    for r in results:
        name = r["config"]
        if name not in strategy_totals:
            strategy_totals[name] = {"trades": 0, "pnl": 0, "pips": 0}
        strategy_totals[name]["trades"] += r["trades"]
        strategy_totals[name]["pnl"] += r["pnl"]
        strategy_totals[name]["pips"] += r["pips"]

    for name, totals in sorted(strategy_totals.items(), key=lambda x: x[1]["pnl"], reverse=True):
        print(f"  {name}: {totals['trades']} trades, {totals['pips']:.1f} pips")

    # By pair
    print("\nBy Pair:")
    pair_totals = {}
    for r in results:
        pair = r["pair"]
        if pair not in pair_totals:
            pair_totals[pair] = {"trades": 0, "pnl": 0, "pips": 0}
        pair_totals[pair]["trades"] += r["trades"]
        pair_totals[pair]["pnl"] += r["pnl"]
        pair_totals[pair]["pips"] += r["pips"]

    for pair, totals in sorted(pair_totals.items(), key=lambda x: x[1]["pnl"], reverse=True):
        print(f"  {pair}: {totals['trades']} trades, {totals['pips']:.1f} pips")

    # Recommendations
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)

    if profitable:
        print("\nEnable these setups:")
        for r in sorted(profitable, key=lambda x: x["pnl"], reverse=True)[:3]:
            print(f"  - {r['config']} on {r['pair']} {r['timeframe']}")
            print(f"    ({r['trades']} trades, {r['win_rate']:.1f}% WR, {r['pips']:.1f} pips)")
    else:
        print("\nNo profitable setups found in this test.")
        print("Consider:")
        print("  - Testing on different timeframes")
        print("  - Adjusting parameter ranges")
        print("  - Testing on more data")


if __name__ == "__main__":
    test_quick()
