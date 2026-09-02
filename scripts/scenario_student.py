"""SCENARIO STUDENT (owner order 2026-09-02: "run a simulation of all the different scenarios
and potential outcomes so the student can have the data with all different variables...
proactive learning of everything that'll be helpful and we've missed").

Corpus: the tuner's replay of 39,539 real UW triggers x 8 exit configs = ~316k scenario
outcomes (true-trigger entries, hourly paths, next-session exits), joined with every variable
the live wide student has never been shown: contract price band, premium band, weekday of
entry (the Wednesday lesson as a feature), DTE, spread at trigger, ticker-vs-20d, SPY-vs-20d,
SPY-vs-50d regime, side, and the exit config itself as conditioning features.

Training: HistGradientBoosting P(win | features + exit config), the proven nightly stack.
Honesty: labels are BAR-PRICE REPLAYS (shape of edge, not executable returns) - this model is
a RESEARCH instrument and candidate-ranker; it wires into nothing. Validation: day-grouped
OOF + a strict last-quarter walk-forward. Output: reports/research/scenario_student_<date>.md
- AUC by validation mode, permutation importance (what carries signal), the "missed
variables" ranking (importance of features the live system does not gate on), and
per-regime/per-exit conditional skill."""
import json
import math
import os
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

EXITS = [(-50.0, 50.0, 0.20), (-50.0, 80.0, 0.30), (-50.0, 80.0, 0.20), (-50.0, 50.0, 0.30),
         (-70.0, 50.0, 0.20), (-70.0, 80.0, 0.30), (-70.0, 80.0, 0.20), (-70.0, 50.0, 0.30)]
FEATS = ["prem", "ask", "side_call", "smd", "reg", "sp", "weekday", "dte", "price_band_49",
         "prem_band_whale", "stop", "trig", "give"]
NOT_GATED_LIVE = {"weekday", "dte", "ask", "prem"}   # variables the live system does not gate on


def dte_of(occ, t, day):
    try:
        exp = "20" + occ[len(t):len(t) + 6]
        return (date(int(exp[:4]), int(exp[4:6]), int(exp[6:8])) - date.fromisoformat(day)).days
    except Exception:
        return None


def main():
    rows = []
    for line in open("reports/research/probe_tuner_rows.jsonl", encoding="utf-8"):
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    X, y, days, regs, exits_ix, all_rets = [], [], [], [], [], []
    for r in rows:
        d = dte_of(r["occ"], r["t"], r["day"])
        if d is None:
            continue
        wd = date.fromisoformat(r["day"]).weekday()
        for ei, (st, tg, gv) in enumerate(EXITS):
            ret = r["rets"][ei]
            if ret is None:
                continue
            X.append([r["prem"], r["ask"], 1.0 if r["side"] == "C" else 0.0, r["smd"], r["reg"],
                      r["sp"], float(wd), float(d), 1.0 if 4.0 < r["ask"] <= 9.0 else 0.0,
                      1.0 if r["prem"] > 400000 else 0.0, st, tg, gv])
            y.append(1 if ret > 0 else 0)
            days.append(r["day"])
            regs.append("bear" if r["reg"] < -2 else "bull" if r["reg"] > 2 else "mild")
            exits_ix.append(ei)
            all_rets.append(ret)
    X = np.array(X); y = np.array(y); days = np.array(days)
    regs = np.array(regs); exits_ix = np.array(exits_ix)
    print(f"scenario corpus: {len(y)} outcome rows, {len(set(days.tolist()))} days, "
          f"win rate {y.mean():.3f}", flush=True)

    uniq = sorted(set(days.tolist()))
    fold_of = {d: i % 5 for i, d in enumerate(uniq)}
    fold = np.array([fold_of[d] for d in days])
    oof = np.full(len(y), np.nan)
    for f in range(5):
        m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.08, random_state=7)
        m.fit(X[fold != f], y[fold != f])
        oof[fold == f] = m.predict_proba(X[fold == f])[:, 1]
    auc_oof = roc_auc_score(y, oof)
    print(f"day-grouped OOF AUC: {auc_oof:.3f}", flush=True)

    cut = uniq[int(len(uniq) * 0.75)]
    tr = days < cut; te = ~tr
    mw = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.08, random_state=7)
    mw.fit(X[tr], y[tr])
    p_te = mw.predict_proba(X[te])[:, 1]
    auc_wf = roc_auc_score(y[te], p_te)
    print(f"walk-forward AUC (last quarter of days): {auc_wf:.3f}", flush=True)

    pi = permutation_importance(mw, X[te], y[te], n_repeats=5, random_state=7,
                                scoring="roc_auc", n_jobs=1)
    imp = sorted(zip(FEATS, pi.importances_mean), key=lambda x: -x[1])

    # ranking lift on the walk-forward slice: top-decile picked vs rest, day-clustered
    rets_te = np.array(all_rets)[te]
    thr = np.quantile(p_te, 0.9)
    per = defaultdict(lambda: [[], []])
    for dd, pp, rr in zip(days[te], p_te, rets_te):
        per[dd][0 if pp >= thr else 1].append(rr)
    picked = [np.mean(v[0]) for v in per.values() if v[0]]
    rest = [np.mean(v[1]) for v in per.values() if v[1]]
    lift = (np.mean(picked) if picked else 0) - (np.mean(rest) if rest else 0)

    L = [f"# SCENARIO STUDENT - {date.today().isoformat()}",
         "", f"corpus: {len(y)} scenario outcomes ({len(rows)} real triggers x 8 exit configs, "
         "true-trigger hourly replays; labels are BAR-PRICE - shape of edge, not executable)",
         f"", f"skill: day-grouped OOF AUC {auc_oof:.3f} | strict walk-forward AUC {auc_wf:.3f}",
         f"ranking lift (walk-forward): top-decile picks {np.mean(picked) if picked else 0:+.1f}%/day "
         f"vs rest {np.mean(rest) if rest else 0:+.1f}%/day = +{lift:.1f} pts/day", "",
         "## What carries signal (permutation importance, walk-forward slice)",
         "| variable | importance | live system gates on it? |", "|---|---|---|"]
    for f_, v in imp:
        L.append(f"| {f_} | {v:+.4f} | {'NO - candidate missed variable' if f_ in NOT_GATED_LIVE and v > 0.002 else 'yes/partial' if f_ not in NOT_GATED_LIVE else 'no (weak)'} |")
    L += ["", "## Conditional skill (walk-forward AUC by slice)"]
    for rg in ("bull", "mild", "bear"):
        mask = te & (regs == rg)
        if mask.sum() > 500 and len(set(y[mask].tolist())) > 1:
            L.append(f"  {rg}: AUC {roc_auc_score(y[mask], mw.predict_proba(X[mask])[:, 1]):.3f} "
                     f"(n={mask.sum()})")
    for ei, ex in enumerate(EXITS):
        mask = te & (exits_ix == ei)
        if mask.sum() > 500 and len(set(y[mask].tolist())) > 1:
            L.append(f"  exit {ex}: AUC {roc_auc_score(y[mask], mw.predict_proba(X[mask])[:, 1]):.3f}")
    L += ["", "GUARDRAILS: research instrument only - wires into nothing; any use walks the",
          "META_SELECT gate (virgin days + owner sign-off). Replay labels flatter returns;",
          "the AUC (rank skill) is the honest number here, not the day-means."]
    fn = f"reports/research/scenario_student_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("SCENARIO STUDENT COMPLETE", flush=True)


if __name__ == "__main__":
    main()
