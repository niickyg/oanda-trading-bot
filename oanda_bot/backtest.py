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
import logging.handlers
from pythonjsonlogger import jsonlogger
from .data import get_candles
from .strategy.base import BaseStrategy
from .strategy.macd_trends import sl_tp_levels

# Configure rotating log handler
handler = logging.handlers.RotatingFileHandler(
    filename="backtest.log",
    maxBytes=10_000_000,  # 10 MB
    backupCount=5
)
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s"
)
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)


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
    module_name = f"oanda_bot.strategy.{raw}"
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
    Run backtest on candles (list of OANDA candle dicts). Returns a stats dictionary.
    """
    start_time = time.perf_counter()

    wins = losses = trades = 0
    total_win = total_loss = 0.0

    bars: Deque = deque(maxlen=warmup + 5)
    logger.debug(
        "Starting backtest: warmup=%d, total candles=%d",
        warmup,
        len(candles),
    )
    position = None  # holds current open trade or None
    for idx, candle in enumerate(candles):
        bars.append(candle)

        # -------- handle open position exits ---------------------------------
        if position:
            side       = position["side"]          # "BUY" or "SELL"
            sl         = position["sl"]
            tp         = position["tp"]
            entry_idx  = position["entry_idx"]
            price_high = float(candle["mid"]["h"])
            price_low  = float(candle["mid"]["l"])
            price_close = float(candle["mid"]["c"])

            hit_sl = (side == "BUY"  and price_low  <= sl) or \
                     (side == "SELL" and price_high >= sl)
            hit_tp = (side == "BUY"  and price_high >= tp) or \
                     (side == "SELL" and price_low  <= tp)
            max_dur = strategy.params.get("max_duration", 0)
            hit_time = max_dur and (idx - entry_idx) >= max_dur

            if hit_sl or hit_tp or hit_time:
                exit_price = (
                    tp if hit_tp else
                    sl if hit_sl else
                    price_close            # time exit
                )
                pnl = (
                    exit_price - position["entry_price"]
                    if side == "BUY"
                    else position["entry_price"] - exit_price
                )
                logger.debug(
                    "EXIT %s at idx %d: entry=%.5f exit=%.5f pnl=%.5f reason=%s",
                    side, idx, position["entry_price"], exit_price, pnl,
                    "TP" if hit_tp else "SL" if hit_sl else "TIME"
                )
                if pnl > 0:
                    wins += 1
                    total_win += pnl
                else:
                    losses += 1
                    total_loss += abs(pnl)
                trades += 1
                strategy.update_trade_result(pnl > 0, pnl)
                position = None  # flat for now

        # -------- look for a new entry signal --------------------------------
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
                logger.debug(
                    "ENTER %s at idx %d: entry=%.5f sl=%.5f tp=%.5f",
                    signal, idx, entry_price, sl, tp
                )

    win_rate = wins / trades if trades else 0.0
    avg_win = total_win / wins if wins else 0.0
    avg_loss = total_loss / losses if losses else 0.0
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
    total_pnl = total_win - total_loss

    # Convert PnL to pips for EUR/USD (1 pip = 0.0001)
    pip_size = 0.0001
    total_pnl_pips = total_pnl / pip_size

    logger.info(
        "Backtest results: trades=%d, win_rate=%.2f, avg_win=%.5f, "
        "avg_loss=%.5f, expectancy=%.5f, total_pnl=%.4f, "
        "total_pips=%.1f",
        trades, win_rate, avg_win, avg_loss, expectancy, total_pnl, total_pnl_pips
    )
    duration = time.perf_counter() - start_time
    logger.info("run_backtest duration: %.2f seconds", duration)

    # Build and return a stats dictionary (single, canonical API)
    stats = {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "expectancy": expectancy,
        "total_pnl": total_pnl,
    }
    return stats


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
    # Call backtest (tuple for compatibility or dict for JSON)
    res = run_backtest(strat, candles, args.warmup)
    results = res
    elapsed = time.perf_counter() - start
    logger.info("Backtest completed in %.2f seconds", elapsed)
    print(json.dumps(results, indent=2))


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
