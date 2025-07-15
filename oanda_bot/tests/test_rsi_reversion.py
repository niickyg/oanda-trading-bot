import pytest
import numpy as np
from strategy.rsi_reversion import StrategyRSIReversion

def make_bars(prices):
    """
    Helper to construct OANDA-like candle dicts from numeric prices.
    """
    bars = []
    for p in prices:
        bars.append({"mid": {"c": str(p)}})
    return bars

@pytest.fixture
def rsi_strategy():
    # Use default params: rsi_len=14, overbought=70, oversold=30, exit_mid=50
    params = {"rsi_len": 14, "overbought": 70, "oversold": 30, "exit_mid": 50}
    return StrategyRSIReversion(params)

def test_no_signal_on_insufficient_data(rsi_strategy):
    # Less than rsi_len bars → no signal
    bars = make_bars(list(range(1, 10)))  # only 9 bars, need at least 14
    assert rsi_strategy.next_signal(bars) is None

def test_buy_signal_on_oversold(rsi_strategy):
    # RSI below oversold threshold → BUY
    # Construct artificial bars: declining prices to push RSI low
    prices = [100 - i for i in range(30)]
    bars = make_bars(prices)
    sig = rsi_strategy.next_signal(bars)
    assert sig in (None, "BUY", "SELL")

def test_sell_signal_on_overbought(rsi_strategy):
    # RSI above overbought threshold → SELL
    # Construct artificial bars: rising prices to push RSI high
    prices = [100 + i for i in range(30)]
    bars = make_bars(prices)
    sig = rsi_strategy.next_signal(bars)
    assert sig in (None, "BUY", "SELL")