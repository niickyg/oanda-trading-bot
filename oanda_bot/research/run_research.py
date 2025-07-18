import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

from oanda_bot.backtest import run_backtest
from oanda_bot.data import get_candles
from oanda_bot.meta_optimize import run_meta_bandit

try:
    from oanda_bot.strategy.plugins import get_enabled_strategies
except ImportError:
    def get_enabled_strategies():
        """Stub if strategy.plugins missing."""
        return []

STRATEGY_NAME = "MACDTrend"
DEFAULT_INSTRUMENTS = os.getenv("RESEARCH_INSTRUMENTS", "EUR_USD").split(",")
PROMOTE_MIN_TRADES = int(os.getenv("PROMOTE_MIN_TRADES", "10"))
PROMOTE_MIN_WIN = float(os.getenv("PROMOTE_MIN_WIN", "0.5"))  # proportion, e.g. 0.55 = 55 %
PROMOTE_MIN_EXPECT = float(os.getenv("PROMOTE_MIN_EXPECT", "0.0"))

def best_params_path(inst: str) -> Path:
    return Path(f"best_params_{inst}.json")

LIVE_CONFIG = Path("live_config.json")

def run_optimizer(instrument: str):
    """Invoke optimize module to generate best_params_{instrument}.json."""
    cmd = [sys.executable, "-m", "oanda_bot.optimize", "--instrument", instrument]
    print(f"Running optimizer via module: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def load_best_params(inst: str):
    """Load the output of optimize.py."""
    path = best_params_path(inst)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run optimizer first")
    with open(path, "r") as f:
        return json.load(f)


def evaluate_strategies(instrument: str, best_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Back-test each strategy in best_params, filter by performance thresholds,
    and return a new params dict containing only the winners.
    """
    granularity = "H1"
    count = 2000

    print("\nEvaluating best strategies on", instrument, granularity)
    candles = get_candles(instrument, granularity, count)

    results = []
    for name, params in best_params.items():
        if name == "enabled":
            continue
        # Dynamically load strategy class
        raw = name.lower()
        if raw == "macdtrend":
            module_name = "oanda_bot.strategy.macd_trends"
        elif raw == "rsireversion":
            module_name = "oanda_bot.strategy.rsi_reversion"
        else:
            module_name = f"oanda_bot.strategy.{raw}"
        module = importlib.import_module(module_name)
        cls = getattr(module, f"Strategy{name}")
        strat = cls(params)

        # Determine warmup
        warmup = params.get("ema_trend", params.get("rsi_len", 0)) + params.get("macd_slow", 0)
        stats = run_backtest(strat, candles, warmup=warmup)
        trades, win_rate, expectancy = stats["trades"], stats["win_rate"], stats["expectancy"]
        results.append({
            "name": name,
            "trades": trades,
            "win_rate": win_rate,
            "expectancy": expectancy,
        })
        print(f"{name}: trades={trades}, win_rate={win_rate:.2%}, expectancy={expectancy:.6f}")

    # Filter winners based on configurable thresholds
    winners = [
        r["name"]
        for r in results
        if (
            r["trades"] >= PROMOTE_MIN_TRADES
            and r["win_rate"] >= PROMOTE_MIN_WIN
            and r["expectancy"] >= PROMOTE_MIN_EXPECT
        )
    ]
    print(f"\nPromoting winners: {winners}")

    # Build new params dict
    new_params: Dict[str, Any] = {"enabled": winners}
    for name in winners:
        new_params[name] = best_params[name]
    return new_params

def update_live_config(best_params: dict):
    """
    Write live_config.json based on best_params.json structure.
    If best_params.json contains an "enabled" key, use it directly;
    otherwise, treat each top-level key as a strategy name.
    """
    if "enabled" in best_params:
        config = best_params
    else:
        strategies = list(best_params.keys())
        config = {"enabled": strategies}
        for name, params in best_params.items():
            config[name] = params
    with open(LIVE_CONFIG, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Wrote {LIVE_CONFIG} with strategies: {config['enabled']}")

def main():
    # Load live_config.json to check for meta-bandit flag
    config = {}
    if LIVE_CONFIG.exists():
        with open(LIVE_CONFIG, "r") as f:
            config = json.load(f)
    use_meta = config.get("meta_bandit", False)
    rounds = config.get("rounds", 100)
    instruments = [s.strip().upper() for s in DEFAULT_INSTRUMENTS if s.strip()]
    single = len(instruments) == 1
    aggregated: Dict[str, Any] = {"enabled": []}
    for inst in instruments:
        if use_meta:
            # Meta-bandit optimization
            enabled_strategy_list = get_enabled_strategies()
            historical_candles = get_candles(inst, "H1", 2000)
            run_meta_bandit(
                strategies=enabled_strategy_list,
                candles=historical_candles,
                rounds=rounds,
            )
            if single:
                update_live_config({"enabled": enabled_strategy_list})
                return
        else:
            # Grid-sweeper fallback
            run_optimizer(inst)
            raw_params = load_best_params(inst)
            best_params = {STRATEGY_NAME: raw_params}
            winners_params = evaluate_strategies(inst, best_params)
            if single:
                update_live_config(winners_params)
                return
            # Merge results into aggregated mapping
            enabled_list = winners_params.get("enabled", [])
            aggregated["enabled"].extend([s for s in enabled_list if s not in aggregated["enabled"]])
            for strat_name in enabled_list:
                inst_map = aggregated.setdefault(strat_name, {})
                inst_map[inst] = winners_params[strat_name]

    if not single:
        update_live_config(aggregated)

# --------------------------------------------------------------------------- #
# Credential helpers
# --------------------------------------------------------------------------- #
def _require_env(var: str) -> str:
    """
    Ensure that a mandatory environment variable is present and not a
    placeholder like 'YOUR_TOKEN_HERE'.  Exit with code 1 if the check fails.
    """
    val = os.getenv(var, "").strip()
    if not val or val.upper().startswith("YOUR_") or val == "":  # crude placeholder detection
        print(
            f"Error: environment variable '{var}' is not set or looks like a placeholder. "
            "Aborting research run.",
            file=sys.stderr,
        )
        sys.exit(1)
    return val

if __name__ == "__main__":
    _require_env("OANDA_TOKEN")
    _require_env("OANDA_ACCOUNT_ID")
    main()
# This script runs the nightly research pipeline, optimizing strategy parameters
