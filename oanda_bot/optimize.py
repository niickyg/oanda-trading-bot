#!/usr/bin/env python3
import argparse
import importlib
import json
import time
import logging
import numpy as np
from oanda_bot.backtest import run_backtest
from oanda_bot.data.core import get_candles

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
        max_duration_options = [10, 20, 50, 100]  # bars before forced exit
        trail_atr_ratios = [0.5, 1.0, 1.5]       # trailing stop as ATR multiples

        # --- progress bookkeeping -------------------------------------------------
        total_tests = (
            len(sl_mults)
            * len(tp_mults)
            * len(max_duration_options)
            * len(trail_atr_ratios)
        )
        completed = 0

        results = []
        for sl_mult in sl_mults:
            for tp_mult in tp_mults:
                for max_dur in max_duration_options:
                    for trail_atr in trail_atr_ratios:
                        logger.info(
                            "Trying SLx%.2f TPx%.2f Dur=%d TrailATR=%.2f",
                            sl_mult, tp_mult, max_dur, trail_atr
                        )
                        logger.debug(
                            "Testing SL=%.2f TP=%.2f Dur=%d Trail=%.2f",
                            sl_mult, tp_mult, max_dur, trail_atr
                        )
                        # Set parameters for this run
                        params = {
                            **base_params,
                            "sl_mult": sl_mult,
                            "tp_mult": tp_mult,
                            "max_duration": max_dur,
                            "trail_atr": trail_atr,
                        }
                        logger.debug("PARAMS: %s", params)
                        strategy = strat_cls(params)
                        stats = run_backtest(strategy, candles, warmup=warmup)
                        trades = stats["trades"]
                        if trades == 0:
                            continue
                        completed += 1
                        if completed % 50 == 0 or completed == total_tests:
                            pct = completed / total_tests * 100
                            logger.info("Progress: %d/%d (%.1f%%)", completed, total_tests, pct)
                        results.append({
                            "sl_mult": sl_mult,
                            "tp_mult": tp_mult,
                            "max_duration": max_dur,
                            "trail_atr": trail_atr,
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
        logger.info("Best parameters: %s", best)

        # write to JSON
        out = f"best_params_{inst}.json"
        with open(out, "w") as f:
            json.dump(best, f, indent=2)
        logger.info(f"Wrote best parameters to {out}")
    logger.info(f"Completed in {time.perf_counter() - start:.1f} seconds")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
