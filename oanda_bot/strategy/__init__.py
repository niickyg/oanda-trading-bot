"""
strategy package initializer.
Expose strategy plugins and legacy utilities.
"""

# Primary strategy functions
from .macd_trends import generate_signal, compute_atr, sl_tp_levels

# Strategy classes
from .macd_trends import MACDTrendStrategy
from .rsi_reversion import StrategyRSIReversion
from .tri_arb import StrategyTriArb

# Legacy utilities from the strategy utils module
from .utils import update_strategy_performance

__all__ = [
    "generate_signal",
    "compute_atr",
    "sl_tp_levels",
    "MACDTrendStrategy",
    "StrategyRSIReversion",
    "StrategyTriArb",
    "update_strategy_performance",
]
