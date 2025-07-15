"""
strategy/tri_arb.py

Stub triangular arbitrage strategy for backtesting.
"""
from typing import Sequence, Any
from strategy.base import BaseStrategy


class StrategyTriArb(BaseStrategy):
    """
    Minimal triangular arbitrage strategy stub: always holds,
    ensures module import and class discovery succeed in CI.
    """

    name = "TriArb"

    def __init__(self, config: dict[str, Any] | None = None):
        # Store provided configuration (may be empty)
        self.config = config or {}
        super().__init__(**self.config)

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        # No arbitrage logic yet; always return None (hold)
        return None
