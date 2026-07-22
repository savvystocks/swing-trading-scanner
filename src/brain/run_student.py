"""The Stage-2 Student run: snapshot -> Foundry -> train + OOF-evaluate -> CPCV/PBO -> the item-8
acceptance gates -> model card + shadow report. Below GATE_FB feature-bearing rows the run is
PROVISIONAL and the official verdict is withheld; the same pipeline re-run at/above the gate IS the
official ignition. Weekly via brain_weekly.yml after discovery; artifacts to the workdir, reports to
reports/student/. Nothing here touches the engine or any live path.

CLI:  python -m src.brain.run_student --snapshot <dir-or-gz> --out <workdir> --reports reports/student
"""
import os
import json
import time
import argparse
import numpy as np

from . import loader, foundry
from . import discovery as D
from . import convergence as CV
from . import student as S


def run(snapshot_source, out_dir, reports_dir):
    t0 = time.time()
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    trials = D.Trials()

    snap = loader.load_snapshot(snapshot_source, workdir=os.path.join(out_dir, "snap"))
    ds = foundry.build_dataset(snap, out_dir)
    snap_id = ds["dataset_version"]
    fb, X, kept, meta = CV.prepare_frame(ds, snap["db_path"])
    base = CV.variant_frame(fb, X, kept, meta, dict(CV.BASE_CFG), {"y2": None, "r2": None})
    if base is None:
        raise ValueError("feature-bearing frame too thin to train")
    dfb, Xb, _ = base
    n_fb = len(dfb)

    trained = S.train_student(dfb, Xb, kept, trials)
    pbo_out = S.cpcv_pbo(dfb, Xb, trained["features"], trials)
    acc = S.acceptance(trained, pbo_out, n_fb, trials)
    shadow = S.shadow_table(trained, dfb, Xb)
    artifact_path = S.save_artifact(trained, out_dir, snap_id)

    shadow_csv = os.path.join(reports_dir, f"shadow_{snap_id}.csv")
    if not shadow.empty:
        shadow.to_csv(shadow_csv, index=False)
    card = {
        "snapshot": snap_id, "status": acc["status"], "verdict": acc["verdict"],
        "gates": acc["gates"], "all_gates_pass": acc["all_gates_pass"],
        "n_feature_bearing": n_fb, "gate_fb": S.GATE_FB,
        "n_oof": trained["n_oof"], "oof_weighted_auc": round(trained["auc"], 4),
        "calibration": trained["calibration"]["selected"] if trained["calibration"] else None,
        "hurdle": round(trained["hurdle"]["threshold"], 4),
        "selection": trained["selection"], "engine_same_splits": trained["engine_same_splits"],
        "pbo": pbo_out["pbo"], "dsr": pbo_out["dsr"], "dsr_note": pbo_out["dsr_note"],
        "cpcv": {"splits": pbo_out["n_splits"], "paths": pbo_out["n_paths"],
                 "grid": pbo_out["grid_size"]},
        "features_used": len(trained["features"]),
        "features_clustered_out": len(trained["dropped"]),
        "config": trained["config"], "trials": trials.as_dict(),
        "artifact": os.path.basename(artifact_path), "runtime_s": round(time.time() - t0, 1),
    }
    card_path = os.path.join(reports_dir, f"card_{snap_id}.json")
    json.dump(card, open(card_path, "w", encoding="utf-8"), indent=2, default=str)

    md = _render(card, trained, pbo_out, acc, shadow, snap_id)
    report_path = os.path.join(reports_dir, f"student_{snap_id}.md")
    open(report_path, "w", encoding="utf-8").write(md)
    return {"report_path": report_path, "card": card, "status": acc["status"],
            "verdict": acc["verdict"], "shadow_rows": int(len(shadow))}


def _fmt(x, nd=4):
    return "N/A" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{nd}f}"


def _render(card, trained, pbo_out, acc, shadow, snap_id):
    s = trained["selection"]
    e = trained["engine_same_splits"]
    L = [f"# Student (Stage 2) - {snap_id} - {acc['status']}", "",
         f"**{acc['verdict']}**", "",
         f"- feature-bearing rows: {card['n_feature_bearing']} (gate {S.GATE_FB}"
         + (f" - {S.GATE_FB - card['n_feature_bearing']} short)" if acc["provisional"] else " - MET)"),
         f"- OOF weighted AUC {_fmt(trained['auc'], 3)} on {trained['n_oof']} out-of-fold rows; "
         f"calibration {card['calibration']}; features {card['features_used']} "
         f"(clustered out {card['features_clustered_out']} redundant)",
         f"- trials this run: {card['trials']}", "",
         "## The four acceptance gates (item 8)", ""]
    g = acc["gates"]
    L += [f"1. OOS Wilson lower bound {_fmt(s['wilson_lo'])} > hurdle {_fmt(trained['hurdle']['threshold'])}: "
          f"**{'PASS' if g['1_oos_wilson_lo_above_hurdle'] else 'FAIL'}** "
          f"(selection: n {s['n']}, n_eff {s['n_eff']}, hit {_fmt(s['hit'])}, net {_fmt(s['net_ret'])})",
          f"2. PBO {_fmt(pbo_out['pbo'], 3)} <= {S.PBO_MAX}: **{'PASS' if g['2_pbo_at_or_below_0.20'] else 'FAIL'}** "
          f"({pbo_out['n_splits']} CPCV splits x {pbo_out['grid_size']} configs, {pbo_out['n_paths']} paths)",
          f"3. Deflated Sharpe {_fmt(pbo_out['dsr'], 3)} > 0.5: **{'PASS' if g['3_deflated_sharpe_positive'] else 'FAIL'}** "
          f"{pbo_out['dsr_note'] or ''}",
          f"4. Beats the engine on the same purged splits: **{'PASS' if g['4_beats_engine_same_splits'] else 'FAIL'}** "
          f"(student net {_fmt(s['net_ret'])} vs engine net {_fmt(e['net_ret'])}; "
          f"student hit {_fmt(s['hit'])} vs engine hit {_fmt(e['hit'])}, engine n {e['n']})", ""]
    L += ["## Shadow (reporting only - the engine is untouched)", ""]
    if shadow.empty:
        L += ["- no recent candidates to shadow-score"]
    else:
        takes = shadow[shadow["student_says"] == "TAKE"]
        vetoes = shadow[shadow["student_says"] == "VETO"]
        eng_took = shadow[shadow["engine_took"] == 1]
        agree = eng_took[eng_took["student_says"] == "TAKE"]
        L += [f"- last-days candidates scored: {len(shadow)} | student TAKE {len(takes)} / VETO {len(vetoes)}",
              f"- of the engine's {len(eng_took)} executed picks the student agreed with {len(agree)} "
              f"and would have vetoed {len(eng_took) - len(agree)}",
              f"- full table: `shadow_{snap_id}.csv` (per-candidate p, decision, stated reason, outcome)"]
    L += ["", "## Provenance", "",
          f"- config (pinned): {card['config']}",
          f"- model artifact: `{card['artifact']}` (workdir; not committed)",
          f"- run: {card['runtime_s']}s | brain-side only, zero live changes"]
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", default="brain_work_student")
    ap.add_argument("--reports", default="reports/student")
    a = ap.parse_args()
    out = run(a.snapshot, a.out, a.reports)
    print(f"student {out['card']['snapshot']}: {out['status']} | {out['verdict']} | "
          f"AUC {out['card']['oof_weighted_auc']} | PBO {out['card']['pbo']} | "
          f"shadow rows {out['shadow_rows']} | {out['card']['runtime_s']}s")
    print("report ->", out["report_path"])
