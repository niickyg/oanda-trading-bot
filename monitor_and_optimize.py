#!/usr/bin/env python3
"""
Continuous monitoring and optimization system for OANDA bot.
Analyzes performance metrics and triggers optimizations when needed.
"""

import time
import json
import csv
import os
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# Paths
TRADES_LOG = Path("/home/user0/oandabot16/oanda_bot/trades_log.csv")
CONFIG_FILE = Path("/home/user0/oandabot16/oanda_bot/live_config.json")
PERFORMANCE_LOG = Path("/app/performance_log.json")

# Monitoring intervals
CHECK_INTERVAL = 300  # Check every 5 minutes
OPTIMIZATION_INTERVAL = 3600  # Full optimization every hour
PERFORMANCE_WINDOW = 50  # Analyze last 50 trades

# Performance thresholds (trigger optimization if breached)
MIN_WIN_RATE = 0.45
MAX_DRAWDOWN_CONSECUTIVE = 5
MIN_PROFIT_FACTOR = 1.1
MAX_SPREAD_COST_PCT = 0.03


class PerformanceMonitor:
    """Monitors bot performance and triggers optimizations."""

    def __init__(self):
        self.last_trade_count = 0
        self.last_optimization = time.time()
        self.performance_history = []

    def load_recent_trades(self, n=PERFORMANCE_WINDOW):
        """Load the last N trades from CSV."""
        if not TRADES_LOG.exists():
            return []

        trades = []
        with open(TRADES_LOG, 'r') as f:
            reader = csv.DictReader(f)
            all_trades = list(reader)
            return all_trades[-n:] if len(all_trades) > n else all_trades

    def analyze_performance(self, trades):
        """Analyze trade performance and return metrics."""
        if not trades:
            return None

        metrics = {
            'total_trades': len(trades),
            'timestamp': datetime.now().isoformat(),
            'by_strategy': defaultdict(lambda: {'count': 0, 'wins': 0, 'losses': 0}),
            'by_pair': defaultdict(lambda: {'count': 0, 'wins': 0, 'losses': 0}),
            'consecutive_losses': 0,
            'max_consecutive_losses': 0,
        }

        current_consecutive = 0

        # Simplified analysis - we don't have outcome data in the log
        # Track frequency by strategy and pair
        for trade in trades:
            strategy = trade.get('strategy', 'unknown')
            pair = trade.get('pair', 'unknown')

            metrics['by_strategy'][strategy]['count'] += 1
            metrics['by_pair'][pair]['count'] += 1

        # Calculate concentration risk
        total = len(trades)
        max_pair_concentration = max(m['count'] for m in metrics['by_pair'].values()) / total if total > 0 else 0
        max_strategy_concentration = max(m['count'] for m in metrics['by_strategy'].values()) / total if total > 0 else 0

        metrics['max_pair_concentration'] = max_pair_concentration
        metrics['max_strategy_concentration'] = max_strategy_concentration

        # Identify overtrading patterns
        if len(trades) >= 10:
            timestamps = [datetime.fromisoformat(t['timestamp']) for t in trades[-10:]]
            time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() for i in range(len(timestamps)-1)]
            avg_time_between_trades = sum(time_diffs) / len(time_diffs) if time_diffs else 0
            metrics['avg_time_between_trades'] = avg_time_between_trades
            metrics['overtrading'] = avg_time_between_trades < 120  # Less than 2 minutes

        return metrics

    def check_optimization_needed(self, metrics):
        """Determine if optimization is needed based on metrics."""
        if not metrics:
            return False, []

        issues = []

        # Check for pair concentration
        if metrics.get('max_pair_concentration', 0) > 0.4:
            issues.append(f"High pair concentration: {metrics['max_pair_concentration']:.1%} of trades on one pair")

        # Check for strategy concentration
        if metrics.get('max_strategy_concentration', 0) > 0.6:
            issues.append(f"High strategy concentration: {metrics['max_strategy_concentration']:.1%} from one strategy")

        # Check for overtrading
        if metrics.get('overtrading'):
            issues.append(f"Overtrading detected: avg {metrics['avg_time_between_trades']:.0f}s between trades")

        # Force optimization every hour
        time_since_last = time.time() - self.last_optimization
        if time_since_last > OPTIMIZATION_INTERVAL:
            issues.append(f"Scheduled optimization (last: {time_since_last/60:.0f} min ago)")

        return len(issues) > 0, issues

    def log_performance(self, metrics):
        """Save performance metrics to log file."""
        if not PERFORMANCE_LOG.exists():
            history = []
        else:
            with open(PERFORMANCE_LOG, 'r') as f:
                history = json.load(f)

        history.append(metrics)

        # Keep last 100 entries
        history = history[-100:]

        with open(PERFORMANCE_LOG, 'w') as f:
            json.dump(history, f, indent=2)

    def get_optimization_recommendations(self, metrics, issues):
        """Generate optimization recommendations based on issues."""
        recommendations = {
            'timestamp': datetime.now().isoformat(),
            'issues': issues,
            'actions': []
        }

        # Recommend cooldown increase if overtrading
        if metrics.get('overtrading'):
            current_cooldown = self.get_current_cooldown()
            new_cooldown = min(current_cooldown * 1.5, 600)  # Max 10 minutes
            recommendations['actions'].append({
                'type': 'increase_cooldown',
                'from': current_cooldown,
                'to': int(new_cooldown)
            })

        # Recommend disabling concentrated strategy
        if metrics.get('max_strategy_concentration', 0) > 0.6:
            # Find the dominant strategy
            dominant_strategy = max(metrics['by_strategy'].items(), key=lambda x: x[1]['count'])[0]
            recommendations['actions'].append({
                'type': 'review_strategy',
                'strategy': dominant_strategy,
                'reason': 'high_concentration'
            })

        # Recommend removing concentrated pair
        if metrics.get('max_pair_concentration', 0) > 0.4:
            dominant_pair = max(metrics['by_pair'].items(), key=lambda x: x[1]['count'])[0]
            recommendations['actions'].append({
                'type': 'review_pair',
                'pair': dominant_pair,
                'reason': 'high_concentration'
            })

        return recommendations

    def get_current_cooldown(self):
        """Read current cooldown from config."""
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('global', {}).get('cooldown_seconds', 300)
        except Exception:
            return 300

    def monitor_loop(self):
        """Main monitoring loop."""
        print(f"[{datetime.now()}] Starting continuous monitoring...")
        print(f"Check interval: {CHECK_INTERVAL}s")
        print(f"Optimization interval: {OPTIMIZATION_INTERVAL}s")
        print()

        while True:
            try:
                # Load recent trades
                trades = self.load_recent_trades()
                new_trade_count = len(trades)

                # Check if new trades since last check
                if new_trade_count > self.last_trade_count:
                    print(f"[{datetime.now()}] New trades detected: {new_trade_count - self.last_trade_count}")
                    self.last_trade_count = new_trade_count

                    # Analyze performance
                    metrics = self.analyze_performance(trades)
                    if metrics:
                        self.log_performance(metrics)

                        # Check if optimization needed
                        needs_optimization, issues = self.check_optimization_needed(metrics)

                        if needs_optimization:
                            print(f"[{datetime.now()}] ⚠️  OPTIMIZATION NEEDED:")
                            for issue in issues:
                                print(f"  - {issue}")

                            recommendations = self.get_optimization_recommendations(metrics, issues)
                            print(f"[{datetime.now()}] Recommendations:")
                            for action in recommendations['actions']:
                                print(f"  - {action}")

                            print()
                            print("=" * 80)
                            print("TRIGGER WEALTH-GENERATOR OPTIMIZATION")
                            print("=" * 80)
                            print()
                            print("Run this command to trigger optimization:")
                            print()
                            print("  Analyze performance and deploy fixes")
                            print()
                            print("Issues to address:")
                            for issue in issues:
                                print(f"  • {issue}")
                            print()
                            print("=" * 80)
                            print()

                            self.last_optimization = time.time()
                        else:
                            print(f"[{datetime.now()}] ✓ Performance looks healthy")
                            print(f"  Total trades analyzed: {metrics['total_trades']}")
                            print(f"  Strategies active: {len(metrics['by_strategy'])}")
                            print(f"  Pairs traded: {len(metrics['by_pair'])}")
                else:
                    print(f"[{datetime.now()}] No new trades (total: {new_trade_count})")

                print()

                # Sleep until next check
                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                print(f"[{datetime.now()}] ERROR: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    monitor = PerformanceMonitor()
    monitor.monitor_loop()
