"""
strategy/tri_arb.py

Stub triangular arbitrage strategy for backtesting.
"""
from typing import Sequence, Optional
from strategy.base import BaseStrategy

class StrategyTriArb(BaseStrategy):
    """
    Minimal triangular arbitrage strategy stub: always holds,
    ensures module import and class discovery succeed in CI.
    """
    name = "TriArb"

    def __init__(self, **params):
        super().__init__(**params)

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        # No arbitrage logic yet; always return None (hold)
        return None
