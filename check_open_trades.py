#!/usr/bin/env python3
"""Check open trades in detail"""
import os
import oandapyV20
from oandapyV20.endpoints import trades
from oandapyV20.endpoints.trades import TradeClose
from dotenv import load_dotenv

# Load env
load_dotenv('/home/user0/oandabot16/oanda_bot/.env')

OANDA_TOKEN = os.getenv('OANDA_TOKEN')
OANDA_ACCOUNT_ID = os.getenv('OANDA_ACCOUNT_ID')
OANDA_ENV = os.getenv('OANDA_ENV', 'practice')

# Blocked pairs
BLOCKED_PAIRS = [
    "NZD_JPY",
    "AUD_NZD",
    "GBP_JPY",
    "EUR_JPY",
    "AUD_JPY",
    "USD_JPY"
]

api = oandapyV20.API(access_token=OANDA_TOKEN, environment=OANDA_ENV)

print("=== OPEN TRADES ===")
r = trades.TradesList(OANDA_ACCOUNT_ID, params={'state': 'OPEN'})
resp = api.request(r)

for trade in resp.get('trades', []):
    trade_id = trade['id']
    instr = trade['instrument']
    units = trade['currentUnits']
    pl = float(trade.get('unrealizedPL', 0))
    open_time = trade.get('openTime', '?')[:19]

    blocked = " [BLOCKED PAIR!]" if instr in BLOCKED_PAIRS else ""
    print(f"Trade {trade_id}: {instr} {units} units, P/L=${pl:.2f}, opened {open_time}{blocked}")

    if instr in BLOCKED_PAIRS:
        print(f"  -> Closing trade {trade_id}...")
        try:
            req = TradeClose(OANDA_ACCOUNT_ID, trade_id)
            resp2 = api.request(req)
            print(f"  -> Closed: {resp2}")
        except Exception as e:
            print(f"  -> Error: {e}")
