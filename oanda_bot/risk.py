def calc_units(balance: float, pair: str, sl_pips: float, risk_pct: float) -> int:
    """
    Calculate number of units to trade based on account balance, currency pair notation,
    stop loss in pips, and risk percentage of the account equity.
    """
    # Determine pip value for the pair: 0.01 for JPY quote currency, otherwise 0.0001
    try:
        _, quote = pair.split("_")
    except ValueError:
        raise ValueError("Pair must be in the format 'XXX_YYY'")
    pip_size = 0.01 if quote == "JPY" else 0.0001
    risk_amount = balance * risk_pct
    if sl_pips <= 0:
        raise ValueError("Stop-loss pips must be positive")
    units = int(risk_amount / (sl_pips * pip_size))
    return max(units, 1)


import pytest
from oanda_bot.risk import calc_units

@pytest.mark.parametrize("balance,pair,sl_pips,risk_pct,expected", [
    (10000, "EUR_USD", 50, 0.01, int(10000 * 0.01 / (50 * 0.0001))),
    (5000, "USD_JPY", 20, 0.02, int(5000 * 0.02 / (20 * 0.01))),
    (1000, "GBP_USD", 100, 0.05, int(1000 * 0.05 / (100 * 0.0001))),
    (1000, "AUD_JPY", 25, 0.01, int(1000 * 0.01 / (25 * 0.01))),
    # Risk amount too small yields at least 1 unit
    (100, "EUR_USD", 1000, 0.001, 1),
])
def test_calc_units(balance, pair, sl_pips, risk_pct, expected):
    assert calc_units(balance, pair, sl_pips, risk_pct) == expected

def test_calc_units_invalid_pair():
    with pytest.raises(ValueError):
        calc_units(1000, "EURUSD", 50, 0.01)

def test_calc_units_invalid_sl_pips():
    with pytest.raises(ValueError):
        calc_units(1000, "EUR_USD", 0, 0.01)
