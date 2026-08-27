"""STUDENT V2 STRICT WALK-FORWARD (2026-08-28: the check before the ranker goes near the court.

No mixing of eras: train strictly on the past, test strictly on the future, and the top-decile
cut comes from TRAIN-period scores (using the test period's own quantile would leak). Two tests:
  1. Single split: train <2026, test 2026.
  2. Rolling quarters: train everything before quarter Q, test Q - the deployment reality.
Metric: the one that pays - day-clustered mean of top-decile picks vs rest, in the TEST period.
Output: reports/research/student_wf_2026-08-28.md
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
         "&start=2024-05-01&end=2026-08-28&limit=10000&adjustment=split&feed=iex")
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


def hourly_outcome(bars, e, stop=-50.0, trig=50.0, give=0.20):
    peak, on = -999.0, False
    for (h, l, c) in bars:
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
    return (bars[-1][2] / e - 1) * 100 if bars else None


def dstat(rows):
    per = defaultdict(list)
    for d, r in rows:
        per[d].append(r)
    m = [sum(v) / len(v) for _, v in sorted(per.items())]
    n = len(m)
    if n < 5:
        return None
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return {"n": len(rows), "days": n, "mean": round(mu, 1), "t": round(t, 2)}


def main():
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=60)
    tks = {r[0] for r in src.execute("select ticker from contracts_daily group by ticker "
                                     "having count(distinct day) >= 400")}
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); spy20 = smad(spyc)
    sd_ = sorted(spyc); s50 = {}; buf = []
    for x in sd_:
        buf.append(spyc[x]); s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100

    X, y, days_l, rets = [], [], [], []
    seen = set()
    cur = lib.cursor()
    for row in src.execute(
            """select ticker,option_symbol,day,total_premium,ask_volume,bid_volume,volume,
                      sweep_volume,open_interest,prev_oi,implied_volatility,delta,nbbo_bid,nbbo_ask
               from contracts_daily
               where total_premium between 30000 and 1000000 and ask_volume>bid_volume
                 and nbbo_ask is not null and nbbo_bid is not null and nbbo_ask>0 order by day"""):
        t, occ, day, prem, av, bv, vol, swv, oi, poi, iv, dl, bid, ask = row
        if occ in seen or t not in tks:
            continue
        smd = (sm.get(t) or {}).get(day); sp = spy20.get(day); reg = s50.get(day)
        if smd is None or sp is None or reg is None:
            continue
        mid = (bid + ask) / 2.0
        spr = (ask - bid) / mid * 100 if mid > 0 else 99.0
        if spr > 2.0:
            continue
        seen.add(occ)
        bars = [(h, l, c) for ts, h, l, c in
                cur.execute("select ts, h, l, c from bars where occ=? order by ts", (occ,))
                if ts[:10] > day]
        if len(bars) < 3:
            continue
        r = hourly_outcome(bars, ask)
        if r is None:
            continue
        try:
            exp = "20" + occ[len(t):len(t) + 6]
            dte = (date(int(exp[:4]), int(exp[4:6]), int(exp[6:8])) - date.fromisoformat(day)).days
        except Exception:
            dte = 0
        side = 1 if occ[-9] == "C" else -1
        X.append([side, math.log(prem), (swv or 0) / vol if vol else 0,
                  1.0 if (oi or 0) > (poi or 0) else 0.0, float(iv) if iv else 0.5,
                  abs(float(dl)) if dl is not None else 0.5, dte, smd, sp, reg, spr])
        y.append(1 if r > 0 else 0)
        days_l.append(day); rets.append(r)
    X = np.array(X); y = np.array(y); rets = np.array(rets)
    days_arr = np.array(days_l)
    print(f"cohort {len(y)}", flush=True)

    L = ["# STUDENT V2 - STRICT WALK-FORWARD - 2026-08-28", ""]

    def run_split(train_m, test_m, label):
        if train_m.sum() < 5000 or test_m.sum() < 2000:
            return None
        mdl = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06,
                                             max_iter=250, random_state=7)
        mdl.fit(X[train_m], y[train_m])
        p_tr = mdl.predict_proba(X[train_m])[:, 1]
        thr = float(np.quantile(p_tr, 0.9))          # decile cut from TRAIN scores only
        p_te = mdl.predict_proba(X[test_m])[:, 1]
        auc = roc_auc_score(y[test_m], p_te)
        d_te = days_arr[test_m]; r_te = rets[test_m]
        top = [(d, r) for d, r, p in zip(d_te, r_te, p_te) if p >= thr]
        rest = [(d, r) for d, r, p in zip(d_te, r_te, p_te) if p < thr]
        st, sr = dstat(top), dstat(rest)
        return {"label": label, "auc": round(auc, 3),
                "top": st, "rest": sr,
                "picked_frac": round(len(top) / max(test_m.sum(), 1), 3)}

    # 1. single split
    res = run_split(days_arr < "2026-01-01", days_arr >= "2026-01-01", "train<2026 -> test 2026")
    if res:
        L += [f"## 1. {res['label']}", "",
              f"test AUC {res['auc']} | picked {res['picked_frac']:.0%} of test trades",
              f"  TOP picks (train-set decile cut): {res['top']['mean']:+.1f}%/day "
              f"t{res['top']['t']:+.2f} (n={res['top']['n']}, {res['top']['days']}d)" if res['top'] else "thin",
              f"  REST: {res['rest']['mean']:+.1f}%/day t{res['rest']['t']:+.2f}" if res['rest'] else "thin",
              f"  WALK-FORWARD LIFT: {res['top']['mean'] - res['rest']['mean']:+.1f} pts/day"
              if res['top'] and res['rest'] else "", ""]

    # 2. rolling quarters
    L += ["## 2. Rolling quarters (train on all history before Q, test Q)", "",
          "| test quarter | AUC | top-decile mean/t | rest mean | lift |", "|---|---|---|---|---|"]
    qs = [("2025-01-01", "2025-04-01"), ("2025-04-01", "2025-07-01"),
          ("2025-07-01", "2025-10-01"), ("2025-10-01", "2026-01-01"),
          ("2026-01-01", "2026-04-01"), ("2026-04-01", "2026-07-01"),
          ("2026-07-01", "2026-08-28")]
    lifts = []
    for q0, q1 in qs:
        r = run_split(days_arr < q0, (days_arr >= q0) & (days_arr < q1), f"{q0[:7]}")
        if r and r["top"] and r["rest"]:
            lift = r["top"]["mean"] - r["rest"]["mean"]
            lifts.append(lift)
            L.append(f"| {q0[:7]} | {r['auc']} | {r['top']['mean']:+.1f}/t{r['top']['t']:+.1f} | "
                     f"{r['rest']['mean']:+.1f} | {lift:+.1f} |")
        else:
            L.append(f"| {q0[:7]} | thin | | | |")
    if lifts:
        pos = sum(1 for x in lifts if x > 0)
        L += ["", f"quarters with POSITIVE lift: {pos}/{len(lifts)} | median lift "
              f"{sorted(lifts)[len(lifts)//2]:+.1f} pts/day"]
    open("reports/research/student_wf_2026-08-28.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("STUDENT WF COMPLETE", flush=True)


if __name__ == "__main__":
    main()
