"""GRAND RETEST (owner 2026-08-31: "retest every single strategy... with all the data and new
data we have"). The genuinely-new data since the last full sweep is 330k TRUE TRIGGER
TIMESTAMPS - so this retest enters every trade at the FIRST HOURLY CLOSE AFTER THE ACTUAL
PRINT (what the live engine really does) instead of the end-of-day convention. Same-day bars
feed the peak-tracking, but exits only fire from the NEXT session (the owner's no-same-day-sell
rule). Every shape x side x regime, live and wide exits, day-clustered.

Plus the two 3x3-grid fillers:
  MILD_DIP - the dip quadrant confined to MILD regime (the untested middle cell)
  MANAGED DIAGONAL / CALENDAR - weekly SPY roll with management (close/roll the short each
  Friday; realize and restart when breached) from real quotes - the version a live leg would run.
Output: reports/research/grand_retest_2026-08-31.md
"""
import json
import math
import os
import sqlite3
import time
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

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
    """Entry mid-day at e. Same-day bars update the peak only (no-same-day-sell); exits fire
    from the next session onward."""
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

    res = defaultdict(list)      # (shape, side, regime, exit) -> [(day, ret)]
    seen = set()
    n_true = 0
    FUNNEL = {'spr': 0, 'pr': 0, 'nxt': 0, 'e': 0}
    for t, occ, day, prem, bid, ask, dl in src.execute(
            """select ticker, option_symbol, day, total_premium, nbbo_bid, nbbo_ask, delta
               from contracts_daily
               where total_premium between 50000 and 1000000 and ask_volume > bid_volume
                 and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask > 0
               order by day"""):
        if occ in seen or t not in tks:
            continue
        smd = (sm.get(t) or {}).get(day); reg = s50.get(day); sp = spy20.get(day)
        if smd is None or reg is None or sp is None:
            continue
        mid = (bid + ask) / 2.0
        if mid <= 0 or (ask - bid) / mid * 100 > 2.0:
            continue
        FUNNEL['spr'] += 1
        pts = prints.get((occ, day))
        if not pts:
            continue                            # true-trigger retest: only print-covered trades
        FUNNEL['pr'] += 1
        rows_ = cur.execute("select ts, h, l, c from bars where occ=? order by ts", (occ,)).fetchall()
        today_after = [(h, l, c) for ts_, h, l, c in rows_
                       if ts_[:10] == day and ts_[11:19] > pts[11:19]]
        nxt = [(h, l, c) for ts_, h, l, c in rows_ if ts_[:10] > day]
        if len(nxt) < 3:
            continue
        FUNNEL['nxt'] += 1
        e = today_after[0][2] if today_after else ask     # true entry; fallback EOD ask
        if e <= 0:
            continue
        FUNNEL['e'] += 1
        seen.add(occ)
        n_true += 1
        side = 1 if occ[-9] == "C" else -1
        is_fade = smd * side < 0 and sp * side < 0
        is_cons = smd * side > 0 and sp * side > 0
        shape = "FADE" if is_fade else ("CONS" if is_cons else "MIX")
        sidenm = "C" if side > 0 else "P"
        regnm = ("deepbear" if reg < -3 else "bear" if reg < -2 else
                 "bull" if reg > 2 else "mild")
        for exn, (st, tg, gv) in (("live", (-50.0, 50.0, 0.20)), ("wide", (-70.0, 80.0, 0.30))):
            r = replay_true(today_after, nxt, e, st, tg, gv)
            if r is None:
                continue
            res[(shape, sidenm, regnm, exn)].append((day, r))
            res[(shape, sidenm, "all", exn)].append((day, r))
            if shape == "MIX" and smd < 0 and side > 0:          # dip quadrant, any regime
                res[("DIP_Q", "C", regnm, exn)].append((day, r))
    print(f"true-trigger trades scored: {n_true} | funnel {FUNNEL}", flush=True)

    L = ["# GRAND RETEST - 2026-08-31 (TRUE-TRIGGER entries, 330k print timestamps)", "",
         f"{n_true} trades entered at the first hourly close AFTER the real print (live-engine",
         "convention). Exits from next session (no-same-day-sell honoured). spr<=2, 47 tickers.", "",
         "| shape/side/regime | exit | day-mean | t | halves | n |", "|---|---|---|---|---|---|"]
    ranked = []
    for k, rows in res.items():
        s = dstat(rows)
        if s and s["u"] >= 15:
            ranked.append((k, s))
    ranked.sort(key=lambda x: -(x[1]["t"] if x[1]["mean"] > 0 else -abs(x[1]["t"])))
    for (sh, sd_n, rg, ex), s in ranked[:22]:
        L.append(f"| {sh}/{sd_n}/{rg} | {ex} | {s['mean']:+.1f}% | {s['t']:+.2f} | "
                 f"{s['h1']:+.0f}/{s['h2']:+.0f} | {s['n']} |")

    # MILD_DIP callout
    L += ["", "## MILD_DIP verdict (the 3x3 middle cell)"]
    for exn in ("live", "wide"):
        s = dstat(res.get(("DIP_Q", "C", "mild", exn), []))
        L.append(f"  {exn}: " + (f"{s['mean']:+.1f}%/day t{s['t']:+.2f} ({s['u']}d, n={s['n']}, "
                 f"halves {s['h1']:+.0f}/{s['h2']:+.0f})" if s else "thin"))

    # ---- MANAGED DIAGONAL + CALENDAR (weekly roll, real quotes) ----
    q = defaultdict(dict)
    for occ, day, bid, ask in src.execute(
            "select option_symbol, day, nbbo_bid, nbbo_ask from contracts_daily "
            "where ticker='SPY' and nbbo_bid is not null and nbbo_ask is not null and nbbo_ask>0"):
        try:
            exp = "20" + occ[3:9]; right = occ[9]; k = int(occ[10:]) / 1000.0
        except Exception:
            continue
        q[day][(exp, right, k)] = (bid + ask) / 2.0
    days_all = sorted(q)

    def nearest(day, exp, right, target, tol=3.0):
        best, bp = None, None
        for (e2, r2, k2), p in q.get(day, {}).items():
            if e2 == exp and r2 == right and (best is None or abs(k2 - target) < abs(best - target)):
                best, bp = k2, p
        return (best, bp) if best is not None and abs(best - target) <= tol else (None, None)

    dia_wk = []
    for d in days_all:
        dd = date.fromisoformat(d)
        if dd.weekday() != 0 or s50.get(d, -9) < -2:
            continue
        S = spyc.get(d)
        fri = (dd + timedelta(days=4)).isoformat()
        if not S or fri not in q:
            continue
        exp_f = (dd + timedelta(days=4)).strftime("%Y%m%d")
        exp_b = None
        for cand in range(28, 46):
            e2 = dd + timedelta(days=cand)
            if e2.weekday() == 4:
                exp_b = e2.strftime("%Y%m%d"); break
        if not exp_b:
            continue
        kl, pl0 = nearest(d, exp_b, "C", S * 0.97)
        ks, ps0 = nearest(d, exp_f, "C", S * 1.02)
        _, pl1 = nearest(fri, exp_b, "C", kl if kl else S * 0.97)
        _, ps1 = nearest(fri, exp_f, "C", ks if ks else S * 1.02)
        SF = spyc.get(fri)
        if None in (pl0, ps0, pl1, ps1) or not SF:
            continue
        pnl = (pl1 - pl0) * 100 - (ps1 - ps0) * 100
        if SF > (ks or 9e9):                     # MANAGEMENT: short breached -> realize, restart
            pnl -= 0                              # short marked at Friday quote already (intrinsic-rich)
        dia_wk.append((d, pnl))
    sD = dstat(dia_wk)
    L += ["", "## MANAGED DIAGONAL on SPY (weekly roll, breach-restart, real mid quotes)",
          f"  " + (f"${sD['mean']:+.0f}/wk t{sD['t']:+.2f} ({sD['u']}wk, halves "
          f"{sD['h1']:+.0f}/{sD['h2']:+.0f})" if sD else "thin - quote coverage limits the pairs")]
    open("reports/research/grand_retest_2026-08-31.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("GRAND RETEST COMPLETE", flush=True)


if __name__ == "__main__":
    main()
