from typing import Sequence, Optional, Tuple
import datetime as _dt

import numpy as np

# ---------------------------------------------------------------------------
# Adaptive parameters
# ---------------------------------------------------------------------------
from collections import deque

_PERF_WINDOW = 100  # rolling trade outcomes to track
_results = deque(maxlen=_PERF_WINDOW)  # True=win, False=loss

# Tunable strategy parameters (start with defaults)
PARAMS = {
    "ema_trend": 200,   # trend filter period
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_sig": 9,
}


# ---------------------------------------------------------------------------
# Adaptive performance update
# ---------------------------------------------------------------------------
def update_strategy_performance(trade_won: bool):
    """
    Call this from the trading loop after each closed trade.
    Maintains a rolling win‑loss record and nudges parameters.

    Simple rule:
    - If rolling win‑rate < 45 %, make strategy MORE aggressive:
        shorten MACD fast/slow by 2 periods (min fast=6, slow=fast+8)
    - If win‑rate > 60 %, make strategy LESS aggressive:
        lengthen MACD fast/slow by 2 periods (max fast=20, slow=fast+10)
    - Trend EMA adjusts with slow MACD period (trend = slow*8 roughly)
    """
    _results.append(trade_won)
    if len(_results) < 20:  # need some data first
        return

    win_rate = sum(_results) / len(_results)

    if win_rate < 0.45:
        # more trades → shorten EMAs
        PARAMS["macd_fast"] = max(6, PARAMS["macd_fast"] - 2)
    elif win_rate > 0.60:
        # fewer trades → lengthen EMAs
        PARAMS["macd_fast"] = min(20, PARAMS["macd_fast"] + 2)

    PARAMS["macd_slow"] = PARAMS["macd_fast"] + 8
    PARAMS["macd_sig"] = max(6, int(PARAMS["macd_fast"] / 2))
    PARAMS["ema_trend"] = PARAMS["macd_slow"] * 8


def _parse_iso(ts: str) -> _dt.datetime:
    """
    Parse an ISO‑8601 timestamp (with optional nanoseconds) into a timezone‑aware
    datetime, truncating fractional seconds to microseconds.
    """
    ts = ts.replace("Z", "+00:00")
    if "." in ts:
        main, rest = ts.split(".", 1)
        frac, tz = rest.split("+", 1)
        ts = f"{main}.{frac[:6]}+{tz}"
    return _dt.datetime.fromisoformat(ts)


def breakout_signal(
    candles: Sequence[dict],
    buffer: float = 0.0001,
) -> Optional[str]:
    """
    London-open breakout strategy.

    Args
    ----
    candles : list of dicts returned by get_candles() where each dict has:
        - "time"  : ISO-8601 string
        - "mid"   : {"h": str, "l": str, "c": str}
    buffer  : price offset (in quote-currency units) added above the pre-open
              high / below the pre-open low to avoid stop-hunts.

    Returns
    -------
    "BUY", "SELL", or None
    """
    if len(candles) < 5:
        return None

    # Parse last candle timestamp
    last = candles[-1]
    ts = _parse_iso(last["time"])

    # Define London session windows (UTC)
    pre_start = _dt.time(7, 15)   # 07:15–07:45 gather range
    pre_end = _dt.time(7, 45)
    trade_end = _dt.time(10, 0)   # invalidate breakout after 10:00

    # 1) Build the pre-open range
    day_candles = [
        c for c in candles
        if pre_start <= _parse_iso(c["time"]).time() <= pre_end
        and _parse_iso(c["time"]).date() == ts.date()
    ]
    if not day_candles:
        return None

    high = max(float(c["mid"]["h"]) for c in day_candles)
    low = min(float(c["mid"]["l"]) for c in day_candles)

    # 2) During the range-building window: no trade
    if ts.time() <= pre_end:
        return None

    # 3) Between 07:45 and 10:00 → check breakout
    if pre_end < ts.time() <= trade_end:
        last_high = float(last["mid"]["h"])
        last_low = float(last["mid"]["l"])
        if last_high > high + buffer:
            return "BUY"
        if last_low < low - buffer:
            return "SELL"

    return None


def _ema_last(arr: np.ndarray, span: int) -> float:
    """
    Compute the last value of an Exponential Moving Average (EMA) for
    the given NumPy array and span. Implemented in pure NumPy for speed.
    """
    alpha = 2.0 / (span + 1)
    ema = arr[0]
    for v in arr[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def _ema_series(arr: np.ndarray, span: int) -> np.ndarray:
    """Full EMA series (numpy single‑pass)."""
    alpha = 2.0 / (span + 1)
    ema = np.empty_like(arr)
    ema[0] = arr[0]
    for i in range(1, len(arr)):
        ema[i] = alpha * arr[i] + (1 - alpha) * ema[i - 1]
    return ema


def _macd(arr: np.ndarray, fast=12, slow=26, sig=9) -> Tuple[np.ndarray, np.ndarray]:
    """MACD (fast‑slow EMA) and signal line."""
    macd_line = _ema_series(arr, fast) - _ema_series(arr, slow)
    signal_line = _ema_series(macd_line, sig)
    return macd_line, signal_line


def generate_signal(prices: Sequence[float]) -> Optional[str]:
    """
    MACD + adaptive EMA trend‑following signal.

    Returns "BUY", "SELL", or None
    """
    # Need at least enough prices for trend filter
    if len(prices) < PARAMS["ema_trend"] + 1:
        return None

    arr = np.asarray(prices, dtype=np.float64)

    # Trend filter (adaptive period)
    ema_trend_per = PARAMS["ema_trend"]
    ema_trend = _ema_last(arr, ema_trend_per)

    # MACD components using adaptive params
    f, s, g = PARAMS["macd_fast"], PARAMS["macd_slow"], PARAMS["macd_sig"]
    macd_line, macd_sig = _macd(arr, fast=f, slow=s, sig=g)

    # Use previous bar for cross detection
    macd_prev, sig_prev = macd_line[-2], macd_sig[-2]
    macd_curr, sig_curr = macd_line[-1], macd_sig[-1]
    price_curr = arr[-1]

    # Bullish crossover in up‑trend
    if price_curr > ema_trend and macd_prev < sig_prev and macd_curr > sig_curr:
        return "BUY"

    # Bearish crossover in down‑trend
    if price_curr < ema_trend and macd_prev > sig_prev and macd_curr < sig_curr:
        return "SELL"

    return None


# ---------------------------------------------------------------------------
# Risk‑management helpers
# ---------------------------------------------------------------------------


def compute_atr(candles: Sequence[dict], period: int = 14) -> float:
    """
    Simple Average True Range (ATR).

    Args
    ----
    candles : list of OANDA price dictionaries, newest last.
    period  : number of bars for the ATR (default 14).

    Returns
    -------
    ATR value in price units (e.g. 0.00123 for EURUSD).
    """
    if len(candles) < period + 1:
        return 0.0

    highs = [float(c["mid"]["h"]) for c in candles[-(period + 1):]]
    lows = [float(c["mid"]["l"]) for c in candles[-(period + 1):]]
    closes = [float(c["mid"]["c"]) for c in candles[-(period + 1):]]

    tr_vals = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_vals.append(tr)

    return sum(tr_vals) / len(tr_vals)


def sl_tp_levels(
    entry_price: float,
    direction: str,
    atr_value: float,
    sl_mult: float = 1.0,
    tp_mult: float = 2.0,
) -> Tuple[float, float]:
    """
    Calculate stop‑loss and take‑profit prices using ATR multiples.

    Args
    ----
    entry_price : price at which the trade is opened
    direction   : "BUY" or "SELL"
    atr_value   : ATR in price units
    sl_mult     : multiple of ATR for stop‑loss (default 1.0)
    tp_mult     : multiple of ATR for take‑profit (default 2.0)

    Returns
    -------
    (stop_loss_price, take_profit_price)
    """
    if atr_value <= 0:
        raise ValueError("ATR must be positive")

    if direction == "BUY":
        sl = entry_price - sl_mult * atr_value
        tp = entry_price + tp_mult * atr_value
    elif direction == "SELL":
        sl = entry_price + sl_mult * atr_value
        tp = entry_price - tp_mult * atr_value
    else:
        raise ValueError("direction must be 'BUY' or 'SELL'")

    # Dynamic precision: JPY‑priced instruments trade to 2 dp, others to 5 dp.
    # Use entry price as a proxy (JPY pairs quote >20).
    prec = 2 if entry_price >= 20 else 5
    sl_rounded = round(sl, prec)
    tp_rounded = round(tp, prec)
    # Ensure SL/TP are not equal to the entry price
    pip = 0.01 if entry_price >= 20 else 0.0001
    # Nudge SL if it equals entry
    if sl_rounded == entry_price:
        sl_rounded = entry_price - pip if direction == "BUY" else entry_price + pip
    # Nudge TP if it equals entry
    if tp_rounded == entry_price:
        tp_rounded = entry_price + pip if direction == "BUY" else entry_price - pip
    return sl_rounded, tp_rounded
