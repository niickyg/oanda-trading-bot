"""
oanda_bot package initializer.

This package provides the core functionality for the OANDA trading bot,
including backtesting, research routines, configuration management, and data access.
"""

__version__ = "0.1.0"

# Expose top-level modules and subpackages
from . import app
from . import backtest
from . import broker
from . import config_manager
from . import data
from .research import run_research
from . import strategy

__all__ = [
    "app",
    "backtest",
    "broker",
    "config_manager",
    "data",
    "run_research",
    "strategy",
]