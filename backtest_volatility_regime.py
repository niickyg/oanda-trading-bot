#!/usr/bin/env python3
"""
Comprehensive backtest for Volatility Regime Strategy

This script:
1. Fetches historical forex data from OANDA
2. Runs the volatility regime strategy
3. Calculates comprehensive performance metrics:
   - Win rate
   - Profit factor
   - Maximum drawdown
   - Sharpe ratio
   - Sortino ratio
   - Total return
   - Average trade metrics
"""

import sys
import os
import json
import numpy as np
from datetime import datetime
from collections import deque

# Ensure we can import from oanda_bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oanda_bot.data.core import get_candles
from oanda_bot.strategy.volatility_regime import StrategyVolatilityRegime


def calculate_drawdown(equity_curve):
    """Calculate maximum drawdown from equity curve."""
    if len(equity_curve) == 0:
        return 0.0, 0.0, 0

    equity = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max * 100

    max_dd = abs(np.min(drawdown))
    max_dd_idx = np.argmin(drawdown)

    return max_dd, np.min(drawdown), max_dd_idx


def calculate_sharpe_ratio(returns, risk_free_rate=0.0):
    """Calculate Sharpe ratio from returns."""
    if len(returns) == 0 or np.std(returns) == 0:
        return 0.0

    excess_returns = returns - risk_free_rate
    return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)  # Annualized


def calculate_sortino_ratio(returns, risk_free_rate=0.0):
    """Calculate Sortino ratio (uses downside deviation)."""
    if len(returns) == 0:
        return 0.0

    excess_returns = returns - risk_free_rate
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0 or np.std(downside_returns) == 0:
        return 0.0

    downside_std = np.std(downside_returns)
    return np.mean(excess_returns) / downside_std * np.sqrt(252)  # Annualized


def sl_tp_levels(bars, signal, params):
    """Calculate stop loss and take profit levels based on ATR."""
    if len(bars) < 20:
        # Default fallback
        close = float(bars[-1]["mid"]["c"])
        stop_dist = close * 0.002  # 0.2%
        target_dist = close * 0.003  # 0.3%
    else:
        # Calculate ATR
        high = np.array([float(c["mid"]["h"]) for c in bars])
        low = np.array([float(c["mid"]["l"]) for c in bars])
        close_arr = np.array([float(c["mid"]["c"]) for c in bars])

        atr_period = params.get("atr_period", 14)
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close_arr, 1))
        tr3 = np.abs(low - np.roll(close_arr, 1))
        tr = np.maximum(np.maximum(tr1, tr2), tr3)

        atr = np.mean(tr[-atr_period:])
        close = close_arr[-1]

        stop_mult = params.get("stop_loss_atr", 2.0)
        target_mult = params.get("profit_target_atr", 3.0)

        stop_dist = atr * stop_mult
        target_dist = atr * target_mult

    if signal == "BUY":
        sl = close - stop_dist
        tp = close + target_dist
    else:  # SELL
        sl = close + stop_dist
        tp = close - target_dist

    return sl, tp


def run_backtest(strategy, candles, warmup=100):
    """
    Run backtest and calculate comprehensive performance metrics.
    """
    print(f"\n{'='*80}")
    print(f"Running Backtest: {strategy.name}")
    print(f"{'='*80}")
    print(f"Total candles: {len(candles)}")
    print(f"Warmup period: {warmup}")
    print(f"Strategy params: {json.dumps(strategy.params, indent=2)}")

    # Track all trades
    trades = []
    equity_curve = [10000]  # Start with $10,000
    daily_returns = []

    wins = losses = 0
    total_win = total_loss = 0.0
    win_trades = []
    loss_trades = []

    bars = deque(maxlen=warmup + 50)
    position = None

    for idx, candle in enumerate(candles):
        bars.append(candle)

        # Handle open position exits
        if position:
            side = position["side"]
            sl = position["sl"]
            tp = position["tp"]
            entry_idx = position["entry_idx"]
            entry_price = position["entry_price"]

            price_high = float(candle["mid"]["h"])
            price_low = float(candle["mid"]["l"])
            price_close = float(candle["mid"]["c"])

            hit_sl = (side == "BUY" and price_low <= sl) or \
                     (side == "SELL" and price_high >= sl)
            hit_tp = (side == "BUY" and price_high >= tp) or \
                     (side == "SELL" and price_low <= tp)

            max_hold = strategy.params.get("max_hold_bars", 50)
            hit_time = (idx - entry_idx) >= max_hold

            if hit_sl or hit_tp or hit_time:
                exit_price = tp if hit_tp else sl if hit_sl else price_close
                pnl = (exit_price - entry_price) if side == "BUY" else (entry_price - exit_price)
                pnl_pct = (pnl / entry_price) * 100

                # Update equity
                pnl_dollars = equity_curve[-1] * (pnl / entry_price)
                new_equity = equity_curve[-1] + pnl_dollars
                equity_curve.append(new_equity)
                daily_returns.append(pnl / entry_price)

                # Record trade
                trade = {
                    "entry_idx": entry_idx,
                    "exit_idx": idx,
                    "side": side,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "pnl_dollars": pnl_dollars,
                    "duration": idx - entry_idx,
                    "exit_reason": "TP" if hit_tp else "SL" if hit_sl else "TIME"
                }
                trades.append(trade)

                if pnl > 0:
                    wins += 1
                    total_win += pnl
                    win_trades.append(pnl)
                else:
                    losses += 1
                    total_loss += abs(pnl)
                    loss_trades.append(pnl)

                # Notify strategy
                strategy.update_trade_result(pnl > 0, pnl)
                position = None

        # Look for new entry signal
        if position is None and idx < len(candles) - 1:
            signal = strategy.next_signal(list(bars))

            if signal in ("BUY", "SELL"):
                entry_price = float(candle["mid"]["c"])
                sl, tp = sl_tp_levels(list(bars), signal, strategy.params)

                position = {
                    "side": signal,
                    "entry_price": entry_price,
                    "sl": sl,
                    "tp": tp,
                    "entry_idx": idx,
                }

    # Calculate performance metrics
    total_trades = wins + losses
    win_rate = wins / total_trades if total_trades > 0 else 0.0
    avg_win = total_win / wins if wins > 0 else 0.0
    avg_loss = total_loss / losses if losses > 0 else 0.0

    profit_factor = total_win / total_loss if total_loss > 0 else float('inf')
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

    total_pnl = total_win - total_loss
    total_return_pct = ((equity_curve[-1] - equity_curve[0]) / equity_curve[0]) * 100

    max_dd, max_dd_pct, max_dd_idx = calculate_drawdown(equity_curve)
    sharpe = calculate_sharpe_ratio(np.array(daily_returns))
    sortino = calculate_sortino_ratio(np.array(daily_returns))

    # Calculate additional metrics
    avg_trade_duration = np.mean([t["duration"] for t in trades]) if trades else 0
    avg_win_pct = np.mean([t["pnl_pct"] for t in trades if t["pnl"] > 0]) if win_trades else 0
    avg_loss_pct = np.mean([t["pnl_pct"] for t in trades if t["pnl"] < 0]) if loss_trades else 0

    largest_win = max(win_trades) if win_trades else 0
    largest_loss = min(loss_trades) if loss_trades else 0

    # Count consecutive wins/losses
    consecutive_wins = 0
    consecutive_losses = 0
    max_consecutive_wins = 0
    max_consecutive_losses = 0

    for trade in trades:
        if trade["pnl"] > 0:
            consecutive_wins += 1
            consecutive_losses = 0
            max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
        else:
            consecutive_losses += 1
            consecutive_wins = 0
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)

    # Print results
    print(f"\n{'='*80}")
    print(f"BACKTEST RESULTS")
    print(f"{'='*80}")
    print(f"\nTrade Statistics:")
    print(f"  Total trades:        {total_trades}")
    print(f"  Winning trades:      {wins} ({win_rate*100:.2f}%)")
    print(f"  Losing trades:       {losses} ({(1-win_rate)*100:.2f}%)")
    print(f"  Win rate:            {win_rate*100:.2f}%")
    print(f"\nProfit Metrics:")
    print(f"  Total PnL:           {total_pnl:.5f} ({total_pnl/0.0001:.1f} pips)")
    print(f"  Total return:        {total_return_pct:.2f}%")
    print(f"  Profit factor:       {profit_factor:.2f}")
    print(f"  Expectancy:          {expectancy:.5f} ({expectancy/0.0001:.1f} pips)")
    print(f"\nAverage Trade:")
    print(f"  Average win:         {avg_win:.5f} ({avg_win_pct:.2f}%)")
    print(f"  Average loss:        {avg_loss:.5f} ({avg_loss_pct:.2f}%)")
    print(f"  Avg duration:        {avg_trade_duration:.1f} bars")
    print(f"\nBest/Worst:")
    print(f"  Largest win:         {largest_win:.5f}")
    print(f"  Largest loss:        {largest_loss:.5f}")
    print(f"  Max consecutive wins:   {max_consecutive_wins}")
    print(f"  Max consecutive losses: {max_consecutive_losses}")
    print(f"\nRisk Metrics:")
    print(f"  Maximum drawdown:    {max_dd:.2f}%")
    print(f"  Sharpe ratio:        {sharpe:.2f}")
    print(f"  Sortino ratio:       {sortino:.2f}")
    print(f"\nEquity:")
    print(f"  Starting equity:     ${equity_curve[0]:,.2f}")
    print(f"  Final equity:        ${equity_curve[-1]:,.2f}")

    # Trade breakdown by exit reason
    exit_reasons = {}
    for trade in trades:
        reason = trade["exit_reason"]
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    print(f"\nExit Reasons:")
    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason}: {count} ({count/total_trades*100:.1f}%)")

    print(f"\n{'='*80}\n")

    return {
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "total_pnl": total_pnl,
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "equity_curve": equity_curve,
        "trade_history": trades,
        "avg_trade_duration": avg_trade_duration,
        "largest_win": largest_win,
        "largest_loss": largest_loss,
        "max_consecutive_wins": max_consecutive_wins,
        "max_consecutive_losses": max_consecutive_losses,
    }


def main():
    """Run comprehensive backtest on multiple pairs and timeframes."""
    print(f"\n{'#'*80}")
    print(f"# VOLATILITY REGIME STRATEGY - COMPREHENSIVE BACKTEST")
    print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*80}\n")

    # Test configurations
    pairs = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD"]
    granularities = ["M1", "M5", "M15"]  # 1-min, 5-min, 15-min

    # Strategy parameters
    params = {
        "lookback": 100,
        "vol_window": 20,
        "regime_threshold": 1.5,
        "breakout_mult": 2.0,
        "spike_mult": 3.0,
        "mean_revert_mult": 0.5,
        "atr_period": 14,
        "stop_loss_atr": 2.0,
        "profit_target_atr": 3.0,
        "max_hold_bars": 50,
        "min_vol_ratio": 0.3,
    }

    all_results = []

    for pair in pairs:
        for granularity in granularities:
            print(f"\n{'='*80}")
            print(f"Testing {pair} @ {granularity}")
            print(f"{'='*80}")

            try:
                # Fetch candles
                count = 2000 if granularity == "M1" else 1000
                print(f"Fetching {count} candles...")
                candles = get_candles(pair, granularity, count)
                print(f"Retrieved {len(candles)} candles")

                if len(candles) < 200:
                    print(f"Insufficient data for {pair} @ {granularity}")
                    continue

                # Adjust parameters based on timeframe
                adjusted_params = params.copy()
                if granularity == "M1":
                    adjusted_params["max_hold_bars"] = 30
                    adjusted_params["lookback"] = 100
                elif granularity == "M5":
                    adjusted_params["max_hold_bars"] = 40
                    adjusted_params["lookback"] = 150
                elif granularity == "M15":
                    adjusted_params["max_hold_bars"] = 50
                    adjusted_params["lookback"] = 200

                # Create strategy instance
                strategy = StrategyVolatilityRegime(adjusted_params)

                # Run backtest
                warmup = min(200, len(candles) // 4)
                results = run_backtest(strategy, candles, warmup=warmup)

                results["pair"] = pair
                results["granularity"] = granularity
                all_results.append(results)

            except Exception as e:
                print(f"ERROR testing {pair} @ {granularity}: {e}")
                import traceback
                traceback.print_exc()
                continue

    # Summary across all tests
    print(f"\n{'#'*80}")
    print(f"# SUMMARY ACROSS ALL PAIRS AND TIMEFRAMES")
    print(f"{'#'*80}\n")

    if not all_results:
        print("No results to summarize.")
        return

    profitable = [r for r in all_results if r["total_pnl"] > 0]
    unprofitable = [r for r in all_results if r["total_pnl"] <= 0]

    print(f"Total tests:           {len(all_results)}")
    print(f"Profitable:            {len(profitable)} ({len(profitable)/len(all_results)*100:.1f}%)")
    print(f"Unprofitable:          {len(unprofitable)} ({len(unprofitable)/len(all_results)*100:.1f}%)")

    # Overall statistics
    total_trades = sum(r["trades"] for r in all_results)
    total_wins = sum(r["wins"] for r in all_results)
    overall_win_rate = total_wins / total_trades if total_trades > 0 else 0

    avg_profit_factor = np.mean([r["profit_factor"] for r in all_results if r["profit_factor"] != float('inf')])
    avg_sharpe = np.mean([r["sharpe_ratio"] for r in all_results])
    avg_max_dd = np.mean([r["max_drawdown_pct"] for r in all_results])

    print(f"\nOverall Statistics:")
    print(f"  Total trades:        {total_trades}")
    print(f"  Overall win rate:    {overall_win_rate*100:.2f}%")
    print(f"  Avg profit factor:   {avg_profit_factor:.2f}")
    print(f"  Avg Sharpe ratio:    {avg_sharpe:.2f}")
    print(f"  Avg max drawdown:    {avg_max_dd:.2f}%")

    # Best performing configurations
    print(f"\nTop 5 Configurations (by Sharpe Ratio):")
    sorted_by_sharpe = sorted(all_results, key=lambda x: x["sharpe_ratio"], reverse=True)[:5]
    for i, r in enumerate(sorted_by_sharpe, 1):
        print(f"  {i}. {r['pair']} @ {r['granularity']}: "
              f"Sharpe={r['sharpe_ratio']:.2f}, "
              f"Win Rate={r['win_rate']*100:.1f}%, "
              f"PF={r['profit_factor']:.2f}, "
              f"Return={r['total_return_pct']:.2f}%")

    print(f"\nTop 5 Configurations (by Total Return):")
    sorted_by_return = sorted(all_results, key=lambda x: x["total_return_pct"], reverse=True)[:5]
    for i, r in enumerate(sorted_by_return, 1):
        print(f"  {i}. {r['pair']} @ {r['granularity']}: "
              f"Return={r['total_return_pct']:.2f}%, "
              f"Sharpe={r['sharpe_ratio']:.2f}, "
              f"Win Rate={r['win_rate']*100:.1f}%, "
              f"PF={r['profit_factor']:.2f}")

    # Save results to JSON
    output_file = "volatility_regime_backtest_results.json"
    with open(output_file, "w") as f:
        # Remove equity curves for smaller file size
        results_for_save = []
        for r in all_results:
            r_copy = r.copy()
            r_copy.pop("equity_curve", None)
            r_copy.pop("trade_history", None)
            results_for_save.append(r_copy)

        json.dump({
            "timestamp": datetime.now().isoformat(),
            "strategy": "VolatilityRegime",
            "parameters": params,
            "results": results_for_save,
            "summary": {
                "total_tests": len(all_results),
                "profitable": len(profitable),
                "total_trades": total_trades,
                "overall_win_rate": overall_win_rate,
                "avg_profit_factor": avg_profit_factor,
                "avg_sharpe_ratio": avg_sharpe,
                "avg_max_drawdown": avg_max_dd,
            }
        }, f, indent=2)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
