#!/usr/bin/env python3
"""Close all open positions"""
import os
import oandapyV20
from oandapyV20.endpoints import trades
from oandapyV20.endpoints.trades import TradeClose
from dotenv import load_dotenv

load_dotenv('/home/user0/oandabot16/oanda_bot/.env')
OANDA_TOKEN = os.getenv('OANDA_TOKEN')
OANDA_ACCOUNT_ID = os.getenv('OANDA_ACCOUNT_ID')
OANDA_ENV = os.getenv('OANDA_ENV', 'practice')

api = oandapyV20.API(access_token=OANDA_TOKEN, environment=OANDA_ENV)

print("Closing ALL open trades...")
r = trades.TradesList(OANDA_ACCOUNT_ID, params={'state': 'OPEN'})
resp = api.request(r)

for trade in resp.get('trades', []):
    trade_id = trade['id']
    instr = trade['instrument']
    units = trade.get('currentUnits', 0)
    pl = float(trade.get('unrealizedPL', 0))

    print(f"Closing trade {trade_id}: {instr} {units} units, P/L=${pl:.2f}")
    try:
        req = TradeClose(OANDA_ACCOUNT_ID, trade_id)
        resp2 = api.request(req)
        realized_pl = float(resp2.get('orderFillTransaction', {}).get('pl', 0))
        print(f"  -> Closed with realized P/L: ${realized_pl:.2f}")
    except Exception as e:
        print(f"  -> Error: {e}")

print("\nDone.")
