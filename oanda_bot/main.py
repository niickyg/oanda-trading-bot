
import csv
import json
import os
import itertools
import time
from collections import deque
from datetime import datetime
from requests.exceptions import ChunkedEncodingError
import requests
import pkgutil
import importlib
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
import signal
import sys
import logging
import logging.handlers
from pythonjsonlogger import jsonlogger

from oandapyV20.endpoints.accounts import AccountSummary
import broker  # noqa: F401  # expose module for tests that patch main.broker
# Only pull in the live OANDA data core when running as the main script
if __name__ == "__main__":
    from data.core import (
        OANDA_ACCOUNT_ID as ACCOUNT,
        api as API,
        build_active_list,
        get_candles,
        stream_bars,
    )
else:
    # Stubs for import-time usage (e.g. pytest)
    ACCOUNT = None
    API = None

    def build_active_list(pairs, top_k):
        return pairs

    def get_candles(*args, **kwargs):
        return []

    def stream_bars(*args, **kwargs):
        return iter([])
from strategy.base import BaseStrategy
from strategy.utils import sl_tp_levels
from dotenv import load_dotenv

# Load environment variables from .env file, if present
load_dotenv()


# Error-reporting webhook (e.g., Slack or custom endpoint)
ERROR_WEBHOOK_URL = os.getenv("ERROR_WEBHOOK_URL")


def send_alert(message: str):
    """Send alert on errors via webhook, if configured."""
    if ERROR_WEBHOOK_URL:
        try:
            requests.post(ERROR_WEBHOOK_URL, json={"text": message}, timeout=5)
        except Exception:
            logger.warning("Failed to send error alert", exc_info=True)

# ---------------------------------------------------------------------------
# Logging (must be configured before any thread tries to use `logger`)
# ---------------------------------------------------------------------------


handler = logging.handlers.RotatingFileHandler(
    filename="live_trading.log",
    maxBytes=10_000_000,
    backupCount=5,
)
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s"
)
handler.setFormatter(formatter)

# Also log to stdout so crashes are visible when running locally
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
# ---------------------------------------------------------------------------


def handle_exit(signum, frame):
    logger.info(f"💀 Received signal {signum}, shutting down...")
    sys.exit(0)


# Register for SIGINT and SIGTERM
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()


def start_health_server():
    try:
        server = HTTPServer(("0.0.0.0", 8000), HealthHandler)
        server.serve_forever()
    except OSError as e:
        logger.warning("Health server failed to start (port busy): %s", e)


try:
    from meta_optimize import run_meta_bandit  # noqa: E402
except ImportError:
    def run_meta_bandit(*args, **kwargs):
        """Stub for tests if meta_optimize missing."""
        pass

try:
    from strategy.plugins import get_enabled_strategies  # noqa: E402
except ImportError:
    def get_enabled_strategies():
        """Stub for tests if strategy.plugins missing."""
        return []

# Inline manager functionality
CONFIG_FILE = "live_config.json"
POLL_INTERVAL = 60  # seconds


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def load_strategies():
    """
    Auto‑discover and instantiate every BaseStrategy subclass inside
    the *installed* ``strategy`` package, regardless of the current
    working directory.
    """
    import strategy as strategy_pkg  # import the package itself

    strategies = []
    seen = set()
    # Walk through all sub‑modules inside strategy/
    for _, module_name, _ in pkgutil.iter_modules(
        strategy_pkg.__path__,
        strategy_pkg.__name__ + ".",
    ):
        module = importlib.import_module(module_name)
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseStrategy)
                and obj is not BaseStrategy
            ):
                if obj not in seen:
                    strategies.append(obj({}))
                    seen.add(obj)

    names = [s.name for s in strategies]
    print(f"[manager] Loaded strategies: {names}")
    return strategies


# def watch_strategies():
#     """
#     Generator yielding updated strategy lists whenever the config changes.
#     """
#     last_mtime = None
#     strategies = []
#     while True:
#         try:
#             mtime = os.path.getmtime(CONFIG_FILE)
#         except Exception:
#             mtime = None
#         if mtime != last_mtime:
#             strategies = load_strategies()
#             print("[manager] Loaded strategies:", [s.name for s in strategies])
#             last_mtime = mtime
#         time.sleep(POLL_INTERVAL)
#         yield strategies


# End inline manager


# Load optimized parameters (handle missing keys gracefully)
with open("best_params.json", "r") as _f:
    _best = json.load(_f)

# BEST_FAST    = _best.get("fast")        # no longer used
# BEST_SLOW    = _best.get("slow")        # no longer used
BEST_SL_MULT = _best.get("sl_mult", 1.5)  # sensible fallback
BEST_TP_MULT = _best.get("tp_mult", 2.0)


# Allowed decimal precision per instrument
PRECISION = {
    # JPY pairs (2 decimal places)
    "GBP_JPY": 2,
    "EUR_JPY": 2,
    "NZD_JPY": 2,
    "USD_JPY": 2,
    # Major crosses (5 decimal places)
    "GBP_USD": 5,
    "EUR_USD": 5,
    "AUD_USD": 5,
    "USD_CAD": 5,
    "USD_CHF": 5,
    # Other common pairs (adjust as needed)
    "AUD_JPY": 2,
    "EUR_GBP": 5,
    "GBP_AUD": 5,
    "EUR_AUD": 5,
    # Default fallback
}


def round_price(instrument: str, price: float) -> str:
    """Round price to the allowed precision for the given instrument."""
    prec = PRECISION.get(instrument, 5)
    return f"{price:.{prec}f}"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ALL_PAIRS = [
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "NZD_USD",
    "USD_JPY",
    "USD_CHF",
    "USD_CAD",
    "EUR_JPY",
    "EUR_GBP",
    "EUR_AUD",
    "EUR_CHF",
    "EUR_CAD",
    "GBP_JPY",
    "GBP_AUD",
    "GBP_CHF",
    "GBP_CAD",
    "AUD_JPY",
    "AUD_NZD",
    "AUD_CAD",
    "NZD_JPY",
    "NZD_CAD",
]  # 20 majors & crosses

BAR_SECONDS = 2  # aggregation window
MAX_UNITS = 1000  # cap position size to avoid excessive orders
LOG_FILE = "trades_log.csv"
BANDIT_DRAWDOWN_THRESHOLD = 0.05  # 5% drawdown triggers live re-optimization
BANDIT_ROUNDS = 50

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
ACTIVE_PAIRS = build_active_list(ALL_PAIRS, top_k=10)

pair_cycle = itertools.cycle(ACTIVE_PAIRS)
history = {p: deque(maxlen=300) for p in ALL_PAIRS}
atr_history = {p: deque(maxlen=30) for p in ALL_PAIRS}
recent_trades = deque(maxlen=100)  # store True=win, False=loss for last 100 trades
last_equity_fetch = 0.0
account_equity = 1000.0  # will be refreshed from API
peak_equity = account_equity
drawdown_pct = 0.0
last_order_ts = 0.0  # epoch seconds

# Load and watch for config changes to strategies
strategy_instances = load_strategies()
# config_watcher = watch_strategies()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log_trade(
    pair: str,
    side: str,
    units: int,
    order_id: str,
    entry: float,
    sl: float,
    tp: float,
    atr: float,
    session_hour: int,
):
    """Append one trade entry to LOG_FILE."""
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode="a", newline="") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(
                [
                    "timestamp",
                    "pair",
                    "side",
                    "units",
                    "order_id",
                    "entry",
                    "stop_loss",
                    "take_profit",
                    "ATR",
                    "session_hour",
                ]
            )
        w.writerow(
            [
                datetime.utcnow().isoformat(),
                pair,
                side,
                units,
                order_id,
                f"{entry:.5f}",
                sl,
                tp,
                f"{atr:.5f}",
                session_hour,
            ]
        )


# ---------------------------------------------------------------------------
# Core trading logic
# ---------------------------------------------------------------------------


# Unified signal handler for modular strategies
def handle_signal(pair: str, price: float, signal: str):
    """
    Issue order for a given signal using risk-managed broker.
    """
    global last_order_ts, account_equity, last_equity_fetch, peak_equity, drawdown_pct

    if not signal:
        logger.debug("signal.none", extra={"instrument": pair})
        return

    # Normalize signal to uppercase for sl_tp_levels
    signal = signal.upper()

    # Enforce rate-limit
    if time.time() - last_order_ts < BAR_SECONDS:
        return

    # Compute ATR (placeholder)
    atr = 0.0005

    # Determine SL/TP levels
    sl_raw, tp_raw = sl_tp_levels(
        price, signal, atr, sl_mult=BEST_SL_MULT, tp_mult=BEST_TP_MULT
    )
    sl = round_price(pair, sl_raw)
    tp = round_price(pair, tp_raw)
    # Skip if stop-loss equals entry price to avoid zero-risk errors
    if float(sl) == price:
        logger.warning(f"{pair} | SKIP {signal} @ {price:.5f}: SL equals entry")
        return

    # Refresh equity every 30s
    if time.time() - last_equity_fetch >= 30:
        last_equity_fetch = time.time()

        # Compute drawdown based on existing equity first
        peak_equity = max(peak_equity, account_equity)
        drawdown_pct = (peak_equity - account_equity) / peak_equity

        if drawdown_pct > BANDIT_DRAWDOWN_THRESHOLD:
            logger.warning(f"Drawdown exceeded 5%: {drawdown_pct:.2%}")
            # Live bandit re-optimization on drawdown
            logger.info("Triggering live meta-bandit optimization due to drawdown")
            try:
                strategies = get_enabled_strategies()
                historical_candles = get_candles(pair, "H1", 2000)
                run_meta_bandit(
                    strategies=strategies,
                    candles=historical_candles,
                    rounds=BANDIT_ROUNDS,
                )
                strategy_instances[:] = load_strategies()
            except Exception:
                logger.error("Live bandit optimization failed", exc_info=True)
        if drawdown_pct > 0.10:
            logger.error(f"Drawdown exceeded 10%: {drawdown_pct:.2%}")

        # Now fetch fresh equity for next cycle
        try:
            summary = API.request(AccountSummary(ACCOUNT))
            account_equity = float(summary["account"]["NAV"])
        except Exception:
            logger.error("Equity fetch error", exc_info=True)

    # Base risk fraction
    risk_frac = 0.01
    # Reduce risk if drawdown exceeds 5%
    if drawdown_pct > 0.05:
        risk_frac *= 0.5
    # Further reduction if drawdown exceeds 10%
    if drawdown_pct > 0.10:
        risk_frac *= 0.5

    # Place order
    resp = broker.place_risk_managed_order(
        instrument=pair,
        side=signal,
        price=price,
        stop_price=float(sl),
        equity=account_equity,
        risk_pct=risk_frac,
        tp_price=float(tp),
    )
    # Accommodate simplified stub responses used in unit tests that might
    # return a flat dict instead of the full OANDA transaction structure.
    order_tx = resp.get("orderCreateTransaction", resp)
    order_id = order_tx.get("id", "TEST")
    units = int(order_tx.get("units", 0))

    session_hour = datetime.utcnow().hour
    logger.info(
        "trade.executed",
        extra={
            "instrument": pair,
            "side": signal,
            "units": units,
            "entry": price,
            "stop_loss": float(sl),
            "take_profit": float(tp),
            "atr": atr,
            "session_hour": session_hour,
            "order_id": order_id,
        },
    )
    log_trade(pair, signal, units, order_id, price, sl, tp, atr, session_hour)
    last_order_ts = time.time()


def handle_bar(bar_close: dict):
    """Process one 5-second bar set (bar_close is {pair: price})."""
    # Update history for each active pair in this bar
    for pair, price in bar_close.items():
        if pair in ACTIVE_PAIRS and price is not None:
            history[pair].append(price)

    # Check for updated strategy config
    # try:
    #     strategy_instances[:] = next(config_watcher)
    # except StopIteration:
    #     pass

    # Evaluate and handle signals for each active pair
    for pair in list(ACTIVE_PAIRS):
        price = bar_close.get(pair)
        if price is None:
            continue

        # Aggregate signals from all enabled strategies
        signal = None
        for strat in strategy_instances:
            sig = strat.next_signal(list(history[pair]))
            if sig:
                signal = sig
                break

        # Optional: log signal generation with structured logging
        if signal:
            logger.debug(
                "signal.generated",
                extra={"instrument": pair, "signal": signal, "price": price},
            )

        # Handle the signal for this pair
        handle_signal(pair, price, signal)


# ---------------------------------------------------------------------------
# Bootstrap historical closes so signals are ready immediately
# ---------------------------------------------------------------------------
def bootstrap_history():
    """Pre‑fill `history` deques with ~300 recent closes for each pair."""
    print("Bootstrapping price history …")
    for pair in ALL_PAIRS:
        try:
            candles = get_candles(symbol=pair, count=300)
            closes = [float(c["mid"]["c"]) for c in candles]
            history[pair].extend(closes)
            # seed ATR deque too (smaller)
            for c in candles[-30:]:
                h, l, c_ = (
                    float(c["mid"]["h"]),
                    float(c["mid"]["l"]),
                    float(c["mid"]["c"]),
                )
                prev_c = closes[closes.index(c_) - 1] if len(closes) > 1 else c_
                tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                atr_history[pair].append(tr)  # raw TR; compute ATR later if needed
        except Exception as e:
            print(f"Bootstrap error for {pair}: {e}")
    print("Bootstrap complete.")


# ---------------------------------------------------------------------------
# Main event loop
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info(f"🚀 Bot starting up in {os.getenv('MODE', 'paper')} mode")
    # In CI we never launch the health‑check server
    if os.getenv("CI"):
        logger.info("CI detected – skipping health server start")
    else:
        # Start HTTP /health endpoint only when running interactively
        if os.getenv("ENABLE_HEALTH", "1") == "1":
            Thread(target=start_health_server, daemon=True).start()
        else:
            logger.info("Health server disabled via ENABLE_HEALTH=0")
    bootstrap_history()
    last_active_refresh = time.time()
    print(f"Streaming {BAR_SECONDS}-second bars … Ctrl-C to stop.")
    while True:

        try:
            # Refresh active pairs every 5 minutes
            if time.time() - last_active_refresh >= 300:
                ACTIVE_PAIRS[:] = build_active_list(ALL_PAIRS, top_k=10)
                last_active_refresh = time.time()
                print(f"Active pairs updated: {ACTIVE_PAIRS}")

            for bar in stream_bars(ALL_PAIRS, seconds=BAR_SECONDS):
                handle_bar(bar)
        except KeyboardInterrupt:
            logger.info("Stopped by user. Closing profitable positions.")
            logger.info("🏁 Bot exiting normally")
            send_alert("Bot stopped by user via KeyboardInterrupt")
            break
        except ChunkedEncodingError:
            logger.warning("Stream dropped—reconnecting in 1s…", exc_info=True)
            time.sleep(1)
            continue
        except Exception:
            logger.exception("Unexpected error in main loop, shutting down.")
            send_alert("Fatal error in main loop, check live_trading.log for details")
            logger.info("🏁 Bot exiting normally")
            break
