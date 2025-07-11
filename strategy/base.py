"""
strategy/base.py
----------------

Common interface that every strategy plug‑in should implement.

Guidelines
~~~~~~~~~~
* Keep **zero external dependencies** beyond NumPy / standard library.
* Never place orders here – just emit `"BUY"`, `"SELL"`, or `None`.
* The engine will call:

    1. ``strategy.next_signal(recent_bars)`` – returns a signal.
    2. ``strategy.update_trade_result(win: bool, pnl: float)`` – optional
       feedback hook for adaptive strategies.

* All parameters must be passed via ``params`` dict so the optimiser or
  live config can tweak them without editing code.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Sequence, Optional, Any, Dict


class BaseStrategy(ABC):
    """
    Abstract parent class for all strategies.

    Sub‑classes must implement :py:meth:`next_signal`.
    The default :py:meth:`update_trade_result` does nothing, but can be
    overridden for adaptive logic.
    """

    #: Human‑readable name, overridden by subclasses
    name: str = "Base"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        self.params: Dict[str, Any] = params or {}
        self.cumulative_pnl: float = 0.0
        self.pull_count: int = 0

    # --------------------------------------------------------------------- #
    # Mandatory API
    # --------------------------------------------------------------------- #
    @abstractmethod
    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """
        Decide what to do on the next bar.

        Args
        ----
        bars : A *list* of OANDA candle dictionaries, oldest→newest.
               Length can vary – strategy should handle warm‑up.

        Returns
        -------
        "BUY", "SELL", or ``None``.
        """
        raise NotImplementedError

    # --------------------------------------------------------------------- #
    # Optional feedback hook
    # --------------------------------------------------------------------- #
    def update_trade_result(self, win: bool, pnl: float) -> None:  # noqa: D401
        """
        Called by the engine after a position closes.

        Default implementation does nothing. Override if the strategy
        adapts its parameters based on performance.

        Args
        ----
        win  : ``True`` if the trade hit TP, ``False`` if SL.
        pnl  : Profit or loss in account currency.
        """
        self.pull_count += 1
        self.cumulative_pnl += pnl

    # --------------------------------------------------------------------- #
    # Helper utilities (may be reused by subclasses)
    # --------------------------------------------------------------------- #
    @staticmethod
    def _pip_size(instrument: str) -> float:
        """0.01 for JPY pairs, else 0.0001."""
        return 0.01 if instrument.endswith("JPY") else 0.0001