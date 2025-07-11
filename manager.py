"""
manager.py

Hot-reloads strategy modules based on `live_config.json` and provides
a unified interface for the trading engine to retrieve live signals.
"""

__all__ = ["load_config", "load_strategies", "watch_strategies"]

import json
import time
import importlib
import os
from typing import List, Iterator

from strategy.base import BaseStrategy

CONFIG_FILE = "live_config.json"
POLL_INTERVAL = 60  # seconds to check for config changes


def load_config() -> dict:
    """Load the live configuration for enabled strategies and parameters."""
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def load_strategies() -> List[BaseStrategy]:
    """
    Instantiate strategy classes listed under 'enabled' in the config,
    passing their respective params dict to each.
    """
    cfg = load_config()
    strategies = []
    for name in cfg.get("enabled", []):
        params = cfg.get(name, {})
        # Normalize module filename
        raw = name.lower()
        if raw == "macdtrend":
            raw = "macd_trends"
        elif raw == "rsireversion":
            raw = "rsi_reversion"
        module_name = f"strategy.{raw}"
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, f"Strategy{name}")
            strat = cls(params)
            strategies.append(strat)
        except Exception as e:
            print(f"[manager] Error loading strategy {name}: {e}")
    return strategies


def watch_strategies() -> Iterator[List[BaseStrategy]]:
    """
    Periodically reload strategies when the config file changes.

    Yields
    ------
    List[BaseStrategy]
        The currently enabled strategy instances.
    """
    last_cfg_time = None
    strategies = []
    while True:
        try:
            mtime = os.path.getmtime(CONFIG_FILE)
        except Exception:
            mtime = None

        if mtime != last_cfg_time:
            strategies = load_strategies()
            print(f"[manager] Loaded strategies: {[s.name for s in strategies]}")
            last_cfg_time = mtime

        time.sleep(POLL_INTERVAL)
        yield strategies


if __name__ == "__main__":
    # Simple CLI test
    print("Manager starting; watching for changes in", CONFIG_FILE)
    for current_strats in watch_strategies():
        pass