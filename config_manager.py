"""
config_manager.py

Handle loading, validation, and hot-reloading of live_config.json.
"""

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict
import logging
logger = logging.getLogger(__name__)

CONFIG_PATH = Path("live_config.json")


class ConfigManager:
    """
    Watches the live_config.json for changes, validates it, and notifies
    subscribers on update.
    """

    def __init__(
        self,
        on_update: Callable[[Dict[str, Any]], None],
        poll_interval: float = 1.0,
    ):
        self._on_update = on_update
        self._poll_interval = poll_interval
        self._last_mtime = None
        self._last_cfg = None
        self._running = False
        self._thread = None

    def _load(self) -> Dict[str, Any]:
        with CONFIG_PATH.open("r") as f:
            return json.load(f)

    def _watch_loop(self):
        while self._running:
            try:
                mtime = CONFIG_PATH.stat().st_mtime
            except FileNotFoundError:
                mtime = None

            if mtime != self._last_mtime:
                try:
                    cfg = self._load()
                    # Only notify on actual content change
                    if cfg != self._last_cfg:
                        self._on_update(cfg)
                        logger.info("Config reloaded from %s", CONFIG_PATH)
                        self._last_cfg = cfg
                    self._last_mtime = mtime
                except Exception:
                    logger.error("Error loading config", exc_info=True)
            time.sleep(self._poll_interval)

    def start(self):
        """Start watching the config file for changes."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop watching the config file."""
        self._running = False
        if self._thread:
            self._thread.join()