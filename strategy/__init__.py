"""
strategy package initializer.
Expose strategy plugins and legacy utilities.
"""

from .macd_trends import MACDTrendStrategy
from .rsi_reversion import StrategyRSIReversion
from .tri_arb import StrategyTriArb

# Legacy utilities from the strategy utils module
from .utils import sl_tp_levels, update_strategy_performance

__all__ = [
    "MACDTrendStrategy",
    "StrategyRSIReversion",
    "sl_tp_levels",
    "update_strategy_performance",
    "StrategyTriArb",
]
