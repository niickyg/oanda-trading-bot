from .base import BaseStrategy
from typing import Dict, Any

class StrategyTrendMA(BaseStrategy):
    """
    Simple moving-average crossover trend follower.
    Signals BUY on golden cross, SELL on death cross using fast/slow SMAs.
    Applies ATR-based stop loss and placeholder for trailing.
    """
    # Strategy identifier
    name = "TrendMA"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Fast and slow MA windows (e.g., 50 and 200)
        self.fast = int(config.get("fast", 50))
        self.slow = int(config.get("slow", 200))
        # ATR window and multiplier for stop loss
        self.atr_window = int(config.get("atr_window", 14))
        self.atr_mult = float(config.get("atr_mult", 1.5))
        # Price history
        self.highs = []
        self.lows = []
        self.closes = []
        # Previous MA values for crossover detection
        self.prev_fast_ma = None
        self.prev_slow_ma = None

    # ------------------------------------------------------------------ #
    # Helper: normalise various candle formats to a uniform bar dict.    #
    # ------------------------------------------------------------------ #
    def _candle_to_bar(self, candle):
        """
        Normalises a raw candle (tuple, dict, or OANDA object) into a bar dict.
        Supports lists/tuples of length 4–6, dicts with open/high/low/close or nested mid/bid/ask, and objects.
        """
        try:
            # 1) Tuple or list formats
            if isinstance(candle, (list, tuple)):
                length = len(candle)
                if length == 6:
                    t, o, h, l, c, v = candle
                elif length == 5:
                    t = None
                    o, h, l, c, v = candle
                elif length == 4:
                    t = None
                    o, h, l, c = candle
                    v = 0
                else:
                    return None
                return {
                    "time": t,
                    "open":  self._safe_float(o),
                    "high":  self._safe_float(h),
                    "low":   self._safe_float(l),
                    "close": self._safe_float(c),
                    "volume": self._safe_float(v),
                }

            # 2) Dict formats
            if isinstance(candle, dict):
                leg = candle.get("mid") or candle.get("bid") or candle.get("ask")
                base = leg if isinstance(leg, dict) else candle
                return {
                    "time":   candle.get("time") or candle.get("timestamp"),
                    "open":   self._safe_float(base.get("o") or base.get("open")),
                    "high":   self._safe_float(base.get("h") or base.get("high")),
                    "low":    self._safe_float(base.get("l") or base.get("low")),
                    "close":  self._safe_float(base.get("c") or base.get("close")),
                    "volume": self._safe_float(candle.get("volume") or candle.get("tradeCount")),
                }

            # 3) OANDA Candle objects
            if hasattr(candle, "__dict__") and hasattr(candle, "complete"):
                return {
                    "time":   getattr(candle, "time", None) or getattr(candle, "timestamp", None),
                    "open":   self._safe_float(getattr(candle, "open", None)),
                    "high":   self._safe_float(getattr(candle, "high", None)),
                    "low":    self._safe_float(getattr(candle, "low", None)),
                    "close":  self._safe_float(getattr(candle, "close", None)),
                    "volume": self._safe_float(getattr(candle, "volume", None)),
                }

            # Unsupported format
            return None
        except Exception:
            return None

    @staticmethod
    def _safe_float(val):
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def next_signal(self, candles):
        """
        Wrap handle_bar logic so the main loop can use this strategy.
        Returns "BUY", "SELL", or None.
        """
        if not candles:
            return None

        bar = self._candle_to_bar(candles[-1])

        result = self.handle_bar(bar)

        # handle_bar may return a dict, a list of dicts, or None
        if isinstance(result, dict):
            return result.get("side", "").upper() if "side" in result else None
        if isinstance(result, list) and result and isinstance(result[0], dict):
            return result[0].get("side", "").upper()
        return None

    def handle_bar(self, bar: Dict[str, Any]):
        """
        Called on each new bar.
        Returns a single signal dict or None.
        """
        # Ensure numeric types – convert strings to floats
        try:
            bar_high = float(bar["high"])
            bar_low = float(bar["low"])
            bar_close = float(bar["close"])
        except (KeyError, TypeError, ValueError):
            # Skip this bar if it lacks the required numeric fields
            return None

        # Append bar data
        self.highs.append(bar_high)
        self.lows.append(bar_low)
        self.closes.append(bar_close)
        # Maintain history length
        max_len = max(self.slow, self.atr_window) + 1
        if len(self.closes) > max_len:
            self.highs.pop(0)
            self.lows.pop(0)
            self.closes.pop(0)

        # Ensure enough data for slow MA and ATR
        if len(self.closes) < max(self.slow, self.atr_window) + 1:
            return None

        # Calculate SMAs
        fast_ma = sum(self.closes[-self.fast:]) / self.fast
        slow_ma = sum(self.closes[-self.slow:]) / self.slow

        signal = None
        # Only check for crossover if we have previous values
        if self.prev_fast_ma is not None and self.prev_slow_ma is not None:
            # Golden cross: fast crosses above slow
            if self.prev_fast_ma <= self.prev_slow_ma and fast_ma > slow_ma:
                # Calculate ATR for stop loss
                trs = []
                for i in range(-self.atr_window, 0):
                    h = self.highs[i]
                    l = self.lows[i]
                    prev_close = self.closes[i-1]
                    trs.append(max(h - l, abs(h - prev_close), abs(l - prev_close)))
                atr = sum(trs) / len(trs)
                stop_loss = bar["close"] - self.atr_mult * atr
                signal = {
                    "type": "market",
                    "side": "buy",
                    "price": bar["close"],
                    "stop_loss": stop_loss
                }
            # Death cross: fast crosses below slow
            elif self.prev_fast_ma >= self.prev_slow_ma and fast_ma < slow_ma:
                trs = []
                for i in range(-self.atr_window, 0):
                    h = self.highs[i]
                    l = self.lows[i]
                    prev_close = self.closes[i-1]
                    trs.append(max(h - l, abs(h - prev_close), abs(l - prev_close)))
                atr = sum(trs) / len(trs)
                stop_loss = bar["close"] + self.atr_mult * atr
                signal = {
                    "type": "market",
                    "side": "sell",
                    "price": bar["close"],
                    "stop_loss": stop_loss
                }

        # Update previous MA for next crossover check
        self.prev_fast_ma = fast_ma
        self.prev_slow_ma = slow_ma

        if signal:
            return [signal]
        return None