"""BULL EXPENSIVE-TRIGGER TEST (owner order 2026-09-01, the CONSENSUS-replacement candidate):
the split test located the mild-dip edge in expensive trigger contracts. Same question for the
BULL regime cell: do expensive triggers (ask $4-9, the live-shippable band) beat cheap ones on
bull-regime dip calls, with and without the SPY<20d confirmation gate? True-trigger entries,
trigger-contract outcomes, day-clustered. If a cell clears (t>=2, both halves positive), it
enters the roster as BULL_DIP_X with evidence; otherwise graveyard."""
import json
import math
import os
import sqlite3
import time
import urllib.request
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}


def closes_series(s):
    u = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={s}&timeframe=1Day"
         "&start=2024-05-01&end=2026-08-31&limit=10000&adjustment=split&feed=iex")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                return {x["t"][:10]: x["c"] for x in (json.loads(r.read()).get("bars") or {}).get(s) or []}
        except Exception:
            time.sleep(3)
    return {}


def smad(c, n=20):
    d = sorted(c); o = {}; buf = []
    for x in d:
        buf.append(c[x]); o[x] = (c[x] / (sum(buf[-n:]) / min(len(buf), n)) - 1) * 100
    return o


def dstat(rows):
    per = defaultdict(list)
    for d, r in rows:
        per[d].append(r)
    m = [sum(v) / len(v) for _, v in sorted(per.items())]
    n = len(m)
    if n < 6:
        return None
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    h = n // 2
    return {"n": len(rows), "u": n, "mean": round(mu, 1), "t": round(t, 2),
            "h1": round(sum(m[:h]) / max(h, 1), 1), "h2": round(sum(m[h:]) / max(n - h, 1), 1)}


def replay_true(bars_today_after, bars_next, e, stop, trig, give):
    peak = -999.0
    on = False
    for (h, l, c) in bars_today_after:
        rh = (h / e - 1) * 100
        if rh >= trig:
            on = True
        peak = max(peak, rh)
    for (h, l, c) in bars_next:
        rh = (h / e - 1) * 100; rl = (l / e - 1) * 100
        if rh >= trig:
            on = True
        if on:
            peak = max(peak, rh)
            fl = peak * (1 - give)
            if rl <= fl:
                return fl
        if rl <= stop:
            return stop
    return (bars_next[-1][2] / e - 1) * 100 if bars_next else None


def main():
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=60)
    cur = lib.cursor()
    tks = {r[0] for r in src.execute("select ticker from contracts_daily group by ticker "
                                     "having count(distinct day) >= 400")}
    sm = {t: smad(closes_series(t)) for t in tks}
    spyc = closes_series("SPY"); spy20 = smad(spyc)
    sd_ = sorted(spyc); s50 = {}; buf = []
    for x in sd_:
        buf.append(spyc[x]); s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100
    prints = {}
    for occ, day, ts in src.execute("select occ, day, min(executed_at) from flow_prints group by occ, day"):
        prints[(occ, day)] = ts

    res = defaultdict(list)
    seen = set()
    for t, occ, day, prem, bid, ask in src.execute(
            """select ticker, option_symbol, day, total_premium, nbbo_bid, nbbo_ask
               from contracts_daily
               where total_premium between 50000 and 400000 and ask_volume > bid_volume
                 and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask > 0
               order by day"""):
        if occ in seen or t not in tks or occ[-9] != "C":
            continue
        smd = (sm.get(t) or {}).get(day); reg = s50.get(day); sp = spy20.get(day)
        if smd is None or reg is None or sp is None:
            continue
        if not (reg > 2 and smd < 0):               # BULL regime, ticker dipping
            continue
        band = "exp" if 4.0 < ask <= 9.0 else ("cheap" if 0.30 <= ask <= 4.0 else None)
        if band is None:
            continue
        mid = (bid + ask) / 2.0
        if mid <= 0 or (ask - bid) / mid * 100 > 2.0:
            continue
        pts = prints.get((occ, day))
        if not pts:
            continue
        rows_ = cur.execute("select ts, h, l, c from bars where occ=? order by ts", (occ,)).fetchall()
        today_after = [(h, l, c) for ts_, h, l, c in rows_
                       if ts_[:10] == day and ts_[11:19] > pts[11:19]]
        nxt = [(h, l, c) for ts_, h, l, c in rows_ if ts_[:10] > day]
        if len(nxt) < 3:
            continue
        e = today_after[0][2] if today_after else ask
        if e <= 0:
            continue
        seen.add(occ)
        conf = "spyconf" if sp < 0 else "noconf"
        for exn, (st, tg, gv) in (("live", (-50.0, 50.0, 0.20)), ("wide", (-70.0, 80.0, 0.30))):
            r = replay_true(today_after, nxt, e, st, tg, gv)
            if r is None:
                continue
            res[(band, conf, exn)].append((day, r))
            res[(band, "all", exn)].append((day, r))

    L = ["# BULL EXPENSIVE-TRIGGER TEST - 2026-09-01", "",
         "BULL regime (SPY>+2 vs 50d), ticker<20d, calls, aggressor, prem 50-400k, spr<=2,",
         "true-trigger entries on the trigger contract. exp = ask $4-9 (live band), cheap = $0.30-4.", ""]
    for band in ("exp", "cheap"):
        for conf in ("all", "spyconf", "noconf"):
            for exn in ("live", "wide"):
                s = dstat(res.get((band, conf, exn), []))
                L.append(f"  {band}/{conf}/{exn}: " + (f"{s['mean']:+.1f}%/day t{s['t']:+.2f} "
                         f"({s['u']}d, n={s['n']}, halves {s['h1']:+.0f}/{s['h2']:+.0f})" if s else "thin"))
    open("reports/research/bull_expensive_2026-09-01.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("BULL EXPENSIVE TEST COMPLETE", flush=True)


if __name__ == "__main__":
    main()
