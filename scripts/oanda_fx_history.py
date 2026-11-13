"""Pull bid/ask candles from the OANDA practice API into gzip CSVs. Read-only (no orders), token never printed.
Env: INSTRUMENTS (space separated, default the nine USD pairs), GRANULARITY (default H1), START_DATE (default
2002-01-01), OUT_DIR (default fx_history). Writes <OUT_DIR>/<INSTRUMENT>_<GRAN>.csv.gz, MANIFEST.txt (first and
last bar, rows, missing weekday bars, sha256 per file; instruments the API refuses are listed as UNAVAILABLE) and,
when OANDA_ACCOUNT_ID is set, INSTRUMENTS.json: the account's instrument list as returned (type, minimum trade size,
margin rate, current financing rates)."""
import csv
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HOST = "https://api-fxpractice.oanda.com"
TOKEN = os.environ.get("OANDA_API_TOKEN", "")
ACCOUNT = os.environ.get("OANDA_ACCOUNT_ID", "")
DEFAULT = "EUR_USD GBP_USD USD_JPY USD_CHF AUD_USD NZD_USD USD_CAD USD_SEK USD_NOK"
PAIRS = (os.environ.get("INSTRUMENTS") or DEFAULT).split()
GRAN = os.environ.get("GRANULARITY") or "H1"
START = datetime.strptime(os.environ.get("START_DATE") or "2002-01-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
OUT = os.environ.get("OUT_DIR") or "fx_history"
STEP = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D": 86400}[GRAN]


class Refused(Exception):
    pass


def get(path, params=None):
    url = HOST + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + TOKEN})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 403, 404):
                raise Refused(f"HTTP {e.code}") from None
            if attempt == 4:
                raise RuntimeError(f"{path}: HTTP {e.code}") from None
        except Exception as e:
            if attempt == 4:
                raise RuntimeError(f"{path}: {type(e).__name__}") from None
        time.sleep(2 + 3 * attempt)


def pull(pair):
    rows, t = [], START
    now = datetime.now(timezone.utc)
    while t < now:
        d = get(f"/v3/instruments/{pair}/candles",
                {"granularity": GRAN, "price": "BA", "from": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "count": 5000})
        c = [x for x in d.get("candles", []) if x.get("complete")]
        if not c:
            t += timedelta(days=200 if STEP >= 3600 else 20)
            continue
        for x in c:
            b, a = x["bid"], x["ask"]
            rows.append([x["time"][:19], b["o"], b["h"], b["l"], b["c"], a["o"], a["h"], a["l"], a["c"], x["volume"]])
        t = datetime.strptime(c[-1]["time"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc) + timedelta(seconds=STEP)
        time.sleep(0.05)
    return rows


def gaps(rows):
    if not rows:
        return 0
    seen = {r[0] for r in rows}
    n = 0
    t = datetime.strptime(rows[0][0], "%Y-%m-%dT%H:%M:%S")
    end = datetime.strptime(rows[-1][0], "%Y-%m-%dT%H:%M:%S")
    step = timedelta(seconds=min(STEP, 86400))
    while t <= end:
        wd, h = t.weekday(), t.hour
        trading = wd < 4 or (wd == 4 and h < 21) or (wd == 6 and h >= 22)
        if trading and t.strftime("%Y-%m-%dT%H:%M:%S") not in seen:
            n += 1
        t += step
    return n


def main():
    if not TOKEN:
        print("FAIL: token missing")
        return 1
    os.makedirs(OUT, exist_ok=True)
    account = ACCOUNT
    if not account:
        try:
            accs = get("/v3/accounts").get("accounts", [])
            account = accs[0]["id"] if accs else ""
        except (Refused, RuntimeError) as e:
            print(f"account list: not read ({e})", flush=True)
    if account:
        try:
            inst = get(f"/v3/accounts/{account}/instruments")
            with open(f"{OUT}/INSTRUMENTS.json", "w") as fh:
                json.dump({"pulled_utc": f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}", **inst}, fh, indent=1)
            print(f"account instruments: {len(inst.get('instruments', []))}", flush=True)
        except (Refused, RuntimeError) as e:
            print(f"account instruments: not read ({e})", flush=True)
    lines = []
    for pair in PAIRS:
        try:
            rows = pull(pair)
        except Refused as e:
            line = f"{pair} UNAVAILABLE ({e})"
            print(line, flush=True)
            lines.append(line)
            continue
        path = f"{OUT}/{pair}_{GRAN}.csv.gz"
        with gzip.open(path, "wt", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["time_utc", "bid_o", "bid_h", "bid_l", "bid_c", "ask_o", "ask_h", "ask_l", "ask_c", "volume"])
            w.writerows(rows)
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        line = (f"{pair} rows {len(rows)} first {rows[0][0] if rows else '-'} last {rows[-1][0] if rows else '-'} "
                f"missing_weekday_bars {gaps(rows)} sha256 {sha}")
        print(line, flush=True)
        lines.append(line)
    with open(f"{OUT}/MANIFEST.txt", "w") as fh:
        fh.write(f"pulled {datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ} from {HOST} {GRAN} BA, start {START:%Y-%m-%d}\n")
        fh.write("missing_weekday_bars is approximate (FX 24x5 clock; holidays, weekend edges and CFD session "
                 "breaks count)\n")
        fh.write("\n".join(lines) + "\n")
    print("FX HISTORY PULL: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
