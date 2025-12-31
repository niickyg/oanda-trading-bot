#!/usr/bin/env python3
"""
Comprehensive Price Action Edge Backtester

This script researches and backtests multiple price action edges:
1. Pin bars at support/resistance
2. Engulfing patterns
3. Breakout and retest setups
4. Range breakout strategies
5. Supply/demand zone reversals

Tests across multiple:
- Currency pairs
- Timeframes (2s bars for scalping, M1, M5, H1 for swing trading)
- Parameter sets

Outputs detailed performance metrics and recommendations.
"""

import sys
import os
import json
from typing import Dict, List, Any, Tuple
from collections import defaultdict

# Ensure we can import from oanda_bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oanda_bot.data.core import get_candles
from oanda_bot.backtest import run_backtest
from oanda_bot.strategy.price_action import StrategyPriceAction


class PriceActionResearcher:
    """
    Researches and backtests price action trading edges.
    """

    def __init__(self):
        self.results = []
        self.pair_results = defaultdict(list)
        self.timeframe_results = defaultdict(list)
        self.pattern_results = defaultdict(list)

    def get_test_configurations(self) -> List[Dict[str, Any]]:
        """
        Define test configurations for different price action edges.
        """
        configs = []

        # 1. Pin Bar Strategy - Conservative
        configs.append({
            "name": "PinBar_Conservative",
            "description": "Pin bars at S/R with tight stops",
            "params": {
                "min_body_ratio": 0.35,
                "pin_wick_ratio": 2.5,
                "lookback_sr": 20,
                "breakout_confirm": 2,
                "atr_period": 14,
                "sl_mult": 1.0,
                "tp_mult": 2.5,
                "pin_weight": 1.5,
                "engulf_weight": 0.5,
                "breakout_weight": 0.3,
                "min_signal_strength": 1.5
            }
        })

        # 2. Pin Bar Strategy - Aggressive
        configs.append({
            "name": "PinBar_Aggressive",
            "description": "More pin bar setups with wider stops",
            "params": {
                "min_body_ratio": 0.4,
                "pin_wick_ratio": 2.0,
                "lookback_sr": 15,
                "breakout_confirm": 1,
                "atr_period": 14,
                "sl_mult": 1.5,
                "tp_mult": 3.0,
                "pin_weight": 1.3,
                "engulf_weight": 0.5,
                "breakout_weight": 0.3,
                "min_signal_strength": 1.0
            }
        })

        # 3. Engulfing Pattern Strategy
        configs.append({
            "name": "Engulfing_Primary",
            "description": "Focus on engulfing patterns",
            "params": {
                "min_body_ratio": 0.25,
                "pin_wick_ratio": 2.5,
                "lookback_sr": 20,
                "breakout_confirm": 2,
                "atr_period": 14,
                "sl_mult": 1.2,
                "tp_mult": 2.5,
                "pin_weight": 0.5,
                "engulf_weight": 2.0,
                "breakout_weight": 0.3,
                "min_signal_strength": 1.5
            }
        })

        # 4. Breakout Strategy
        configs.append({
            "name": "Breakout_Momentum",
            "description": "Range breakouts with momentum",
            "params": {
                "min_body_ratio": 0.3,
                "pin_wick_ratio": 2.0,
                "lookback_sr": 25,
                "breakout_confirm": 3,
                "atr_period": 14,
                "sl_mult": 1.5,
                "tp_mult": 3.5,
                "pin_weight": 0.3,
                "engulf_weight": 0.5,
                "breakout_weight": 2.0,
                "min_signal_strength": 1.2
            }
        })

        # 5. Combined Signals - Balanced
        configs.append({
            "name": "Combined_Balanced",
            "description": "Balanced weight on all patterns",
            "params": {
                "min_body_ratio": 0.3,
                "pin_wick_ratio": 2.2,
                "lookback_sr": 20,
                "breakout_confirm": 2,
                "atr_period": 14,
                "sl_mult": 1.3,
                "tp_mult": 2.8,
                "pin_weight": 1.0,
                "engulf_weight": 1.0,
                "breakout_weight": 1.0,
                "min_signal_strength": 1.3
            }
        })

        # 6. High Conviction Only
        configs.append({
            "name": "HighConviction_Only",
            "description": "Only strongest signals",
            "params": {
                "min_body_ratio": 0.25,
                "pin_wick_ratio": 3.0,
                "lookback_sr": 25,
                "breakout_confirm": 3,
                "atr_period": 20,
                "sl_mult": 1.5,
                "tp_mult": 4.0,
                "pin_weight": 1.5,
                "engulf_weight": 1.5,
                "breakout_weight": 1.2,
                "min_signal_strength": 2.0
            }
        })

        # 7. Scalping Setup (for faster timeframes)
        configs.append({
            "name": "Scalp_Quick",
            "description": "Quick scalping setups",
            "params": {
                "min_body_ratio": 0.35,
                "pin_wick_ratio": 1.8,
                "lookback_sr": 15,
                "breakout_confirm": 1,
                "atr_period": 10,
                "sl_mult": 1.0,
                "tp_mult": 2.0,
                "pin_weight": 1.0,
                "engulf_weight": 1.0,
                "breakout_weight": 0.8,
                "min_signal_strength": 0.8
            }
        })

        # 8. Swing Trading Setup (for longer timeframes)
        configs.append({
            "name": "Swing_Patient",
            "description": "Patient swing trading",
            "params": {
                "min_body_ratio": 0.25,
                "pin_wick_ratio": 2.5,
                "lookback_sr": 30,
                "breakout_confirm": 3,
                "atr_period": 20,
                "sl_mult": 2.0,
                "tp_mult": 5.0,
                "pin_weight": 1.2,
                "engulf_weight": 1.2,
                "breakout_weight": 1.0,
                "min_signal_strength": 1.5
            }
        })

        return configs

    def backtest_configuration(
        self,
        config: Dict[str, Any],
        pair: str,
        timeframe: str,
        candle_count: int
    ) -> Dict[str, Any]:
        """
        Backtest a single configuration on given pair and timeframe.
        """
        try:
            print(f"  Testing {config['name']} on {pair} {timeframe}...")

            # Fetch candles
            candles = get_candles(pair, timeframe, candle_count)

            if not candles or len(candles) < 100:
                return {
                    "error": f"Insufficient data: {len(candles) if candles else 0} candles",
                    "trades": 0
                }

            # Create strategy
            strategy = StrategyPriceAction(config["params"])

            # Determine warmup
            warmup = max(
                config["params"].get("lookback_sr", 20),
                config["params"].get("atr_period", 14)
            ) + 10

            # Run backtest
            stats = run_backtest(strategy, candles, warmup=warmup)

            # Add metadata
            result = {
                "config_name": config["name"],
                "description": config["description"],
                "pair": pair,
                "timeframe": timeframe,
                "candle_count": len(candles),
                **stats
            }

            return result

        except Exception as e:
            return {
                "config_name": config["name"],
                "pair": pair,
                "timeframe": timeframe,
                "error": str(e),
                "trades": 0,
                "win_rate": 0,
                "total_pnl": 0
            }

    def run_comprehensive_backtest(
        self,
        pairs: List[str],
        timeframes: List[Tuple[str, int]]
    ):
        """
        Run backtests across all configurations, pairs, and timeframes.

        Args:
            pairs: List of currency pairs
            timeframes: List of (granularity, candle_count) tuples
        """
        configs = self.get_test_configurations()

        print("=" * 80)
        print("PRICE ACTION EDGE RESEARCH - COMPREHENSIVE BACKTEST")
        print("=" * 80)
        print(f"\nTesting {len(configs)} configurations")
        print(f"Across {len(pairs)} pairs: {', '.join(pairs)}")
        print(f"On {len(timeframes)} timeframes: {', '.join(tf[0] for tf in timeframes)}")
        print()

        total_tests = len(configs) * len(pairs) * len(timeframes)
        test_num = 0

        for pair in pairs:
            print(f"\n{'='*60}")
            print(f"TESTING PAIR: {pair}")
            print(f"{'='*60}")

            for timeframe, candle_count in timeframes:
                print(f"\n--- Timeframe: {timeframe} ({candle_count} candles) ---")

                for config in configs:
                    test_num += 1
                    print(f"[{test_num}/{total_tests}] ", end="")

                    result = self.backtest_configuration(
                        config, pair, timeframe, candle_count
                    )

                    self.results.append(result)
                    self.pair_results[pair].append(result)
                    self.timeframe_results[timeframe].append(result)
                    self.pattern_results[config["name"]].append(result)

                    # Print summary
                    if "error" in result:
                        print(f"    ERROR: {result['error']}")
                    else:
                        trades = result.get("trades", 0)
                        win_rate = result.get("win_rate", 0) * 100
                        pnl = result.get("total_pnl", 0)
                        expectancy = result.get("expectancy", 0)

                        status = "+" if pnl > 0 else "-" if pnl < 0 else "="
                        print(f"    {trades} trades, {win_rate:.1f}% WR, "
                              f"PnL: {pnl:.5f}, Exp: {expectancy:.6f} [{status}]")

    def analyze_results(self) -> Dict[str, Any]:
        """
        Analyze backtest results and generate insights.
        """
        print("\n\n" + "=" * 80)
        print("ANALYSIS & RECOMMENDATIONS")
        print("=" * 80)

        analysis = {
            "summary": {},
            "best_configs": [],
            "best_pairs": [],
            "best_timeframes": [],
            "recommendations": []
        }

        # Filter valid results
        valid_results = [r for r in self.results if "error" not in r and r.get("trades", 0) >= 5]

        if not valid_results:
            print("\nInsufficient data for analysis (need at least 5 trades per test)")
            return analysis

        # Overall statistics
        total_tests = len(self.results)
        valid_tests = len(valid_results)
        total_trades = sum(r.get("trades", 0) for r in valid_results)
        profitable_tests = sum(1 for r in valid_results if r.get("total_pnl", 0) > 0)

        analysis["summary"] = {
            "total_tests": total_tests,
            "valid_tests": valid_tests,
            "total_trades": total_trades,
            "profitable_tests": profitable_tests,
            "profitability_rate": profitable_tests / valid_tests if valid_tests > 0 else 0
        }

        print(f"\nOverall Summary:")
        print(f"  Total tests run: {total_tests}")
        print(f"  Valid tests (≥5 trades): {valid_tests}")
        print(f"  Total trades: {total_trades}")
        print(f"  Profitable tests: {profitable_tests} ({profitable_tests/valid_tests*100:.1f}%)")

        # Best configurations
        print(f"\n{'='*60}")
        print("TOP PERFORMING CONFIGURATIONS")
        print(f"{'='*60}")

        config_performance = defaultdict(lambda: {"trades": 0, "pnl": 0, "wins": 0, "tests": 0})

        for result in valid_results:
            config = result["config_name"]
            config_performance[config]["trades"] += result.get("trades", 0)
            config_performance[config]["pnl"] += result.get("total_pnl", 0)
            config_performance[config]["wins"] += int(result.get("trades", 0) * result.get("win_rate", 0))
            config_performance[config]["tests"] += 1

        sorted_configs = sorted(
            config_performance.items(),
            key=lambda x: x[1]["pnl"],
            reverse=True
        )

        for rank, (config_name, perf) in enumerate(sorted_configs[:5], 1):
            win_rate = perf["wins"] / perf["trades"] * 100 if perf["trades"] > 0 else 0
            avg_pnl = perf["pnl"] / perf["tests"]

            analysis["best_configs"].append({
                "rank": rank,
                "name": config_name,
                "trades": perf["trades"],
                "win_rate": win_rate,
                "total_pnl": perf["pnl"],
                "avg_pnl_per_test": avg_pnl
            })

            print(f"\n{rank}. {config_name}")
            print(f"   Total trades: {perf['trades']}")
            print(f"   Win rate: {win_rate:.1f}%")
            print(f"   Total PnL: {perf['pnl']:.5f}")
            print(f"   Avg PnL/test: {avg_pnl:.5f}")

        # Best pairs
        print(f"\n{'='*60}")
        print("BEST CURRENCY PAIRS")
        print(f"{'='*60}")

        pair_performance = defaultdict(lambda: {"trades": 0, "pnl": 0, "wins": 0})

        for result in valid_results:
            pair = result["pair"]
            pair_performance[pair]["trades"] += result.get("trades", 0)
            pair_performance[pair]["pnl"] += result.get("total_pnl", 0)
            pair_performance[pair]["wins"] += int(result.get("trades", 0) * result.get("win_rate", 0))

        sorted_pairs = sorted(
            pair_performance.items(),
            key=lambda x: x[1]["pnl"],
            reverse=True
        )

        for rank, (pair, perf) in enumerate(sorted_pairs, 1):
            win_rate = perf["wins"] / perf["trades"] * 100 if perf["trades"] > 0 else 0

            analysis["best_pairs"].append({
                "rank": rank,
                "pair": pair,
                "trades": perf["trades"],
                "win_rate": win_rate,
                "total_pnl": perf["pnl"]
            })

            print(f"{rank}. {pair}: {perf['trades']} trades, {win_rate:.1f}% WR, PnL: {perf['pnl']:.5f}")

        # Best timeframes
        print(f"\n{'='*60}")
        print("BEST TIMEFRAMES")
        print(f"{'='*60}")

        tf_performance = defaultdict(lambda: {"trades": 0, "pnl": 0, "wins": 0})

        for result in valid_results:
            tf = result["timeframe"]
            tf_performance[tf]["trades"] += result.get("trades", 0)
            tf_performance[tf]["pnl"] += result.get("total_pnl", 0)
            tf_performance[tf]["wins"] += int(result.get("trades", 0) * result.get("win_rate", 0))

        sorted_tfs = sorted(
            tf_performance.items(),
            key=lambda x: x[1]["pnl"],
            reverse=True
        )

        for rank, (tf, perf) in enumerate(sorted_tfs, 1):
            win_rate = perf["wins"] / perf["trades"] * 100 if perf["trades"] > 0 else 0

            analysis["best_timeframes"].append({
                "rank": rank,
                "timeframe": tf,
                "trades": perf["trades"],
                "win_rate": win_rate,
                "total_pnl": perf["pnl"]
            })

            print(f"{rank}. {tf}: {perf['trades']} trades, {win_rate:.1f}% WR, PnL: {perf['pnl']:.5f}")

        # Specific recommendations
        print(f"\n{'='*60}")
        print("ACTIONABLE RECOMMENDATIONS")
        print(f"{'='*60}\n")

        # Find best overall setup
        best_results = sorted(
            valid_results,
            key=lambda x: x.get("total_pnl", 0),
            reverse=True
        )[:10]

        print("Top 10 Individual Test Results:")
        for i, result in enumerate(best_results, 1):
            win_rate = result.get("win_rate", 0) * 100
            print(f"{i}. {result['config_name']} on {result['pair']} {result['timeframe']}")
            print(f"   Trades: {result['trades']}, WR: {win_rate:.1f}%, "
                  f"PnL: {result['total_pnl']:.5f}, Exp: {result.get('expectancy', 0):.6f}")

        # Generate recommendations
        recommendations = []

        if sorted_configs:
            best_config = sorted_configs[0]
            recommendations.append(
                f"1. Use {best_config[0]} configuration - showed best overall performance "
                f"with {best_config[1]['pnl']:.5f} total PnL"
            )

        if sorted_pairs:
            best_pair = sorted_pairs[0]
            recommendations.append(
                f"2. Focus on {best_pair[0]} - most profitable pair with "
                f"{best_pair[1]['pnl']:.5f} total PnL"
            )

        if sorted_tfs:
            best_tf = sorted_tfs[0]
            recommendations.append(
                f"3. Trade on {best_tf[0]} timeframe - highest returns with "
                f"{best_tf[1]['pnl']:.5f} total PnL"
            )

        # Pattern-specific insights
        pin_results = [r for r in valid_results if "Pin" in r["config_name"]]
        engulf_results = [r for r in valid_results if "Engulf" in r["config_name"]]
        breakout_results = [r for r in valid_results if "Breakout" in r["config_name"]]

        if pin_results:
            pin_pnl = sum(r.get("total_pnl", 0) for r in pin_results)
            recommendations.append(f"4. Pin bar strategies: {len(pin_results)} tests, {pin_pnl:.5f} total PnL")

        if engulf_results:
            engulf_pnl = sum(r.get("total_pnl", 0) for r in engulf_results)
            recommendations.append(f"5. Engulfing strategies: {len(engulf_results)} tests, {engulf_pnl:.5f} total PnL")

        if breakout_results:
            breakout_pnl = sum(r.get("total_pnl", 0) for r in breakout_results)
            recommendations.append(f"6. Breakout strategies: {len(breakout_results)} tests, {breakout_pnl:.5f} total PnL")

        print("\nKey Recommendations:")
        for rec in recommendations:
            print(f"  {rec}")

        analysis["recommendations"] = recommendations

        return analysis

    def save_results(self, filename: str = "price_action_backtest_results.json"):
        """Save all results to JSON file."""
        output = {
            "all_results": self.results,
            "by_pair": dict(self.pair_results),
            "by_timeframe": dict(self.timeframe_results),
            "by_pattern": dict(self.pattern_results)
        }

        with open(filename, "w") as f:
            json.dump(output, f, indent=2)

        print(f"\n\nResults saved to {filename}")


def main():
    """Main entry point."""

    # Test parameters
    pairs = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD"]

    # Timeframes: (granularity, candle_count)
    # Note: S5 (5-second) is closest to 2-second bars available in OANDA
    timeframes = [
        ("S5", 2000),   # 5-second bars (closest to ultra-short)
        ("M1", 1000),   # 1-minute bars for scalping
        ("M5", 800),    # 5-minute bars
        ("M15", 600),   # 15-minute bars
        ("H1", 500),    # 1-hour bars for swing trading
    ]

    # Create researcher
    researcher = PriceActionResearcher()

    # Run comprehensive backtest
    researcher.run_comprehensive_backtest(pairs, timeframes)

    # Analyze results
    analysis = researcher.analyze_results()

    # Save results
    researcher.save_results()

    print("\n" + "=" * 80)
    print("BACKTEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
