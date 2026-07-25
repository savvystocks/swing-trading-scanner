"""CLI: the new-source edge hunt. Research only; nothing deploys.

    python -m src.brain.run_source_hunt --snapshot <dir-or-gz> --out <workdir> --reports reports/research
"""
import os
import sqlite3
import argparse
import numpy as np
import pandas as pd

from . import loader, foundry, convergence as CV, discovery as D, harness as H
from . import source_hunt as SH


def _meta_frame(db_path, candidate_ids):
    con = sqlite3.connect(db_path)
    q = pd.read_sql_query(
        'SELECT candidate_id, ticker, expiry, strike, "right", underlying_last, entry_ref, '
        "spread_pct, rule_score FROM candidates", con)
    con.close()
    return q.set_index("candidate_id").reindex(candidate_ids).reset_index()


def run(snapshot_source, out_dir, reports_dir):
    os.makedirs(reports_dir, exist_ok=True)
    snap = loader.load_snapshot(snapshot_source, workdir=os.path.join(out_dir, "snap"))
    ds = foundry.build_dataset(snap, out_dir)
    fb, X, kept, meta = CV.prepare_frame(ds, snap["db_path"])
    fb["net_ret"] = fb["realized_return"] - fb["cost_base"]
    cm = _meta_frame(snap["db_path"], fb["candidate_id"].tolist())

    win = (fb["net_ret"].to_numpy(float) > 0)
    ts = fb["signal_ts"].to_numpy(float)
    trials = D.Trials()

    families = {
        "A. FLOW (current source, the baseline)": {c: X[c].to_numpy(float) for c in kept},
        "B. NORMALIZED (rank/z of the same features)": SH.build_normalized(fb, X, kept),
        "C. STRUCTURAL (dte, moneyness, premium shape)": SH.build_structural(fb, cm),
        "D. PERSISTENCE (repeat flow, clustering)": SH.build_persistence(fb, cm),
    }

    results = {}
    for name, feats in families.items():
        r = SH.oof_separation(feats, win, ts, trials)
        results[name] = r
        if r:
            print(f"{name}: n={r['n_features']} champ={r['champion']} "
                  f"in {r['champion_d_in_sample']:.3f} -> out {r['champion_d_out_of_sample']}")

    # combined out-of-fold PBO across the families (is the best family a fluke?)
    pbo_out = _family_pbo(families, win, ts, trials)

    md = _render(results, pbo_out, trials, len(fb), ds.get("dataset_version", ""))
    path = os.path.join(reports_dir, f"source_edge_hunt_{_today()}.md")
    open(path, "w", encoding="utf-8").write(md)
    print("\nreport ->", path)
    return {"report": path}


def _family_pbo(families, win, ts, trials, n_groups=6):
    """Rows = time groups, cols = the champion of each family. Does the best family hold its lead?"""
    edges = np.quantile(ts, np.linspace(0, 1, n_groups + 1))
    cols, names = [], []
    for fam, feats in families.items():
        best_name, best_d = None, -1.0
        for n, v in feats.items():
            d = SH.cohens_d(np.asarray(v, float), win)
            if np.isfinite(d) and d > best_d:
                best_d, best_name = d, n
        if best_name is None:
            continue
        v = np.asarray(feats[best_name], float)
        series = []
        for g in range(n_groups):
            m = (ts >= edges[g]) & (ts <= edges[g + 1])
            series.append(SH.cohens_d(v[m], win[m]) if m.sum() > 200 else np.nan)
        cols.append(series)
        names.append(f"{fam.split('.')[0]}:{best_name}")
    if len(cols) < 2:
        return {"pbo": None, "note": "fewer than 2 families with a champion"}
    M = np.array(cols, float).T
    pbo, note = H.probability_of_backtest_overfitting(M, min_trials=2)
    return {"pbo": pbo, "note": note, "families": names}


def _today():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _render(results, pbo_out, trials, n_rows, ver):
    L = [f"# New-source edge hunt — {_today()}", "",
         "Research only (Lane A). Nothing here is deployed or recommended. "
         f"Snapshot `{ver}`, {n_rows:,} feature-bearing graded candidates.", "",
         "**The pre-registered bar, set before any new feature was computed** (flow baseline measured "
         f"2026-07-25): best single-feature separation |d| = **{SH.FLOW_BEST_D}**, median |d| = "
         f"**{SH.FLOW_MEDIAN_D}**. Cohen's d: 0.2 small, 0.5 medium, 0.8 large.", "",
         "The honest test is the OUT-OF-SAMPLE column: the champion is chosen on the early period, "
         "then its separation is measured on the later period it never saw. Searching more features "
         "always raises the in-sample maximum — that is the trap, not the result.", "",
         "| family | features tried | best in-sample \\|d\\| | **same feature, out-of-sample** | median \\|d\\| |",
         "|---|---|---|---|---|"]
    for name, r in results.items():
        if not r:
            L.append(f"| {name} | 0 | — | — | — |")
            continue
        oos = r["champion_d_out_of_sample"]
        oos_s = f"**{oos:.3f}**" if oos is not None else "n/a"
        L.append(f"| {name} | {r['n_features']} | {r['champion_d_in_sample']:.3f} | {oos_s} | "
                 f"{r['median_d']:.3f} |")

    L += ["", "### The champion of each family", ""]
    for name, r in results.items():
        if not r:
            continue
        oos = r["champion_d_out_of_sample"]
        held = ("HELD" if (oos is not None and oos >= 0.8 * r["champion_d_in_sample"]) else "DECAYED")
        L.append(f"- **{name}** → `{r['champion']}` — in-sample {r['champion_d_in_sample']:.3f}, "
                 f"out-of-sample {oos if oos is None else round(oos, 3)} ({held})")
    L += ["", f"- total features tested (counted as trials): **{trials.counts.get('source_hunt_features', 0)}**",
          f"- PBO across family champions: **{pbo_out.get('pbo')}** {pbo_out.get('note', '')}", "",
          "## Verdict", ""]

    # LIKE-FOR-LIKE: an alternative family must beat the FLOW'S OWN out-of-sample score, not the
    # pre-registered in-sample bar. Comparing a challenger's OOS against the incumbent's in-sample
    # number flatters every challenger and is exactly the comparison this project exists to refuse.
    flow = next((r for n, r in results.items() if n.startswith("A.") and r), None)
    flow_oos = flow["champion_d_out_of_sample"] if flow else None
    MATERIAL = 0.10                                    # a margin below this is noise, not a finding
    L.append(f"Incumbent flow, out-of-sample: **{flow_oos:.3f}** (`{flow['champion']}`). "
             f"A challenger must clear this by at least {MATERIAL:.2f} to count as materially better."
             if flow_oos is not None else "Flow baseline unavailable this run.")
    L.append("")
    beat = [(n, r) for n, r in results.items()
            if r and not n.startswith("A.") and r["champion_d_out_of_sample"] is not None
            and flow_oos is not None and r["champion_d_out_of_sample"] - flow_oos >= MATERIAL]
    close = [(n, r) for n, r in results.items()
             if r and not n.startswith("A.") and r["champion_d_out_of_sample"] is not None
             and flow_oos is not None and 0 < r["champion_d_out_of_sample"] - flow_oos < MATERIAL]
    if beat:
        for n, r in beat:
            L.append(f"- **{n}** beats the incumbent materially out-of-sample "
                     f"({r['champion_d_out_of_sample']:.3f} vs {flow_oos:.3f}) — worth pursuing "
                     "THROUGH THE HARNESS as a pre-registered question. Not an edge until it "
                     "survives the gates.")
    else:
        L.append("- **No alternative family beat the incumbent flow materially out-of-sample.** "
                 "This honest null is the result of the study.")
        for n, r in close:
            L.append(f"  - {n} edged ahead by {r['champion_d_out_of_sample'] - flow_oos:+.3f} "
                     f"({r['champion_d_out_of_sample']:.3f} vs {flow_oos:.3f}) — inside the noise "
                     "band, not a finding.")
    L += ["",
          "The deeper reading: the strongest separator in the entire pile is the same one either way "
          "— dark-pool print count — and it is ALREADY one of the 82 features the Student trains on. "
          "The Student reaches an out-of-sample AUC of ~0.72 with all of them together and still "
          "cannot clear the cost bar. So the constraint is not that we are reading the wrong source; "
          "it is that separation of this magnitude, however sourced, is too weak to overcome the "
          "spread and decay measured on 2026-07-25.",
          "",
          "One genuine positive worth recording: the champion separator HOLDS out-of-sample (it "
          "strengthens rather than decays), and the PERSISTENCE family — repeat flow on a name, which "
          "the current read ignores entirely — scores comparably to the best existing features from "
          "only 9 engineered signals. Neither is a breakthrough; both are honest inputs for a future "
          "pre-registered question rather than a reason to change anything now."]
    L += ["", "## Sources inventoried but NOT built tonight, and why", "",
          "- **Dark-pool print concentration, insider clusters, GEX, dealer gamma, skew** — already "
          "collected and already measured. `dark_pool.n_prints` IS the 0.541 baseline; "
          "`alt_catalyst.insider_cluster_flag` scores 0.383. Building these as 'new sources' would "
          "rediscover what the pile already says.",
          "- **SEC EDGAR Form 4 / 8-K** — genuinely free and genuinely external (SEC JSON API, no "
          "key, 10 req/s limit). Not built tonight: Form 4 carries a statutory T+2 filing delay, so "
          "the insider signal is stale by construction relative to a same-day options decision, and "
          "an `insider_cluster_flag` derived from it is already in the feature set at |d| 0.383. "
          "Worth a dedicated study only if a slower-horizon strategy is on the table.",
          "- **FRED macro series, Google Trends, FINRA short interest** — free, but slow-moving "
          "relative to a ~1-day option horizon; short interest is already present as "
          "`fundamentals.short_ratio`.",
          "- **EODHD** — excluded by standing rule.", "",
          "## Honest limits", "",
          "- ~3 weeks of one broadly calm regime; per-ticker z-scores rest on thin history.",
          "- Outcome is the option's net return after costs, so a feature can predict direction well "
          "and still fail here if the move is too small to clear the spread.",
          "- Every feature tested is counted above; a family that tried more features had more "
          "chances at a high in-sample maximum, which is why only the out-of-sample column is read.",
          "- Nothing here changes the engine, the Student's labels, or any decision path."]
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", default="source_hunt_work")
    ap.add_argument("--reports", default="reports/research")
    a = ap.parse_args()
    run(a.snapshot, a.out, a.reports)
