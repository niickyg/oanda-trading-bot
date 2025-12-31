#!/usr/bin/env python3
"""Deep analysis of recent closed trades to find what's working and what's not"""
import os
import oandapyV20
from oandapyV20.endpoints import trades
from dotenv import load_dotenv
from collections import defaultdict
from datetime import datetime

# Load env
load_dotenv('/home/user0/oandabot16/oanda_bot/.env')

OANDA_TOKEN = os.getenv('OANDA_TOKEN')
OANDA_ACCOUNT_ID = os.getenv('OANDA_ACCOUNT_ID')
OANDA_ENV = os.getenv('OANDA_ENV', 'practice')

api = oandapyV20.API(access_token=OANDA_TOKEN, environment=OANDA_ENV)

# Get more closed trades
print('=== ANALYZING LAST 500 CLOSED TRADES ===')
r = trades.TradesList(OANDA_ACCOUNT_ID, params={'state': 'CLOSED', 'count': 500})
resp = api.request(r)

total_pl = 0
wins = 0
losses = 0
pair_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pl': 0, 'trades': 0})
strategy_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pl': 0, 'trades': 0})
side_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pl': 0})
hour_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pl': 0})

all_trades = resp.get('trades', [])
print(f"Total closed trades retrieved: {len(all_trades)}")

for trade in all_trades:
    pl = float(trade.get('realizedPL', 0))
    instr = trade.get('instrument', 'Unknown')
    units = int(trade.get('initialUnits', 0))
    side = 'BUY' if units > 0 else 'SELL'

    # Get open time for hour analysis
    open_time = trade.get('openTime', '')
    try:
        dt = datetime.fromisoformat(open_time.replace('Z', '+00:00'))
        hour = dt.hour
    except:
        hour = -1

    # Extract strategy from client extensions
    ext = trade.get('clientExtensions', {})
    strategy = ext.get('tag', 'Unknown')

    total_pl += pl

    if pl > 0:
        wins += 1
        pair_stats[instr]['wins'] += 1
        strategy_stats[strategy]['wins'] += 1
        side_stats[side]['wins'] += 1
        if hour >= 0:
            hour_stats[hour]['wins'] += 1
    elif pl < 0:
        losses += 1
        pair_stats[instr]['losses'] += 1
        strategy_stats[strategy]['losses'] += 1
        side_stats[side]['losses'] += 1
        if hour >= 0:
            hour_stats[hour]['losses'] += 1

    pair_stats[instr]['pl'] += pl
    pair_stats[instr]['trades'] += 1
    strategy_stats[strategy]['pl'] += pl
    strategy_stats[strategy]['trades'] += 1
    side_stats[side]['pl'] += pl
    if hour >= 0:
        hour_stats[hour]['pl'] += pl

print()
print(f"Total P/L (all retrieved): ${total_pl:,.2f}")
print(f"Wins: {wins}, Losses: {losses}")
if wins + losses > 0:
    print(f"Overall Win Rate: {100*wins/(wins+losses):.1f}%")
    # Calculate profit factor
    gross_profit = sum(float(t.get('realizedPL', 0)) for t in all_trades if float(t.get('realizedPL', 0)) > 0)
    gross_loss = abs(sum(float(t.get('realizedPL', 0)) for t in all_trades if float(t.get('realizedPL', 0)) < 0))
    if gross_loss > 0:
        print(f"Profit Factor: {gross_profit / gross_loss:.2f}")
    print(f"Gross Profit: ${gross_profit:.2f}")
    print(f"Gross Loss: ${gross_loss:.2f}")

print()
print('=== PAIR PERFORMANCE (Sorted by P/L) ===')
for pair, stats in sorted(pair_stats.items(), key=lambda x: x[1]['pl'], reverse=True):
    total = stats['wins'] + stats['losses']
    wr = 100 * stats['wins'] / total if total > 0 else 0
    avg_pl = stats['pl'] / stats['trades'] if stats['trades'] > 0 else 0
    print(f"{pair:12s}: P/L=${stats['pl']:>8.2f}, Trades={stats['trades']:>3}, Wins={stats['wins']:>2}, Losses={stats['losses']:>2}, WR={wr:>5.1f}%, Avg=${avg_pl:>6.2f}")

print()
print('=== STRATEGY PERFORMANCE (Sorted by P/L) ===')
for strat, stats in sorted(strategy_stats.items(), key=lambda x: x[1]['pl'], reverse=True):
    total = stats['wins'] + stats['losses']
    wr = 100 * stats['wins'] / total if total > 0 else 0
    avg_pl = stats['pl'] / stats['trades'] if stats['trades'] > 0 else 0
    print(f"{strat:15s}: P/L=${stats['pl']:>8.2f}, Trades={stats['trades']:>3}, Wins={stats['wins']:>2}, Losses={stats['losses']:>2}, WR={wr:>5.1f}%, Avg=${avg_pl:>6.2f}")

print()
print('=== SIDE PERFORMANCE ===')
for side, stats in sorted(side_stats.items(), key=lambda x: x[1]['pl'], reverse=True):
    total = stats['wins'] + stats['losses']
    wr = 100 * stats['wins'] / total if total > 0 else 0
    print(f"{side}: P/L=${stats['pl']:,.2f}, Wins={stats['wins']}, Losses={stats['losses']}, WR={wr:.1f}%")

print()
print('=== HOURLY PERFORMANCE (UTC) ===')
for hour in sorted(hour_stats.keys()):
    stats = hour_stats[hour]
    total = stats['wins'] + stats['losses']
    if total > 0:
        wr = 100 * stats['wins'] / total
        print(f"Hour {hour:02d}: P/L=${stats['pl']:>8.2f}, Wins={stats['wins']:>2}, Losses={stats['losses']:>2}, WR={wr:>5.1f}%")

# Show last 20 trades
print()
print('=== LAST 20 TRADES ===')
for trade in all_trades[:20]:
    pl = float(trade.get('realizedPL', 0))
    instr = trade.get('instrument', '?')
    units = trade.get('initialUnits', 0)
    ext = trade.get('clientExtensions', {})
    strategy = ext.get('tag', '?')
    open_time = trade.get('openTime', '?')[:19]
    close_time = trade.get('closeTime', '?')[:19]
    status = 'WIN' if pl > 0 else 'LOSS'
    print(f"{open_time} | {instr:8s} | {strategy:12s} | {units:>6} | ${pl:>7.2f} | {status}")
