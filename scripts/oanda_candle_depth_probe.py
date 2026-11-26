"""Read-only probe: how far back OANDA's short-granularity bid/ask candles go (S5, S30, M1). Places no orders."""
import json
import os
import sys
import urllib.error
import urllib.request

HOST = "https://api-fxpractice.oanda.com"
TOKEN = os.environ.get("OANDA_API_TOKEN", "")
STARTS = ["2003-01-06", "2005-01-03", "2008-01-02", "2010-01-04", "2012-01-03", "2015-01-05", "2018-01-02", "2022-01-03"]


def get(path):
    req = urllib.request.Request(HOST + path, headers={"Authorization": "Bearer " + TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    if not TOKEN:
        print("FAIL: token missing")
        return 1
    for pair in ("EUR_USD", "USD_JPY"):
        for g in ("S5", "S30", "M1"):
            for d in STARTS:
                code, j = get(f"/v3/instruments/{pair}/candles?granularity={g}&price=BA&count=3&from={d}T12:00:00Z")
                c = (j or {}).get("candles") or []
                first = c[0] if c else {}
                sp = (float(first["ask"]["c"]) - float(first["bid"]["c"])) if first else None
                print(f"{pair} {g:3s} from {d} -> {code} first {first.get('time', '-')} n {len(c)} spread {sp} "
                      f"{'' if code == 200 else j.get('errorMessage', '')}")
    print("CANDLE DEPTH PROBE DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
