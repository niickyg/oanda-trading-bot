import os
import math
import logging

from typing import Optional, List

from oandapyV20.endpoints.positions import (
    OpenPositions,
    PositionClose,
)
from oandapyV20.endpoints.orders import (
    OrderCreate,
)

from oanda_bot.data.core import api as API
from oanda_bot.data.core import OANDA_ACCOUNT_ID as ACCOUNT


# If running in CI (or ACCOUNT is missing), avoid real network calls and simulate responses.
_TEST_MODE = bool(os.getenv("CI")) or not ACCOUNT

logger = logging.getLogger(__name__)


def _pip_size(instrument: str) -> float:
    """Return pip size (0.0001 for most pairs, 0.01 for JPY pairs)."""
    # JPY pairs have 2 decimal places, others have 4
    if instrument.endswith("JPY"):
        return 0.01
    return 0.0001


def place_order(instrument: str, units: str, order_type: str = "MARKET", **kwargs):
    logger.info(
        "Placing order: instrument=%s, units=%s, type=%s, kwargs=%s",
        instrument, units, order_type, kwargs
    )
    """
    Place an order for the given instrument and units.
    Units should be a string: positive for buy, negative for sell.

    Optional kwargs:
      - price: str (for LIMIT orders)
      - stopLossOnFill: dict (stop loss order parameters)
      - takeProfitOnFill: dict (take profit order parameters)
    """
    if _TEST_MODE:
        logger.info("TEST_MODE: Simulating place_order for %s %s", instrument, units)
        return {"orderFillTransaction": {"orderID": "SIMULATED"}}
    order_data = {
        "order": {
            "instrument": instrument,
            "units": units,
            "type": order_type,
            "positionFill": "DEFAULT"
        }
    }
    # Include optional parameters if provided
    if "price" in kwargs:
        order_data["order"]["price"] = str(kwargs["price"])
    if "stopLossOnFill" in kwargs:
        order_data["order"]["stopLossOnFill"] = kwargs["stopLossOnFill"]
    if "takeProfitOnFill" in kwargs:
        order_data["order"]["takeProfitOnFill"] = kwargs["takeProfitOnFill"]
    req = OrderCreate(ACCOUNT, data=order_data)
    return API.request(req)


def place_risk_managed_order(
    instrument: str,
    side: str,
    price: float,
    stop_price: float,
    equity: float,
    risk_pct: float = 0.01,
    tp_price: Optional[float] = None,
):
    if _TEST_MODE:
        logger.info("TEST_MODE: Simulating risk‑managed order %s %s", instrument, side)
        return {"orderFillTransaction": {"orderID": "SIMULATED"}}
    """
    Compute position size so that (price - stop_price) risks ~risk_pct * equity.
    side: "BUY" or "SELL"
    """
    # Ensure stop_price is not equal to entry price: nudge by one pip if so
    pip = _pip_size(instrument)
    if stop_price == price:
        if side.upper() == "BUY":
            stop_price = price - pip
        else:
            stop_price = price + pip
    # Round stop_price and tp_price to instrument precision
    decimals = int(round(-math.log10(_pip_size(instrument))))
    stop_price = round(stop_price, decimals)
    if tp_price is not None:
        tp_price = round(tp_price, decimals)
    risk_dollar = equity * risk_pct
    per_unit_risk = abs(price - stop_price)
    units = int(risk_dollar / per_unit_risk)
    MAX_UNITS = 1_000
    if units > MAX_UNITS:
        units = MAX_UNITS

    logger.debug(
        "Risk-managed order for %s: side=%s, entry=%.5f, stop=%.5f, tp=%s, "
        " equity=%.2f, risk_pct=%.2f, units=%d",
        instrument,
        side,
        price,
        stop_price,
        tp_price,
        equity,
        risk_pct,
        units,
    )

    if side.upper() == "SELL":
        units = -units

    # Format SL and TP to instrument precision strings
    decimals = int(round(-math.log10(_pip_size(instrument))))
    sl_str = f"{stop_price:.{decimals}f}"
    order_kwargs = {"stopLossOnFill": {"price": sl_str}}
    if tp_price is not None:
        tp_str = f"{tp_price:.{decimals}f}"
        order_kwargs["takeProfitOnFill"] = {"price": tp_str}

    return place_order(
        instrument=instrument,
        units=str(units),
        **order_kwargs
    )


def close_all_positions(instruments: Optional[List[str]] = None):
    if _TEST_MODE:
        logger.info("TEST_MODE: Skipping close_all_positions in CI")
        return
    """
    Close all open positions for the given instruments.
    If instruments is None, close all positions.
    """
    req = OpenPositions(ACCOUNT)
    data = API.request(req)
    for pos in data.get("positions", []):
        if instruments is None or pos["instrument"] in instruments:
            logger.info("Closing all positions for instrument: %s", pos["instrument"])
            payload = {"longUnits": "ALL", "shortUnits": "ALL"}
            req2 = PositionClose(ACCOUNT, instrument=pos["instrument"], data=payload)
            API.request(req2)


def close_profitable_positions() -> dict[str, dict]:
    if _TEST_MODE:
        logger.info("TEST_MODE: Skipping close_profitable_positions in CI")
        return {}
    """
    Close only positions with positive unrealized P/L.
    Returns a dict mapping instrument to the API response.
    """
    req = OpenPositions(ACCOUNT)
    data = API.request(req)
    results: dict[str, dict] = {}

    for pos in data.get("positions", []):
        pl = float(pos.get("unrealizedPL", 0))
        instr = pos["instrument"]
        if pl > 0:
            logger.info(
                "Closing profitable position for %s with unrealized PL=%.2f", instr, pl
            )
            payload = {"longUnits": "ALL", "shortUnits": "ALL"}
            req2 = PositionClose(ACCOUNT, instrument=instr, data=payload)
            resp = API.request(req2)
            results[instr] = resp

    return results
