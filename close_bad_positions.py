#!/usr/bin/env python3
"""Close positions on blocked pairs to stop losses"""
import os
import oandapyV20
from oandapyV20.endpoints.positions import OpenPositions, PositionClose
from dotenv import load_dotenv

# Load env
load_dotenv('/home/user0/oandabot16/oanda_bot/.env')

OANDA_TOKEN = os.getenv('OANDA_TOKEN')
OANDA_ACCOUNT_ID = os.getenv('OANDA_ACCOUNT_ID')
OANDA_ENV = os.getenv('OANDA_ENV', 'practice')

# Blocked pairs - close any positions on these
BLOCKED_PAIRS = [
    "NZD_JPY",
    "AUD_NZD",
    "GBP_JPY",
    "EUR_JPY",
    "AUD_JPY",
    "USD_JPY"
]

api = oandapyV20.API(access_token=OANDA_TOKEN, environment=OANDA_ENV)

print("Checking for positions on blocked pairs...")

r = OpenPositions(OANDA_ACCOUNT_ID)
resp = api.request(r)

positions_to_close = []
for pos in resp.get('positions', []):
    instr = pos['instrument']
    pl = float(pos.get('unrealizedPL', 0))
    long_units = pos.get('long', {}).get('units', '0')
    short_units = pos.get('short', {}).get('units', '0')

    print(f"{instr}: Long={long_units}, Short={short_units}, Unrealized P/L=${pl:.2f}")

    if instr in BLOCKED_PAIRS:
        positions_to_close.append(instr)
        print(f"  -> BLOCKED PAIR - will close")

if positions_to_close:
    print(f"\nClosing {len(positions_to_close)} positions on blocked pairs...")
    for instr in positions_to_close:
        try:
            payload = {"longUnits": "ALL", "shortUnits": "ALL"}
            req = PositionClose(OANDA_ACCOUNT_ID, instrument=instr, data=payload)
            resp = api.request(req)
            print(f"Closed {instr}: {resp}")
        except Exception as e:
            print(f"Error closing {instr}: {e}")
else:
    print("\nNo blocked pair positions to close.")

print("\nDone.")
