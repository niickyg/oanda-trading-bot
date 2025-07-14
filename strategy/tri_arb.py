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

    def __init__(self, config):
        # Store the provided configuration
        self.config = config
        # Initialize the base strategy with unpacked config
        super().__init__(**config)

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        # No arbitrage logic yet; always return None (hold)
        return None
