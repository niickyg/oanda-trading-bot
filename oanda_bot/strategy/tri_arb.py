"""
strategy/tri_arb.py

Stub triangular arbitrage strategy for backtesting.
"""
from typing import Sequence, Any, Dict, Optional

def _candle_to_bar(candle):
    """
    Normalize a candle into a dict with keys:
    time, open, high, low, close, volume.

    Accepts any of:
    • dict (already normalized)
    • 6-field tuple: (time, open, high, low, close, volume)
    • 5-field tuple: (time, open, high, low, close)
    • 4-field tuple: (open, high, low, close)

    Returns a dict and leaves missing fields as None.
    """
    try:
        # Handle string markers
        if isinstance(candle, str):
            return None

        # Dict formats
        if isinstance(candle, dict):
            # Prioritize standard keys
            if {"open", "high", "low", "close"}.issubset(candle.keys()):
                return {
                    "time": candle.get("time") or candle.get("timestamp"),
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"]),
                    "volume": candle.get("volume")
                }
            # OANDA short keys
            if {"o", "h", "l", "c"}.issubset(candle.keys()):
                return {
                    "time": candle.get("time") or candle.get("timestamp"),
                    "open": float(candle["o"]),
                    "high": float(candle["h"]),
                    "low": float(candle["l"]),
                    "close": float(candle["c"]),
                    "volume": candle.get("volume") or candle.get("tradeCount")
                }
            # Nested legs
            for leg in ("mid", "bid", "ask"):
                leg_dict = candle.get(leg)
                if isinstance(leg_dict, dict) and {"o", "h", "l", "c"}.issubset(leg_dict.keys()):
                    return {
                        "time": candle.get("time") or candle.get("timestamp"),
                        "open": float(leg_dict["o"]),
                        "high": float(leg_dict["h"]),
                        "low": float(leg_dict["l"]),
                        "close": float(leg_dict["c"]),
                        "volume": candle.get("volume") or candle.get("tradeCount")
                    }
            # Fallback dict
            return None

        # Tuple or list formats
        if isinstance(candle, (list, tuple)):
            length = len(candle)
            if length == 6:
                t, o, h, l, c, v = candle
            elif length == 5:
                t, o, h, l, c = candle
                v = None
            elif length == 4:
                o, h, l, c = candle
                t = v = None
            else:
                return None
            return {"time": t, "open": float(o), "high": float(h), "low": float(l), "close": float(c), "volume": v}

        # Objects with attributes
        if hasattr(candle, "__dict__") or hasattr(candle, "time"):
            return {
                "time": getattr(candle, "time", None) or getattr(candle, "timestamp", None),
                "open": float(getattr(candle, "open", None)),
                "high": float(getattr(candle, "high", None)),
                "low": float(getattr(candle, "low", None)),
                "close": float(getattr(candle, "close", None)),
                "volume": getattr(candle, "volume", None)
            }

        # Unsupported type
        return None
    except Exception:
        return None

from .base import BaseStrategy


class StrategyTriArb(BaseStrategy):
    """
    Minimal triangular arbitrage strategy stub: always holds,
    ensures module import and class discovery succeed in CI.
    """

    name = "TriArb"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Store provided configuration (may be empty)
        self.config = config or {}
        super().__init__(**self.config)

    def next_signal(self, bars: Sequence[Any]) -> Optional[str]:
        if not bars:
            return None

        converted_bars = [bar for bar in (_candle_to_bar(b) for b in bars) if bar]
        if not converted_bars:
            return None

        latest_bar = converted_bars[-1]
        # Placeholder – real arbitrage logic would go here
        return None
