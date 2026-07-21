"""The discovery run: snapshot -> Foundry -> Parts 1-3 baseline search -> Part 5 ten-angle
convergence campaign -> one dated report + ledger + accreting convergence state.

Standing process (Part 4): brain_weekly.yml runs this every Sunday after the weekly edge report and
commits reports/discovery/. Promotion is by the ROADMAP rule only - a survivor whose OOS lower CI
clears the cost-inclusive hurdle with acceptable PBO across consecutive runs becomes a SHADOW
candidate for the Student pipeline; NOTHING deploys live from this rig.

CLI:  python -m src.brain.run_discovery --snapshot <dir-or-gz> --out <workdir> --reports reports/discovery
"""
import os
import time
import argparse
import numpy as np
import pandas as pd

from . import loader, foundry, ev as EV, calibration as CAL
from . import discovery as D
from . import convergence as CV


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
        raise ValueError("feature-bearing frame too thin for any search")
    dfb, Xb, cfgb = base

    cost = EV.cost_model(dfb["cost_base"].to_numpy())
    hurdle = EV.solve_threshold(dfb["realized_return"].to_numpy(), cost=cost)

    y = dfb[cfgb["ycol"]].to_numpy(dtype=np.float64)
    w = dfb[cfgb["wcol"]].to_numpy(dtype=np.float64)
    Xm = Xb[kept].to_numpy(dtype=np.float64)
    starts = dfb["window_start"].to_numpy(dtype=np.float64)
    ends = dfb["window_end"].to_numpy(dtype=np.float64)

    oof, folds = D.oof_predict(Xm, y, w, starts, ends, cfgb["learner"], cfgb["seed"], trials)
    fin = np.isfinite(oof)
    auc = D.weighted_auc(y[fin], oof[fin], w[fin]) if fin.any() else float("nan")
    cal = CAL.calibrate(oof[fin], y[fin]) if fin.sum() >= 50 else None
    q80 = np.nanquantile(oof[fin], 0.8) if fin.any() else np.nan
    top_m = fin & (oof >= q80)
    p_top, neff_top = D.weighted_rate(y[top_m], w[top_m]) if top_m.any() else (float("nan"), 0.0)
    p_base, _ = D.weighted_rate(y[fin], w[fin]) if fin.any() else (float("nan"), 0.0)

    mda = D.mda_importance(Xm, y, w, folds, kept, cfgb["seed"]) if folds else pd.Series(dtype=float)
    verdict = D.verdict_table(dfb, kept, Xb, cfgb["ycol"], cfgb["wcol"], "cost_base",
                              cfgb["scheme"], trials)

    baseline_findings = CV.run_variant(dfb, Xb, kept, cfgb, trials) or {}
    wf = D.walk_forward(dfb, Xb, kept, cfgb, trials)
    eq = D.equity_lines(wf["ledger"])

    M = D.pbo_matrix(dfb, Xb, kept, cfgb, trials)
    pbo, pbo_note = H_pbo(M)
    dsr, sr0, dsr_note = D.dsr_of_champion(wf["champ_returns"], max(trials.total, 1))

    matrix, angle_notes = CV.run_campaign(fb, X, kept, meta, trials)
    survivors, flickers, mirages = CV.classify(matrix)
    state_path = os.path.join(reports_dir, "convergence_state.json")
    standing = CV.accrete(state_path, snap_id, matrix, survivors)

    shadow = _shadow_candidates(survivors, baseline_findings, hurdle, pbo, standing)

    verdict_csv = os.path.join(reports_dir, f"verdict_{snap_id}.csv")
    verdict.to_csv(verdict_csv, index=False)
    ledger_csv = os.path.join(reports_dir, f"ledger_{snap_id}.csv")
    wf["ledger"].to_csv(ledger_csv, index=False)

    md = _render(snap_id, ds, meta, hurdle, cost, verdict, mda, auc, cal, p_top, neff_top, p_base,
                 baseline_findings, wf, eq, pbo, pbo_note, dsr, sr0, dsr_note, trials, matrix,
                 angle_notes, survivors, flickers, mirages, standing, shadow,
                 os.path.basename(ledger_csv), os.path.basename(verdict_csv), time.time() - t0)
    report_path = os.path.join(reports_dir, f"discovery_{snap_id}.md")
    open(report_path, "w", encoding="utf-8").write(md)
    return {"report_path": report_path, "snapshot": snap_id, "trials": trials.as_dict(),
            "pbo": pbo, "survivors": [s for s, _, _ in survivors],
            "flickers": [s for s, _, _ in flickers], "mirages": [s for s, _, _ in mirages],
            "shadow_candidates": shadow, "runtime_s": round(time.time() - t0, 1)}


def H_pbo(M):
    from . import harness as H
    if M.size == 0:
        return None, "N/A (no scoreable trials)"
    return H.probability_of_backtest_overfitting(M, min_trials=2)


def _shadow_candidates(survivors, baseline_findings, hurdle, pbo, standing):
    """The promotion rule, mechanically applied: SURVIVOR + OOS lower CI above the cost-inclusive
    hurdle + PBO <= 0.20 + survived every run it has appeared in. Consecutive-run persistence is
    enforced by the accretion standing."""
    out = []
    for sig, n_conf, _ in survivors:
        f = baseline_findings.get(sig)
        if not f or f.get("p") is None or f.get("n_eff", 0) < D.MIN_BAND:
            continue
        lo, _ = D.wilson_eff(f["p"], f["n_eff"])
        persisted = standing.get(sig, "").startswith("SURVIVOR")
        if lo > hurdle["threshold"] and pbo is not None and pbo <= 0.20 and persisted:
            out.append({"finding": sig, "oos_lower_ci": round(lo, 4), "hurdle": round(hurdle["threshold"], 4),
                        "pbo": pbo, "standing": standing.get(sig)})
    return out


def _fmt(x, nd=4):
    return "N/A" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{nd}f}"


def _finding_line(sig, f, trials_total, pbo):
    """A winner NEVER prints without its trials count and PBO attached."""
    return (f"- `{sig}` OOS up-rate {_fmt(f.get('p'))} (n_eff {f.get('n_eff')}, lift {f.get('lift')}) "
            f"| PBO {_fmt(pbo, 3)} | trials {trials_total}")


def _render(snap_id, ds, meta, hurdle, cost, verdict, mda, auc, cal, p_top, neff_top, p_base,
            baseline_findings, wf, eq, pbo, pbo_note, dsr, sr0, dsr_note, trials, matrix,
            angle_notes, survivors, flickers, mirages, standing, shadow, ledger_name, verdict_name,
            runtime_s):
    L = [f"# Discovery report - {snap_id}", ""]

    L += ["## Plain-English close-out", ""]
    powered = {s: f for s, f in baseline_findings.items()
               if f.get("p") is not None and f.get("n_eff", 0) >= D.MIN_BAND}
    best3 = sorted(powered.items(), key=lambda kv: -(kv[1].get("lift") or 0))[:3]
    if best3:
        L += ["Three best-looking findings (honesty numbers attached - OOS, PBO, trials, sample):"]
        for sig, f in best3:
            L.append(_finding_line(sig, f, trials.total, pbo))
    else:
        L += ["No finding had enough out-of-sample power to headline."]
    blind = verdict[verdict["note"].str.contains("sparse", na=False)]["feature"].nunique()
    n_surv = len(survivors)
    if shadow:
        edge_line = ("Today's data contains a DEFENSIBLE candidate edge (see SHADOW candidates) - "
                     "still paper-only, promotion rule applies.")
    elif n_surv:
        edge_line = ("Today's data contains a HINT of an edge (survivors exist but have not cleared "
                     "the promotion bar) - not yet defensible.")
    elif flickers:
        edge_line = "Today's data contains a hint at best: flickers only, nothing survived the angles."
    else:
        edge_line = "Neither a defensible edge nor a solid hint in today's data."
    L += ["", f"Worst-confused features: {blind} feature(s) too sparse to band (blind, not useless - "
          "sensor repair pending); the per-feature fill rates below separate blind from useless.",
          edge_line,
          "Zero live changes were made by this run: it reads the snapshot and writes this report only.", ""]

    L += ["## Part 1 - Feature Verdict Table", "",
          f"- dataset: {len(ds['df'])} graded rows; feature-bearing {meta['n_feature_bearing']} "
          f"({meta['fb_share']:.1%} of the pile - the 'none' prefilter tier carries no feature vector "
          "and cannot be searched; that is a fill-rate fact, not a finding)",
          f"- cost-inclusive hurdle (empirical, THE bar - never the retired 62.5% figure): "
          f"{_fmt(hurdle['threshold'])} CI {[_fmt(x) for x in hurdle['ci']]} at mean cost {_fmt(cost)}",
          f"- full per-band table: `{verdict_name}` (fill rate first, then weighted up-rate + CI, "
          "mean return, EV per band; thin bands say UNDERPOWERED)", ""]
    block_fill = verdict.groupby("block")["fill_rate"].max().sort_values()
    L += ["Fill rate by feature block (lowest first - blind-vs-useless disambiguation):",
          "```", block_fill.round(3).to_string(), "```", ""]
    if not mda.empty:
        L += ["Out-of-sample predictive contribution (MDA under purged CV; ranking source for this "
              "table - NOT in-sample correlation). Top five, annotated:"]
        for c, v in mda.head(5).items():
            fr = float(verdict[verdict["feature"] == c]["fill_rate"].max())
            L.append(f"- `{c}` MDA {_fmt(v)} (fill {fr:.0%}): genuinely moves OOS separation this week.")
        L += ["Bottom five (no OOS contribution this week - dead weight or blind):"]
        for c, v in mda.tail(5).items():
            fr = float(verdict[verdict["feature"] == c]["fill_rate"].max())
            blindtag = "BLIND (sparse)" if fr < 0.5 else "populated but useless so far"
            L.append(f"- `{c}` MDA {_fmt(v)} (fill {fr:.0%}): {blindtag}.")
        L.append("")

    L += ["## Part 2 - The Search (everything counted)", "",
          f"- model: {CV.BASE_CFG['learner']} under purged+embargoed folds; OOS weighted AUC "
          f"{_fmt(auc, 3)}; top-quintile OOS up-rate {_fmt(p_top)} vs pool {_fmt(p_base)} "
          f"(n_eff {neff_top:.0f})",
          f"- calibration: {cal['selected'] if cal else 'UNDERPOWERED'}"
          + (f", Brier sigmoid {_fmt(cal['brier']['sigmoid'], 3)} / isotonic "
             f"{_fmt(cal['brier']['isotonic'], 3)}" if cal else ""),
          "- readable rules (depth <= 3), mined on train folds, graded OOS only:"]
    for sig, f in sorted(baseline_findings.items(), key=lambda kv: -(kv[1].get("lift") or 0))[:8]:
        L.append("  " + _finding_line(sig, f, trials.total, pbo))
    L += ["", f"### THE COUNTER (non-negotiable)", "",
          f"- trials this run, ALL angles aggregated: `{trials.as_dict()}`",
          f"- PBO fed by the whole campaign: {_fmt(pbo, 3)} {pbo_note}",
          f"- Deflated Sharpe of the walk-forward champion: "
          + (f"{_fmt(dsr, 3)} (expected max SR benchmark {_fmt(sr0, 3)})" if dsr is not None else dsr_note), ""]

    L += ["## Part 3 - The Honest Dated Replay (walk-forward)", ""]
    for ws in wf["windows"]:
        if ws.get("champion"):
            L.append(f"- {ws['week']}: train {ws['n_train']} -> test {ws['n_test']}, champion "
                     f"`{ws['champion']}`, takes {ws.get('n_takes')} (n_eff {ws.get('n_eff_takes')}), "
                     f"OOS up-rate {_fmt(ws.get('oos_up_rate'))}, OOS net ret "
                     f"{_fmt(ws.get('oos_net_ret'))} {ws.get('note', '')}")
        else:
            L.append(f"- {ws['week']}: train {ws['n_train']} -> test {ws['n_test']} - {ws['note']}")
    n_weeks = sum(1 for ws in wf["windows"] if ws.get("champion"))
    L += ["", f"- trade-by-trade ledger (every test-week candidate, decision + stated reason + "
          f"graded outcome + net P&L): `{ledger_name}`",
          f"- TRUE out-of-sample territory today: {n_weeks} scoreable week(s). That is THIN - "
          "verdict-grade replay needs months, not weeks; treat every number above accordingly."]
    if not eq.empty:
        last = eq.iloc[-1]
        L += ["", "Three lines, uniqueness-weighted, cost-inclusive (cumulative weighted net return):",
              f"- engine's actual picks: {_fmt(last['engine'], 3)}",
              f"- discovered strategy (OOS takes): {_fmt(last['strategy'], 3)}",
              f"- pool baseline (every candidate): {_fmt(last['pool'], 3)}", ""]

    L += ["## Part 4 - Standing process", "",
          "- this rig re-runs with every Sunday brain cycle and appends here (reports/discovery/); "
          "the convergence matrix accretes in `convergence_state.json`.",
          "- promotion rule (in ROADMAP): a SURVIVOR whose OOS lower CI clears the cost-inclusive "
          "hurdle with PBO <= 0.20 across consecutive runs becomes a SHADOW candidate for the "
          "Student pipeline - never a live deployment from this rig."]
    if shadow:
        L += ["- SHADOW candidates THIS run:"]
        for s in shadow:
            L.append(f"  - `{s['finding']}` OOS lower CI {s['oos_lower_ci']} > hurdle {s['hurdle']}, "
                     f"PBO {_fmt(s['pbo'], 3)}, {s['standing']}")
    else:
        L += ["- nothing clears the promotion bar this run. What would change the odds: more graded "
              "weeks (the binding constraint), repaired sparse sensors (earnings/short-float/IV-term/"
              "skew/dark-pool blocks), or an owner-decided re-sourcing of the signal itself "
              "(the referenced adjudication file does not exist in this repo - flagged)."]
    L.append("")

    L += ["## Part 5 - The Ten Angles (Convergence Matrix)", "",
          "Cells: confirmed / weak / absent / UNDERPOWERED. Judged by intersection, never selection.", ""]
    angle_names = [a for a, _ in CV.ANGLES]
    hdr = "| finding | " + " | ".join(a.split(" ", 1)[0] for a in angle_names) + " | confirmed |"
    sep = "|" + "---|" * (len(angle_names) + 2)
    L += [hdr, sep]
    order = sorted(matrix.items(),
                   key=lambda kv: -sum(1 for a in angle_names if kv[1].get(a) == "confirmed"))
    for sig, cells in order[:14]:
        n_conf = sum(1 for a in angle_names if cells.get(a) == "confirmed")
        row = "| `" + sig[:48] + "` | " + " | ".join(
            {"confirmed": "C", "weak": "w", "absent": "-", "UNDERPOWERED": "U"}.get(
                cells.get(a, "-"), "-") for a in angle_names) + f" | {n_conf}/10 |"
        L.append(row)
    L += ["", "Angle sample notes: " + "; ".join(f"{a}: {n}" for a, n in angle_notes.items()), ""]
    L += [f"SURVIVORS (>= {CV.SURVIVOR_MIN}/10; only shortlist eligible for the shadow path):"]
    L += [f"- `{s}` ({n}/10) {standing.get(s, '')}" for s, n, _ in survivors] or ["- none"]
    L += ["", f"FLICKERS ({CV.FLICKER_MIN}-{CV.SURVIVOR_MIN - 1}; watch, don't act):"]
    L += [f"- `{s}` ({n}/10)" for s, n, _ in flickers] or ["- none"]
    L += ["", "MIRAGES (<= 3; named and buried - do not rediscover):"]
    L += [f"- `{s}` ({n}/10)" for s, n, _ in mirages] or ["- none"]
    surv_txt = (f"{len(survivors)} finding(s) survived >= 8/10 angles"
                if survivors else "nothing survived >= 8/10 angles")
    L += ["", f"Plain-English close: {surv_txt}; "
          f"{len(mirages)} mirage(s) were luck wearing a good week. "
          + ("The survivors list justifies keeping the Student on schedule."
             if survivors else "Nothing here changes the Student schedule by itself - the honest "
             "read is wait-for-data; a deliberate re-sourcing is an owner decision (the referenced "
             "adjudication file is absent from this repo)."), ""]
    L += [f"---", f"run: {runtime_s:.1f}s | rows {len(ds['df'])} | feature-bearing "
          f"{meta['n_feature_bearing']} | trials {trials.total} | brain-side only, zero live changes"]
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", default="brain_work_discovery")
    ap.add_argument("--reports", default="reports/discovery")
    a = ap.parse_args()
    out = run(a.snapshot, a.out, a.reports)
    print(f"discovery {out['snapshot']}: trials {out['trials']['TOTAL']}, PBO {out['pbo']}, "
          f"survivors {len(out['survivors'])}, shadow {len(out['shadow_candidates'])}, "
          f"{out['runtime_s']}s")
    print("report ->", out["report_path"])
