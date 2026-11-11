"""Pull hourly bid/ask candles for the nine USD pairs from the OANDA practice API into gzip CSVs.
Read-only (no orders), token never printed. Writes fx_history/<PAIR>_H1.csv.gz plus fx_history/MANIFEST.txt
(first and last bar, rows, missing weekday hours, sha256 per file)."""
import csv
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HOST = "https://api-fxpractice.oanda.com"
TOKEN = os.environ.get("OANDA_API_TOKEN", "")
PAIRS = "EUR_USD GBP_USD USD_JPY USD_CHF AUD_USD NZD_USD USD_CAD USD_SEK USD_NOK".split()
START = datetime(2002, 1, 1, tzinfo=timezone.utc)
OUT = "fx_history"


def get(path, params):
    url = HOST + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt == 4:
                raise RuntimeError(f"{path}: {type(e).__name__}") from None
            time.sleep(2 + 3 * attempt)


def pull(pair):
    rows, t = [], START
    now = datetime.now(timezone.utc)
    while t < now:
        d = get(f"/v3/instruments/{pair}/candles",
                {"granularity": "H1", "price": "BA", "from": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "count": 5000})
        c = [x for x in d.get("candles", []) if x.get("complete")]
        if not c:
            t += timedelta(days=200)
            continue
        for x in c:
            b, a = x["bid"], x["ask"]
            rows.append([x["time"][:19], b["o"], b["h"], b["l"], b["c"], a["o"], a["h"], a["l"], a["c"], x["volume"]])
        t = datetime.strptime(c[-1]["time"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc) + timedelta(hours=1)
        time.sleep(0.05)
    return rows


def main():
    if not TOKEN:
        print("FAIL: token missing")
        return 1
    os.makedirs(OUT, exist_ok=True)
    lines = []
    for pair in PAIRS:
        rows = pull(pair)
        path = f"{OUT}/{pair}_H1.csv.gz"
        with gzip.open(path, "wt", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["time_utc", "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c", "volume"])
            w.writerows(rows)
        seen = {r[0] for r in rows}
        gaps = 0
        if rows:
            t = datetime.strptime(rows[0][0], "%Y-%m-%dT%H:%M:%S")
            end = datetime.strptime(rows[-1][0], "%Y-%m-%dT%H:%M:%S")
            while t <= end:
                wd, h = t.weekday(), t.hour
                trading = wd < 4 or (wd == 4 and h < 21) or (wd == 6 and h >= 22)
                if trading and t.strftime("%Y-%m-%dT%H:%M:%S") not in seen:
                    gaps += 1
                t += timedelta(hours=1)
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        line = (f"{pair} rows {len(rows)} first {rows[0][0] if rows else '-'} last {rows[-1][0] if rows else '-'} "
                f"missing_weekday_hours {gaps} sha256 {sha}")
        print(line, flush=True)
        lines.append(line)
    with open(f"{OUT}/MANIFEST.txt", "w") as fh:
        fh.write(f"pulled {datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ} from {HOST} H1 BA, start {START:%Y-%m-%d}\n")
        fh.write("missing_weekday_hours is approximate (holidays and the 21:00/22:00 UTC weekend edges count)\n")
        fh.write("\n".join(lines) + "\n")
    print("FX HISTORY PULL: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
