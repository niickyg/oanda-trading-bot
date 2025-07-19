#!/usr/bin/env python3
import argparse
import importlib
import json
import time
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

# Third-party imports
import numpy as np


# Local application imports
from oanda_bot.backtest import run_backtest
from oanda_bot.data.core import get_candles


# Worker initializer to set up globals for pickling efficiency
def init_worker(candles_data, strategy_class, warmup_bars):
    global _candles, _strat_cls, _warmup
    _candles = candles_data
    _strat_cls = strategy_class
    _warmup = warmup_bars


# Module-level run_one that only takes params
def run_one(params):
    strategy = _strat_cls(params)
    stats = run_backtest(strategy, _candles, warmup=_warmup)
    return params, stats


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting optimize.py…")
    start = time.perf_counter()
    arg_parser = argparse.ArgumentParser(
        description="Optimize EMA + ATR strategy"
    )
    arg_parser.add_argument("--granularity", default="H1")
    arg_parser.add_argument(
        "--count",
        type=int,
        default=4999,
        help=(
            "Initial candle request (script auto-backs off if API refuses)"
        ),
    )
    arg_parser.add_argument(
        "--min_trades",
        "--min-trades",
        type=int,
        default=10,
        dest="min_trades",
        help=(
            "Reject parameter sets with fewer than this many trades "
            "(default 10)"
        ),
    )
    arg_parser.add_argument(
        "--target_win_rate",
        "--target-win-rate",
        type=float,
        default=0.53,
        dest="target_win_rate",
        help=(
            "Minimum win rate threshold (e.g., 0.53 for 53%)"
        ),
    )
    arg_parser.add_argument(
        "--strategy",
        default="MACDTrend",
        help="Strategy name to optimize (must match Strategy<Class>)",
    )
    arg_parser.add_argument(
        "--instruments",
        "--instrument",
        nargs="+",
        default=["EUR_USD"],
        help=(
            "List of instruments to optimize (e.g. EUR_USD GBP_USD USD_JPY)"
        ),
    )
    arg_parser.add_argument(
        "--config",
        default="live_config.json",
        help=(
            "JSON file with strategy parameters (default: live_config.json)"
        ),
    )
    args = arg_parser.parse_args()
    logger.debug("Arguments: %s", args)

    # Fail fast if no real OANDA API token is available
    token = os.getenv("OANDA_TOKEN", "")
    if not token or token.lower().startswith("dummy"):
        logger.error(
            "Environment variable OANDA_TOKEN is missing or clearly invalid. "
            "Provide a valid token (e.g., via CI secret or .env) before running optimize.py."
        )
        sys.exit(1)

    # Load base parameters for the chosen strategy (optional config)
    try:
        with open(args.config, "r") as f:
            cfg = json.load(f)
        base_params = cfg.get(args.strategy, {})
    except FileNotFoundError:
        logger.warning("%s not found; proceeding with empty base parameters", args.config)
        base_params = {}

    # Load candles for each instrument
    instruments = args.instruments
    candles_map = {
        inst: get_candles(inst, args.granularity, args.count)
        for inst in instruments
    }
    combined = {}
    for inst, cands in candles_map.items():
        logger.info("Optimizing %s", inst)
        candles = cands

        # Dynamically load the chosen strategy plugin
        raw = args.strategy.lower()
        if raw == "macdtrend":
            raw = "macd_trends"
        elif raw == "rsireversion":
            raw = "rsi_reversion"
        module = importlib.import_module(f"oanda_bot.strategy.{raw}")
        strat_cls = getattr(module, f"Strategy{args.strategy}")

        # Determine warmup length based on strategy requirements
        if args.strategy == "MACDTrend":
            warmup = int(base_params.get("ema_trend", 200)) + int(
                base_params.get("macd_slow", 26)
            )
        elif args.strategy == "RSIReversion":
            warmup = int(base_params.get("rsi_len", 14)) + 1
        else:
            warmup = args.min_trades
        logger.info(f"Using warmup={warmup} bars for strategy {args.strategy}")

        # Generate grid of SL, TP, max_duration, and trailing ATR ratios
        sl_mults = list(np.linspace(0.5, 3.0, int((3.0 - 0.5) / 0.25) + 1))
        tp_mults = list(np.linspace(0.5, 3.0, int((3.0 - 0.5) / 0.25) + 1))
        max_duration_options = [10, 20, 50, 100]
        trail_atr_ratios = [0.5, 1.0, 1.5]

        # Build list of parameter sets
        param_list = [
            {
                **base_params,
                "sl_mult": sl,
                "tp_mult": tp,
                "max_duration": md,
                "trail_atr": ta,
            }
            for sl in sl_mults
            for tp in tp_mults
            for md in max_duration_options
            for ta in trail_atr_ratios
        ]

        results = []

        total = len(param_list)
        with ProcessPoolExecutor(
            initializer=init_worker,
            initargs=(candles, strat_cls, warmup)
        ) as executor:
            futures = [executor.submit(run_one, p) for p in param_list]
            for i, fut in enumerate(as_completed(futures), 1):
                params, stats = fut.result()
                trades = stats.get("trades", 0)
                if trades == 0:
                    continue
                pct = i / total * 100
                logger.info("Progress: %d/%d (%.1f%%)", i, total, pct)
                results.append({
                    **params,
                    "trades": trades,
                    "win_rate": stats["win_rate"],
                    "expectancy": stats["expectancy"],
                    "sharpe": stats.get("sharpe"),
                    "drawdown": stats.get("max_drawdown"),
                })

        logger.info("Evaluated %d parameter sets (raw)", len(results))
        if not results:
            logger.warning("No valid parameter sets found")
            logger.info(f"Completed in {time.perf_counter() - start:.1f} seconds")
            return

        # Rank parameter sets by expectancy so best sets print in order
        results.sort(key=lambda r: r["expectancy"], reverse=True)

        print("Top 5 parameter sets by expectancy:")
        for r in results[:5]:
            print(
                f"SLx{r['sl_mult']:.1f} TPx{r['tp_mult']:.1f} → "
                f"Trades: {r['trades']}, "
                f"Win Rate: {r['win_rate']:.2%}, "
                f"Expectancy: {r['expectancy']:.4f}"
            )
        # To optimize for Sharpe ratio instead, uncomment:
        # results.sort(key=lambda r: (r["sharpe"] or float('-inf')), reverse=True)
        # Or to minimize max drawdown:
        # results.sort(key=lambda r: r["drawdown"], reverse=False)
        # Temporarily allow all results (including negative expectancy) for inspection
        # best is now the top entry by the chosen metric
        # e.g., using least-negative expectancy or highest Sharpe
        # TODO: switch key to "sharpe" or "drawdown" as needed
        # results.sort(key=lambda r: r["expectancy"], reverse=True)
        best = results[0]
        wrapped = {args.strategy: best}
        logger.info("Best parameters: %s", wrapped)
        combined[inst] = best

        # write to JSON
        out = f"best_params_{inst}.json"
        with open(out, "w") as f:
            json.dump(wrapped, f, indent=2)
        logger.info(f"Wrote best parameters to {out}")
    # Write consolidated parameters for all instruments
    with open("live_config.json", "w") as f:
        json.dump({args.strategy: combined}, f, indent=2)
    logger.info("Wrote consolidated live_config.json")
    logger.info(f"Completed in {time.perf_counter() - start:.1f} seconds")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
