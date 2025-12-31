#!/usr/bin/env python3
"""Check OANDA account status and P&L"""
import os
import oandapyV20
from oandapyV20.endpoints import accounts, trades
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load env
load_dotenv('/home/user0/oandabot16/oanda_bot/.env')

OANDA_TOKEN = os.getenv('OANDA_TOKEN')
OANDA_ACCOUNT_ID = os.getenv('OANDA_ACCOUNT_ID')
OANDA_ENV = os.getenv('OANDA_ENV', 'practice')

print(f'Account: {OANDA_ACCOUNT_ID}')
print(f'Environment: {OANDA_ENV}')

api = oandapyV20.API(access_token=OANDA_TOKEN, environment=OANDA_ENV)

# Get account summary
r = accounts.AccountSummary(OANDA_ACCOUNT_ID)
resp = api.request(r)
account = resp['account']

print()
print('=== ACCOUNT SUMMARY ===')
print(f"Balance: ${float(account['balance']):,.2f}")
print(f"NAV: ${float(account['NAV']):,.2f}")
print(f"Unrealized P/L: ${float(account['unrealizedPL']):,.2f}")
print(f"Realized P/L (total): ${float(account['pl']):,.2f}")
print(f"Open Trades: {account['openTradeCount']}")
print(f"Open Positions: {account['openPositionCount']}")
print(f"Margin Used: ${float(account['marginUsed']):,.2f}")
print(f"Margin Available: ${float(account['marginAvailable']):,.2f}")

# Get recent closed trades to analyze performance
print()
print('=== RECENT CLOSED TRADES (Last 100) ===')
r = trades.TradesList(OANDA_ACCOUNT_ID, params={'state': 'CLOSED', 'count': 100})
resp = api.request(r)

total_pl = 0
wins = 0
losses = 0
strategy_stats = {}

for trade in resp.get('trades', []):
    pl = float(trade.get('realizedPL', 0))
    total_pl += pl
    if pl > 0:
        wins += 1
    elif pl < 0:
        losses += 1

    # Extract strategy from client extensions if available
    ext = trade.get('clientExtensions', {})
    strategy = ext.get('tag', 'Unknown')
    if strategy not in strategy_stats:
        strategy_stats[strategy] = {'wins': 0, 'losses': 0, 'pl': 0}
    strategy_stats[strategy]['pl'] += pl
    if pl > 0:
        strategy_stats[strategy]['wins'] += 1
    elif pl < 0:
        strategy_stats[strategy]['losses'] += 1

print(f"Total P/L (last 100 trades): ${total_pl:,.2f}")
print(f"Wins: {wins}, Losses: {losses}")
if wins + losses > 0:
    print(f"Win Rate: {100*wins/(wins+losses):.1f}%")

print()
print('=== STRATEGY PERFORMANCE ===')
for strat, stats in sorted(strategy_stats.items(), key=lambda x: x[1]['pl'], reverse=True):
    total = stats['wins'] + stats['losses']
    wr = 100 * stats['wins'] / total if total > 0 else 0
    print(f"{strat}: P/L=${stats['pl']:,.2f}, Wins={stats['wins']}, Losses={stats['losses']}, WR={wr:.1f}%")

# Get open positions
print()
print('=== OPEN POSITIONS ===')
from oandapyV20.endpoints.positions import OpenPositions
r = OpenPositions(OANDA_ACCOUNT_ID)
resp = api.request(r)
for pos in resp.get('positions', []):
    instr = pos['instrument']
    pl = float(pos.get('unrealizedPL', 0))
    long_units = pos.get('long', {}).get('units', '0')
    short_units = pos.get('short', {}).get('units', '0')
    print(f"{instr}: Long={long_units}, Short={short_units}, Unrealized P/L=${pl:,.2f}")
