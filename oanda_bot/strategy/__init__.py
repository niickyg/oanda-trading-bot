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
from .momentum_scalp import StrategyMomentumScalp
from .order_flow import StrategyOrderFlow
from .micro_reversion import StrategyMicroReversion
from .zscore_reversion import StrategyZScoreReversion
from .volatility_regime import StrategyVolatilityRegime
from .stat_arb import StrategyStatArb
from .trend_ma import StrategyTrendMA

# Legacy utilities from the strategy utils module
from .utils import update_strategy_performance

__all__ = [
    "generate_signal",
    "compute_atr",
    "sl_tp_levels",
    "MACDTrendStrategy",
    "StrategyRSIReversion",
    "StrategyTriArb",
    "StrategyMomentumScalp",
    "StrategyOrderFlow",
    "StrategyMicroReversion",
    "StrategyZScoreReversion",
    "StrategyVolatilityRegime",
    "StrategyStatArb",
    "StrategyTrendMA",
    "update_strategy_performance",
]
