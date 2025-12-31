from .base import BaseStrategy
from typing import Dict, Any, List


# Helper: tolerant candle-to-bar normalizer
def _candle_to_bar(candle, instrument=None):
    """
    Normalise various candle shapes into a standard bar dict.

    Accepts:
        • 4‑field tuple  -> (open, high, low, close)
        • 5‑field tuple  -> (time, open, high, low, close)
        • 6‑field tuple  -> (time, open, high, low, close, volume)
        • pre‑built dict -> returned as‑is

    Missing fields are filled with sensible defaults (empty string for time,
    0 for volume). The `instrument` key is injected when supplied and absent.
    """
    # Already a dict ─ just make sure required keys exist
    if isinstance(candle, dict):
        bar = dict(candle)
        if instrument and "instrument" not in bar:
            bar["instrument"] = instrument
        bar.setdefault("volume", 0)
        return bar

    # Tuple / list handling
    if len(candle) == 6:
        time_str, open_p, high, low, close, volume = candle
    elif len(candle) == 5:
        time_str, open_p, high, low, close = candle
        volume = 0
    elif len(candle) == 4:
        open_p, high, low, close = candle
        time_str = ""
        volume = 0
    else:
        raise ValueError(f"Unsupported candle length: {len(candle)} — {candle}")

    return {
        "time": time_str,
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "instrument": instrument,
    }

class StrategyVolatilityGrid(BaseStrategy):
    """
    Grid scalping in low-volatility ranges.
    Place staggered limit buys/sells every N pips; close when price retraces grid size.
    Respect a risk cap on simultaneous grid levels.
    """
    # Strategy identifier
    name = "VolatilityGrid"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Instrument this strategy trades (may be None if not provided)
        self.instrument = config.get("instrument")
        # Grid spacing (in price units, e.g. pips)
        self.grid_size = float(config.get("grid_size", 0.0005))
        # Number of levels above/below current price
        self.levels = int(config.get("levels", 3))
        # Maximum simultaneous grid orders
        self.risk_cap = int(config.get("risk_cap", 4))
        # Track placed entry levels: price -> side
        self.active_entries: Dict[float, str] = {}
        # Track which entries have been closed
        self.closed_entries: set = set()

    def next_signal(self, candles):
        """
        Wrap handle_bar logic so the main loop can use this strategy.
        Returns "BUY", "SELL", or None.
        """
        if not candles:
            return None

        # Convert the latest candle (whatever its shape) into a bar dict
        bar = _candle_to_bar(candles[-1], instrument=self.instrument)

        result = self.handle_bar(bar)
        if isinstance(result, list) and result:
            return result[0].get("side", "").upper()
        return None

    def handle_bar(self, bar: Dict[str, Any]) -> List[Dict[str, Any]] or None:
        """
        Place grid orders once, then close when price retraces grid_size.
        bar: {time, open, high, low, close, instrument} or OANDA candle dict
        """
        # Handle both flat dict and OANDA nested dict formats
        if "close" in bar:
            price = float(bar["close"])
        elif "mid" in bar and isinstance(bar["mid"], dict):
            price = float(bar["mid"].get("c") or bar["mid"].get("close", 0))
        else:
            # Try to extract from various formats
            price = float(bar.get("c") or bar.get("close") or 0)

        if price == 0:
            return None
        signals: List[Dict[str, Any]] = []

        # Initial grid placement
        if not self.active_entries:
            # Place buys below price
            for i in range(1, self.levels + 1):
                if len(self.active_entries) >= self.risk_cap:
                    break
                entry_price = price - i * self.grid_size
                self.active_entries[entry_price] = "buy"
                signals.append({
                    "type": "limit",
                    "side": "buy",
                    "price": entry_price
                })
            # Place sells above price
            for i in range(1, self.levels + 1):
                if len(self.active_entries) >= self.risk_cap:
                    break
                entry_price = price + i * self.grid_size
                self.active_entries[entry_price] = "sell"
                signals.append({
                    "type": "limit",
                    "side": "sell",
                    "price": entry_price
                })
            return signals

        # Manage closings: when retraced by grid_size
        for entry_price, side in list(self.active_entries.items()):
            if entry_price in self.closed_entries:
                continue
            # For buys, close when price moves up by grid_size
            if side == "buy" and price >= entry_price + self.grid_size:
                signals.append({
                    "type": "market",
                    "side": "sell",
                    "price": price
                })
                self.closed_entries.add(entry_price)
            # For sells, close when price moves down by grid_size
            if side == "sell" and price <= entry_price - self.grid_size:
                signals.append({
                    "type": "market",
                    "side": "buy",
                    "price": price
                })
                self.closed_entries.add(entry_price)

        # Clean up closed entries and reset for next grid cycle
        if signals:
            for entry_price in list(self.closed_entries):
                self.active_entries.pop(entry_price, None)
            self.closed_entries.clear()

        return signals or None