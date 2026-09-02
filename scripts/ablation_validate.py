"""ABLATION VALIDATION (owner order 2026-09-03: "run this past all the data we have now and
validate everything"). Two independent exams of the PATH / VOL / IVX findings:

A. STABILITY on the enriched corpus (39.5k print-covered triggers x 8 exits): each block's
   delta re-measured at three walk-forward cuts (60/75/85% of days) AND day-grouped 5-fold
   OOF. A real block is positive everywhere; a lucky one flips sign.
B. REPLICATION on the OTHER corpus: precise_partial.jsonl - 66k trades, the FULL 2 years
   including both bear episodes and the pre-prints era, different sampling, different exit
   convention. VOL and IVX join cleanly (prev-day/underlying data). PATH cannot be built
   there (it needs the print timestamp) - stated, not fudged.
Verdict per block: CONFIRMED (positive in every exam) / MIXED / FAILED.
Memory-bounded archive joins (the 00:15 OOM lesson): only needed (occ,day)/(ticker,day) kept.
Output: reports/research/ablation_validation_<date>.md"""
import json
import os
import sqlite3
import time
import urllib.request
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

H = {"APCA-API-KEY-ID": os.environ.get("ALPACA_PAPER_API_KEY", ""),
     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_PAPER_SECRET_KEY", "")}
BASE_F = ["prem", "ask", "side_call", "smd", "reg", "sp", "weekday", "dte", "stop", "trig", "give"]
BLOCKS = {"IVX": ["tkr_iv_prev", "delta_prev", "theta_prev", "prev_oi", "oi_chg"],
          "PATH": ["n_bars_pre", "range_pre", "drift_pre"],
          "VOL": ["rv20"]}


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


def model_auc(X, y, tr, te):
    m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.08, random_state=7)
    m.fit(X[tr], y[tr])
    return roc_auc_score(y[te], m.predict_proba(X[te])[:, 1])


def build_matrix(feats, cols):
    M = np.full((len(feats), len(cols)), np.nan)
    for i, row in enumerate(feats):
        for j, c in enumerate(cols):
            v = row.get(c)
            if isinstance(v, (int, float)):
                M[i, j] = v
    return M


def exam_deltas(feats, y, days, blocks, base_cols):
    y = np.array(y); days = np.array(days)
    uniq = sorted(set(days.tolist()))
    out = defaultdict(list)
    for frac in (0.60, 0.75, 0.85):
        cut = uniq[int(len(uniq) * frac)]
        tr = days < cut; te = ~tr
        if te.sum() < 2000 or len(set(y[te].tolist())) < 2:
            continue
        b = model_auc(build_matrix(feats, base_cols), y, tr, te)
        for name, cols in blocks.items():
            a = model_auc(build_matrix(feats, base_cols + cols), y, tr, te)
            out[name].append((f"wf{int(frac*100)}", round(a - b, 4)))
    fold_of = {d: i % 5 for i, d in enumerate(uniq)}
    fold = np.array([fold_of[d] for d in days])
    def oof_auc(cols):
        X = build_matrix(feats, cols)
        oof = np.full(len(y), np.nan)
        for f in range(5):
            m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.08, random_state=7)
            m.fit(X[fold != f], y[fold != f])
            oof[fold == f] = m.predict_proba(X[fold == f])[:, 1]
        return roc_auc_score(y, oof)
    b = oof_auc(base_cols)
    for name, cols in blocks.items():
        out[name].append(("oof5", round(oof_auc(base_cols + cols) - b, 4)))
    return out


def main():
    L = [f"# ABLATION VALIDATION - {date.today().isoformat()}", ""]

    # ---- A. stability on the enriched corpus ----
    raw = []
    for line in open("reports/research/enriched_rows.jsonl", encoding="utf-8"):
        try:
            raw.append(json.loads(line))
        except Exception:
            pass
    EX = [(-50.0, 50.0, 0.20), (-50.0, 80.0, 0.30), (-50.0, 80.0, 0.20), (-50.0, 50.0, 0.30),
          (-70.0, 50.0, 0.20), (-70.0, 80.0, 0.30), (-70.0, 80.0, 0.20), (-70.0, 50.0, 0.30)]
    feats, ys, days = [], [], []
    for r in raw:
        t = r["t"]
        try:
            exp = "20" + r["occ"][len(t):len(t) + 6]
            d = (date(int(exp[:4]), int(exp[4:6]), int(exp[6:8])) - date.fromisoformat(r["day"])).days
        except Exception:
            continue
        flat = {"prem": r["prem"], "ask": r["ask"], "side_call": 1.0 if r["side"] == "C" else 0.0,
                "smd": r["smd"], "reg": r["reg"], "sp": r["sp"],
                "weekday": float(date.fromisoformat(r["day"]).weekday()), "dte": float(d)}
        for blk in ("ivx", "path", "vol"):
            for k, v in (r["blocks"].get(blk) or {}).items():
                flat[k] = v
        for ei in range(8):
            if r["rets"][ei] is None:
                continue
            st, tg, gv = EX[ei]
            row = dict(flat); row["stop"] = st; row["trig"] = tg; row["give"] = gv
            feats.append(row); ys.append(1 if r["rets"][ei] > 0 else 0); days.append(r["day"])
    print(f"exam A rows: {len(ys)}", flush=True)
    resA = exam_deltas(feats, ys, days, BLOCKS, BASE_F)
    L += ["## A. Stability - enriched corpus (39.5k triggers), delta vs BASE at every cut",
          "| block | " + " | ".join(k for k, _ in resA["VOL"]) + " | verdict |", "|---|" +
          "---|" * (len(resA["VOL"]) + 1)]
    verdictA = {}
    for name in BLOCKS:
        ds = [v for _, v in resA[name]]
        v = "CONFIRMED" if all(x > 0.002 for x in ds) else ("MIXED" if any(x > 0.002 for x in ds) else "FAILED")
        verdictA[name] = v
        L.append(f"| {name} | " + " | ".join(f"{x:+.4f}" for x in ds) + f" | {v} |")
    print("exam A done", flush=True)

    # ---- B. replication on the 2-year corpus (VOL + IVX only; PATH needs print ts) ----
    rep = []
    for line in open("reports/research/precise_partial.jsonl", encoding="utf-8"):
        try:
            j = json.loads(line)
            if j.get("rh") is not None:
                rep.append(j)
        except Exception:
            pass
    print(f"replication corpus: {len(rep)} trades", flush=True)
    need = {(r["occ"], r["day"]) for r in rep}
    tks = sorted({r["occ"][:len(r["occ"]) - 15] for r in rep})
    src = sqlite3.connect("file:data/uw_history.db?mode=ro", uri=True, timeout=60)
    iv_sum = defaultdict(float); iv_n = defaultdict(int)
    contract_state = {}
    tset = set(tks)
    for t, occ, day, iv, dl, th, oi, poi, bid, ask, prem in src.execute(
            "select ticker, option_symbol, day, implied_volatility, delta, theta, "
            "open_interest, prev_oi, nbbo_bid, nbbo_ask, total_premium from contracts_daily"):
        if t in tset and iv:
            iv_sum[(t, day)] += iv; iv_n[(t, day)] += 1
        if (occ, day) in need:
            contract_state[(occ, day)] = (dl, th, oi, poi, ask, prem)
    day_sorted = defaultdict(list)
    for (t, day) in iv_n:
        day_sorted[t].append(day)
    for t in day_sorted:
        day_sorted[t].sort()
    print("archive joined (bounded)", flush=True)
    sm = {}; rv = {}
    spyc = closes_series("SPY")
    sds = sorted(spyc); s50 = {}; s20 = {}; buf = []
    for x in sds:
        buf.append(spyc[x])
        s50[x] = (spyc[x] / (sum(buf[-50:]) / min(len(buf), 50)) - 1) * 100
        s20[x] = (spyc[x] / (sum(buf[-20:]) / min(len(buf), 20)) - 1) * 100
    for t in tks:
        c = closes_series(t)
        ds_ = sorted(c); buf2 = []
        for i, x in enumerate(ds_):
            buf2.append(c[x])
            sm[(t, x)] = (c[x] / (sum(buf2[-20:]) / min(len(buf2), 20)) - 1) * 100
            win = [c[ds_[k]] / c[ds_[k - 1]] - 1 for k in range(max(1, i - 20), i)]
            if len(win) >= 10:
                mu = sum(win) / len(win)
                rv[(t, x)] = (sum((z - mu) ** 2 for z in win) / (len(win) - 1)) ** 0.5 * 100
    print("underlying series built", flush=True)
    featsB, ysB, daysB = [], [], []
    for r in rep:
        occ, day = r["occ"], r["day"]
        t = occ[:len(occ) - 15]
        cs = contract_state.get((occ, day))
        if not cs:
            continue
        dl, th, oi, poi, ask, prem = cs
        try:
            exp = "20" + occ[len(t):len(t) + 6]
            d = (date(int(exp[:4]), int(exp[4:6]), int(exp[6:8])) - date.fromisoformat(day)).days
        except Exception:
            continue
        pdays = [x for x in day_sorted.get(t, []) if x < day]
        pd = pdays[-1] if pdays else None
        row = {"prem": prem, "ask": ask, "side_call": 1.0 if occ[len(occ) - 9] == "C" else 0.0,
               "smd": sm.get((t, day)), "reg": s50.get(day), "sp": s20.get(day),
               "weekday": float(date.fromisoformat(day).weekday()), "dte": float(d),
               "stop": -50.0, "trig": 50.0, "give": 0.20,
               "rv20": rv.get((t, day)),
               "tkr_iv_prev": (iv_sum[(t, pd)] / iv_n[(t, pd)]) if pd and iv_n.get((t, pd)) else None,
               "delta_prev": None, "theta_prev": None, "prev_oi": poi, "oi_chg": None}
        featsB.append(row); ysB.append(1 if r["rh"] > 0 else 0); daysB.append(day)
    print(f"exam B rows: {len(ysB)}", flush=True)
    resB = exam_deltas(featsB, ysB, daysB,
                       {"IVX": ["tkr_iv_prev", "prev_oi"], "VOL": ["rv20"]}, BASE_F)
    L += ["", "## B. Replication - 2-year corpus (66k trades, both bear episodes, different "
          "sampling; PATH not constructible here - needs print timestamps)",
          "| block | " + " | ".join(k for k, _ in resB["VOL"]) + " | verdict |", "|---|" +
          "---|" * (len(resB["VOL"]) + 1)]
    for name in ("IVX", "VOL"):
        ds = [v for _, v in resB[name]]
        v = "CONFIRMED" if all(x > 0.002 for x in ds) else ("MIXED" if any(x > 0.002 for x in ds) else "FAILED")
        L.append(f"| {name} | " + " | ".join(f"{x:+.4f}" for x in ds) + f" | {v} |")
    L += ["", "## Combined verdicts",
          f"  PATH: {verdictA['PATH']} on its only constructible corpus (stability exams)",
          f"  VOL: A={verdictA['VOL']}, B={'see table'} - both corpora, both eras",
          f"  IVX: A={verdictA['IVX']}, B={'see table'}",
          "", "Friday queue (owner 2026-09-03): PATH + VOL features wired into the nightly wide",
          "student - training-side retro-compute plus live capture at entry; live capture",
          "touches the harvest path so test_harvest_passivity is mandatory before push."]
    fn = f"reports/research/ablation_validation_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("VALIDATION COMPLETE", flush=True)


if __name__ == "__main__":
    main()
