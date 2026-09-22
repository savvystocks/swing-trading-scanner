"""DAILY SHARE-PRICE ARCHIVE (owner 2026-09-22, after the Unusual Whales exit: "we save no market data at all").

The two strategies the research has actually cleared - the published RSI(2) dip-buy on ETF shares (17 years out of
sample, 16 of 16 ETFs) and Faber's 200-day switch - both run on daily share bars and need no options data and no paid
feed. Until now nothing on this box stored a single daily bar, so neither could be watched, re-tested or traded on
fresh data. This is the smallest thing that fixes that: one Alpaca call per run for every ETF those two strategies
name, appended to data/daily_bars.db, a few megabytes a year, zero incremental cost.

Off the trade path: it reads market data only, writes its own database, and never raises into a caller (an evidence
job never pages). Idempotent - re-running a day replaces the same rows.
"""
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(REPO, "data", "daily_bars.db")
# RSI(2) dip-buy universe (the published 16) + the 200-day switch's own instruments + what the live book hedges to.
SYMBOLS = ("SPY QQQ IWM DIA MDY EFA EEM TLT IEF LQD HYG GLD SLV XLE XLF XLK XLV XLI XLP XLU XLB XLRE XBI SMH "
           "SSO QLD UPRO TQQQ VTI VOO").split()
LOOKBACK_DAYS = int(os.environ.get("BARS_LOOKBACK_DAYS", "10"))   # a small rolling window closes weekend/holiday gaps


def open_db(path=DB):
    db = sqlite3.connect(path, timeout=60)
    db.execute("create table if not exists bars(symbol text, day text, open real, high real, low real, close real, "
               "volume real, trade_count real, vwap real, primary key(symbol, day))")
    db.execute("create index if not exists i_bars_day on bars(day)")
    db.commit()
    return db


def fetch(symbols, start, key, secret, timeout=20):
    """One paged call per batch: Alpaca returns {'bars': {SYM: [...]}, 'next_page_token': ...}."""
    out, token = {}, None
    while True:
        u = ("https://data.alpaca.markets/v2/stocks/bars?symbols=" + ",".join(symbols) +
             f"&timeframe=1Day&start={start}&limit=10000&adjustment=split&feed=iex")
        if token:
            u += "&page_token=" + token
        req = urllib.request.Request(u, headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read())
        for sym, rows in (j.get("bars") or {}).items():
            out.setdefault(sym, []).extend(rows)
        token = j.get("next_page_token")
        if not token:
            return out


def run(db=None, now=None, fetcher=fetch):
    key = (os.environ.get("ALPACA_PAPER_API_KEY") or os.environ.get("ALPACA_API_KEY") or "").strip()
    secret = (os.environ.get("ALPACA_PAPER_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY") or "").strip()
    if not (key and secret):
        print("daily bars: no Alpaca keys in env - nothing pulled", flush=True)
        return 0
    now = now or datetime.now(timezone.utc)
    start = (now.date() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    close_db = db is None
    db = db or open_db()
    n = 0
    try:
        data = fetcher(SYMBOLS, start, key, secret)
        for sym, rows in data.items():
            for b in rows:
                day = (b.get("t") or "")[:10]
                if not day:
                    continue
                db.execute("insert or replace into bars values (?,?,?,?,?,?,?,?,?)",
                           (sym, day, b.get("o"), b.get("h"), b.get("l"), b.get("c"),
                            b.get("v"), b.get("n"), b.get("vw")))
                n += 1
        db.commit()
        tot, syms, first, last = db.execute("select count(*), count(distinct symbol), min(day), max(day) from bars").fetchone()
        print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} daily bars: {n} rows written for "
              f"{len(data)} symbols; store now {tot:,} rows over {syms} symbols, {first} .. {last}", flush=True)
    except Exception as e:                               # an evidence job never pages and never raises
        print(f"daily bars failed open: {type(e).__name__}: {e}", flush=True)
    finally:
        if close_db:
            db.close()
    return n


if __name__ == "__main__":
    sys.exit(0 if run() >= 0 else 0)
