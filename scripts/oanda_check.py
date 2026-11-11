"""Read-only OANDA practice check: account summary and one EUR/USD daily candle. Places no orders; never prints the token."""
import json
import os
import sys
import urllib.request

HOST = "https://api-fxpractice.oanda.com"
TOKEN = os.environ.get("OANDA_API_TOKEN", "")
ACCOUNT = os.environ.get("OANDA_ACCOUNT_ID", "")


def get(path):
    req = urllib.request.Request(HOST + path, headers={"Authorization": "Bearer " + TOKEN})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def main():
    if not TOKEN or not ACCOUNT:
        print("FAIL: token or account id missing")
        return 1
    a = get(f"/v3/accounts/{ACCOUNT}/summary")["account"]
    print(f"account {a['id']} currency {a['currency']} balance {a['balance']} NAV {a['NAV']} "
          f"open trades {a['openTradeCount']} margin rate {a.get('marginRate')}")
    c = get("/v3/instruments/EUR_USD/candles?granularity=D&count=3&price=BA")["candles"]
    for x in c:
        print(f"EUR_USD {x['time'][:10]} bid close {x['bid']['c']} ask close {x['ask']['c']} complete {x['complete']}")
    print("OANDA READ-ONLY CHECK: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
