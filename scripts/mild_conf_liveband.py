"""LIVE-BAND VERIFICATION of the DIP_CONF_MILD cell (adversarial review 2026-09-01): the grand
retest's +11.3%/day t2.43 came from premium 50k-1M with no per-contract price cap, but the live
funnel only reaches premium 50k-400k and ask $0.30-$4.00. Re-run the exact cell restricted to
what the live probe can actually buy. If the edge dies in the live band, the spec evidence block
must say so before the court cites it."""
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
    for band, pmin, pmax, amin, amax in (("liveband", 50000, 400000, 0.30, 4.00),
                                         ("fullband", 50000, 1000000, 0.0, 1e9)):
        seen.clear()
        for t, occ, day, prem, bid, ask in src.execute(
                """select ticker, option_symbol, day, total_premium, nbbo_bid, nbbo_ask
                   from contracts_daily
                   where total_premium between ? and ? and ask_volume > bid_volume
                     and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask > 0
                   order by day""", (pmin, pmax)):
            if occ in seen or t not in tks or occ[-9] != "C":
                continue
            if not (amin <= ask <= amax):
                continue
            smd = (sm.get(t) or {}).get(day); reg = s50.get(day); sp = spy20.get(day)
            if smd is None or reg is None or sp is None:
                continue
            if not (smd < 0 and sp < 0 and -2 <= reg <= 2):
                continue                        # the DIP_CONF_MILD cell exactly
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
            for exn, (st, tg, gv) in (("live", (-50.0, 50.0, 0.20)), ("wide", (-70.0, 80.0, 0.30))):
                r = replay_true(today_after, nxt, e, st, tg, gv)
                if r is not None:
                    res[(band, exn)].append((day, r))

    L = ["# DIP_CONF_MILD LIVE-BAND VERIFICATION - 2026-09-01", "",
         "same cell (MILD 50d + ticker<20d + SPY<20d + calls, true-trigger, spr<=2),",
         "restricted to what the live probe funnel can reach (prem 50-400k, ask $0.30-4.00):", ""]
    for band in ("liveband", "fullband"):
        for exn in ("live", "wide"):
            s = dstat(res.get((band, exn), []))
            L.append(f"  {band}/{exn}: " + (f"{s['mean']:+.1f}%/day t{s['t']:+.2f} "
                     f"({s['u']}d, n={s['n']}, halves {s['h1']:+.0f}/{s['h2']:+.0f})" if s else "thin"))
    open("reports/research/mild_conf_liveband_2026-09-01.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("LIVEBAND CHECK COMPLETE", flush=True)


if __name__ == "__main__":
    main()
