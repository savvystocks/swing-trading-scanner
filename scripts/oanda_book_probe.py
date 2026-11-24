"""Read-only probe: how far back do OANDA's order book and position book snapshots go? Places no orders."""
import json
import os
import sys
import urllib.error
import urllib.request

HOST = "https://api-fxpractice.oanda.com"
TOKEN = os.environ.get("OANDA_API_TOKEN", "")
DATES = ["", "2026-11-01T12:00:00Z", "2025-01-02T12:00:00Z", "2023-01-03T12:00:00Z", "2021-01-04T12:00:00Z",
         "2019-01-02T12:00:00Z", "2018-01-02T12:00:00Z", "2017-06-01T12:00:00Z", "2017-01-03T12:00:00Z",
         "2016-06-01T12:00:00Z", "2015-01-05T12:00:00Z", "2012-01-03T12:00:00Z", "2008-01-02T12:00:00Z"]


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
        for book in ("orderBook", "positionBook"):
            for d in DATES:
                code, j = get(f"/v3/instruments/{pair}/{book}" + (f"?time={d}" if d else ""))
                b = j.get(book) or {}
                bk = b.get("buckets") or []
                print(f"{pair} {book:12s} asked {d or 'latest':22s} -> {code} snapshot {b.get('time', '-')} "
                      f"price {b.get('price', '-')} buckets {len(bk)} width {b.get('bucketWidth', '-')} "
                      f"{'' if code == 200 else j.get('errorMessage', '')}")
    print("BOOK PROBE DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
