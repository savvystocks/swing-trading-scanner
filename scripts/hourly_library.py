"""HOURLY PATH LIBRARY (owner order 2026-08-27: "test every single strategy we have ever
thought of with this new data base").

Fetches and PERMANENTLY STORES the hour-by-hour price path of every tradeable contract in the
archive universe - batched 50 contracts per request (the speedup promised after last night's
one-by-one run), so the whole universe lands in ~1 hour instead of ~10. Once stored, ANY
strategy or exit design is testable in seconds, forever, without another API call.

Universe: every archive contract-day with an aggressor buy, premium 30k-1M, quoted spread <=3%
(wider than live's 2 so spread variants are testable), full-coverage tickers, BOTH sides, ALL
regimes. Bars INCLUDE the entry day (confirmed-entry / time-of-day strategies need it; the
no-same-day-exit rule is applied at replay time, not fetch time).

Output: data/hourly_paths.db  (bars: occ, entry_day irrelevant - bars keyed occ+ts; meta backed
by contracts_daily). Checkpointed per contract batch; budget-free (Alpaca data API, off-hours).
"""
import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
SRC = "data/uw_history.db"
DST = "data/hourly_paths.db"
H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}
BATCH = 50


def fetch_batch(symbols, start, end):
    """One batched request (paginated) -> {occ: [(ts,o,h,l,c), ...]}."""
    out = defaultdict(list)
    token = None
    for _page in range(40):
        q = {"symbols": ",".join(symbols), "timeframe": "1Hour", "start": start,
             "end": end, "limit": 10000}
        if token:
            q["page_token"] = token
        u = "https://data.alpaca.markets/v1beta1/options/bars?" + urllib.parse.urlencode(q)
        for att in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=45) as r:
                    j = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(15 * (att + 1)); continue
                return out
            except Exception:
                time.sleep(4)
        else:
            return out
        for occ, bars in (j.get("bars") or {}).items():
            for b in bars:
                out[occ].append((b["t"], b["o"], b["h"], b["l"], b["c"]))
        token = j.get("next_page_token")
        if not token:
            break
        time.sleep(0.35)
    return out


def main():
    con = sqlite3.connect(DST, timeout=60)
    con.execute("create table if not exists bars (occ text, ts text, o real, h real, l real, "
                "c real, primary key (occ, ts))")
    con.execute("create table if not exists fetched (occ text primary key, n int)")
    con.commit()
    src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True, timeout=60)
    tks = {r[0] for r in src.execute("select ticker from contracts_daily group by ticker "
                                     "having count(distinct day) >= 400")}
    # first trigger day per contract (fetch window = entry day .. +70d)
    first = {}
    for t, occ, day in src.execute(
            """select ticker, option_symbol, min(day) from contracts_daily
               where total_premium between 30000 and 1000000 and ask_volume > bid_volume
                 and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask > 0
                 and (nbbo_ask - nbbo_bid) / ((nbbo_ask + nbbo_bid) / 2.0) * 100 <= 3.0
               group by option_symbol"""):
        if t in tks:
            first[occ] = day
    done = {r[0] for r in con.execute("select occ from fetched")}
    todo = [(occ, d) for occ, d in first.items() if occ not in done]
    print(f"universe {len(first)} contracts; already stored {len(done)}; to fetch {len(todo)}",
          flush=True)
    # group by entry month so one batch shares a sane window
    groups = defaultdict(list)
    for occ, d in todo:
        groups[d[:7]].append((occ, d))
    n_done = 0
    for month in sorted(groups):
        items = groups[month]
        for i in range(0, len(items), BATCH):
            chunk = items[i:i + BATCH]
            start = min(d for _, d in chunk)
            end = min(date.fromisoformat(max(d for _, d in chunk)) + timedelta(days=70),
                      date.today() - timedelta(days=1)).isoformat()
            got = fetch_batch([occ for occ, _ in chunk], start, end)
            for occ, _ in chunk:
                bars = got.get(occ) or []
                con.executemany("insert or ignore into bars values (?,?,?,?,?,?)",
                                [(occ, ts, o, h, l, c) for ts, o, h, l, c in bars])
                con.execute("insert or replace into fetched values (?,?)", (occ, len(bars)))
            con.commit()
            n_done += len(chunk)
            if n_done % 1000 < BATCH:
                print(f"{n_done}/{len(todo)} contracts stored ({month})", flush=True)
            time.sleep(0.35)
    tot = con.execute("select count(*) from bars").fetchone()[0]
    print(f"LIBRARY COMPLETE: {n_done} fetched this run, {tot} hourly bars stored", flush=True)


if __name__ == "__main__":
    main()
