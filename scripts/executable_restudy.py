"""EXECUTABLE-PRICE RESTUDY (2026-08-23 - the honesty pass on the whole archive dig).

Every archive replay today (edge-mine, regime, structure) priced entry AND exit at avg_price
(VWAP). The project rule is executable-only: ENTRY AT THE ASK, OUTCOMES ON THE BID. That gap
flatters exactly the contracts with the widest spreads - deep-OTM/long-dated - which is where
the structure study found its best cell. This rebases the findings honestly:

  entry = nbbo_ask on the signal day; forward path = nbbo_bid on later days; live exits
  (trail 50/20, stop -50). Also reports each bucket's median quoted spread and the share that
  would survive the LIVE book's <=2% spread filter - a cell that cannot be traded is not an edge.

Sections: (1) delta x DTE grid, executable; (2) spread reality per bucket; (3) the headline
strategies (FADE by regime, FOLLOW+calls, CONSENSUS+calls) rebased.
Output: reports/research/executable_restudy_2026-08-23.md
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
    h = n // 2
    return {"n": len(rows), "days": n, "mean": mu, "t": t,
            "h1": sum(m[:h]) / max(h, 1), "h2": sum(m[h:]) / max(n - h, 1),
            "win": sum(1 for _, r in rows if r > 0) / len(rows)}


DB_ = [(0.05, 0.15), (0.15, 0.30), (0.30, 0.45), (0.45, 0.60), (0.60, 0.80), (0.80, 1.01)]
TB_ = [(0, 7), (8, 21), (22, 45), (46, 90), (91, 400)]


def main():
    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    tks = [r[0] for r in con.execute("select distinct ticker from contracts_daily")]
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); spy = smad(spyc)
    sd_ = sorted(spyc); s50 = {}; buf = []
    for x in sd_:
        buf.append(spyc[x]); s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100

    # forward BID path per contract (executable exits)
    fwd = defaultdict(list)
    for occ, day, bid in con.execute("select option_symbol,day,nbbo_bid from contracts_daily "
                                     "where nbbo_bid is not null order by day"):
        fwd[occ].append((day, bid))

    rows = []
    seen = set()
    for t, occ, day, av, bv, dl, bid, ask in con.execute(
            """select ticker,option_symbol,day,ask_volume,bid_volume,delta,nbbo_bid,nbbo_ask
               from contracts_daily
               where total_premium between 50000 and 400000 and ask_volume>bid_volume
                 and delta is not null and nbbo_ask is not null and nbbo_bid is not null
                 and nbbo_ask > 0 order by day"""):
        if occ in seen:
            continue
        smd = (sm.get(t) or {}).get(day); sp = spy.get(day); reg = s50.get(day)
        if smd is None or sp is None or reg is None:
            continue
        path = [b for d, b in fwd.get(occ, []) if d > day]
        if len(path) < 2:
            continue
        seen.add(occ)
        try:
            exp = "20" + occ[len(t):len(t) + 6]
            dte = (date(int(exp[:4]), int(exp[4:6]), int(exp[6:8])) - date.fromisoformat(day)).days
        except Exception:
            continue
        mid = (bid + ask) / 2.0
        spr = ((ask - bid) / mid * 100) if mid > 0 else 999.0
        side = 1 if occ[-9] == "C" else -1
        rows.append({"day": day, "d": abs(float(dl)), "dte": dte, "spr": spr,
                     "ret": rep(path, ask),                      # ENTRY AT ASK, EXITS ON BID
                     "side": side, "sma": smd, "spy": sp, "reg": reg})
    print(f"executable cohort {len(rows)}", flush=True)

    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else 0.0

    L = ["# Executable-price restudy - 2026-08-23", "",
         "THE HONESTY PASS. Entry at the ASK, outcomes on the BID (project rule), live exits.",
         "Every other archive result today used VWAP->VWAP and is therefore spread-optimistic.",
         "'pass2%' = share of the bucket that would clear the LIVE book's <=2% spread filter -",
         "an edge in contracts we cannot trade is not an edge.", "",
         "## Delta x DTE (executable day-mean %, n)", "",
         "| delta \\ DTE | " + " | ".join(f"{a}-{b}d" for a, b in TB_) + " |",
         "|---|" + "---|" * len(TB_)]
    for lo, hi in DB_:
        cells = []
        for a, b in TB_:
            s = dstat([(r["day"], r["ret"]) for r in rows if lo <= r["d"] < hi and a <= r["dte"] <= b])
            cells.append(f"{s['mean']:+.1f} ({s['n']})" if s else "-")
        L.append(f"| {lo:.2f}-{hi:.2f} | " + " | ".join(cells) + " |")

    L += ["", "## Spread reality", "",
          "| bucket | median spread | pass<=2% | executable day-mean | t | tradeable day-mean (spread<=2%) |",
          "|---|---|---|---|---|---|"]
    for lo, hi in DB_:
        sub = [r for r in rows if lo <= r["d"] < hi]
        if not sub:
            continue
        s = dstat([(r["day"], r["ret"]) for r in sub])
        tr = dstat([(r["day"], r["ret"]) for r in sub if r["spr"] <= 2.0])
        pas = sum(1 for r in sub if r["spr"] <= 2.0) / len(sub)
        L.append(f"| delta {lo:.2f}-{hi:.2f} | {med([r['spr'] for r in sub]):.1f}% | {pas:.1%} | "
                 f"{s['mean']:+.2f}% | {s['t']:+.2f} | " + (f"{tr['mean']:+.2f}% (n={tr['n']}) |" if tr else "thin |"))
    for a, b in TB_:
        sub = [r for r in rows if a <= r["dte"] <= b]
        if not sub:
            continue
        s = dstat([(r["day"], r["ret"]) for r in sub])
        tr = dstat([(r["day"], r["ret"]) for r in sub if r["spr"] <= 2.0])
        pas = sum(1 for r in sub if r["spr"] <= 2.0) / len(sub)
        L.append(f"| DTE {a}-{b}d | {med([r['spr'] for r in sub]):.1f}% | {pas:.1%} | "
                 f"{s['mean']:+.2f}% | {s['t']:+.2f} | " + (f"{tr['mean']:+.2f}% (n={tr['n']}) |" if tr else "thin |"))

    fade = lambda r: r["sma"] * r["side"] < 0 and r["spy"] * r["side"] < 0
    cons = lambda r: r["sma"] * r["side"] > 0 and r["spy"] * r["side"] > 0
    strat = {"FADE (all)": fade,
             "FADE bear-regime": lambda r: fade(r) and r["reg"] < -2,
             "FADE bull-regime": lambda r: fade(r) and r["reg"] > 2,
             "CONSENSUS": cons,
             "CONSENSUS+calls": lambda r: cons(r) and r["side"] > 0,
             "FOLLOW+calls": lambda r: r["side"] > 0}
    L += ["", "## Headline strategies, rebased (executable, and tradeable = spread<=2%)", "",
          "| strategy | executable mean/t | halves | tradeable mean/t (spread<=2%) |", "|---|---|---|---|"]
    for nm, f in strat.items():
        s = dstat([(r["day"], r["ret"]) for r in rows if f(r)])
        tr = dstat([(r["day"], r["ret"]) for r in rows if f(r) and r["spr"] <= 2.0])
        L.append(f"| {nm} | " + (f"{s['mean']:+.2f}%/{s['t']:+.2f}" if s else "thin") + " | " +
                 (f"{s['h1']:+.0f}/{s['h2']:+.0f}" if s else "-") + " | " +
                 (f"{tr['mean']:+.2f}%/{tr['t']:+.2f} (n={tr['n']})" if tr else "thin") + " |")
    open("reports/research/executable_restudy_2026-08-23.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)


if __name__ == "__main__":
    main()
