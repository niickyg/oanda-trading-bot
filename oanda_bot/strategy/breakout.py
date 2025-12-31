def _candle_to_bar(candle):
    """
    Convert various candle representations to a uniform bar dict with 'open', 'high', 'low', 'close', 'time'.
    """
    try:
        if isinstance(candle, dict):
            return {
                "time": candle.get("time") or candle.get("timestamp"),
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
            }
        # Handle tuple or list formats like (time, o, h, l, c)
        if isinstance(candle, (list, tuple)) and len(candle) >= 5:
            t, o, h, l, c = candle[:5]
            return {"time": t, "open": float(o), "high": float(h), "low": float(l), "close": float(c)}
        # Handle objects with attributes
        return {
            "time": getattr(candle, "time", None) or getattr(candle, "timestamp", None),
            "open": float(getattr(candle, "open", None)),
            "high": float(getattr(candle, "high", None)),
            "low": float(getattr(candle, "low", None)),
            "close": float(getattr(candle, "close", None)),
        }
    except Exception:
        # Returning None indicates conversion failure
        return None

# In the StrategyTriArb class, inside the next_signal method:

    converted_bars = [b for b in (_candle_to_bar(b) for b in bars) if b]
    if not converted_bars:
        return None
    latest_bar = converted_bars[-1]