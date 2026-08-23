"""STRUCTURE STUDY (owner order 2026-08-23: build the delta/DTE filter - EVIDENCE FIRST).

The archive-student ranked delta (+0.055) and DTE (+0.024) as the only real predictors, but it
was trained on P(win). Our live exit is ASYMMETRIC (trail +50%/give 20%): cheap OTM tickets lose
often and occasionally triple. So a "higher delta" filter could RAISE win-rate and LOWER return.
This study settles it on the metric that pays: day-clustered MEAN RETURN under the live exit
replay, per |delta| and DTE bucket, walk-forward split, with win-rate shown alongside so the
divergence (if any) is visible.

Buckets: |delta| .05-.15 / .15-.30 / .30-.45 / .45-.60 / .60-.80 / .80+ ; DTE 0-7 / 8-21 / 22-45
/ 46-90 / 90+ . Also the joint grid, and the LIVE BOOK's current cell (4% OTM ~35dte ~ delta .30-.45)
so the change is measured against what we actually do today.
Output: reports/research/structure_study_2026-08-23.md
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
H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}


def closes(s):
    u = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={s}&timeframe=1Day"
         "&start=2024-05-01&end=2026-08-22&limit=10000&adjustment=split&feed=iex")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                b = (json.loads(r.read()).get("bars") or {}).get(s) or []
            return {x["t"][:10]: x["c"] for x in b}
        except Exception:
            time.sleep(3)
    return {}


def smad(c, n=20):
    d = sorted(c); o = {}; buf = []
    for x in d:
        buf.append(c[x]); o[x] = (c[x] / (sum(buf[-n:]) / min(len(buf), n)) - 1) * 100
    return o


def rep(path, e, stop=-50, trig=50, g=0.20):
    pk, on = -999.0, False
    for b in path:
        if not b or e <= 0:
            continue
        r = (b / e - 1) * 100
        if r >= trig:
            on = True
        if on:
            pk = max(pk, r)
            if r <= pk * (1 - g):
                return r
        if r <= stop:
            return stop
    return (path[-1] / e - 1) * 100 if path and path[-1] and e > 0 else 0.0


def dstat(rows):
    """rows = [(day, ret)] -> day-clustered mean, t, n, win-rate."""
    per = defaultdict(list)
    for d, r in rows:
        per[d].append(r)
    m = [sum(v) / len(v) for _, v in sorted(per.items())]
    n = len(m)
    if n < 10:
        return None
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    wins = sum(1 for _, r in rows if r > 0) / len(rows)
    return {"n": len(rows), "days": n, "mean": mu, "t": t, "win": wins}


DB = [(0.05, 0.15), (0.15, 0.30), (0.30, 0.45), (0.45, 0.60), (0.60, 0.80), (0.80, 1.01)]
TB = [(0, 7), (8, 21), (22, 45), (46, 90), (91, 400)]


def main():
    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    tks = [r[0] for r in con.execute("select distinct ticker from contracts_daily")]
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); spy = smad(spyc)
    fwd = defaultdict(list)
    for occ, day, ap in con.execute("select option_symbol,day,avg_price from contracts_daily "
                                    "where avg_price is not null order by day"):
        fwd[occ].append((day, ap))
    rows = []
    seen = set()
    for t, occ, day, av, bv, dl, avgp in con.execute(
            """select ticker,option_symbol,day,ask_volume,bid_volume,delta,avg_price
               from contracts_daily
               where total_premium between 50000 and 400000 and ask_volume>bid_volume
                 and delta is not null order by day"""):
        if occ in seen:
            continue
        smd = (sm.get(t) or {}).get(day); sp = spy.get(day)
        if smd is None or sp is None or not avgp or avgp <= 0:
            continue
        path = [ap for d, ap in fwd.get(occ, []) if d > day]
        if len(path) < 2:
            continue
        seen.add(occ)
        try:
            exp = "20" + occ[len(t):len(t) + 6]
            dte = (date(int(exp[:4]), int(exp[4:6]), int(exp[6:8])) - date.fromisoformat(day)).days
        except Exception:
            continue
        rows.append({"day": day, "d": abs(float(dl)), "dte": dte, "ret": rep(path, avgp)})
    print(f"cohort {len(rows)}", flush=True)

    L = ["# Structure study - 2026-08-23 (does delta/DTE pay, or only win more?)", "",
         "Real triggers, live exit replay (trail 50/20, stop -50). MEAN = day-clustered mean",
         "return (the metric that pays). WIN = per-trade win-rate (what the student optimised).",
         "If MEAN and WIN disagree, WIN is the trap - asymmetric exits pay runners, not accuracy.", "",
         "## By |delta|", "", "| bucket | trades | day-mean | t | win-rate | 2026 mean |", "|---|---|---|---|---|---|"]
    for lo, hi in DB:
        sub = [(r["day"], r["ret"]) for r in rows if lo <= r["d"] < hi]
        s = dstat(sub)
        te = dstat([(d, x) for d, x in sub if d >= "2026-01-01"])
        if s:
            L.append(f"| {lo:.2f}-{hi:.2f} | {s['n']} | {s['mean']:+.2f}% | {s['t']:+.2f} | "
                     f"{s['win']:.3f} | {te['mean']:+.2f}% |" if te else
                     f"| {lo:.2f}-{hi:.2f} | {s['n']} | {s['mean']:+.2f}% | {s['t']:+.2f} | {s['win']:.3f} | - |")
    L += ["", "## By DTE", "", "| bucket | trades | day-mean | t | win-rate | 2026 mean |", "|---|---|---|---|---|---|"]
    for lo, hi in TB:
        sub = [(r["day"], r["ret"]) for r in rows if lo <= r["dte"] <= hi]
        s = dstat(sub)
        te = dstat([(d, x) for d, x in sub if d >= "2026-01-01"])
        if s:
            L.append(f"| {lo}-{hi}d | {s['n']} | {s['mean']:+.2f}% | {s['t']:+.2f} | "
                     f"{s['win']:.3f} | {te['mean']:+.2f}% |" if te else
                     f"| {lo}-{hi}d | {s['n']} | {s['mean']:+.2f}% | {s['t']:+.2f} | {s['win']:.3f} | - |")
    L += ["", "## Joint grid (day-mean %, blank = thin)", "",
          "| delta \\ DTE | " + " | ".join(f"{a}-{b}d" for a, b in TB) + " |",
          "|---|" + "---|" * len(TB)]
    for lo, hi in DB:
        cells = []
        for a, b in TB:
            s = dstat([(r["day"], r["ret"]) for r in rows if lo <= r["d"] < hi and a <= r["dte"] <= b])
            cells.append(f"{s['mean']:+.1f} ({s['n']})" if s else "-")
        L.append(f"| {lo:.2f}-{hi:.2f} | " + " | ".join(cells) + " |")
    # the live book's current cell: ~4% OTM, 35 DTE -> delta ~.30-.45, dte 22-45
    cur = dstat([(r["day"], r["ret"]) for r in rows if 0.30 <= r["d"] < 0.45 and 22 <= r["dte"] <= 45])
    best = None
    for lo, hi in DB:
        for a, b in TB:
            s = dstat([(r["day"], r["ret"]) for r in rows if lo <= r["d"] < hi and a <= r["dte"] <= b])
            if s and s["n"] >= 300 and (best is None or s["mean"] > best[0]["mean"]):
                best = (s, (lo, hi), (a, b))
    L += ["", "## Verdict", ""]
    if cur:
        L.append(f"LIVE BOOK today (4% OTM ~35dte = delta .30-.45, 22-45d): day-mean {cur['mean']:+.2f}%, "
                 f"t {cur['t']:+.2f}, win {cur['win']:.3f}, n={cur['n']}")
    if best:
        s, (dlo, dhi), (tlo, thi) = best
        L.append(f"BEST cell (n>=300): delta {dlo:.2f}-{dhi:.2f}, DTE {tlo}-{thi}d -> day-mean "
                 f"{s['mean']:+.2f}%, t {s['t']:+.2f}, win {s['win']:.3f}, n={s['n']}")
        if cur:
            L.append(f"LIFT vs live book: {s['mean'] - cur['mean']:+.2f} pts/trade-day")
    L.append("")
    L.append("If the best cell is HIGHER delta than .30-.45 AND its day-mean beats the live cell, the "
             "structural filter is real. If win-rate rises but day-mean does NOT, the filter is a TRAP "
             "(accuracy bought with lost runners) and must NOT be built.")
    open("reports/research/structure_study_2026-08-23.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)


if __name__ == "__main__":
    main()
