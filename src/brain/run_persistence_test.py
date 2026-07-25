"""Head-to-head harness test of the FLOW PERSISTENCE features (ROADMAP question, pre-registered
2026-07-26). Research only; nothing deploys.

    python -m src.brain.run_persistence_test --snapshot <dir-or-gz> --out <workdir> --reports reports/research

The same Student, same seed, same PurgedKFold splits, trained WITH and WITHOUT nine causal
persistence features. Judged on the pre-registered tripwire: adding them must raise the out-of-fold
selection's uniqueness-weighted net return AND its hit-rate Wilson lower bound, without pushing PBO
past 0.20 - on two consecutive weekly runs. A higher raw separation is explicitly not sufficient.
"""
import os
import sqlite3
import argparse
import numpy as np
import pandas as pd

from . import loader, foundry, convergence as CV, discovery as D, student as S
from . import source_hunt as SH


def _meta(db_path, ids):
    con = sqlite3.connect(db_path)
    q = pd.read_sql_query('SELECT candidate_id, ticker, expiry, strike, "right", underlying_last, '
                          "entry_ref, spread_pct, rule_score FROM candidates", con)
    con.close()
    return q.set_index("candidate_id").reindex(ids).reset_index()


def run(snapshot_source, out_dir, reports_dir, seed=7):
    os.makedirs(reports_dir, exist_ok=True)
    snap = loader.load_snapshot(snapshot_source, workdir=os.path.join(out_dir, "snap"))
    ds = foundry.build_dataset(snap, out_dir)
    fb, X, kept, meta = CV.prepare_frame(ds, snap["db_path"])
    fb["net_ret"] = fb["realized_return"] - fb["cost_base"]
    cm = _meta(snap["db_path"], fb["candidate_id"].tolist())

    pers = SH.build_persistence(fb, cm)
    pers = {k: v for k, v in pers.items() if k in SH.CAUSAL_PERSISTENCE}   # causal only, no lookahead
    Xp = X.copy()
    for k, v in pers.items():
        Xp[k] = v
    kept_p = list(kept) + list(pers.keys())
    print(f"rows {len(fb)} | base features {len(kept)} | + persistence {len(pers)} = {len(kept_p)}")

    tr_base, tr_pers = D.Trials(), D.Trials()
    print("training WITHOUT persistence...", flush=True)
    base = S.train_student(fb, X, kept, tr_base, seed=seed)
    print("training WITH persistence...", flush=True)
    withp = S.train_student(fb, Xp, kept_p, tr_pers, seed=seed)

    print("CPCV/PBO on the persistence variant...", flush=True)
    pbo_p = S.cpcv_pbo(fb, Xp, withp["features"], tr_pers, seed=seed)
    print("CPCV/PBO on the base...", flush=True)
    pbo_b = S.cpcv_pbo(fb, X, base["features"], tr_base, seed=seed)

    # which persistence features actually survived clustering into the model?
    survived = [f for f in withp["features"] if f.startswith("persist::")]
    dropped = [f for f in kept_p if f.startswith("persist::") and f not in withp["features"]]

    md = _render(base, withp, pbo_b, pbo_p, tr_base, tr_pers, survived, dropped,
                 len(fb), ds.get("dataset_version", ""))
    path = os.path.join(reports_dir, f"persistence_harness_{_today()}.md")
    open(path, "w", encoding="utf-8").write(md)
    print("\n" + md)
    print("report ->", path)
    return {"report": path}


def _today():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _render(base, withp, pbo_b, pbo_p, tr_b, tr_p, survived, dropped, n_rows, ver):
    sb, sp = base["selection"], withp["selection"]
    hurdle = base["hurdle"]["threshold"]

    def g(v, d=4):
        return "n/a" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))

    # tripwire arithmetic
    net_up = (sp["net_ret"] is not None and sb["net_ret"] is not None and sp["net_ret"] > sb["net_ret"])
    lo_up = (sp["wilson_lo"] is not None and sb["wilson_lo"] is not None
             and sp["wilson_lo"] > sb["wilson_lo"])
    pbo_ok = (pbo_p["pbo"] is not None and pbo_p["pbo"] <= S.PBO_MAX)
    passes = net_up and lo_up and pbo_ok

    L = [f"# Flow persistence — head-to-head through the harness — {_today()}", "",
         "Research only (Lane A). Nothing deploys from this. "
         f"Snapshot `{ver}`, {n_rows:,} feature-bearing graded candidates. Same Student, same seed, "
         "same PurgedKFold splits; the only difference is nine causal persistence features.", "",
         "> **Provenance.** An earlier non-causal version of these features (whole-day aggregates "
         "counting signals that arrive AFTER the decision point) scored 0.465 separation on "
         "2026-07-25. That figure was lookahead-contaminated and is void. Everything below uses "
         "expanding-window features that see only what had already happened.", "",
         "## The comparison", "",
         "| metric | base (82 features) | + persistence | moved? |",
         "|---|---|---|---|",
         f"| OOF weighted AUC | {g(base['auc'])} | {g(withp['auc'])} | "
         f"{'better' if withp['auc'] > base['auc'] else 'worse or flat'} |",
         f"| selections made | {sb['n']} | {sp['n']} | |",
         f"| independent bets (n_eff) | {sb['n_eff']} | {sp['n_eff']} | |",
         f"| selection hit rate | {g(sb['hit'])} | {g(sp['hit'])} | |",
         f"| **hit-rate 95% lower bound** | {g(sb['wilson_lo'])} | {g(sp['wilson_lo'])} | "
         f"{'UP' if lo_up else 'not up'} |",
         f"| **net return after costs** | {g(sb['net_ret'])} | {g(sp['net_ret'])} | "
         f"{'UP' if net_up else 'not up'} |",
         f"| PBO | {g(pbo_b['pbo'])} | {g(pbo_p['pbo'])} | "
         f"{'within 0.20' if pbo_ok else 'FAILS 0.20'} |",
         f"| deflated Sharpe | {g(pbo_b['dsr'])} | {g(pbo_p['dsr'])} | |",
         "",
         f"The bar every selection must clear is the empirical cost-inclusive hurdle: **{hurdle:.4f}**.",
         "",
         "## Pre-registered tripwire (written before this was computed)", "",
         f"- (a) net return rises: **{'PASS' if net_up else 'FAIL'}** "
         f"({g(sb['net_ret'])} → {g(sp['net_ret'])})",
         f"- (b) hit-rate lower bound rises: **{'PASS' if lo_up else 'FAIL'}** "
         f"({g(sb['wilson_lo'])} → {g(sp['wilson_lo'])})",
         f"- (c) PBO stays within 0.20: **{'PASS' if pbo_ok else 'FAIL'}** ({g(pbo_p['pbo'])})",
         "- (d) all three repeat on a second consecutive weekly run: **not yet evaluable (run 1 of 2)**",
         "",
         f"### Verdict: **{'PROVISIONALLY MEETS (a)-(c); needs run 2' if passes else 'DOES NOT MEET THE TRIPWIRE'}**",
         ""]
    if not passes:
        L.append("Logged as measured-and-rejected. Persistence does not earn a place in the Student's "
                 "feature set on this evidence. Per the pre-registration, a higher raw separation is "
                 "explicitly not sufficient — only tradeable improvement counts, and there is none.")
    else:
        L.append("Provisional only. A second consecutive weekly run must reproduce all three before "
                 "this becomes a governed Student feature-set change at a Sunday boundary.")
    L += ["", "## What the model did with them", "",
          f"- persistence features surviving correlation clustering into the model: "
          f"**{len(survived)}** of 9 — {', '.join(f'`{s}`' for s in survived) if survived else 'none'}",
          f"- dropped as redundant: {', '.join(f'`{d}`' for d in dropped) if dropped else 'none'}",
          f"- trials counted — base {tr_b.total}, persistence variant {tr_p.total}",
          "", "## Honest limits", "",
          "- ~3 weeks of one broadly calm regime; repeat-flow history per ticker is correspondingly thin.",
          "- The outcome is the option's net return after executable costs, so a feature can carry real "
          "information about direction and still fail here if the move cannot clear the spread.",
          "- Both arms share the same snapshot, seed and splits, so the comparison is like-for-like; "
          "what it cannot rule out is that a different model family would use these features better.",
          "- Nothing here changes the engine, the Student in production, or any decision path."]
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", default="persist_work")
    ap.add_argument("--reports", default="reports/research")
    a = ap.parse_args()
    run(a.snapshot, a.out, a.reports)
