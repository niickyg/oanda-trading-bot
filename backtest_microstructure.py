#!/usr/bin/env python3
"""
backtest_microstructure.py
==========================

Comprehensive backtesting script for the SpreadMomentum microstructure strategy.

This script:
1. Fetches historical S5 (5-second) candle data from OANDA
2. Runs the SpreadMomentum strategy on this data
3. Computes comprehensive performance metrics including:
   - Win rate
   - Profit factor
   - Maximum drawdown
   - Sharpe ratio
   - Total trades and PnL
4. Generates detailed performance report
"""

import sys
import json
import numpy as np
from typing import Dict, List, Tuple
from collections import deque

# Import from oanda_bot package
from oanda_bot.data import get_candles
from oanda_bot.strategy.spread_momentum import StrategySpreadMomentum
from oanda_bot.strategy.macd_trends import sl_tp_levels


def compute_performance_metrics(
    trades: List[Dict],
    equity_curve: List[float],
    initial_capital: float = 10000.0
) -> Dict:
    """
    Compute comprehensive performance metrics.

    Args:
        trades: List of trade dictionaries with pnl values
        equity_curve: List of equity values over time
        initial_capital: Starting capital for calculations

    Returns:
        Dictionary with all performance metrics
    """
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
            "total_pnl": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
        }

    # Basic trade statistics
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]

    total_trades = len(trades)
    win_count = len(wins)
    loss_count = len(losses)

    win_rate = win_count / total_trades if total_trades > 0 else 0.0

    total_win = sum(t["pnl"] for t in wins)
    total_loss = abs(sum(t["pnl"] for t in losses))
    avg_win = total_win / win_count if win_count > 0 else 0.0
    avg_loss = total_loss / loss_count if loss_count > 0 else 0.0

    # Profit factor
    profit_factor = total_win / total_loss if total_loss > 0 else (float('inf') if total_win > 0 else 0.0)

    # Expectancy
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

    # Total PnL
    total_pnl = sum(t["pnl"] for t in trades)

    # Maximum drawdown
    if equity_curve:
        peak = equity_curve[0]
        max_dd = 0.0
        max_dd_pct = 0.0

        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = peak - equity
            dd_pct = (dd / peak * 100) if peak > 0 else 0.0

            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
    else:
        max_dd = 0.0
        max_dd_pct = 0.0

    # Sharpe ratio (annualized, assuming 252 trading days)
    if len(trades) > 1:
        returns = [t["pnl"] / initial_capital for t in trades]
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return > 0:
            # Annualize: sqrt(number of periods per year)
            # For 5-second bars: 17280 bars per day (assuming 24h trading)
            # 252 trading days per year
            # But we're looking at returns per trade, so use sqrt(trades per year estimate)
            # Conservative estimate: 20 trades per day * 252 days = 5040 trades/year
            trades_per_year = 5040
            sharpe_ratio = (mean_return / std_return) * np.sqrt(trades_per_year)
        else:
            sharpe_ratio = 0.0
    else:
        sharpe_ratio = 0.0

    return {
        "total_trades": total_trades,
        "wins": win_count,
        "losses": loss_count,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "sharpe_ratio": sharpe_ratio,
        "total_pnl": total_pnl,
        "total_pnl_pct": (total_pnl / initial_capital * 100) if initial_capital > 0 else 0.0,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
    }


def run_backtest(
    strategy: StrategySpreadMomentum,
    candles: List[dict],
    warmup: int = 50,
    initial_capital: float = 10000.0,
    position_size_pct: float = 0.01,  # 1% risk per trade
) -> Tuple[Dict, List[Dict], List[float]]:
    """
    Run backtest with detailed tracking.

    Args:
        strategy: Strategy instance
        candles: List of OHLCV candles
        warmup: Number of bars to warm up before trading
        initial_capital: Starting capital
        position_size_pct: Position size as % of capital

    Returns:
        Tuple of (metrics dict, trades list, equity curve)
    """
    print(f"Starting backtest with {len(candles)} candles...")

    bars = deque(maxlen=warmup + 100)
    trades = []
    equity_curve = [initial_capital]
    current_capital = initial_capital

    position = None

    for idx, candle in enumerate(candles):
        bars.append(candle)

        if idx < warmup:
            continue

        # Position exit logic
        if position:
            side = position["side"]
            sl = position["sl"]
            tp = position["tp"]
            entry_idx = position["entry_idx"]
            entry_price = position["entry_price"]
            entry_capital = position["entry_capital"]

            price_high = float(candle["mid"]["h"])
            price_low = float(candle["mid"]["l"])
            price_close = float(candle["mid"]["c"])

            hit_sl = (side == "BUY" and price_low <= sl) or (side == "SELL" and price_high >= sl)
            hit_tp = (side == "BUY" and price_high >= tp) or (side == "SELL" and price_low <= tp)

            max_dur = strategy.params.get("max_duration", strategy.max_hold_bars)
            hit_time = max_dur and (idx - entry_idx) >= max_dur

            if hit_sl or hit_tp or hit_time:
                exit_price = tp if hit_tp else (sl if hit_sl else price_close)

                # Calculate PnL in pips and money
                pip_size = 0.0001  # EUR_USD
                pips = (exit_price - entry_price) / pip_size if side == "BUY" else (entry_price - exit_price) / pip_size

                # Position size based on capital at entry
                units = (entry_capital * position_size_pct) / (abs(entry_price - sl))
                pnl = pips * pip_size * units

                current_capital += pnl
                equity_curve.append(current_capital)

                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": idx,
                    "side": side,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pips": pips,
                    "pnl": pnl,
                    "reason": "TP" if hit_tp else ("SL" if hit_sl else "TIME"),
                })

                strategy.update_trade_result(pnl > 0, pnl)
                position = None

                if idx % 100 == 0:
                    print(f"  Bar {idx}/{len(candles)}: {len(trades)} trades, Capital: ${current_capital:.2f}")

        # Entry logic
        if position is None:
            signal = strategy.next_signal(list(bars))

            if signal in ("BUY", "SELL"):
                entry_price = float(candle["mid"]["c"])

                # Calculate SL/TP
                sl, tp = sl_tp_levels(list(bars), signal, strategy.params)

                position = {
                    "side": signal,
                    "entry_price": entry_price,
                    "sl": sl,
                    "tp": tp,
                    "entry_idx": idx,
                    "entry_capital": current_capital,
                }

    # Compute metrics
    metrics = compute_performance_metrics(trades, equity_curve, initial_capital)

    print(f"\nBacktest complete: {len(trades)} trades executed")

    return metrics, trades, equity_curve


def main():
    """Main backtesting execution."""
    print("=" * 80)
    print("MARKET MICROSTRUCTURE STRATEGY BACKTEST")
    print("Strategy: SpreadMomentum")
    print("=" * 80)

    # Parameters
    instrument = "EUR_USD"
    granularity = "S5"  # 5-second bars (closest to 2-second on OANDA)
    count = 5000  # Maximum allowed by OANDA API
    warmup = 50

    # Strategy parameters (optimized for microstructure)
    params = {
        "spread_window": 30,
        "volume_window": 20,
        "velocity_window": 10,
        "spread_expansion_threshold": 1.5,
        "volume_surge_threshold": 2.0,
        "velocity_accel_threshold": 1.3,
        "efficiency_threshold": 0.7,
        "max_hold_bars": 12,  # 60 seconds
        "profit_target_atr": 1.2,
        "stop_loss_atr": 0.8,
        "max_duration": 12,
    }

    print(f"\nFetching {count} candles for {instrument} @ {granularity}...")

    try:
        candles = get_candles(instrument, granularity, count, price="M")
        print(f"Successfully fetched {len(candles)} candles")
    except Exception as e:
        print(f"ERROR: Failed to fetch candles: {e}")
        print("\nNote: This requires valid OANDA API credentials in .env file")
        print("OANDA_TOKEN and OANDA_ACCOUNT_ID must be set")
        sys.exit(1)

    if not candles:
        print("ERROR: No candles returned from API")
        sys.exit(1)

    # Initialize strategy
    print(f"\nInitializing SpreadMomentum strategy with parameters:")
    for key, value in params.items():
        if not key.startswith("_"):
            print(f"  {key}: {value}")

    strategy = StrategySpreadMomentum(params)

    # Run backtest
    print("\n" + "=" * 80)
    print("RUNNING BACKTEST")
    print("=" * 80)

    metrics, trades, equity_curve = run_backtest(
        strategy,
        candles,
        warmup=warmup,
        initial_capital=10000.0,
        position_size_pct=0.01,
    )

    # Print results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)

    print(f"\nTRADE STATISTICS:")
    print(f"  Total Trades:        {metrics['total_trades']}")
    print(f"  Wins:                {metrics['wins']}")
    print(f"  Losses:              {metrics['losses']}")
    print(f"  Win Rate:            {metrics['win_rate']:.2%}")
    print(f"  Average Win:         ${metrics['avg_win']:.2f}")
    print(f"  Average Loss:        ${metrics['avg_loss']:.2f}")
    print(f"  Expectancy:          ${metrics['expectancy']:.2f}")

    print(f"\nPERFORMANCE METRICS:")
    print(f"  Total PnL:           ${metrics['total_pnl']:.2f}")
    print(f"  Total Return:        {metrics['total_pnl_pct']:.2f}%")
    print(f"  Profit Factor:       {metrics['profit_factor']:.2f}")
    print(f"  Max Drawdown:        ${metrics['max_drawdown']:.2f} ({metrics['max_drawdown_pct']:.2f}%)")
    print(f"  Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")

    print(f"\nFINAL EQUITY:          ${equity_curve[-1]:.2f}")

    # Save detailed results
    results = {
        "strategy": "SpreadMomentum",
        "instrument": instrument,
        "granularity": granularity,
        "total_candles": len(candles),
        "parameters": params,
        "metrics": metrics,
        "trades_summary": {
            "first_10": trades[:10] if len(trades) > 10 else trades,
            "last_10": trades[-10:] if len(trades) > 10 else [],
        },
    }

    output_file = "backtest_results_microstructure.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDetailed results saved to: {output_file}")

    # Analysis
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    if metrics["total_trades"] > 0:
        if metrics["win_rate"] >= 0.55 and metrics["profit_factor"] >= 1.5:
            print("\n✓ STRATEGY SHOWS PROMISE:")
            print("  - Win rate above 55%")
            print("  - Profit factor above 1.5")
            print("  - Consider live testing with small position sizes")
        elif metrics["win_rate"] >= 0.50 and metrics["profit_factor"] >= 1.2:
            print("\n~ STRATEGY NEEDS REFINEMENT:")
            print("  - Positive expectancy but marginal edge")
            print("  - Consider parameter optimization")
            print("  - Test on different market conditions")
        else:
            print("\n✗ STRATEGY NEEDS IMPROVEMENT:")
            print("  - Win rate or profit factor too low")
            print("  - Review entry/exit logic")
            print("  - Consider different market microstructure patterns")

        if metrics["sharpe_ratio"] >= 1.5:
            print("  - Excellent risk-adjusted returns (Sharpe > 1.5)")
        elif metrics["sharpe_ratio"] >= 1.0:
            print("  - Good risk-adjusted returns (Sharpe > 1.0)")
        else:
            print("  - Risk-adjusted returns need improvement")

        if metrics["max_drawdown_pct"] <= 10.0:
            print("  - Manageable drawdown (<10%)")
        elif metrics["max_drawdown_pct"] <= 20.0:
            print("  - Moderate drawdown (10-20%)")
        else:
            print("  - High drawdown (>20%) - risk management needed")
    else:
        print("\n! NO TRADES EXECUTED:")
        print("  - Strategy may be too conservative")
        print("  - Consider relaxing entry conditions")
        print("  - Verify data quality and timeframe")

    print("\n" + "=" * 80)
    print("MICROSTRUCTURE EDGE ANALYSIS")
    print("=" * 80)
    print("""
This strategy exploits three key market microstructure inefficiencies:

1. SPREAD DYNAMICS:
   - Spread expansion signals information asymmetry
   - Market makers widen spreads before volatile moves
   - Spread contraction after expansion = liquidity return

2. VOLUME-PRICE RELATIONSHIP:
   - High volume + small price move = absorption
   - Low volume + large price move = thin liquidity
   - Volume surge at extremes = potential reversal

3. TICK VELOCITY:
   - Accelerating velocity = aggressive order flow
   - Decelerating velocity = exhaustion
   - Velocity divergence = early reversal signal

The edge exists because:
- Retail traders ignore microstructure signals
- Algorithms react to these patterns predictably
- 2-5 second timeframe captures institutional footprints
- Mean reversion to VWAP exploits over-extension
    """)

    print("=" * 80)


if __name__ == "__main__":
    main()
