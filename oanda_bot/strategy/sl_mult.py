

import pandas as pd
from oanda_bot.common.indicators import ATR


def generate_signals(data: pd.DataFrame,
                     stop_loss_multiplier: float = 1.5,
                     atr_window: int = 14) -> pd.Series:
    """
    Compute stop-loss levels based on ATR multiplier.
    Returns a Series of stop-loss prices.
    """
    # Make a copy to avoid mutating original DataFrame
    df = data.copy()
    # Calculate ATR
    df['atr'] = ATR(df['high'], df['low'], df['close'], window=atr_window)
    # Stop-loss price = close price minus multiplier * ATR
    stop_loss = df['close'] - stop_loss_multiplier * df['atr']
    return stop_loss


# Parameter grid for research tuning

param_grid = {
    'stop_loss_multiplier': [1.0, 1.5, 2.0, 2.5],
    'atr_window': [10, 14, 20]
}


# Strategy class wrapper
class Strategysl_mult:
    """
    Stop-loss multiplier strategy: wraps generate_signals and exposes param_grid.
    """
    name = "sl_mult"

    def __init__(self, stop_loss_multiplier: float = 1.5, atr_window: int = 14):
        self.stop_loss_multiplier = stop_loss_multiplier
        self.atr_window = atr_window

    @staticmethod
    def generate_signals(
        data: pd.DataFrame,
        stop_loss_multiplier: float = 1.5,
        atr_window: int = 14
    ) -> pd.Series:
        return generate_signals(data, stop_loss_multiplier, atr_window)

    param_grid = param_grid
