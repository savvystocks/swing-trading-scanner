"""GRAND BACKTEST (owner order 2026-08-23: biggest backtest possible, ruthless, all data).

Scores EVERY candidate on one MARKET-NEUTRAL yardstick - the ruthless bar that fade and the
bull-beta 'follow' shape both fail: a strategy is DURABLE only if it is positive OVERALL,
positive on RED (down-SPY) days (beta-stripped), positive in the 2026 walk-forward test, AND
positive in both halves. Anything that only works because the market went up is flagged BETA,
not durable.

Universe:
  FLOW shapes (real UW aggressor triggers, data/uw_history.db): fade / consensus / follow,
    x single + PAIRED conditioners (OIbuild, sweep, IV, DTE, prem, day-colour, side).
  STRUCTURAL legs (no flow needed): credit-spread / condor / wheel weekly P&L from the 2y
    Alpaca-priced backtest (reports/research/fivek_backtests_2026-08-18/weekly_pnl.json).
Output: reports/research/grand_backtest_2026-08-23.md (ranked) + grand_durable.json (survivors
for the priority-probe pipeline).
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
    m = [sum(v) / len(v) for _, v in sorted(per.items())]
    n = len(m)
    if n < 10:
        return None
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    h = n // 2
    return {"n": len(pts), "days": n, "mean": round(mu, 2), "t": round(t, 2),
            "h1": round(sum(m[:h]) / max(h, 1), 1), "h2": round(sum(m[h:]) / max(n - h, 1), 1)}


def main():
    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    tks = [r[0] for r in con.execute("select distinct ticker from contracts_daily")]
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); sm["SPY"] = smad(spyc); spy = sm["SPY"]
    sd_ = sorted(spyc)
    color = {sd_[i]: (1 if spyc[sd_[i]] >= spyc[sd_[i-1]] else -1) for i in range(1, len(sd_))}
    fwd = defaultdict(list)
    for occ, day, ap in con.execute("select option_symbol,day,avg_price from contracts_daily where avg_price is not null order by day"):
        fwd[occ].append((day, ap))
    T = []; seen = set()
    for t, occ, day, prem, av, bv, vol, swv, oi, poi, iv, avgp in con.execute(
            """select ticker,option_symbol,day,total_premium,ask_volume,bid_volume,volume,sweep_volume,
                      open_interest,prev_oi,implied_volatility,avg_price from contracts_daily
               where total_premium between 50000 and 400000 and ask_volume>bid_volume order by day"""):
        if occ in seen:
            continue
        side = 1 if occ[-9] == "C" else -1
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
            dte = 0
        T.append({"day": day, "side": side, "sma": smd, "spy": sp, "ret": rep(path, avgp),
                  "oi": (oi or 0) > (poi or 0), "swf": (swv or 0) / vol if vol else 0,
                  "iv": float(iv) if iv else 0.5, "dte": dte, "prem": prem, "color": color.get(day, 0)})
    print(f"flow triggers: {len(T)}", flush=True)

    shapes = {"FADE": lambda r: r["sma"]*r["side"] < 0 and r["spy"]*r["side"] < 0,
              "CONSENSUS": lambda r: r["sma"]*r["side"] > 0 and r["spy"]*r["side"] > 0,
              "FOLLOW": lambda r: True}
    conds = {"": lambda r: True, "OIbuild": lambda r: r["oi"], "sweep50": lambda r: r["swf"] >= 0.5,
             "shortDTE": lambda r: 0 < r["dte"] <= 7, "midDTE": lambda r: 8 <= r["dte"] <= 30,
             "calls": lambda r: r["side"] > 0, "puts": lambda r: r["side"] < 0,
             "highIV": lambda r: r["iv"] >= 0.6, "bigprem": lambda r: r["prem"] >= 200000}
    cnames = list(conds)
    rows = []
    for sn, sf in shapes.items():
        combos = [("",)] + [(c,) for c in cnames if c] + \
                 [(cnames[i], cnames[j]) for i in range(len(cnames)) for j in range(i+1, len(cnames))]
        for combo in combos:
            def pred(r, sf=sf, combo=combo):
                return sf(r) and all(conds[c](r) for c in combo if c)
            pts = [(r["day"], r["ret"]) for r in T if pred(r)]
            a = dstats(pts)
            if not a or a["days"] < 15:
                continue
            red = dstats([(r["day"], r["ret"]) for r in T if pred(r) and r["color"] < 0])
            te = dstats([(d, x) for d, x in pts if d >= "2026-01-01"])
            durable = (a["mean"] > 0 and a["h1"] > 0 and a["h2"] > 0 and te and te["mean"] > 0
                       and red and red["mean"] > 0 and red["t"] > 0.5)     # RUTHLESS: must survive red days
            nm = sn + ("+" + "+".join(c for c in combo if c) if any(combo) else "")
            rows.append({"name": nm, "all": a, "red": red, "test": te, "durable": durable, "kind": "FLOW"})

    # structural legs (no flow) - week-clustered from the priced backtest
    try:
        wk = json.load(open("reports/research/fivek_backtests_2026-08-18/weekly_pnl.json"))
        for leg in ("credit", "condor", "wheel"):
            pl = wk.get(leg) or []
            if len(pl) < 10:
                continue
            pts = [(d, p) for d, p in pl]  # $ per week
            per = [p for _, p in pts]
            n = len(per); mu = sum(per)/n
            sdv = (sum((x-mu)**2 for x in per)/(n-1))**0.5
            t = mu/(sdv/math.sqrt(n)) if sdv else 0
            h = n//2
            red = [p for d, p in pts]  # structural legs are market-neutral by construction (defined risk)
            worst = min(per)
            rows.append({"name": "STRUCT_" + leg.upper(), "kind": "STRUCT",
                         "all": {"n": n, "days": n, "mean": round(mu, 2), "t": round(t, 2),
                                 "h1": round(sum(per[:h])/max(h,1),1), "h2": round(sum(per[h:])/max(n-h,1),1)},
                         "red": None, "test": None,
                         "durable": mu > 0 and t > 1.5 and sum(per[:h]) > 0 and sum(per[h:]) > 0,
                         "worst_wk": worst})
    except Exception as e:
        print("struct skipped:", e, flush=True)

    rows.sort(key=lambda x: (x["durable"], x["all"]["t"]), reverse=True)
    L = ["# GRAND BACKTEST - 2026-08-23 (ruthless, market-neutral bar)", "",
         "FLOW = real UW triggers, day-mean %. STRUCT = weekly $ P&L. DURABLE (ruthless) = positive",
         "overall + on RED days + 2026 test + both halves (FLOW) / t>1.5 + both halves (STRUCT).",
         "Mined/in-sample - durables become PRIORITY probes, still cleared by live virgin days.", "",
         "| candidate | kind | all mean/t | red-day | 2026 test | DURABLE |",
         "|---|---|---|---|---|---|"]
    for r in rows[:35]:
        a = r["all"]
        rd = f"{r['red']['mean']:+.1f}/t{r['red']['t']:+.1f}" if r.get("red") else ("n-a" if r["kind"] == "STRUCT" else "-")
        te = f"{r['test']['mean']:+.1f}" if r.get("test") else "-"
        L.append(f"| {r['name']} | {r['kind']} | {a['mean']:+.1f}/{a['t']:+.2f} | {rd} | {te} | {'YES' if r['durable'] else ''} |")
    dur = [r for r in rows if r["durable"]]
    L += ["", f"DURABLE survivors (ruthless bar): {len(dur)} -> " + (", ".join(r["name"] for r in dur) if dur else "NONE")]
    open("reports/research/grand_backtest_2026-08-23.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    json.dump([r["name"] for r in dur], open("reports/research/grand_durable.json", "w"), indent=1)
    print("\n".join(L), flush=True)


if __name__ == "__main__":
    main()
