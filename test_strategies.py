#!/usr/bin/env python3
"""
Quick backtester for new strategies.
Tests each strategy on recent M1 data to validate positive expectancy.
"""
import json
import sys
import os

# Ensure we can import from oanda_bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oanda_bot.data.core import get_candles
from oanda_bot.backtest import run_backtest

# Import all strategies to test
from oanda_bot.strategy.momentum_scalp import StrategyMomentumScalp
from oanda_bot.strategy.order_flow import StrategyOrderFlow
from oanda_bot.strategy.micro_reversion import StrategyMicroReversion
from oanda_bot.strategy.rsi_reversion import StrategyRSIReversion
from oanda_bot.strategy.macd_trends import MACDTrendStrategy
from oanda_bot.strategy.bollinger_squeeze import StrategyBollingerSqueeze
from oanda_bot.strategy.trend_ma import StrategyTrendMA


def test_strategy(strategy_class, params, candles, warmup=50):
    """Run backtest and return results."""
    try:
        strategy = strategy_class(params)
        stats = run_backtest(strategy, candles, warmup=warmup)
        if isinstance(stats, tuple):
            stats = stats[0]
        return stats
    except Exception as e:
        return {"error": str(e), "trades": 0, "win_rate": 0, "total_pnl": 0}


def main():
    print("=" * 60)
    print("Strategy Backtesting Report")
    print("=" * 60)

    # Pairs to test
    pairs = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD"]

    # Strategies to test
    strategies = [
        ("MomentumScalp", StrategyMomentumScalp, {
            "momentum_period": 5,
            "atr_period": 20,
            "momentum_threshold": 2.0,
            "profit_target_atr": 1.5,
            "stop_loss_atr": 1.0,
            "max_hold_bars": 30,
            "cooldown_bars": 10
        }),
        ("OrderFlow", StrategyOrderFlow, {
            "tick_window": 10,
            "imbalance_threshold": 0.7,
            "min_tick_count": 5,
            "profit_target_pips": 3.0,
            "stop_loss_pips": 2.0
        }),
        ("MicroReversion", StrategyMicroReversion, {
            "lookback": 20,
            "std_mult": 2.5,
            "min_extension": 1.5,
            "profit_target_std": 1.0,
            "stop_loss_std": 1.5,
            "max_hold_bars": 30
        }),
        ("RSIReversion", StrategyRSIReversion, {
            "rsi_len": 14,
            "overbought": 75,
            "oversold": 25,
            "exit_mid": 50
        }),
        ("MACDTrend", MACDTrendStrategy, {
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_sig": 9,
            "ema_trend": 50  # Reduced for faster signals
        }),
        ("BollingerSqueeze", StrategyBollingerSqueeze, {
            "window": 20,
            "atr_window": 14,
            "width_pct": 0.1
        }),
        ("TrendMA", StrategyTrendMA, {
            "fast": 20,  # Reduced for faster signals
            "slow": 50,
            "atr_window": 14,
            "atr_mult": 1.5
        }),
    ]

    results = []

    for pair in pairs:
        print(f"\n--- Testing on {pair} ---")
        print(f"Fetching M1 candles...")

        try:
            candles = get_candles(pair, "M1", 500)
            print(f"Got {len(candles)} candles")
        except Exception as e:
            print(f"Failed to fetch candles for {pair}: {e}")
            continue

        for name, strategy_class, params in strategies:
            stats = test_strategy(strategy_class, params, candles, warmup=100)

            trades = stats.get("trades", 0)
            win_rate = stats.get("win_rate", 0) * 100
            total_pnl = stats.get("total_pnl", 0)
            expectancy = stats.get("expectancy", 0)
            error = stats.get("error", "")

            result = {
                "pair": pair,
                "strategy": name,
                "trades": trades,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "expectancy": expectancy,
                "error": error
            }
            results.append(result)

            if error:
                print(f"  {name}: ERROR - {error}")
            else:
                status = "+" if total_pnl > 0 else "-" if total_pnl < 0 else "="
                print(f"  {name}: {trades} trades, {win_rate:.1f}% win, PnL: {total_pnl:.5f} [{status}]")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    # Aggregate by strategy
    strategy_totals = {}
    for r in results:
        name = r["strategy"]
        if name not in strategy_totals:
            strategy_totals[name] = {"trades": 0, "wins": 0, "pnl": 0}
        strategy_totals[name]["trades"] += r["trades"]
        strategy_totals[name]["pnl"] += r["total_pnl"]
        if r["trades"] > 0 and r["win_rate"] > 0:
            strategy_totals[name]["wins"] += int(r["trades"] * r["win_rate"] / 100)

    print("\nStrategy Performance (all pairs combined):")
    for name, totals in sorted(strategy_totals.items(), key=lambda x: x[1]["pnl"], reverse=True):
        trades = totals["trades"]
        if trades > 0:
            win_rate = totals["wins"] / trades * 100
            pnl = totals["pnl"]
            status = "PROFITABLE" if pnl > 0 else "LOSING"
            print(f"  {name}: {trades} trades, {win_rate:.1f}% win rate, PnL: {pnl:.5f} [{status}]")
        else:
            print(f"  {name}: No trades")

    # Recommendations
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)

    profitable = [name for name, totals in strategy_totals.items()
                  if totals["pnl"] > 0 and totals["trades"] >= 5]
    losing = [name for name, totals in strategy_totals.items()
              if totals["pnl"] < 0 and totals["trades"] >= 5]

    if profitable:
        print(f"Enable: {', '.join(profitable)}")
    if losing:
        print(f"Disable: {', '.join(losing)}")


if __name__ == "__main__":
    main()
