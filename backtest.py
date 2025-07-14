#!/usr/bin/env python3
"""
backtest.py

Generic back-tester: import any strategy plugin and run it on historical data.
It then reports performance metrics.
"""
import argparse
import json
import time
from collections import deque
from typing import Deque, Dict, Any
import logging
from data import get_candles
from strategy.base import BaseStrategy

logging.basicConfig(
    filename="backtest.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def load_strategy(name: str, params: Dict[str, Any]) -> BaseStrategy:
    """
    Dynamically import a strategy plugin from strategy/<name_lower>.py and
    instantiate it with given params.
    """
    raw = name.lower()
    if raw == "macdtrend":
        raw = "macd_trends"
    elif raw == "rsireversion":
        raw = "rsi_reversion"
    module_name = f"strategy.{raw}"
    module = __import__(module_name, fromlist=[f"Strategy{name}"])
    cls = getattr(module, f"Strategy{name}")
    logger.debug("Loaded strategy %s with params %s", name, params)
    return cls(params)


def run_backtest(
    strategy: BaseStrategy,
    candles: list,
    warmup: int,
) -> Dict[str, Any]:
    """
    Run backtest on candles (list of OANDA candle dicts). Returns summary metrics.
    """
    wins = losses = trades = 0
    total_win = total_loss = 0.0

    bars: Deque = deque(maxlen=warmup + 5)
    logger.info(
        "Starting backtest: warmup=%d, total candles=%d",
        warmup,
        len(candles),
    )
    for idx, candle in enumerate(candles[:-1]):
        bars.append(candle)
        signal = strategy.next_signal(list(bars))
        # Simulate single-bar exit: on next candle close
        if signal in ("BUY", "SELL"):
            entry = float(candle["mid"]["c"])
            exit_price = float(candles[idx + 1]["mid"]["c"])
            pnl = (exit_price - entry) if signal == "BUY" else (entry - exit_price)
            logger.debug(
                "Signal %s at idx %d: entry=%.5f exit=%.5f pnl=%.5f",
                signal, idx, entry, exit_price, pnl
            )
            if pnl > 0:
                wins += 1
                total_win += pnl
            else:
                losses += 1
                total_loss += abs(pnl)
            trades += 1
            strategy.update_trade_result(pnl > 0, pnl)

    win_rate = wins / trades if trades else 0.0
    avg_win = total_win / wins if wins else 0.0
    avg_loss = total_loss / losses if losses else 0.0
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
    total_pnl = total_win - total_loss

    logger.info(
        "Backtest results - trades: %d, win_rate: %.2f%%, avg_win: %.5f, "
        "avg_loss: %.5f, expectancy: %.5f",
        trades,
        win_rate * 100,
        avg_win,
        avg_loss,
        expectancy,
    )

    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "total_pnl": total_pnl,
    }


def main():
    parser = argparse.ArgumentParser(description="Generic strategy backtester")
    parser.add_argument(
        "--strategy",
        required=True,
        help=(
            "Strategy name matching class Strategy<Name> and file "
            "strategy/<name_lower>.py"
        ),
    )
    parser.add_argument(
        "--config",
        default="live_config.json",
        help="JSON file with strategy parameters",
    )
    parser.add_argument("--instrument", default="EUR_USD")
    parser.add_argument("--granularity", default="H1")
    parser.add_argument("--count", type=int, default=2000)
    parser.add_argument("--warmup", type=int, default=200)
    args = parser.parse_args()

    # Load params
    with open(args.config, "r") as f:
        cfg = json.load(f)
    params = cfg.get(args.strategy, {})

    logger.info("Loading strategy %s with params %s", args.strategy, params)
    strat = load_strategy(args.strategy, params)

    logger.info(
        "Fetching %d historical candles for %s @ %s",
        args.count, args.instrument, args.granularity
    )
    candles = get_candles(args.instrument, args.granularity, args.count)
    logger.info("Fetched %d candles", len(candles))

    start = time.perf_counter()
    results = run_backtest(strat, candles, args.warmup)
    elapsed = time.perf_counter() - start

    logger.info(
        "Backtest completed in %.2f seconds",
        elapsed,
    )
    print(
        json.dumps(
            results,
            indent=2,
        )
    )

if __name__ == "__main__":
    main()


# For integration with meta-optimizer
class Backtester:
    """
    Wrapper to call run_backtest and return total PnL for use in meta-optimization.
    """

    def __init__(self, strategy, candles):
        self.strategy = strategy
        self.candles = candles

    def run(self):
        # Use the strategy's warmup param if provided, else default to 0
        warmup = getattr(
            self.strategy,
            "params",
            {},
        ).get("warmup", 0)
        stats = run_backtest(self.strategy, self.candles, warmup)
        return stats.get(
            "total_pnl",
            0.0,
        )
