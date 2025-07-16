# data.py
import os
from dotenv import load_dotenv
import oandapyV20
import oandapyV20.endpoints.instruments as instruments
from ..utils.retry import api_retry

import datetime as _dt
import collections
import oandapyV20.endpoints.pricing as pricing

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
    return oandapyV20.API(access_token=_get_token(), environment=OANDA_ENV)


@api_retry
def get_candles(symbol="EUR_USD", granularity="M1", count=500, price="M"):
    """
    Return a list of candle dicts.
    granularity: S5,S10,S15,S30,M1,M2,M5,M15,M30,H1,H2,H4,H6,H8,H12,D,W,M
    price: 'M' midpoint, 'B' bid, 'A' ask, 'BA' both
    """
    params = {"granularity": granularity, "count": count, "price": price}
    r = instruments.InstrumentsCandles(instrument=symbol, params=params)
    _get_api_client().request(r)
    return r.response["candles"]


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


def stream_bars(pairs, seconds: int = 5):
    """
    Yield a dict {pair: close_price} every <seconds> seconds using the
    OANDA PricingStream.  Maintains one persistent TCP connection to avoid
    REST‑poll throttling.

    Example
    -------
    >>> for bar in stream_bars(["EUR_USD", "USD_JPY"]):
    ...     print(bar)      # {'EUR_USD': 1.08123, 'USD_JPY': 161.447}
    """
    if not pairs:
        raise ValueError("pairs list cannot be empty")

    params = {"instruments": ",".join(pairs)}
    stream = pricing.PricingStream(accountID=_get_account_id(), params=params)

    bucket = collections.defaultdict(list)
    bucket_start = _dt.datetime.utcnow()

    for msg in _get_api_client().request(stream):
        # skip heartbeats and other non‑price messages
        if msg.get("type") != "PRICE":
            continue

        instr = msg["instrument"]
        # mid‑price ≈ average of best bid/ask
        bid = float(msg["bids"][0]["price"])
        ask = float(msg["asks"][0]["price"])
        mid_px = (bid + ask) / 2.0
        bucket[instr].append(mid_px)

        # Emit a bar every <seconds>
        if (_dt.datetime.utcnow() - bucket_start).total_seconds() >= seconds:
            bar_close = {p: prices[-1] for p, prices in bucket.items() if prices}
            yield bar_close
            bucket.clear()
            bucket_start = _dt.datetime.utcnow()


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
    "get_last_volume",
    "build_active_list",
    "stream_bars",
]

# expose api client constructor for external use/tests
api = _get_api_client
