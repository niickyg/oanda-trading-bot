import os
from dotenv import load_dotenv
import oandapyV20
import oandapyV20.endpoints.accounts as accounts

load_dotenv()
api = oandapyV20.API(access_token=os.getenv("OANDA_TOKEN"),
                     environment=os.getenv("OANDA_ENV", "practice"))

r = accounts.AccountList()
print("Accessible practice accounts:")
print([acct['id'] for acct in api.request(r)['accounts']])