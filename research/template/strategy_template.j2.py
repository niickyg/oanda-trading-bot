'''
Jinja2 Strategy Plugin Template
--------------------------------

This template generates a new strategy plug-in. Fill in parameters and logic.

Usage:
  Render this template with Jinja2, passing `strategy_name` and parameter definitions.
'''
from __future__ import annotations
from typing import Sequence, Optional, Dict, Any
import numpy as np

from strategy.base import BaseStrategy


class Strategy{{ strategy_name }}(BaseStrategy):
    """
    {{ description }}

    Parameters (configurable via `live_config.json`):
    {% for p in params %}
    - `{{ p.name }}` (default: {{ p.default }}) — {{ p.doc }}
    {% endfor %}
    """
    name = "{{ strategy_name }}"

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(params or {})
        # Initialize any internal state here, e.g.:
        # self._hist = []

    def next_signal(self, bars: Sequence[dict]) -> Optional[str]:
        """
        Decide what to do on the next bar.
        Returns: "BUY", "SELL", or None.
        """
        if not bars:
            return None

        # Extract closes
        closes = np.array([float(c['mid']['c']) for c in bars], dtype=np.float64)

        # Example: EMA filter
        ema_period = self.params.get('ema_period', {{ default_ema }})
        if len(closes) < ema_period + 2:
            return None
        ema = np.mean(closes[-ema_period:])  # placeholder for actual EMA calculation

        # TODO: compute indicator, e.g., MACD or RSI

        # Example entry logic
        price = closes[-1]
        signal = None
        if price > ema:
            signal = 'BUY'
        elif price < ema:
            signal = 'SELL'

        return signal

    def update_trade_result(self, win: bool, pnl: float) -> None:
        """
        Optional performance feedback hook. Called after each trade closes.
        """
        # Example: record history
        # self._hist.append((win, pnl))
        pass
