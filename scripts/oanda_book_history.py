"""Read-only pull of OANDA order book / position book history (snapshots exist from 2017). Places no orders.
One snapshot per STEP_MIN minutes on weekday hours; per snapshot: the full-book totals (long and short % above and below
the price) and the buckets within +/- BAND of the price. Output: one gzipped CSV per pair, book and year."""
import csv
import gzip
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

HOST = "https://api-fxpractice.oanda.com"
TOKEN = os.environ.get("OANDA_API_TOKEN", "")
PAIR = os.environ.get("PAIR", "EUR_USD")
BOOK = os.environ.get("BOOK", "orderBook")
START = os.environ.get("START", "2017-01-01")
END = os.environ.get("END", "2026-11-25")
STEP = int(os.environ.get("STEP_MIN", "60"))
BAND = float(os.environ.get("BAND", "0.02"))
THREADS = int(os.environ.get("THREADS", "2"))
OUT = os.environ.get("OUT_DIR", "books")
_lock = threading.Lock()


def get(path):
    for attempt in range(8):
        req = urllib.request.Request(HOST + path, headers={"Authorization": "Bearer " + TOKEN,
                                                           "Accept-Datetime-Format": "RFC3339"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return 200, json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None
            if e.code in (401, 429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 60))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 ** attempt)
    raise RuntimeError(f"gave up on {path}")


def times():
    t = datetime.fromisoformat(START).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(END).replace(tzinfo=timezone.utc)
    while t < end:
        wd = t.weekday()
        if not (wd == 5 or (wd == 6 and t.hour < 21) or (wd == 4 and t.hour >= 22)):
            yield t
        t += timedelta(minutes=STEP)


def summarise(snap):
    price = float(snap["price"])
    out = {"snapshot_time": snap["time"], "price": price, "bucket_width": float(snap["bucketWidth"]),
           "long_above": 0.0, "long_below": 0.0, "short_above": 0.0, "short_below": 0.0, "n_buckets": len(snap["buckets"])}
    near = []
    for b in snap["buckets"]:
        p, lo, sh = float(b["price"]), float(b["longCountPercent"]), float(b["shortCountPercent"])
        side = "above" if p >= price else "below"
        out["long_" + side] += lo
        out["short_" + side] += sh
        if abs(p - price) <= BAND * price and (lo or sh):
            near.append(f"{b['price']}:{b['longCountPercent']}:{b['shortCountPercent']}")
    out["buckets_near"] = ";".join(near)
    return out


def fetch(t):
    try:
        code, j = get(f"/v3/instruments/{PAIR}/{BOOK}?time={t.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    except Exception as e:
        print(f"  error at {t}: {str(e)[:120]}", flush=True)
        return "error"
    if code == 404 or not j or not j.get(BOOK, {}).get("price"):
        return None
    s = summarise(j[BOOK])
    s["asked_time"] = t.strftime("%Y-%m-%dT%H:%M:%SZ")
    return s


def main():
    if not TOKEN:
        print("FAIL: token missing")
        return 1
    os.makedirs(OUT, exist_ok=True)
    ts = list(times())
    print(f"{PAIR} {BOOK}: {len(ts)} snapshot times {START}..{END} every {STEP} min, band +/-{BAND:.0%}", flush=True)
    by_year, done, miss, err = {}, 0, 0, 0
    with ThreadPoolExecutor(THREADS) as ex:
        for s in ex.map(fetch, ts):
            done += 1
            if s == "error":
                err += 1
            elif s is None:
                miss += 1
            else:
                by_year.setdefault(s["asked_time"][:4], []).append(s)
            if done % 2000 == 0:
                print(f"  {done}/{len(ts)} done, {miss} missing, {err} errors", flush=True)
    cols = ["asked_time", "snapshot_time", "price", "bucket_width", "n_buckets", "long_above", "long_below",
            "short_above", "short_below", "buckets_near"]
    for y, rows in sorted(by_year.items()):
        rows.sort(key=lambda r: r["asked_time"])
        path = os.path.join(OUT, f"{PAIR}_{BOOK}_{y}.csv.gz")
        with gzip.open(path, "wt", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {path}: {len(rows)} snapshots, first {rows[0]['snapshot_time']}, last {rows[-1]['snapshot_time']}")
    print(f"DONE {PAIR} {BOOK}: {done - miss - err} snapshots, {miss} missing or no price, {err} errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
