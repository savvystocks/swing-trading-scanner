"""CLI: fit the shadow Council on a snapshot and render its report + per-candidate shadow table.

    python -m src.brain.run_council --snapshot <dir-or-gz> --out <workdir> --reports reports/council

Brain-side only. Reads the snapshot copy, writes reports. No engine contact, no authority.
"""
import os
import argparse

from . import loader, foundry, discovery as D, convergence as CV, council as C


def run(snapshot_source, out_dir, reports_dir):
    os.makedirs(reports_dir, exist_ok=True)
    snap = loader.load_snapshot(snapshot_source, workdir=os.path.join(out_dir, "snap"))
    ds = foundry.build_dataset(snap, out_dir)
    fb, X, kept, meta = CV.prepare_frame(ds, snap["db_path"])
    fb["net_ret"] = fb["realized_return"] - fb["cost_base"]
    trials = D.Trials()
    res = C.run_council(fb, X, kept, trials)

    sid = ds["dataset_version"]
    sf = C.shadow_frame(fb, res)
    sf.to_csv(os.path.join(reports_dir, f"council_shadow_{sid}.csv"), index=False)

    s = res["selection"]
    takes = int(res["take"].sum())
    eng_take = int(((res["take"]) & (fb["executed"].to_numpy() == 1)).sum())
    eng_total = int((fb["executed"].to_numpy() == 1).sum())
    from collections import Counter
    reasons = Counter(res["veto_reason"].tolist())
    lines = [
        f"# Council (Phase 2, SHADOW) - {sid}", "",
        "Five diverse members, out-of-fold, no authority. Recording only.", "",
        f"- feature-bearing rows scored: {len(fb)}",
        f"- blended OOF AUC: {res['blend_auc']}   (per member: "
        + ", ".join(f"{m} {res['member_auc'][m]}" for m in res["members"]) + ")",
        f"- council TAKEs: {takes} of {len(fb)}  |  agreed with {eng_take} of {eng_total} engine-executed picks",
        f"- disagreement veto band: std > {res['disagree_max']}  |  quorum: {res['quorum']}/5 members must score",
        "",
        "## Selection performance (uniqueness-weighted, out-of-fold)",
        f"- TAKE hit rate: {s['hit']}  [95% lower bound {s['wilson_lo']}]  | net after cost: {s['net_ret']}",
        f"- n={s['n']} (n_eff {s['n_eff']})",
        "",
        "## Decision breakdown",
    ]
    for r, n in reasons.most_common():
        lines.append(f"- {r}: {n}")
    lines += ["", f"- trials counted: {trials.as_dict()}",
              "", "SHADOW ONLY - the Council holds no authority; the engine is untouched. Promotion is the",
              "Governor's decision on track record (Phase 3)."]
    path = os.path.join(reports_dir, f"council_{sid}.md")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines))
    print("report ->", path)
    return {"report": path, "selection": s}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", default="council_work")
    ap.add_argument("--reports", default="reports/council")
    a = ap.parse_args()
    run(a.snapshot, a.out, a.reports)
