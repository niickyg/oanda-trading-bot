import sys
import os
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main

@pytest.fixture(autouse=True)
def reset_globals():
    # Reset globals before each test
    main.peak_equity = 0.0
    main.account_equity = 0.0
    main.strategy_instances = []
    yield

def test_handle_signal_triggers_meta_bandit(monkeypatch):
    # Stub dependencies
    recorded = {}
    monkeypatch.setattr(main, "get_enabled_strategies", lambda: ["s1", "s2"])
    monkeypatch.setattr(main, "get_candles", lambda pair, tf, n: ["CANDLE"])
    def fake_run_meta(strategies, candles, rounds):
        recorded["meta"] = (strategies, candles, rounds)
    monkeypatch.setattr(main, "run_meta_bandit", fake_run_meta)
    monkeypatch.setattr(main, "load_strategies", lambda: ["new"])
    # Set globals to simulate drawdown > threshold
    main.peak_equity = 1000.0
    main.account_equity = 900.0  # 10% drawdown triggers threshold
    main.strategy_instances = ["old"]
    # Invoke
    main.handle_signal("EUR_USD", price=1.0, signal="buy")
    # Verify bandit was triggered
    assert "meta" in recorded
    strategies, candles, rounds = recorded["meta"]
    assert strategies == ["s1", "s2"]
    assert candles == ["CANDLE"]
    assert rounds == main.BANDIT_ROUNDS
    # Verify strategy_instances updated
    assert main.strategy_instances == ["new"]

def test_handle_signal_no_trigger_below_threshold(monkeypatch):
    called = {}
    monkeypatch.setattr(main, "run_meta_bandit", lambda *args, **kwargs: called.setdefault("meta", True))
    # Set globals to simulate drawdown below threshold
    main.peak_equity = 1000.0
    main.account_equity = 980.0  # 2% drawdown < threshold
    main.strategy_instances = ["old"]
    # Invoke
    main.handle_signal("EUR_USD", price=1.0, signal="buy")
    # Verify bandit not triggered
    assert "meta" not in called
    # strategy_instances remains unchanged
    assert main.strategy_instances == ["old"]