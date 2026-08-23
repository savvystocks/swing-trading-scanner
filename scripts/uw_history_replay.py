"""UW HISTORY REPLAY (owner 2026-08-23: run the live fade rule on 2 years of REAL triggers).

Uses data/uw_history.db (per-contract daily rows) as BOTH trigger and outcome path:
  trigger  = a contract-day with premium in-band AND ask-side dominant (aggressive BUY of that
             option) -> flow_type = call:bullish / put:bearish, the real aggressor signal.
  shape    = fade if the flow side opposes BOTH the ticker's 20d-SMA trend AND SPY's trend that
             day (stock closes pulled free from Alpaca; SPY too).
  outcome  = the SAME contract's forward daily last_price path -> live exit replay (trail 50/20,
             stop -50). One trade per contract per first qualifying day.
Reports: day-clustered day-mean / t / halves for the real-trigger fade, split WALK-FORWARD
(2024-09..2025-12 vs 2026), and by premium tier. This is the honest historical test of the
live rule that the free corpus could only approximate. Still not a substitute for virgin days -
tuned-on-the-past stays in-sample - but it validates the trigger the live book actually uses.
Output: reports/research/uw_replay_2026-08-23.md
"""
import json
import math
import os
import sqlite3
import time
import urllib.request
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
DB = "data/uw_history.db"
H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}


def stock_closes(sym):
    url = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={sym}&timeframe=1Day"
           "&start=2024-07-01&end=2026-08-22&limit=10000&adjustment=split&feed=iex")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
                bars = (json.loads(r.read()).get("bars") or {}).get(sym) or []
            return {b["t"][:10]: b["c"] for b in bars}
        except Exception:
            time.sleep(3)
    return {}


def sma_dist(closes):
    days = sorted(closes)
    out, buf = {}, []
    for d in days:
        buf.append(closes[d])
        sma = sum(buf[-20:]) / min(len(buf), 20)
        out[d] = (closes[d] / sma - 1) * 100 if sma else 0.0
    return out


def replay(path, e, stop=-50, trig=50, give=0.20):
    peak, on = -999.0, False
    for b in path:
        if not b or e <= 0:
            continue
        r = (b / e - 1) * 100
        if r >= trig:
            on = True
        if on:
            peak = max(peak, r)
            if r <= peak * (1 - give):
                return r
        if r <= stop:
            return stop
    return (path[-1] / e - 1) * 100 if path and path[-1] and e > 0 else 0.0


def stats(pts):
    per = defaultdict(list)
    for d, r in pts:
        per[d].append(r)
    dm = sorted((d, sum(v) / len(v)) for d, v in per.items())
    if not dm:
        return None
    m = [x for _, x in dm]
    n = len(m)
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    h = n // 2
    return (len(pts), n, round(mu, 2), round(t, 2),
            round(sum(m[:h]) / max(h, 1), 1), round(sum(m[h:]) / max(n - h, 1), 1))


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=60)
    tickers = [r[0] for r in con.execute("select distinct ticker from contracts_daily")]
    print(f"tickers: {len(tickers)}", flush=True)
    smad = {}
    for t in tickers + ["SPY"]:
        smad[t] = sma_dist(stock_closes(t))
        time.sleep(0.2)
    spy = smad.get("SPY", {})
    print("stock trend built", flush=True)

    # forward path per contract: ordered daily last_price across the archive
    fwd = defaultdict(list)
    for occ, day, lp in con.execute(
            "select option_symbol, day, last_price from contracts_daily where last_price is not null order by day"):
        fwd[occ].append((day, lp))

    seen = set()
    trig = con.execute("""select ticker, option_symbol, day, total_premium, ask_volume, bid_volume,
                                 nbbo_ask, avg_price
                          from contracts_daily
                          where total_premium between 50000 and 400000 and ask_volume > bid_volume
                          order by day""")
    fade, whale_rows = [], []
    for t, occ, day, prem, av, bv, ask, avgp in trig:
        if occ in seen:
            continue
        cp = occ[-9]
        side = 1 if cp == "C" else -1
        sd = (smad.get(t) or {}).get(day)
        sp = spy.get(day)
        if sd is None or sp is None:
            continue
        if not (sd * side < 0 and sp * side < 0):     # fade shape
            continue
        e = ask or avgp
        path = [lp for d, lp in fwd.get(occ, []) if d > day]
        if not e or e <= 0 or len(path) < 2:
            continue
        seen.add(occ)
        fade.append((day, replay(path, e)))
    # whale tier, same shape, 400k-1M
    seen_w = set()
    for t, occ, day, prem, av, bv, ask, avgp in con.execute(
            """select ticker, option_symbol, day, total_premium, ask_volume, bid_volume, nbbo_ask, avg_price
               from contracts_daily where total_premium between 400000 and 1000000 and ask_volume > bid_volume
               order by day"""):
        if occ in seen_w:
            continue
        cp = occ[-9]; side = 1 if cp == "C" else -1
        sd = (smad.get(t) or {}).get(day); sp = spy.get(day)
        if sd is None or sp is None or not (sd * side < 0 and sp * side < 0):
            continue
        e = ask or avgp
        path = [lp for d, lp in fwd.get(occ, []) if d > day]
        if not e or e <= 0 or len(path) < 2:
            continue
        seen_w.add(occ)
        whale_rows.append((day, replay(path, e)))

    def line(name, pts):
        s = stats(pts)
        return (f"| {name} | {s[0]} | {s[1]} | {s[2]:+.2f}% | {s[3]:+.2f} | {s[4]:+.1f}/{s[5]:+.1f} |"
                if s else f"| {name} | 0 | - | - | - | - |")

    early = [(d, r) for d, r in fade if d < "2026-01-01"]
    late = [(d, r) for d, r in fade if d >= "2026-01-01"]
    L = ["# UW real-trigger fade replay - 2026-08-23", "",
         "Live rule on 2 years of REAL aggressor prints (ask-side dominant, in-band), outcomes",
         "from each contract's own forward last_price path. In-sample (rule chosen on the past);",
         "validates the trigger, not a substitute for virgin days.", "",
         "| slice | trades | days | day-mean | t | halves |", "|---|---|---|---|---|---|",
         line("FADE all (2y)", fade),
         line("FADE 2024-09..2025-12 (walk-fwd train)", early),
         line("FADE 2026 (walk-fwd test)", late),
         line("FADE_WHALE 400k-1M (2y)", whale_rows)]
    open("reports/research/uw_replay_2026-08-23.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)


if __name__ == "__main__":
    main()
