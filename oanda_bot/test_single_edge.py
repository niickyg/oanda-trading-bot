#!/usr/bin/env python3
"""
test_single_edge.py

Quick test of a single edge strategy to validate implementation.
"""

import json
import logging
from oanda_bot.data.core import get_candles
from oanda_bot.backtest import run_backtest
from oanda_bot.strategy.macd_histogram import StrategyMACDHistogram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test MACD Histogram strategy on EUR_USD H1
params = {
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_sig": 9,
    "ema_trend": 50,
    "hist_threshold": 0.0001,
    "sl_mult": 1.2,
    "tp_mult": 2.0,
    "max_duration": 30,
}

logger.info("Fetching EUR_USD H1 candles...")
candles = get_candles("EUR_USD", "H1", 1000)
logger.info(f"Fetched {len(candles)} candles")

logger.info("Creating strategy...")
strategy = StrategyMACDHistogram(params)

logger.info("Running backtest...")
stats = run_backtest(strategy, candles, warmup=60)

logger.info("Results:")
print(json.dumps(stats, indent=2))
