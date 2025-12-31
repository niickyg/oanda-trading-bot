#!/bin/bash
# Automatic optimization trigger for OANDA bot
# This script is called by the monitor when optimization is needed

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/optimization_log.txt"

echo "========================================" | tee -a "$LOG_FILE"
echo "AUTO-OPTIMIZATION TRIGGERED" | tee -a "$LOG_FILE"
echo "$(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Analyze recent performance
echo "Analyzing recent trades..." | tee -a "$LOG_FILE"
python3 << 'PYTHON_SCRIPT' | tee -a "$LOG_FILE"
import csv
import json
from collections import defaultdict
from pathlib import Path

trades_log = Path("/home/user0/oandabot16/oanda_bot/trades_log.csv")

if not trades_log.exists():
    print("No trades log found")
    exit(1)

# Load last 100 trades
with open(trades_log, 'r') as f:
    reader = csv.DictReader(f)
    all_trades = list(reader)
    recent_trades = all_trades[-100:] if len(all_trades) > 100 else all_trades

# Analyze by strategy
strategy_counts = defaultdict(int)
pair_counts = defaultdict(int)

for trade in recent_trades:
    strategy_counts[trade.get('strategy', 'unknown')] += 1
    pair_counts[trade.get('pair', 'unknown')] += 1

print(f"\nLast {len(recent_trades)} trades:")
print(f"\nBy Strategy:")
for strategy, count in sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True):
    pct = count / len(recent_trades) * 100
    print(f"  {strategy}: {count} ({pct:.1f}%)")

print(f"\nBy Pair:")
for pair, count in sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    pct = count / len(recent_trades) * 100
    print(f"  {pair}: {count} ({pct:.1f}%)")

# Check for concentration issues
max_pair = max(pair_counts.items(), key=lambda x: x[1])
max_strategy = max(strategy_counts.items(), key=lambda x: x[1])

print("\n⚠️  ISSUES DETECTED:")
if max_pair[1] / len(recent_trades) > 0.3:
    print(f"  - High pair concentration: {max_pair[0]} = {max_pair[1]/len(recent_trades)*100:.1f}%")
if max_strategy[1] / len(recent_trades) > 0.5:
    print(f"  - High strategy concentration: {max_strategy[0]} = {max_strategy[1]/len(recent_trades)*100:.1f}%")

PYTHON_SCRIPT

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "OPTIMIZATION COMPLETE" | tee -a "$LOG_FILE"
echo "$(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
