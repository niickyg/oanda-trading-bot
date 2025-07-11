import math
import json
import pytest
from pathlib import Path
try:
    from backtest import Backtester
except ImportError:
    Backtester = None
import meta_optimize as mo

class DummyStrategy:
    def __init__(self, name):
        self.name = name
        self.params = {}
        self.pull_count = 0
        self.cumulative_pnl = 0.0

    def update_trade_result(self, win: bool, pnl: float) -> None:
        self.pull_count += 1
        self.cumulative_pnl += pnl

def test_select_strategy_ucb_prefers_unpulled():
    s1 = DummyStrategy("A")
    s2 = DummyStrategy("B")
    s1.pull_count = 0
    s2.pull_count = 1; s2.cumulative_pnl = 10.0
    chosen = mo.select_strategy_ucb([s1, s2], total_pulls=1)
    assert chosen is s1

def test_select_strategy_ucb_scores_correctly():
    s1 = DummyStrategy("A")
    s2 = DummyStrategy("B")
    # both have pulls, but B has higher average pnl
    s1.pull_count = 2; s1.cumulative_pnl = 2.0   # avg=1.0
    s2.pull_count = 2; s2.cumulative_pnl = 6.0   # avg=3.0
    # total_pulls doesn't affect order when bonus equal
    chosen = mo.select_strategy_ucb([s1, s2], total_pulls=4)
    assert chosen is s2

def test_run_main_writes_live_config(tmp_path, monkeypatch):
    # Monkeypatch strategies and backtester to produce known pnls
    s1 = DummyStrategy("A")
    s2 = DummyStrategy("B")
    monkeypatch.setattr(mo, "get_enabled_strategies", lambda: [s1, s2])
    class StubBT:
        def __init__(self, strat, data): pass
        def run(self):
            # return different pnl for each strategy
            return 5.0 if hasattr(self, 'strat') and self.strat.name == "A" else 3.0
    # ensure stub receives strat attribute
    def stub_init(self, strat, data):
        self.strat = strat
    monkeypatch.setattr(StubBT, "__init__", stub_init)
    monkeypatch.setattr(mo, "Backtester", StubBT)
    monkeypatch.setattr(mo, "load_calibration_data", lambda: [])
    monkeypatch.setattr(mo, "load_round_data", lambda idx: [])
    # Run main for 3 rounds
    import sys
    sys.argv = ["meta_optimize.py", "--rounds", "3"]
    # Change cwd to tmp_path
    monkeypatch.chdir(tmp_path)
    mo.main()
    # Verify live_config.json exists with winners
    cfg_file = tmp_path / "live_config.json"
    assert cfg_file.exists()
    cfg = json.loads(cfg_file.read_text())
    assert "winners" in cfg
    # Winner should be strategy A (higher total pnl)
    winners = cfg["winners"]
    assert isinstance(winners, list) and winners
    assert winners[0]["name"] == "A"