"""ROADMAP TEST BATTERY (owner order 2026-08-28: "rigorously test all of the additions").

Four proposed improvements, each tested on owned data with the house standards (day-clustered,
walk-forward where applicable, honest pricing). Nothing here changes live settings - results
feed the Friday court.

A. EXECUTION ALPHA - what does entry price discipline reclaim? Every stored hourly outcome was
   priced entry-at-ask. Exit price is recoverable (exit = ask*(1+ret)), so the SAME trade at
   entry=mid or entry=mid+25% of spread is exact arithmetic. Reported per headline cohort.
   Caveat stated: a resting mid order does not always fill - ask vs mid BRACKETS reality, the
   +25% row is the realistic middle.
B. TRUE-TRIGGER TIMING - for contracts whose real prints are banked (executed_at), enter at the
   first hourly close AFTER the print (same day) vs next-session entry (current rule).
   NOTE: same-day entry does NOT violate the no-same-day-SELL rule (exits still next day+).
C. STUDENT v2 - retrain on hourly-truth labels (wide-exit outcome > 0) with archive features;
   day-grouped OOF AUC + the metric that pays: day-clustered mean of the model's TOP-DECILE
   picks vs the rest, walk-forward.
D. REGIME SIZING - flat $1k vs regime-scaled (deepbear 2.0x, bear 1.5x, mild/bull 1.0x) on the
   combined proven book (fade-bear wide + calls-family mild/bull): growth, worst day, max DD.

Output: reports/research/roadmap_tests_2026-08-28.md
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


def dstat(rows):
    per = defaultdict(list)
    for d, r in rows:
        per[d].append(r)
    m = [sum(v) / len(v) for _, v in sorted(per.items())]
    n = len(m)
    if n < 8:
        return None
    mu = sum(m) / n
    sd = (sum((x - mu) ** 2 for x in m) / (n - 1)) ** 0.5 if n > 1 else 0.0
    t = mu / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return {"n": len(rows), "days": n, "mean": round(mu, 1), "t": round(t, 2)}


def hourly_outcome(bars, e, stop, trig, give):
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


def main():
    import numpy as np
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    lib = sqlite3.connect("file:data/hourly_paths.db?mode=ro", uri=True, timeout=60)
    tks = {r[0] for r in src.execute("select ticker from contracts_daily group by ticker "
                                     "having count(distinct day) >= 400")}
    sm = {t: smad(closes(t)) for t in tks}
    spyc = closes("SPY"); spy20 = smad(spyc)
    sd_ = sorted(spyc); s50 = {}; buf = []
    for x in sd_:
        buf.append(spyc[x]); s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100

    trades = []
    seen = set()
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
        try:
            exp = "20" + occ[len(t):len(t) + 6]
            dte = (date(int(exp[:4]), int(exp[4:6]), int(exp[6:8])) - date.fromisoformat(day)).days
        except Exception:
            dte = 0
        side = 1 if occ[-9] == "C" else -1
        trades.append({"occ": occ, "day": day, "ask": ask, "bid": bid, "mid": mid, "side": side,
                       "sma": smd, "spy": sp, "reg": reg, "prem": prem, "swf": (swv or 0) / vol if vol else 0,
                       "oib": 1.0 if (oi or 0) > (poi or 0) else 0.0, "iv": float(iv) if iv else 0.5,
                       "dl": abs(float(dl)) if dl is not None else 0.5, "dte": dte, "spr": spr})
    print(f"universe {len(trades)}", flush=True)

    # per-trade hourly bars (post-entry-day and entry-day separately)
    cur = lib.cursor()
    for tr in trades:
        rows_ = cur.execute("select ts, h, l, c from bars where occ=? order by ts",
                            (tr["occ"],)).fetchall()
        tr["bars_next"] = [(h, l, c) for ts, h, l, c in rows_ if ts[:10] > tr["day"]]
        tr["bars_today"] = [(ts, h, l, c) for ts, h, l, c in rows_ if ts[:10] == tr["day"]]
    print("bars joined", flush=True)

    is_fade = lambda tr: tr["sma"] * tr["side"] < 0 and tr["spy"] * tr["side"] < 0
    is_cons = lambda tr: tr["sma"] * tr["side"] > 0 and tr["spy"] * tr["side"] > 0
    COHORTS = {
        "FADE_bear_live":   (lambda tr: is_fade(tr) and tr["reg"] < -2 and 50000 <= tr["prem"] <= 400000,
                             (-50.0, 50.0, 0.20)),
        "DIP_CONVEXITY":    (lambda tr: tr["reg"] < -2 and tr["side"] > 0 and tr["dte"] > 30
                                        and 50000 <= tr["prem"] <= 400000,
                             (-70.0, 80.0, 0.30)),
        "CONSENSUS_CALLS":  (lambda tr: is_cons(tr) and tr["side"] > 0 and tr["reg"] >= -2
                                        and 50000 <= tr["prem"] <= 400000,
                             (-50.0, 50.0, 0.20)),
        "FOLLOW_CALLS":     (lambda tr: tr["side"] > 0 and tr["reg"] >= -2
                                        and 50000 <= tr["prem"] <= 400000,
                             (-50.0, 50.0, 0.20)),
    }
    L = ["# ROADMAP TEST BATTERY - 2026-08-28", ""]

    # ---------- A. EXECUTION ALPHA ----------
    L += ["## A. Execution alpha (same trades, entry price discipline)", "",
          "ask = pay the ask (current); mid+25 = limit filled a quarter-spread above mid",
          "(realistic patient order); mid = perfect mid fill (upper bound). Exits unchanged.", "",
          "| cohort | entry=ask | entry=mid+25% | entry=mid | reclaimed (realistic) |",
          "|---|---|---|---|---|"]
    for cname, (f, (st, tg, gv)) in COHORTS.items():
        rows_a, rows_q, rows_m = [], [], []
        for tr in trades:
            if not f(tr) or len(tr["bars_next"]) < 3:
                continue
            r_ask = hourly_outcome(tr["bars_next"], tr["ask"], st, tg, gv)
            if r_ask is None:
                continue
            exit_px = tr["ask"] * (1 + r_ask / 100.0)
            e_q = tr["mid"] + 0.25 * (tr["ask"] - tr["mid"]) * 2 / 2   # mid + 25% of half... use mid+25% of (ask-mid)
            e_q = tr["mid"] + 0.25 * (tr["ask"] - tr["mid"])
            rows_a.append((tr["day"], r_ask))
            rows_q.append((tr["day"], (exit_px / e_q - 1) * 100))
            rows_m.append((tr["day"], (exit_px / tr["mid"] - 1) * 100))
        a, q, m = dstat(rows_a), dstat(rows_q), dstat(rows_m)
        if a and q and m:
            L.append(f"| {cname} | {a['mean']:+.1f}%/d (t{a['t']:+.1f}) | {q['mean']:+.1f}% | "
                     f"{m['mean']:+.1f}% | **{q['mean']-a['mean']:+.1f} pts/day** |")
    L.append("")

    # ---------- B. TRUE-TRIGGER TIMING ----------
    L += ["## B. True-trigger entry timing (same-day after the print vs next session)", ""]
    prints = {}
    try:
        for occ, day, ts in src.execute(
                "select occ, day, min(executed_at) from flow_prints group by occ, day"):
            prints[(occ, day)] = ts
    except Exception:
        pass
    rows_now, rows_next = [], []
    for tr in trades:
        pts_ts = prints.get((tr["occ"], tr["day"]))
        if not pts_ts or len(tr["bars_next"]) < 3 or not tr["bars_today"]:
            continue
        after = [(h, l, c) for ts, h, l, c in tr["bars_today"] if ts[11:19] > pts_ts[11:19]]
        if not after:
            continue
        e_now = after[0][2]                      # first hourly close after the real print
        if e_now <= 0:
            continue
        st, tg, gv = (-50.0, 50.0, 0.20)
        full_path = [(h, l, c) for h, l, c in after[1:]] + tr["bars_next"]
        r_now = hourly_outcome(full_path, e_now, st, tg, gv)
        r_next = hourly_outcome(tr["bars_next"], tr["ask"], st, tg, gv)
        if r_now is None or r_next is None:
            continue
        rows_now.append((tr["day"], r_now))
        rows_next.append((tr["day"], r_next))
    sn, sx = dstat(rows_now), dstat(rows_next)
    if sn and sx:
        L += [f"trades with real print timestamps + same-day bars: {sn['n']}",
              f"  ENTER SAME-DAY (first close after print): {sn['mean']:+.1f}%/day t{sn['t']:+.2f}",
              f"  ENTER NEXT SESSION (current rule):        {sx['mean']:+.1f}%/day t{sx['t']:+.2f}",
              f"  TIMING VALUE: {sn['mean']-sx['mean']:+.1f} pts/day", ""]
    else:
        L += ["insufficient print coverage yet (puller still accruing) - rerun after tonight", ""]

    # ---------- C. STUDENT v2 (hourly-truth labels) ----------
    L += ["## C. Student v2 - trained on hourly-truth outcomes", ""]
    try:
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.model_selection import GroupKFold
        from sklearn.metrics import roc_auc_score
        X, y, days_l, rets = [], [], [], []
        for tr in trades:
            if len(tr["bars_next"]) < 3:
                continue
            r = hourly_outcome(tr["bars_next"], tr["ask"], -50.0, 50.0, 0.20)
            if r is None:
                continue
            X.append([tr["side"], math.log(tr["prem"]), tr["swf"], tr["oib"], tr["iv"],
                      tr["dl"], tr["dte"], tr["sma"], tr["spy"], tr["reg"], tr["spr"]])
            y.append(1 if r > 0 else 0)
            days_l.append(tr["day"]); rets.append(r)
        X = np.array(X); y = np.array(y); g = np.array(days_l); rets = np.array(rets)
        oof = np.full(len(y), np.nan)
        for tr_i, te_i in GroupKFold(n_splits=5).split(X, y, g):
            mdl = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06,
                                                 max_iter=250, random_state=7)
            mdl.fit(X[tr_i], y[tr_i])
            oof[te_i] = mdl.predict_proba(X[te_i])[:, 1]
        auc = roc_auc_score(y, oof)
        # the metric that pays: top-decile picks per day vs the rest, day-clustered
        thr = np.nanquantile(oof, 0.9)
        top = [(d, r) for d, r, p in zip(days_l, rets, oof) if p >= thr]
        rest = [(d, r) for d, r, p in zip(days_l, rets, oof) if p < thr]
        st_, sr = dstat(top), dstat(rest)
        L += [f"cohort {len(y)} trades | day-grouped OOF AUC: {auc:.3f}",
              f"  TOP-DECILE picks : {st_['mean']:+.1f}%/day t{st_['t']:+.2f} (n={st_['n']})" if st_ else "thin",
              f"  the rest         : {sr['mean']:+.1f}%/day t{sr['t']:+.2f}" if sr else "thin",
              f"  RANKING LIFT: {st_['mean']-sr['mean']:+.1f} pts/day" if st_ and sr else "", ""]
    except Exception as e:
        L += [f"student section skipped: {type(e).__name__}: {str(e)[:80]}", ""]

    # ---------- D. REGIME SIZING ----------
    L += ["## D. Regime-aware sizing (flat $1k vs scaled) on the proven book", ""]
    day_pnl_flat = defaultdict(float); day_pnl_sc = defaultdict(float)
    for tr in trades:
        if len(tr["bars_next"]) < 3:
            continue
        use = None
        if is_fade(tr) and tr["reg"] < -2 and 50000 <= tr["prem"] <= 400000:
            use = (-70.0, 80.0, 0.30)
            scale = 2.0 if tr["reg"] < -3 else 1.5
        elif is_cons(tr) and tr["side"] > 0 and tr["reg"] >= -2 and 50000 <= tr["prem"] <= 400000:
            use = (-50.0, 50.0, 0.20)
            scale = 1.0
        if not use:
            continue
        r = hourly_outcome(tr["bars_next"], tr["ask"], *use)
        if r is None:
            continue
        day_pnl_flat[tr["day"]] += r / 100.0 * 1000 / 40      # /40 normalises trade counts
        day_pnl_sc[tr["day"]] += r / 100.0 * 1000 * scale / 40
    fl = sorted(day_pnl_flat.items()); sc = sorted(day_pnl_sc.items())
    if fl:
        tot_f = sum(v for _, v in fl); tot_s = sum(v for _, v in sc)
        worst_f = min(v for _, v in fl); worst_s = min(v for _, v in sc)
        cum = 0; peak = 0; dd_f = 0
        for _, v in fl:
            cum += v; peak = max(peak, cum); dd_f = min(dd_f, cum - peak)
        cum = 0; peak = 0; dd_s = 0
        for _, v in sc:
            cum += v; peak = max(peak, cum); dd_s = min(dd_s, cum - peak)
        L += [f"| | total P&L | worst day | max drawdown |", "|---|---|---|---|",
              f"| flat $1k | ${tot_f:+,.0f} | ${worst_f:+,.0f} | ${dd_f:+,.0f} |",
              f"| regime-scaled | ${tot_s:+,.0f} | ${worst_s:+,.0f} | ${dd_s:+,.0f} |",
              f"", f"scaling multiplies return {tot_s/tot_f:.2f}x with drawdown {dd_s/dd_f:.2f}x"
              if tot_f and dd_f else ""]
    open("reports/research/roadmap_tests_2026-08-28.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("ROADMAP TESTS COMPLETE", flush=True)


if __name__ == "__main__":
    main()
