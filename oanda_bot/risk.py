"""
Risk management utilities for OANDA trading.
"""


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
    # Determine pip value for the pair: 0.01 for JPY quote currency, otherwise 0.001
    pip_size = 0.01 if quote == "JPY" else 0.001
    risk_amount = balance * risk_pct
    if sl_pips <= 0:
        raise ValueError("Stop-loss pips must be positive")
    units = int(risk_amount / (sl_pips * pip_size))
    return max(units, 1)
