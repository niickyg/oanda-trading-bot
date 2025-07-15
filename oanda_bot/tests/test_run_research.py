import json
import pytest
from pathlib import Path
import research.run_research as rr


@pytest.fixture(autouse=True)
def isolate_cwd(tmp_path, monkeypatch):
    # Change working directory to tmp_path for tests
    monkeypatch.chdir(tmp_path)
    yield


def test_meta_bandit_branch(monkeypatch):
    # Prepare config with meta_bandit enabled
    config = {"meta_bandit": True, "rounds": 3}
    cfg_path = Path("live_config.json")
    cfg_path.write_text(json.dumps(config))

    # Stub out dependencies
    recorded = {}
    monkeypatch.setattr(
        rr,
        "run_meta_bandit",
        lambda strategies, candles, rounds: recorded.setdefault(
            "meta",
            (strategies, candles, rounds),
        ),
    )
    monkeypatch.setattr(
        rr,
        "get_enabled_strategies",
        lambda: ["strategyA", "strategyB"],
    )
    monkeypatch.setattr(
        rr,
        "get_candles",
        lambda inst, tf, n: ["CANDLE_DATA"],
    )

    # Execute
    rr.main()

    # Assert meta-bandit path was taken with correct parameters
    assert "meta" in recorded
    strategies, candles, rounds = recorded["meta"]
    assert strategies == ["strategyA", "strategyB"]
    assert candles == ["CANDLE_DATA"]
    assert rounds == 3


def test_grid_sweeper_fallback(monkeypatch):
    # Prepare config with meta_bandit disabled
    config = {"meta_bandit": False}
    cfg_path = Path("live_config.json")
    cfg_path.write_text(json.dumps(config))

    # Stub out dependencies
    calls = {}
    monkeypatch.setattr(
        rr,
        "run_optimizer",
        lambda inst: calls.setdefault("grid", inst),
    )
    monkeypatch.setattr(
        rr,
        "load_best_params",
        lambda inst: {"paramX": 1},
    )
    monkeypatch.setattr(
        rr,
        "evaluate_strategies",
        lambda inst, params: {"winner": inst},
    )
    monkeypatch.setattr(
        rr,
        "update_live_config",
        lambda winners: calls.setdefault("update", winners),
    )

    # Execute
    rr.main()

    # Assert grid-sweeper path was taken
    assert calls.get("grid") == "EUR_USD"
    assert calls.get("update") == {"winner": "EUR_USD"}
