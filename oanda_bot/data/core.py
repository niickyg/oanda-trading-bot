# data.py
import os
from dotenv import load_dotenv

from ..utils.retry import api_retry

import datetime as _dt
import collections

# Ensure typing is imported

# 1) read .env
load_dotenv()
OANDA_TOKEN = os.getenv("OANDA_TOKEN")
OANDA_ENV = os.getenv("OANDA_ENV", "practice")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID")


def _get_token() -> str:
    token = os.getenv("OANDA_TOKEN", "").strip()
    if len(token) < 30:
        raise RuntimeError(
            "OANDA_TOKEN is missing or looks too short.\n"
            "Ensure this secret is set (for example, in your GitHub Actions "
            "repository secrets or in a local .env file)."
        )
    return token


def _get_account_id() -> str:
    acc = os.getenv("OANDA_ACCOUNT_ID", "")
    if len(acc.strip()) < 6:
        raise RuntimeError(
            "OANDA_ACCOUNT_ID is missing or looks wrong.\n"
            "Set it in your environment or .env file."
        )
    return acc


def _get_api_client():
    """
    Return a fresh OANDA API client using the current environment settings.
    """
    import oandapyV20
    return oandapyV20.API(access_token=_get_token(), environment=OANDA_ENV)


@api_retry
def get_candles(symbol="EUR_USD", granularity="M1", count=500, price="M"):
    """
    Return a list of candle dicts.
    granularity: S5,S10,S15,S30,M1,M2,M5,M15,M30,H1,H2,H4,H6,H8,H12,D,W,M
    price: 'M' midpoint, 'B' bid, 'A' ask, 'BA' both
    """
    from oandapyV20.endpoints import instruments as _instruments
    params = {"granularity": granularity, "count": count, "price": price}
    r = _instruments.InstrumentsCandles(instrument=symbol, params=params)
    _get_api_client().request(r)
    return r.response["candles"]


@api_retry
def get_m1_candles(symbol="EUR_USD", count=200, price="M"):
    """Convenience wrapper for 1‑minute candles (used for fresh ATR)."""
    return get_candles(symbol=symbol, granularity="M1", count=count, price=price)


# ---------------------------------------------------------------------------
# Volume helpers
# ---------------------------------------------------------------------------


@api_retry
def get_last_volume(symbol="EUR_USD", granularity="M5") -> int:
    """
    Return the 'volume' (tick count) of the most recent completed candle
    for the given instrument and granularity.
    """
    candles = get_candles(symbol=symbol, granularity=granularity,
                          count=2, price="M")  # last two to ensure 'complete'
    last = candles[-2] if candles[-1]["complete"] is False else candles[-1]
    return int(last["volume"])


def build_active_list(all_pairs, top_k=12, granularity="M5") -> list[str]:
    """
    Return the top_k instruments by last‑candle volume.
    Makes one API call per instrument (respects 60 req/min limit).
    """
    volumes = []
    for instr in all_pairs:
        try:
            vol = get_last_volume(instr, granularity)
            volumes.append((vol, instr))
        except Exception as exc:
            print(f"[vol] {instr}: {exc}")
            continue
    # sort by volume descending and take top_k
    volumes.sort(reverse=True)
    return [instr for _, instr in volumes[:top_k]]


# ---------------------------------------------------------------------------
# Streaming 5‑second bars
# ---------------------------------------------------------------------------

import time
import logging

logger = logging.getLogger(__name__)


def _stream_bars_once(pairs, seconds: int = 5, on_ohlc=None, timeout_seconds: int = 300):
    """
    Internal implementation of stream_bars without reconnection logic.
    Will raise exception if stream dies or times out.
    """
    from oandapyV20.endpoints import pricing as _pricing

    if not pairs:
        raise ValueError("pairs list cannot be empty")

    params = {"instruments": ",".join(pairs)}
    stream = _pricing.PricingStream(accountID=_get_account_id(), params=params)

    minute_ohlc = {p: {"minute": None, "open": None, "high": None, "low": None, "close": None} for p in pairs}

    bucket = collections.defaultdict(list)
    bucket_start = _dt.datetime.utcnow()
    last_data_time = time.time()

    for msg in _get_api_client().request(stream):
        # Check for stream timeout (no data received for timeout_seconds)
        if time.time() - last_data_time > timeout_seconds:
            logger.warning(f"Stream timeout: no data for {timeout_seconds}s, reconnecting...")
            raise TimeoutError(f"No data received for {timeout_seconds} seconds")

        last_data_time = time.time()

        # skip heartbeats and other non‑price messages
        if msg.get("type") != "PRICE":
            continue

        instr = msg["instrument"]
        # mid‑price ≈ average of best bid/ask
        bid = float(msg["bids"][0]["price"])
        ask = float(msg["asks"][0]["price"])
        mid_px = (bid + ask) / 2.0
        bucket[instr].append(mid_px)

        # Maintain per‑minute OHLC for ATR updates via stream
        now_minute = int(_dt.datetime.utcnow().timestamp() // 60)
        o = minute_ohlc[instr]
        # If this is a new minute, finalize the previous one and notify
        if o["minute"] is not None and o["minute"] != now_minute and o["open"] is not None:
            finalized = {"minute": o["minute"], "open": o["open"], "high": o["high"], "low": o["low"], "close": o["close"]}
            if callable(on_ohlc):
                try:
                    on_ohlc(instr, finalized)
                except Exception:
                    pass
            # start new bucket
            o.update({"minute": now_minute, "open": mid_px, "high": mid_px, "low": mid_px, "close": mid_px})
        else:
            # Same minute or first tick
            if o["minute"] != now_minute or o["open"] is None:
                o.update({"minute": now_minute, "open": mid_px, "high": mid_px, "low": mid_px, "close": mid_px})
            else:
                if mid_px > o["high"]:
                    o["high"] = mid_px
                if mid_px < o["low"]:
                    o["low"] = mid_px
                o["close"] = mid_px

        # Emit a bar every <seconds>
        if (_dt.datetime.utcnow() - bucket_start).total_seconds() >= seconds:
            bar_close = {p: prices[-1] for p, prices in bucket.items() if prices}
            yield bar_close
            bucket.clear()
            bucket_start = _dt.datetime.utcnow()


def stream_bars(pairs, seconds: int = 5, on_ohlc=None):
    """
    Yield a dict {pair: close_price} every <seconds> seconds using the
    OANDA PricingStream with automatic reconnection on failure.

    Maintains one persistent TCP connection to avoid REST‑poll throttling.
    If the connection dies or times out (no data for 5 minutes), it will
    automatically reconnect with exponential backoff.

    Example
    -------
    >>> for bar in stream_bars(["EUR_USD", "USD_JPY"]):
    ...     print(bar)      # {'EUR_USD': 1.08123, 'USD_JPY': 161.447}
    """
    retry_count = 0
    max_backoff = 60  # Maximum 60 seconds between retries

    while True:
        try:
            logger.info(f"Starting price stream for {len(pairs)} pairs (attempt {retry_count + 1})")

            # Reset retry count on successful connection
            for bar in _stream_bars_once(pairs, seconds, on_ohlc, timeout_seconds=300):
                retry_count = 0  # Reset on successful data
                yield bar

        except (TimeoutError, ConnectionError, Exception) as e:
            retry_count += 1
            backoff = min(2 ** retry_count, max_backoff)  # Exponential backoff capped at max_backoff

            logger.error(
                f"Stream connection failed (attempt {retry_count}): {type(e).__name__}: {e}. "
                f"Reconnecting in {backoff}s...",
                exc_info=True if retry_count <= 3 else False  # Full traceback only for first 3 attempts
            )

            time.sleep(backoff)
            logger.info(f"Attempting to reconnect to price stream...")


# quick manual test
if __name__ == "__main__":
    print("Streaming 5‑second bars for EUR_USD, USD_JPY … Ctrl‑C to stop.")
    try:
        for bar in stream_bars(["EUR_USD", "USD_JPY"]):
            print(bar)
    except KeyboardInterrupt:
        print("Stopped.")


__all__ = [
    "get_candles",
    "get_m1_candles",
    "get_last_volume",
    "build_active_list",
    "stream_bars",
]

# expose api client constructor for external use/tests
api = _get_api_client
