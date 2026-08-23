"""REGIME BACKTEST (owner order 2026-08-23: results across BEAR / MILD / BULL, all conditions).

Splits the real-trigger candidate strategies by SPY market regime and reports day-clustered
day-mean / t / days in each. The decisive beta test: a real edge survives BEAR; pure beta
collapses. HONEST CAVEAT stated in output: 2024-09..2026-08 is mostly bull; the BEAR bucket
is dip/correction days (SPY below its 50d), not a sustained bear market - low-confidence.

Regime per day (SPY vs 50-day SMA):  BULL dist50>+2%,  BEAR dist50<-2%,  MILD between.
Candidates: FADE, CONSENSUS, CONSENSUS+calls, FOLLOW+calls, CONSENSUS+highIV+calls.
Output: reports/research/regime_backtest_2026-08-23.md
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


def st(pts):
    per = defaultdict(list)
    for d, r in pts:
        per[d].append(r)
    m = [sum(v) / len(v) for _, v in sorted(per.items())]
    n = len(m)
    if n < 5:
        return None
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return (len(pts), n, round(mu, 2), round(t, 2))


def main():
    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    tks = [r[0] for r in con.execute("select distinct ticker from contracts_daily")]
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); sm["SPY"] = smad(spyc); spy = sm["SPY"]
    d = sorted(spyc); sma50 = {}; buf = []
    for x in d:
        buf.append(spyc[x]); sma50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100
    def regime(day):
        v = sma50.get(day)
        if v is None:
            return None
        return "BULL" if v > 2 else ("BEAR" if v < -2 else "MILD")
    fwd = defaultdict(list)
    for occ, day, ap in con.execute("select option_symbol,day,avg_price from contracts_daily where avg_price is not null order by day"):
        fwd[occ].append((day, ap))
    T = []; seen = set()
    for t, occ, day, prem, av, bv, iv, avgp in con.execute(
            """select ticker,option_symbol,day,total_premium,ask_volume,bid_volume,implied_volatility,avg_price
               from contracts_daily where total_premium between 50000 and 400000 and ask_volume>bid_volume order by day"""):
        if occ in seen:
            continue
        side = 1 if occ[-9] == "C" else -1
        smd = (sm.get(t) or {}).get(day); sp = spy.get(day); rg = regime(day)
        if smd is None or sp is None or rg is None or not avgp or avgp <= 0:
            continue
        path = [ap for dd, ap in fwd.get(occ, []) if dd > day]
        if len(path) < 2:
            continue
        seen.add(occ)
        T.append({"day": day, "side": side, "sma": smd, "spy": sp, "ret": rep(path, avgp),
                  "iv": float(iv) if iv else 0.5, "rg": rg})
    days_by = defaultdict(set)
    for r in T:
        days_by[r["rg"]].add(r["day"])
    print("regime day counts:", {k: len(v) for k, v in days_by.items()}, flush=True)

    cands = {
        "FADE": lambda r: r["sma"]*r["side"] < 0 and r["spy"]*r["side"] < 0,
        "CONSENSUS": lambda r: r["sma"]*r["side"] > 0 and r["spy"]*r["side"] > 0,
        "CONSENSUS+calls": lambda r: r["sma"]*r["side"] > 0 and r["spy"]*r["side"] > 0 and r["side"] > 0,
        "FOLLOW+calls": lambda r: r["side"] > 0,
        "CONSENSUS+highIV+calls": lambda r: r["sma"]*r["side"] > 0 and r["spy"]*r["side"] > 0 and r["side"] > 0 and r["iv"] >= 0.6,
    }
    L = ["# Regime backtest - 2026-08-23 (bear / mild / bull)", "",
         "Real triggers, day-clustered day-mean%/t per SPY regime (vs 50d SMA: bull>+2, bear<-2).",
         f"Regime day coverage: {dict((k, len(v)) for k, v in days_by.items())}.",
         "CAVEAT: 2024-26 is mostly bull; BEAR = dip/correction days, NOT a sustained bear market.", "",
         "| strategy | BEAR | MILD | BULL |", "|---|---|---|---|"]
    for nm, cf in cands.items():
        cells = []
        for rg in ("BEAR", "MILD", "BULL"):
            s = st([(r["day"], r["ret"]) for r in T if cf(r) and r["rg"] == rg])
            cells.append(f"{s[2]:+.1f}% t{s[3]:+.1f} ({s[1]}d)" if s else "thin")
        L.append(f"| {nm} | {cells[0]} | {cells[1]} | {cells[2]} |")
    open("reports/research/regime_backtest_2026-08-23.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)


if __name__ == "__main__":
    main()
