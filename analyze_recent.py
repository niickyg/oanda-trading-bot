#!/usr/bin/env python3
"""Analyze trades since config change (after 22:10 UTC on Dec 30, 2025)"""
import os
import oandapyV20
from oandapyV20.endpoints import trades
from dotenv import load_dotenv
from datetime import datetime

load_dotenv('/home/user0/oandabot16/oanda_bot/.env')
OANDA_TOKEN = os.getenv('OANDA_TOKEN')
OANDA_ACCOUNT_ID = os.getenv('OANDA_ACCOUNT_ID')
OANDA_ENV = os.getenv('OANDA_ENV', 'practice')

api = oandapyV20.API(access_token=OANDA_TOKEN, environment=OANDA_ENV)

# Config change time - Improved R:R (sl=1.5, tp=4.0) started 04:27 UTC Dec 31
CONFIG_CHANGE_TIME = datetime(2025, 12, 31, 4, 27, 0)

print(f"=== TRADES SINCE CONFIG CHANGE ({CONFIG_CHANGE_TIME}) ===")
print()

# Get closed trades
r = trades.TradesList(OANDA_ACCOUNT_ID, params={'state': 'CLOSED', 'count': 50})
resp = api.request(r)

wins = 0
losses = 0
total_pl = 0
trades_since_change = []

for trade in resp.get('trades', []):
    open_time_str = trade.get('openTime', '')
    try:
        open_time = datetime.fromisoformat(open_time_str.replace('Z', '+00:00')).replace(tzinfo=None)
    except:
        continue

    if open_time >= CONFIG_CHANGE_TIME:
        pl = float(trade.get('realizedPL', 0))
        instr = trade.get('instrument', '?')
        units = trade.get('initialUnits', 0)
        close_time = trade.get('closeTime', '?')[:19]

        trades_since_change.append({
            'open_time': open_time_str[:19],
            'close_time': close_time,
            'instrument': instr,
            'units': units,
            'pl': pl
        })

        total_pl += pl
        if pl > 0:
            wins += 1
        elif pl < 0:
            losses += 1

# Print trades
for t in sorted(trades_since_change, key=lambda x: x['open_time']):
    status = 'WIN' if t['pl'] > 0 else ('LOSS' if t['pl'] < 0 else 'BREAK-EVEN')
    print(f"{t['open_time']} | {t['instrument']:8s} | {t['units']:>6} | ${t['pl']:>7.2f} | {status}")

print()
print(f"=== SUMMARY SINCE CONFIG CHANGE ===")
print(f"Total trades: {len(trades_since_change)}")
print(f"Wins: {wins}, Losses: {losses}")
if wins + losses > 0:
    print(f"Win Rate: {100*wins/(wins+losses):.1f}%")
print(f"Total P/L: ${total_pl:.2f}")

# Get open trades
print()
print("=== CURRENTLY OPEN TRADES ===")
r = trades.TradesList(OANDA_ACCOUNT_ID, params={'state': 'OPEN'})
resp = api.request(r)
total_unrealized = 0
for trade in resp.get('trades', []):
    instr = trade['instrument']
    units = trade.get('currentUnits', 0)
    pl = float(trade.get('unrealizedPL', 0))
    open_time = trade.get('openTime', '?')[:19]
    total_unrealized += pl
    print(f"{open_time} | {instr:8s} | {units:>6} | ${pl:>7.2f}")
print(f"Total unrealized P/L: ${total_unrealized:.2f}")
print(f"Combined P/L (realized + unrealized): ${total_pl + total_unrealized:.2f}")
