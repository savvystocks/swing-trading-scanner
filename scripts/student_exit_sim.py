"""STUDENT EXIT SEARCH (owner order 2026-09-11 01:53: "run it again and as close as you can
include the exit strategy - not a holdout - and see if we have even bigger returns").

ENTRY: the formula-search winner - P(win) model on the AFFORD band ($4.00-$9.90 ask), quarterly
walk-forward refits, k picks per week by threshold (identical picker to student_formula_sim).
Scored across the FULL two years (no holdout, as ordered); the first three quarters warm the
model and are not scored.
EXIT: for those picked trades, every one of the 210 fine-grid exit configs (stop x trail
trigger x give-back, the live exit family) on the v3 basis (close-confirmed trail fills,
gap-through stops, bid-side haircut). Reported:
  BASE           the live default (-50/+50/0.20)
  BEST-IN-SAMPLE the single config with the best total on ALL picks (the ceiling; optimistic
                 by construction - 210 trials on the answer)
  WALK-FORWARD   each quarter uses the config that was best on the picks of all PRIOR quarters
                 (implementable; honest)
  PER-REGIME     best config per regime, in-sample (ceiling with regime knowledge)
Research tier: report only."""
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import numpy as np
import student_formula_sim as sf
from glide_sim import GRID, GIX, snap

FINE = "reports/research/glide_fine_rows_v3.jsonl"
BASE_CFG = (-50.0, 50.0, 0.20)


def weekly(picks, rets, meta):
    wk = defaultdict(float)
    for i, r in zip(picks, rets):
        wk[sf.week_key(meta[i][0])] += 10.0 * r
    w = np.array([wk[x] for x in sorted(wk)])
    t = (w.mean() / (w.std(ddof=1) / math.sqrt(len(w)))) if len(w) > 2 and w.std(ddof=1) > 0 else 0.0
    cum = np.cumsum(w)
    dd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(cum) else 0.0
    h = len(w) // 2
    return {"weeks": len(w), "wk_mean": float(w.mean()) if len(w) else 0.0, "wk_t": float(t),
            "pos": float(np.mean(w > 0)) if len(w) else 0.0, "h1": float(w[:h].mean()) if h else 0.0,
            "h2": float(w[h:].mean()) if len(w) - h else 0.0, "maxdd": dd, "total": float(w.sum())}


def row(label, picks, rets, meta):
    s = weekly(picks, rets, meta)
    reg = defaultdict(list)
    for i, r in zip(picks, rets):
        reg[sf.regime(meta[i][2])].append(r)
    rg = " ".join(f"{k}:{len(v)}/{np.mean(v):+.0f}" for k, v in sorted(reg.items()))
    return (f"| {label} | {len(picks)} | {s['weeks']} | {np.mean(rets):+.1f} | {np.mean(np.array(rets) > 0):.0%} | "
            f"{s['wk_mean']:+.0f} | {s['wk_t']:+.2f} | {s['pos']:.0%} | {s['h1']:+.0f}/{s['h2']:+.0f} | "
            f"{s['maxdd']:.0f} | {s['total']:+.0f} | {rg} |")


def main():
    X, meta = sf.load()
    days = [m[0] for m in meta]
    fine = {}
    for l in open(FINE, encoding="utf-8"):
        try:
            j = json.loads(l)
            fine[(j["occ"], j["day"])] = j["rets"]
        except Exception:
            pass
    print(f"coarse rows {len(meta)}, fine rows {len(fine)}", flush=True)
    base_i = 0
    rets_base = np.array([m[6][base_i] if m[6][base_i] is not None else np.nan for m in meta])
    ok = ~np.isnan(rets_base)
    y_cls = (rets_base > 0).astype(int); y_big = (rets_base >= 30).astype(int)
    y_reg = np.clip(np.nan_to_num(rets_base, nan=0.0), -100, 300)
    cm = sf.cohort_mask(meta, "AFFORD") & ok
    scores = sf.fit_stream(X, y_cls, y_big, y_reg, days, "PWIN", cm)
    HDR = ("| exit | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean |\n"
           "|---|---|---|---|---|---|---|---|---|---|---|---|")
    L = [f"# STUDENT EXIT SEARCH - {date.today().isoformat()} (full two years, no holdout)",
         "entry = P(win) student on the AFFORD band, quarterly walk-forward, k picks/week by threshold; "
         "exits = 210 fine-grid configs on the v3 basis (close-confirmed trail fills).", ""]
    for k in (3, 2):
        picks = sf.pick_weekly(scores, days, cm, k)
        picks = [i for i in picks if (meta[i][7], meta[i][0]) in fine]
        if not picks:
            L.append(f"k{k}: no picks with fine-grid rows"); continue
        R = np.array([fine[(meta[i][7], meta[i][0])] for i in picks], dtype=float)   # picks x 210
        R = np.nan_to_num(R, nan=0.0)
        L += ["", f"## k = {k} picks per week ({len(picks)} trades)", "", HDR]
        L.append(row("BASE -50/+50/0.20", picks, R[:, GIX[snap(BASE_CFG)]], meta))
        # best in-sample by total (ceiling) - show the top 5
        totals = R.sum(axis=0)
        order = np.argsort(-totals)
        for j in order[:5]:
            s_, t_, g_ = GRID[j]
            L.append(row(f"IN-SAMPLE #{list(order).index(j) + 1}: {s_:.0f}/+{t_:.0f}/{g_:.2f}", picks, R[:, j], meta))
        # walk-forward exit choice: per quarter, the config best on all prior quarters' picks
        qs = sorted({sf.qkey(meta[i][0]) for i in picks})
        pq = np.array([sf.qkey(meta[i][0]) for i in picks])
        wf = np.zeros(len(picks)); chosen = []
        for qi, q in enumerate(qs):
            prior = np.isin(pq, qs[:qi])
            j = GIX[snap(BASE_CFG)] if prior.sum() < 8 else int(np.argmax(R[prior].sum(axis=0)))
            wf[pq == q] = R[pq == q, j]
            chosen.append(f"{q}:{GRID[j][0]:.0f}/+{GRID[j][1]:.0f}/{GRID[j][2]:.2f}")
        L.append(row("WALK-FORWARD exit choice", picks, wf, meta))
        L.append(f"| (walk-forward chose) | " + ", ".join(chosen) + " | | | | | | | | | | |")
        # per-regime best (ceiling)
        regs = np.array([sf.regime(meta[i][2]) for i in picks])
        pr = np.zeros(len(picks)); parts = []
        for rname in ("BULL", "MILD", "BEAR"):
            m_ = regs == rname
            if m_.sum() == 0:
                continue
            j = int(np.argmax(R[m_].sum(axis=0)))
            pr[m_] = R[m_, j]
            parts.append(f"{rname}:{GRID[j][0]:.0f}/+{GRID[j][1]:.0f}/{GRID[j][2]:.2f}")
        L.append(row("PER-REGIME best (in-sample)", picks, pr, meta))
        L.append(f"| (per-regime configs) | " + ", ".join(parts) + " | | | | | | | | | | |")
    L += ["", "READING: IN-SAMPLE and PER-REGIME rows are ceilings - the exit was chosen on the same trades it is "
              "scored on (210 trials). The WALK-FORWARD row is what a live system could have done: it picks the exit "
              "from the past only. The gap between them is the optimism a no-holdout number carries.",
          "CAVEATS: label returns on the v3 basis; two years dominated by bull and mild tape; picks are ~3 a week so "
              "single trades move the weekly numbers."]
    fn = f"reports/research/student_exit_{date.today().isoformat()}.md"
    open(fn, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L), flush=True)
    print("EXIT SEARCH COMPLETE", flush=True)


if __name__ == "__main__":
    main()
