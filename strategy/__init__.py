"""
strategy package initializer.
Expose strategy plugins and legacy utilities.
"""

from .macd_trends import StrategyMACDTrend
from .rsi_reversion import StrategyRSIReversion

# Legacy utilities from the strategy utils module
from .utils import sl_tp_levels, update_strategy_performance

__all__ = [
    "StrategyMACDTrend",
    "StrategyRSIReversion",
    "sl_tp_levels",
    "update_strategy_performance",
]
