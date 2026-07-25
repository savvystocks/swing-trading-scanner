"""CLI: the Treasurer + macro-brake SHADOW report.

    python -m src.brain.run_treasurer --snapshot <dir-or-gz> --out <workdir> --reports reports/treasurer

Sizes the Council's shadow TAKEs (recommendation only), computes the NORTH_STAR P(halt) estimate on
the measured TAKE distribution, and reports how often the macro brake would have fired. Brain-side,
recording only; the engine still sizes a fixed 1 contract.
"""
import os
import argparse
import numpy as np
import pandas as pd

from . import loader, foundry, discovery as D, convergence as CV, council as C, treasurer as T


def run(snapshot_source, out_dir, reports_dir):
    os.makedirs(reports_dir, exist_ok=True)
    snap = loader.load_snapshot(snapshot_source, workdir=os.path.join(out_dir, "snap"))
    ds = foundry.build_dataset(snap, out_dir)
    fb, X, kept, meta = CV.prepare_frame(ds, snap["db_path"])
    fb["net_ret"] = fb["realized_return"] - fb["cost_base"]
    trials = D.Trials()
    res = C.run_council(fb, X, kept, trials)

    y = fb["y_up"].to_numpy(dtype=np.float64)
    rr = fb["realized_return"].to_numpy(dtype=np.float64)
    mu_win = float(np.nanmean(rr[y == 1])) if (y == 1).any() else 0.30
    mu_loss = float(np.nanmean(rr[y == 0])) if (y == 0).any() else -0.50

    take = res["take"]
    blend = res["blend"]
    import sqlite3
    con = sqlite3.connect(snap["db_path"])
    px = dict(con.execute("SELECT candidate_id, entry_ref FROM candidates").fetchall())
    bs = dict(con.execute("SELECT candidate_id, bid_size FROM candidates").fetchall())
    con.close()
    cid = fb["candidate_id"].to_numpy()
    price = np.array([px.get(c) if px.get(c) is not None else np.nan for c in cid], dtype=np.float64)
    top_size = np.array([bs.get(c) if bs.get(c) is not None else np.nan for c in cid], dtype=np.float64)
    net = fb["net_ret"].to_numpy(dtype=np.float64)
    uniq = fb["weight"].to_numpy(dtype=np.float64)

    sizes = []
    for i in np.where(take & np.isfinite(blend))[0]:
        rec = T.recommend_size(float(blend[i]), mu_win, mu_loss,
                               float(price[i]) if np.isfinite(price[i]) else None,
                               top_size=float(top_size[i]) if np.isfinite(top_size[i]) else None)
        sizes.append(rec["contracts"])
    p_halt = T.estimate_p_halt(net[take], uniq[take], fraction=T.KELLY_FRACTION * 0.1)

    # macro brake over the pile using the harvested VIX context
    vix_col = meta.get("vix_col")
    vix = pd.to_numeric(X[vix_col], errors="coerce").to_numpy() if vix_col else np.full(len(fb), np.nan)
    vix_ref = np.nanmedian(vix) if np.isfinite(vix).any() else None
    braked = 0
    if np.isfinite(vix).any():
        for v in vix:
            if np.isfinite(v) and T.macro_brake_state(float(v), vix_ref)["state"] == "BRAKE":
                braked += 1

    lines = [
        f"# Treasurer + macro brake (Phase 4, SHADOW) - {ds['dataset_version']}", "",
        "Sizing is a recommendation only; the engine sizes a FIXED 1 contract until the Governor",
        "promotes the Treasurer. All figures cost-inclusive and bid-side.", "",
        "## Sizing of the Council's shadow TAKEs",
        f"- Council TAKEs sized this run: {len(sizes)}",
        f"- empirical mean win {mu_win:+.3f} / mean loss {mu_loss:+.3f}  (payoff ratio {abs(mu_win/mu_loss):.2f})"
        if mu_loss else "- payoff ratio unavailable",
        f"- recommended contracts (median / max): {int(np.median(sizes)) if sizes else 0} / {int(np.max(sizes)) if sizes else 0}"
        f"  [half-Kelly cap {T.KELLY_FRACTION}, hard cap {T.KELLY_HARD_CAP}, $800 budget, liquidity {int(T.LIQUIDITY_FRAC*100)}%]",
        "",
        "## P(halt) - NORTH_STAR pre-live requirement",
        f"- probability of a -{int(T.HALT_DRAWDOWN*100)}% drawdown under the measured TAKE distribution: "
        f"{p_halt.get('p_halt')}  ({p_halt.get('note')})",
        f"- {p_halt.get('n_returns', 0)} TAKE returns bootstrapped over a {p_halt.get('horizon', 60)}-trade horizon"
        if p_halt.get("p_halt") is not None else f"- {p_halt.get('note')}",
        "",
        "## Macro circuit brake",
        f"- rows where the macro brake WOULD have fired: {braked} of {len(fb)}"
        f" ({100.0*braked/max(len(fb),1):.1f}%)  [VIX>= {T.VIX_ABS:.0f} or +{int(T.VIX_SPIKE*100)}% spike]",
        "- shadow only: records would-have-braked; arms live only through LIVE_GATE + Governor.",
        "",
        f"- trials counted (council pass): {trials.as_dict()}",
        "", "SHADOW ONLY - no order, size, or brake was changed. The frozen engine is untouched.",
    ]
    path = os.path.join(reports_dir, f"treasurer_{ds['dataset_version']}.md")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines))
    print("report ->", path)
    return {"report": path, "p_halt": p_halt, "n_takes": len(sizes)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--out", default="treasurer_work")
    ap.add_argument("--reports", default="reports/treasurer")
    a = ap.parse_args()
    run(a.snapshot, a.out, a.reports)
