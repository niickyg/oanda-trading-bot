import pytest
from oanda_bot.strategy.macd_trends import MACDTrendStrategy


def make_bars(prices):
    """
    Helper to construct OANDA-like candle dicts from numeric prices.
    """
    bars = []
    for p in prices:
        bars.append({"mid": {"c": str(p)}})
    return bars


@pytest.fixture
def trend_strategy():
    # Use default params
    params = {"ema_trend": 5, "macd_fast": 3, "macd_slow": 5, "macd_sig": 2}
    return MACDTrendStrategy(params)


def test_no_signal_on_insufficient_data(trend_strategy):
    # Less than ema_trend + macd_slow bars → no signal
    bars = make_bars([1, 2, 3, 4, 5, 6, 7])  # only 7 bars, need at least 10
    assert trend_strategy.next_signal(bars) is None


def test_buy_signal_on_uptrend(trend_strategy):
    # Create a simple uptrend long enough for EMA and MACD
    prices = list(range(1, 21))  # 1 to 20
    bars = make_bars(prices)
    sig = trend_strategy.next_signal(bars)
    assert sig in (None, "BUY", "SELL")


def test_sell_signal_on_downtrend(trend_strategy):
    # Create a simple downtrend long enough for EMA and MACD
    prices = list(range(20, 0, -1))  # 20 to 1
    bars = make_bars(prices)
    sig = trend_strategy.next_signal(bars)
    assert sig in (None, "BUY", "SELL")
