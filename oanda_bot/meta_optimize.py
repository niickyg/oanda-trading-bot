import argparse
import json

def _extract_pnl(bt_result):
    """
    Robustly pull a PnL number out of whatever Backtester.run() returns.

    The historical API has changed over time:
      * New style: returns a dict with a 'pnl' (or 'total_pnl') key.
      * Mid‑style: returns a tuple, where the first element is that dict.
      * Legacy: returns the raw numeric PnL directly.

    Args:
        bt_result: Any object returned by Backtester.run()

    Returns:
        float: a best‑effort PnL value (defaults to 0.0 when unavailable)
    """
    # Numeric return
    if isinstance(bt_result, (int, float)):
        return float(bt_result)

    # Dict return
    if isinstance(bt_result, dict):
        return float(bt_result.get("pnl", bt_result.get("total_pnl", 0.0)))

    # Tuple where first element is a dict
    if isinstance(bt_result, tuple) and bt_result:
        first = bt_result[0]
        if isinstance(first, dict):
            return float(first.get("pnl", first.get("total_pnl", 0.0)))

    # Fallback
    return 0.0

# Safely import get_enabled_strategies for tests
try:
    from strategy import get_enabled_strategies
except ImportError:
    def get_enabled_strategies():
        return []

# Safely import Backtester for tests
try:
    from backtest import Backtester
except ImportError:
    Backtester = None


def load_calibration_data():
    """
    Load or generate a small calibration dataset.
    Returns:
        List of market data points.
    """
    # TODO: replace with real data loading logic
    return []


def load_round_data(round_index):
    """
    Load or generate data for a specific optimization round.
    Args:
        round_index (int): index of the current round.
    Returns:
        List of market data points.
    """
    # TODO: replace with real data loading logic
    return []


def select_strategy_ucb(strategies, total_pulls):
    """
    Select a strategy using UCB1 algorithm.
    Args:
        strategies (List[BaseStrategy]): list of strategy instances
        total_pulls (int): total number of pulls so far
    Returns:
        BaseStrategy: chosen strategy instance
    """
    import math
    best = None
    best_score = float('-inf')
    for strat in strategies:
        if strat.pull_count == 0:
            return strat
        average = strat.cumulative_pnl / strat.pull_count
        bonus = math.sqrt(2 * math.log(total_pulls) / strat.pull_count)
        score = average + bonus
        if score > best_score:
            best_score = score
            best = strat
    return best


def main():
    parser = argparse.ArgumentParser(
        description="Meta-optimizer: multi-armed bandit over strategies"
    )
    parser.add_argument(
        "-N", "--rounds", type=int, default=100,
        help="Number of optimization rounds"
    )
    args = parser.parse_args()

    # 1. Import and initialize one arm per enabled strategy
    strategies = get_enabled_strategies()

    # 2. Calibration: run each strategy once on small dataset
    calibration_data = load_calibration_data()
    for strat in strategies:
        bt = Backtester(strat, calibration_data)
        pnl = _extract_pnl(bt.run())
        # update strategy stats via BaseStrategy.update_trade_result
        strat.update_trade_result(win=(pnl > 0), pnl=pnl)

    total_pulls = sum(strat.pull_count for strat in strategies)

    # 3. Main optimization loop
    for i in range(args.rounds):
        chosen = select_strategy_ucb(strategies, total_pulls)
        data = load_round_data(i)
        bt = Backtester(chosen, data)
        pnl = _extract_pnl(bt.run())
        chosen.update_trade_result(win=(pnl > 0), pnl=pnl)
        total_pulls += 1

    # 4. Report cumulative results
    print("Strategy performance:")
    for strat in strategies:
        print(f"{strat.name}: pulls={strat.pull_count}, pnl={strat.cumulative_pnl:.2f}")

    # Write winning strategy(s) to live_config.json
    max_pnl = max(strat.cumulative_pnl for strat in strategies)
    winners = [
        {"name": strat.name, "params": strat.params}
        for strat in strategies if strat.cumulative_pnl == max_pnl
    ]
    with open("live_config.json", "w") as f:
        json.dump({"winners": winners}, f, indent=4)
    print("Wrote winning strategy configuration to live_config.json")


if __name__ == "__main__":
    main()

# Expose run_meta_bandit for external imports
run_meta_bandit = main
