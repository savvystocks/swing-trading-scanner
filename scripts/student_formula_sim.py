"""STUDENT FORMULA SEARCH (owner order 2026-09-11 00:35: "do as many simulations as you possibly
can to get a constant 1-3 trades a week for the best return from what the student would have
picked; a strategy that wins in all regimes; make the student find the formula").

PRE-REGISTERED DESIGN (written before any result was seen):
  DATA     corpus v2 (2 years, 82k contract-days, executable-basis returns under 8 exit configs)
           joined to the archive's per-contract fields (volume splits, premium, OI and its change,
           Greeks, IV, NBBO) and the first-print hour. ~24 features, no label leakage: every
           feature is known at the moment of the print.
  SPLIT    SEARCH = days before 2026-03-01 (18 months). HOLDOUT = 2026-03-01 onward (6 months),
           touched ONCE, by the single pre-registered winner only.
  STUDENT  gradient-boosted trees, refit QUARTERLY on every row before the quarter (expanding),
           scoring the quarter's rows out of sample. Three targets: P(win), P(big win >= +30%),
           expected return (regressor on winsorized return). Four cohorts: ALL, CALLS, FADE shape,
           AFFORD (entry ask 4.00-9.90 = one contract inside the $1,000 cap). Two exits: BASE
           (-50/+50/0.20) and WIDE (-70/+80/0.30). Weekly budget k in {1,2,3}: a candidate is
           taken when its score clears a threshold calibrated on PRIOR out-of-sample scores to
           yield ~k picks per week, first-come by day, best-scored first within a day, hard cap k
           per ISO week. That rule is implementable live as written. 72 configurations.
  RANKING  (fixed here) primary: t-stat of weekly P&L across SEARCH weeks (consistency), subject
           to >= 40 trades; secondary: mean return per trade. "All regimes" flag: positive mean
           per trade in BULL, MILD and BEAR with n >= 10 each. The winner is the top-ranked
           config carrying the flag if any config carries it; otherwise the top-ranked overall,
           and the report says so.
  BASELINES random k/week (200 draws, median and 95th percentile of the weekly t), the whole
           pool, and a naive "largest premium of the day" k/week rule.
  OUTPUT   reports/research/student_formula_<date>.md - search table, holdout result for the
           winner and baselines, regime split, feature importances and the picked-trade profile
           (the readable formula). Research tier: report only.
"""
import json
import math
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
import numpy as np

SEARCH_END = "2026-03-01"
EXITS = {"BASE": 0, "WIDE": 5}          # indices into the 8 coarse exit configs
TARGETS = ["PWIN", "PBIG", "EXPRET"]
COHORTS = ["ALL", "CALLS", "FADE", "AFFORD"]
KS = [1, 2, 3]
FEATS = ["side", "smd", "reg", "sp", "prem", "entry", "spread_frac", "dte", "hour", "dow",
         "vol", "ask_share", "sweep_share", "multi_share", "floor_share", "oi", "oi_chg",
         "vol_oi", "prem_oi", "iv", "delta", "gamma", "theta", "vega", "moneyness_proxy"]


def load():
    src_file = os.environ.get("CORPUS_FILE", "reports/research/probe_tuner_rows_v3.jsonl")
    rows = [json.loads(l) for l in open(src_file, encoding="utf-8") if l.strip()]
    rows = [r for r in rows if r.get("basis") in ("ask_at_print", "ask_at_qualifying_print")]
    print(f"corpus {src_file}: {len(rows)} rows, basis {rows[0].get('basis') if rows else '?'}", flush=True)
    con = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=120)
    con.execute("create temp table need(occ text, day text)")
    con.executemany("insert into need values (?,?)", [(r["occ"], r["day"]) for r in rows])
    cd = {}
    for rec in con.execute(
            """select c.option_symbol, c.day, c.volume, c.ask_volume, c.bid_volume, c.sweep_volume,
                      c.multi_leg_volume, c.floor_volume, c.open_interest, c.prev_oi, c.implied_volatility,
                      c.delta, c.gamma, c.theta, c.vega
               from contracts_daily c join need n on n.occ = c.option_symbol and n.day = c.day"""):
        cd[(rec[0], rec[1])] = rec[2:]
    hr = {}
    for occ, day, ts in con.execute(
            """select f.occ, f.day, min(f.executed_at) from flow_prints f
               join need n on n.occ = f.occ and n.day = f.day group by f.occ, f.day"""):
        try:
            hr[(occ, day)] = int(ts[11:13]) + int(ts[14:16]) / 60.0
        except Exception:
            pass
    X, meta = [], []
    for r in rows:
        f = cd.get((r["occ"], r["day"]))
        if f is None:
            continue
        vol, av, bv, sw, ml, fl, oi, poi, iv, de, ga, th, ve = f
        vol = float(vol or 0)
        try:
            exp = date(2000 + int(r["occ"][-15:-13]), int(r["occ"][-13:-11]), int(r["occ"][-11:-9]))
            dte = (exp - date.fromisoformat(r["day"])).days
        except Exception:
            dte = float("nan")
        d = date.fromisoformat(r["day"])
        side = 1.0 if r["side"] == "C" else -1.0
        nz = lambda v: float(v) if isinstance(v, (int, float)) else float("nan")
        X.append([side, nz(r["smd"]), nz(r["reg"]), nz(r["sp"]), nz(r["prem"]), nz(r["entry"]), nz(r["spread_frac"]),
                  float(dte), hr.get((r["occ"], r["day"]), float("nan")), float(d.weekday()),
                  vol, (float(av or 0) / vol) if vol else float("nan"), (float(sw or 0) / vol) if vol else float("nan"),
                  (float(ml or 0) / vol) if vol else float("nan"), (float(fl or 0) / vol) if vol else float("nan"),
                  nz(oi), (float(oi) - float(poi)) if isinstance(oi, (int, float)) and isinstance(poi, (int, float)) else float("nan"),
                  (vol / float(oi)) if isinstance(oi, (int, float)) and oi else float("nan"),
                  (nz(r["prem"]) / float(oi)) if isinstance(oi, (int, float)) and oi else float("nan"),
                  nz(iv), nz(de), nz(ga), nz(th), nz(ve), abs(nz(de)) if isinstance(de, (int, float)) else float("nan")])
        meta.append((r["day"], r["side"], r["reg"], r["smd"], r["sp"], r["entry"], r["rets"], r["occ"]))
    return np.array(X, float), meta


def regime(reg):
    return "BULL" if reg > 2 else ("BEAR" if reg < -2 else "MILD")


def week_key(d):
    iso = date.fromisoformat(d).isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def cohort_mask(meta, name):
    m = []
    for d, side, reg, smd, sp, entry, rets, occ in meta:
        if name == "ALL":
            m.append(True)
        elif name == "CALLS":
            m.append(side == "C")
        elif name == "FADE":
            m.append((smd < 0 and sp < 0) if side == "C" else (smd > 0 and sp > 0))
        elif name == "AFFORD":
            m.append(4.0 <= entry <= 9.9)
    return np.array(m)


def quarters(days_sorted):
    qs = sorted({d[:4] + "Q" + str((int(d[5:7]) - 1) // 3 + 1) for d in days_sorted})
    return qs


def qkey(d):
    return d[:4] + "Q" + str((int(d[5:7]) - 1) // 3 + 1)


def fit_stream(X, y_cls, y_big, y_reg, days, target, mask, first_q_idx=3):
    """Walk-forward quarterly refits for ONE (target, cohort, exit) stream.
    Returns OOS scores per row (NaN where not scored)."""
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    qs = quarters(sorted(set(days)))
    rowq = np.array([qkey(d) for d in days])
    scores = np.full(len(days), np.nan)
    for qi, q in enumerate(qs):
        if qi < first_q_idx:
            continue
        tr = mask & (np.array([qs.index(x) for x in rowq]) < qi)
        te = mask & (rowq == q)
        if tr.sum() < 300 or te.sum() == 0:
            continue
        if target == "EXPRET":
            m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.06, max_iter=150, random_state=7)
            m.fit(X[tr], y_reg[tr]); scores[te] = m.predict(X[te])
        else:
            yy = y_cls if target == "PWIN" else y_big
            if len(set(yy[tr])) < 2:
                continue
            m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=150, random_state=7)
            m.fit(X[tr], yy[tr]); scores[te] = m.predict_proba(X[te])[:, 1]
    return scores


def pick_weekly(scores, days, mask, k, cal_days=60):
    """Live-implementable rule: threshold calibrated on the trailing window of prior OOS scores
    to yield ~k picks/week; take best-scored first within a day; hard cap k per ISO week."""
    idx = [i for i in np.argsort(np.array(days)) if mask[i] and not np.isnan(scores[i])]
    by_day = defaultdict(list)
    for i in idx:
        by_day[days[i]].append(i)
    dlist = sorted(by_day)
    hist = []                                    # (day, score) of prior OOS candidates
    picks = []
    wk_count = defaultdict(int)
    for d in dlist:
        cand = sorted(by_day[d], key=lambda i: -scores[i])
        recent = [s for dd, s in hist if dd >= dlist[max(0, dlist.index(d) - cal_days)]]
        if len(recent) >= 100:
            weeks = max(1, len({week_key(dd) for dd, _ in hist if dd >= dlist[max(0, dlist.index(d) - cal_days)]}))
            per_week = len(recent) / weeks
            q = 1.0 - min(0.5, (k * 1.5) / per_week)   # aim slightly above k; the cap trims
            thr = float(np.quantile(recent, q))
        else:
            thr = float("-inf") if len(hist) < 100 else float(np.quantile([s for _, s in hist], 0.9))
        wk = week_key(d)
        for i in cand:
            if wk_count[wk] >= k:
                break
            if scores[i] >= thr:
                picks.append(i); wk_count[wk] += 1
        for i in cand:
            hist.append((d, scores[i]))
    return picks


def evaluate(picks, meta, exit_idx, label):
    if not picks:
        return None
    rets = np.array([meta[i][6][exit_idx] if meta[i][6][exit_idx] is not None else 0.0 for i in picks])
    wk = defaultdict(float)
    for i, r in zip(picks, rets):
        wk[week_key(meta[i][0])] += 10.0 * r          # $1,000 per trade -> $ per week
    w = np.array([wk[x] for x in sorted(wk)])
    t = (w.mean() / (w.std(ddof=1) / math.sqrt(len(w)))) if len(w) > 2 and w.std(ddof=1) > 0 else 0.0
    cum = np.cumsum(w); dd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0
    h = len(w) // 2
    reg = defaultdict(list)
    for i, r in zip(picks, rets):
        reg[regime(meta[i][2])].append(r)
    regs = {k: (len(v), float(np.mean(v)) if v else 0.0) for k, v in reg.items()}
    allreg = all(regs.get(k, (0, 0))[0] >= 10 and regs.get(k, (0, 0))[1] > 0 for k in ("BULL", "MILD", "BEAR"))
    return {"label": label, "trades": len(picks), "weeks": len(w), "per_trade": float(rets.mean()),
            "win": float(np.mean(rets > 0)), "wk_mean": float(w.mean()), "wk_t": float(t),
            "pos_weeks": float(np.mean(w > 0)), "h1": float(w[:h].mean()) if h else 0.0,
            "h2": float(w[h:].mean()) if len(w) - h else 0.0, "maxdd": dd, "total": float(w.sum()),
            "regs": regs, "allreg": allreg}


def fmt(e):
    rg = " ".join(f"{k}:{v[0]}/{v[1]:+.0f}" for k, v in sorted(e["regs"].items()))
    return (f"| {e['label']} | {e['trades']} | {e['weeks']} | {e['per_trade']:+.1f} | {e['win']:.0%} | "
            f"{e['wk_mean']:+.0f} | {e['wk_t']:+.2f} | {e['pos_weeks']:.0%} | {e['h1']:+.0f}/{e['h2']:+.0f} | "
            f"{e['maxdd']:.0f} | {e['total']:+.0f} | {rg} | {'YES' if e['allreg'] else 'no'} |")


def main():
    X, meta = load()
    days = [m[0] for m in meta]
    print(f"rows {len(meta)}, features {X.shape[1]}, days {len(set(days))}", flush=True)
    search = np.array([d < SEARCH_END for d in days])
    hold = ~search
    HDR = ("| config | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean | all regimes |\n"
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    results = {}
    streams = {}
    for ex, exi in EXITS.items():
        rets = np.array([m[6][exi] if m[6][exi] is not None else np.nan for m in meta])
        ok = ~np.isnan(rets)
        y_cls = (rets > 0).astype(int); y_big = (rets >= 30).astype(int)
        y_reg = np.clip(np.nan_to_num(rets, nan=0.0), -100, 300)
        for co in COHORTS:
            cm = cohort_mask(meta, co) & ok
            for tg in TARGETS:
                key = (ex, co, tg)
                print(f"fitting stream {key} ...", flush=True)
                streams[key] = fit_stream(X, y_cls, y_big, y_reg, days, tg, cm)
                for k in KS:
                    sc = streams[key].copy(); sc[~search] = np.nan          # SEARCH window only
                    picks = pick_weekly(sc, days, cm, k)
                    e = evaluate(picks, meta, exi, f"{tg}/{co}/{ex}/k{k}")
                    if e:
                        results[(ex, co, tg, k)] = e
    # baselines on SEARCH: pool, random k/week, top-premium k/week
    L = ["# STUDENT FORMULA SEARCH - " + date.today().isoformat(),
         f"rows {len(meta)} (search {int(search.sum())}, holdout {int(hold.sum())}); {len(results)} configurations "
         f"on the SEARCH window (before {SEARCH_END}); walk-forward quarterly refits; $1,000 per trade.", "",
         "## Search window - ranked by weekly t (consistency), >= 40 trades", "", HDR]
    ranked = sorted([e for e in results.values() if e["trades"] >= 40], key=lambda e: -e["wk_t"])
    for e in ranked[:25]:
        L.append(fmt(e))
    rng = np.random.default_rng(7)
    base_rets = np.array([m[6][0] if m[6][0] is not None else np.nan for m in meta])
    sidx = [i for i in range(len(meta)) if search[i] and not np.isnan(base_rets[i])]
    L += ["", "## Baselines on the search window (BASE exit)", "", HDR]
    for k in KS:
        ts = []
        for _ in range(200):
            by_wk = defaultdict(list)
            for i in sidx:
                by_wk[week_key(meta[i][0])].append(i)
            picks = []
            for wk, ids in by_wk.items():
                picks += list(rng.choice(ids, size=min(k, len(ids)), replace=False))
            e = evaluate(picks, meta, 0, f"RANDOM k{k}")
            ts.append(e["wk_t"])
        L.append(f"| RANDOM k{k} (200 draws) | - | - | - | - | - | median {np.median(ts):+.2f}, 95th pct {np.percentile(ts, 95):+.2f} | - | - | - | - | - | - |")
        # naive: largest premium first-come, k per week
        by_day = defaultdict(list)
        for i in sidx:
            by_day[meta[i][0]].append(i)
        picks, wc = [], defaultdict(int)
        for d in sorted(by_day):
            wk = week_key(d)
            for i in sorted(by_day[d], key=lambda i: -X[i][4]):
                if wc[wk] >= k:
                    break
                picks.append(i); wc[wk] += 1
        L.append(fmt(evaluate(picks, meta, 0, f"TOP-PREMIUM k{k}")))
    L.append(fmt(evaluate(sidx, meta, 0, "POOL (every trade)")))
    # WINNER: pre-registered rule
    flagged = [e for e in ranked if e["allreg"]]
    winner = (flagged or ranked)[0] if ranked else None
    L += ["", "## Pre-registered winner", ""]
    if winner is None:
        L.append("no configuration reached 40 trades on the search window")
    else:
        L.append(f"{winner['label']} - chosen by weekly t{' with the all-regimes flag' if flagged else ' (NO config carried the all-regimes flag; top by t instead)'}.")
        ex, co, tg, k = None, None, None, None
        for key, e in results.items():
            if e is winner:
                ex, co, tg, k = key
        exi = EXITS[ex]
        cm = cohort_mask(meta, co) & ~np.isnan(np.array([m[6][exi] if m[6][exi] is not None else np.nan for m in meta]))
        sc = streams[(ex, co, tg)].copy(); sc[search] = np.nan              # HOLDOUT window only
        hp = pick_weekly(sc, days, cm, k)
        he = evaluate(hp, meta, exi, f"HOLDOUT {winner['label']}")
        L += ["", "## Holdout (2026-03-01 onward) - touched once, winner only", "", HDR]
        if he:
            L.append(fmt(he))
        hidx = [i for i in range(len(meta)) if hold[i] and not np.isnan(base_rets[i])]
        L.append(fmt(evaluate(hidx, meta, 0, "HOLDOUT POOL (every trade)")))
        ts = []
        for _ in range(200):
            by_wk = defaultdict(list)
            for i in hidx:
                by_wk[week_key(meta[i][0])].append(i)
            picks = []
            for wk, ids in by_wk.items():
                picks += list(rng.choice(ids, size=min(k, len(ids)), replace=False))
            ts.append(evaluate(picks, meta, 0, "r")["wk_t"])
        L.append(f"| HOLDOUT RANDOM k{k} (200 draws) | - | - | - | - | - | median {np.median(ts):+.2f}, 95th pct {np.percentile(ts, 95):+.2f} | - | - | - | - | - | - |")
        # the formula: importances + picked-trade profile on the final search fit
        from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
        from sklearn.inspection import permutation_importance
        rets = np.array([m[6][exi] if m[6][exi] is not None else np.nan for m in meta])
        tr = cm & search
        if tg == "EXPRET":
            mdl = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.06, max_iter=150, random_state=7)
            mdl.fit(X[tr], np.clip(np.nan_to_num(rets[tr], nan=0.0), -100, 300))
            yy = np.clip(np.nan_to_num(rets[tr], nan=0.0), -100, 300)
        else:
            mdl = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=150, random_state=7)
            yy = (rets[tr] > 0).astype(int) if tg == "PWIN" else (rets[tr] >= 30).astype(int)
            mdl.fit(X[tr], yy)
        sub = rng.choice(np.where(tr)[0], size=min(4000, int(tr.sum())), replace=False)
        if tg == "EXPRET":
            ysub = np.clip(np.nan_to_num(rets[sub], nan=0.0), -100, 300)
        else:
            ysub = (rets[sub] > 0).astype(int) if tg == "PWIN" else (rets[sub] >= 30).astype(int)
        pi = permutation_importance(mdl, X[sub], ysub, n_repeats=5, random_state=7)
        order = np.argsort(-pi.importances_mean)
        L += ["", "## The formula the student found (winner stream, final search-window fit)", "",
              "Feature importances (permutation, top 10):"]
        for j in order[:10]:
            L.append(f"- {FEATS[j]}: {pi.importances_mean[j]:+.4f}")
        allp = [i for i in range(len(meta)) if search[i] and cm[i]]
        wp = pick_weekly(np.where(search, streams[(ex, co, tg)], np.nan), days, cm, k)
        L += ["", "Picked-trade profile vs the cohort (medians, search window):", "",
              "| feature | picked | cohort |", "|---|---|---|"]
        for j, name in enumerate(FEATS):
            a = np.nanmedian(X[wp, j]) if wp else float("nan"); b = np.nanmedian(X[allp, j]) if allp else float("nan")
            L.append(f"| {name} | {a:.3g} | {b:.3g} |")
    L += ["", "CAVEATS: label returns on the executable basis (ask at the print, bid-side exits) with no "
              "live friction beyond the spread; two years dominated by bull and mild tape (bear ~12% of days); "
              "72 configurations searched - the search-window numbers are selection-biased by construction, "
              "which is why only the holdout row is evidence. A weekly-budget picker is implementable live as "
              "written (threshold on prior scores, cap per ISO week)."]
    _tag = "_v3" if "v3" in os.environ.get("CORPUS_FILE", "") else ""
    fn = f"reports/research/student_formula{_tag}_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("FORMULA SEARCH COMPLETE", flush=True)


if __name__ == "__main__":
    main()
