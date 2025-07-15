"""
macd_tuner.py

Grid-search tuner for MACD parameters using the backtest engine.
"""
import itertools
import argparse
from .macd_trends import MACDTrendStrategy
from ..backtest import Backtester as Backtest


def tune_macd(fast_periods, slow_periods, signal_periods, **bt_kwargs):
    """
    Runs backtests over all combinations of provided MACD parameters.
    Returns the best-performing parameter set by Sharpe ratio.
    """
    best = None
    for fast, slow, signal in itertools.product(
        fast_periods, slow_periods, signal_periods
    ):
        if fast >= slow:
            continue  # skip invalid combos
        strat = MACDTrendStrategy(
            fast_period=fast,
            slow_period=slow,
            signal_period=signal
        )
        bt = Backtest(strategy=strat, **bt_kwargs)
        stats = bt.run()
        sharpe = stats.get("sharpe_ratio") or stats.get("sharpe", 0)
        if best is None or sharpe > best["sharpe"]:
            best = {
                "fast_period": fast,
                "slow_period": slow,
                "signal_period": signal,
                "sharpe": sharpe,
                **{
                    k: stats[k]
                    for k in stats
                    if k != "sharpe_ratio" and k != "sharpe"
                },
            }
    return best


def parse_args():
    parser = argparse.ArgumentParser(description="Tune MACD strategy parameters")
    parser.add_argument(
        "--fast", nargs="+", type=int, default=[12],
        help="List of fast EMA periods to try"
    )
    parser.add_argument(
        "--slow", nargs="+", type=int, default=[26],
        help="List of slow EMA periods to try"
    )
    parser.add_argument(
        "--signal", nargs="+", type=int, default=[9],
        help="List of signal line periods to try"
    )
    parser.add_argument(
        "--start", type=str, default=None,
        help="Backtest start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", type=str, default=None,
        help="Backtest end date (YYYY-MM-DD)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    bt_kwargs = {
        "start": args.start,
        "end": args.end,
    }
    print("Tuning MACD with parameters:")
    print(f"  fast:   {args.fast}")
    print(f"  slow:   {args.slow}")
    print(f"  signal: {args.signal}")
    best = tune_macd(args.fast, args.slow, args.signal, **bt_kwargs)
    print("\nBest parameters found:")
    print(f"  fast_period:   {best['fast_period']}")
    print(f"  slow_period:   {best['slow_period']}")
    print(f"  signal_period: {best['signal_period']}")
    print(f"  Sharpe ratio:  {best['sharpe']:.2f}")
