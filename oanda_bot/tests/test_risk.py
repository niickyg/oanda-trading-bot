

"""Unit tests for oanda_bot.risk.calc_units."""

import pytest

from oanda_bot.risk import calc_units


def test_calc_units_eurusd():
    """1 % risk on EUR/USD with 50‑pip SL should size to 2 000 units."""
    units = calc_units(balance=10_000, pair="EUR_USD", sl_pips=50, risk_pct=0.01)
    assert units == 2_000


def test_calc_units_usdjpy():
    """1 % risk on USD/JPY with 50‑pip SL should size to 200 units."""
    units = calc_units(balance=10_000, pair="USD_JPY", sl_pips=50, risk_pct=0.01)
    assert units == 200


def test_calc_units_raises_on_zero_sl():
    """A zero stop‑loss distance must raise ValueError."""
    with pytest.raises(ValueError):
        calc_units(balance=10_000, pair="EUR_USD", sl_pips=0, risk_pct=0.01)
        