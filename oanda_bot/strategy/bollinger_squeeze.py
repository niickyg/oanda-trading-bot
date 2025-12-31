from .base import BaseStrategy
from typing import Dict, Any

class StrategyBollingerSqueeze(BaseStrategy):
    """
    Volatility breakout: when Bollinger Band width <= X% of ATR,
    trade the first close outside the bands on expansion.
    """
    # Strategy identifier
    name = "BollingerSqueeze"


    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Window for Bollinger Bands
        self.window = int(config.get("window", 20))
        # Window for ATR calculation
        self.atr_window = int(config.get("atr_window", 14))
        # Threshold for squeeze (as fraction of ATR, e.g., 0.1 for 10%)
        self.width_pct = float(config.get("width_pct", 0.1))
        # Historical price lists
        self.highs = []
        self.lows = []
        self.closes = []
        # Flag for active squeeze
        self.squeeze_on = False

    def next_signal(self, candles):
        """
        Wrap handle_bar logic so the main loop can use this strategy.
        Expects candles as list of tuples: (time, open, high, low, close, volume).
        """
        if not candles:
            return None
        candle = candles[-1]
        # Support both (open, high, low, close) and (time, open, high, low, close, volume)
        if len(candle) == 4:                      # (o, h, l, c)
            open_price, high, low, close = candle
            volume = None
        elif len(candle) == 6:                    # (t, o, h, l, c, v)
            _, open_price, high, low, close, volume = candle
        else:                                     # unexpected schema
            return None
        bar = {"open": open_price, "high": high, "low": low, "close": close, "volume": volume}
        result = self.handle_bar(bar)
        if isinstance(result, dict) and "side" in result:
            return result["side"].upper()  # "BUY" or "SELL"
        return None

    def handle_bar(self, bar: Dict[str, Any]):
        # Guard against incomplete bar data
        if not all(k in bar for k in ("high", "low", "close")):
            return None
        # Append new bar data
        try:
            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])
        except (TypeError, ValueError):
            # Skip this candle if price fields aren't numeric
            return None

        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)
        # Maintain maximum length
        max_len = max(self.window, self.atr_window) + 1
        if len(self.closes) > max_len:
            self.highs.pop(0)
            self.lows.pop(0)
            self.closes.pop(0)
        # Wait until we have enough data
        if len(self.closes) < max(self.window, self.atr_window) + 1:
            return None

        # Calculate Bollinger Bands
        recent_closes = self.closes[-self.window:]
        sma = sum(recent_closes) / self.window
        variance = sum((c - sma) ** 2 for c in recent_closes) / self.window
        std = variance ** 0.5
        upper = sma + 2 * std
        lower = sma - 2 * std
        band_width = upper - lower

        # Calculate ATR
        trs = []
        for i in range(-self.atr_window, 0):
            h = self.highs[i]
            l = self.lows[i]
            prev_close = self.closes[i - 1]
            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
            trs.append(tr)
        atr = sum(trs) / len(trs)

        # Detect squeeze start
        if not self.squeeze_on:
            if band_width <= self.width_pct * atr:
                self.squeeze_on = True
            return None

        # On expansion, trade first close outside bands
        close_price = self.closes[-1]
        if close_price > upper:
            self.squeeze_on = False
            return {"type": "market", "side": "buy", "price": close_price}
        if close_price < lower:
            self.squeeze_on = False
            return {"type": "market", "side": "sell", "price": close_price}

        return None