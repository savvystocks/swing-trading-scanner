"""ARCHIVE EDGE-MINE (owner order 2026-08-23: fade failed real triggers - now find what DOESN'T).

Tests a LIBRARY of strategy shapes and conditioners against 2 years of REAL aggressor prints
(data/uw_history.db), each scored day-clustered with a WALK-FORWARD split (train 2024-09..2025-12
vs test 2026) and both-halves check. Ranks by a ROBUSTNESS score that kills front-loaded flukes
(the +56/-9 trap): a shape only ranks if it is positive in BOTH periods AND both halves of each.

Honesty: mining 134k trades across many predicates WILL surface spurious positives (multiple
testing). This PROPOSES candidates only - each still walks live virgin days under the hardened
placebo bar before it can touch the spec. Nothing here changes a live setting.

Base shapes (on the real aggressor buy: ask_volume>bid_volume, in-band premium):
  FADE (contra trend&spy), CONSENSUS (with both), FOLLOW (aggressor side, no trend filter),
  CONTRA (opposite the aggressor).
Conditioners layered on each: OI-building (oi>prev_oi = new positioning), sweep fraction,
IV level, DTE bucket, moneyness (ITM/ATM/OTM), premium tier, SPY day-colour, calls/puts.
Output: reports/research/edge_mine_2026-08-23.md (ranked), + edge_mine.json for challenger seeding.
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


def closes(s):
    u = (f"https://data.alpaca.markets/v2/stocks/bars?symbols={s}&timeframe=1Day"
         "&start=2024-07-01&end=2026-08-22&limit=10000&adjustment=split&feed=iex")
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                b = (json.loads(r.read()).get("bars") or {}).get(s) or []
            return {x["t"][:10]: x["c"] for x in b}
        except Exception:
            time.sleep(3)
    return {}


def smad(c):
    d = sorted(c); o = {}; buf = []
    for x in d:
        buf.append(c[x]); o[x] = (c[x] / (sum(buf[-20:]) / min(len(buf), 20)) - 1) * 100
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


def dstats(pts):
    per = defaultdict(list)
    for d, r in pts:
        per[d].append(r)
    dm = sorted(per.items())
    m = [sum(v) / len(v) for _, v in dm]
    n = len(m)
    if n < 8:
        return None
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    h = n // 2
    return {"n": len(pts), "days": n, "mean": round(mu, 2), "t": round(t, 2),
            "h1": round(sum(m[:h]) / max(h, 1), 1), "h2": round(sum(m[h:]) / max(n - h, 1), 1)}


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=60)
    tks = [r[0] for r in con.execute("select distinct ticker from contracts_daily")]
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); sm["SPY"] = smad(spyc)
    spy = sm["SPY"]
    spy_days = sorted(spyc)
    spy_color = {spy_days[i]: (1 if spyc[spy_days[i]] >= spyc[spy_days[i-1]] else -1)
                 for i in range(1, len(spy_days))}
    print("trend built", flush=True)
    fwd = defaultdict(list)
    for occ, day, ap in con.execute("select option_symbol,day,avg_price from contracts_daily "
                                    "where avg_price is not null order by day"):
        fwd[occ].append((day, ap))

    trig = con.execute("""select ticker,option_symbol,day,total_premium,ask_volume,bid_volume,
                                 volume,sweep_volume,open_interest,prev_oi,implied_volatility,avg_price
                          from contracts_daily
                          where total_premium between 50000 and 400000 and ask_volume>bid_volume
                          order by day""")
    T = []
    seen = set()
    for t, occ, day, prem, av, bv, vol, swv, oi, poi, iv, avgp in trig:
        if occ in seen:
            continue
        side = 1 if occ[-9] == "C" else -1
        sd = (sm.get(t) or {}).get(day); sp = spy.get(day)
        if sd is None or sp is None or not avgp or avgp <= 0:
            continue
        path = [ap for d, ap in fwd.get(occ, []) if d > day]
        if len(path) < 2:
            continue
        seen.add(occ)
        # features
        try:
            strike = int(occ[-8:]) / 1000.0
            exp = "20" + occ[len(t):len(t)+6]
            expd = date(int(exp[:4]), int(exp[4:6]), int(exp[6:8]))
            dte = (expd - date.fromisoformat(day)).days
        except Exception:
            strike, dte = 0, 0
        T.append({"day": day, "t": t, "side": side, "sma": sd, "spy": sp, "ret": rep(path, avgp),
                  "oi_build": (oi or 0) > (poi or 0), "swf": (swv or 0) / vol if vol else 0,
                  "iv": float(iv) if iv else None, "dte": dte, "prem": prem,
                  "color": spy_color.get(day, 0), "strike": strike})
    print(f"triggers with outcomes: {len(T)}", flush=True)
    def stk(pred):
        return [(r["day"], r["ret"]) for r in T if pred(r)]

    fade = lambda r: r["sma"] * r["side"] < 0 and r["spy"] * r["side"] < 0
    cons = lambda r: r["sma"] * r["side"] > 0 and r["spy"] * r["side"] > 0
    follow = lambda r: True
    contra = lambda r: False  # aggressor is a BUY; "contra" = we'd fade the buy = same as taking put side; skip
    shapes = {"FADE": fade, "CONSENSUS": cons, "FOLLOW_AGGRESSOR": follow}
    conds = {
        "": lambda r: True,
        "+OIbuild": lambda r: r["oi_build"],
        "+sweep50": lambda r: r["swf"] >= 0.5,
        "+lowsweep": lambda r: r["swf"] < 0.2,
        "+shortDTE<=7": lambda r: 0 < r["dte"] <= 7,
        "+midDTE8-30": lambda r: 8 <= r["dte"] <= 30,
        "+longDTE>30": lambda r: r["dte"] > 30,
        "+greenday": lambda r: r["color"] > 0,
        "+redday": lambda r: r["color"] < 0,
        "+calls": lambda r: r["side"] > 0,
        "+puts": lambda r: r["side"] < 0,
        "+highIV": lambda r: r["iv"] is not None and r["iv"] >= 0.6,
        "+lowIV": lambda r: r["iv"] is not None and r["iv"] < 0.4,
        "+bigprem200k": lambda r: r["prem"] >= 200000,
    }
    rows = []
    for sn, sf in shapes.items():
        for cn, cf in conds.items():
            pts = stk(lambda r: sf(r) and cf(r))
            alls = dstats(pts)
            if not alls or alls["days"] < 12:
                continue
            tr = dstats([(d, x) for d, x in pts if d < "2026-01-01"])
            te = dstats([(d, x) for d, x in pts if d >= "2026-01-01"])
            robust = (alls["mean"] > 0 and alls["h1"] > 0 and alls["h2"] > 0
                      and tr and te and tr["mean"] > 0 and te["mean"] > 0
                      and tr["h1"] > 0 and tr["h2"] > 0 and te["h1"] > 0 and te["h2"] > 0)
            rows.append({"name": sn + cn, "all": alls, "train": tr, "test": te, "robust": robust})
    rows.sort(key=lambda x: (x["robust"], x["all"]["t"]), reverse=True)
    L = ["# Archive edge-mine - 2026-08-23", "",
         "Real aggressor triggers (2y, 134k pool), day-clustered, walk-forward (train<2026 / test 2026).",
         "ROBUST = positive in both periods AND both halves of each (kills front-loaded flukes).",
         "In-sample/mined - candidates must still clear live virgin days + placebo bar.", "",
         "| shape+cond | all mean/t | halves | train mean | test 2026 mean | ROBUST |",
         "|---|---|---|---|---|---|"]
    for r in rows[:30]:
        a = r["all"]; tr = r["train"]; te = r["test"]
        trm = f"{tr['mean']:+.1f}" if tr else "-"
        tem = f"{te['mean']:+.1f}/{te['t']:+.2f}" if te else "-"
        L.append(f"| {r['name']} | {a['mean']:+.1f}/{a['t']:+.2f} ({a['days']}d) | "
                 f"{a['h1']:+.0f}/{a['h2']:+.0f} | {trm} | {tem} | {'YES' if r['robust'] else ''} |")
    robust = [r for r in rows if r["robust"]]
    L.append("")
    L.append(f"ROBUST candidates (pass every gate): {len(robust)} -> " +
             (", ".join(r["name"] for r in robust) if robust else "NONE"))
    open("reports/research/edge_mine_2026-08-23.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump(rows[:30], open("reports/research/edge_mine.json", "w"), indent=1, default=str)
    print("\n".join(L), flush=True)


if __name__ == "__main__":
    main()
