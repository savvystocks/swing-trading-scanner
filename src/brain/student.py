"""Stage 2 - the STUDENT (ROADMAP item 8): a gradient-boosted meta-labeler that answers ONE question
per candidate - "is this signal real?" - on the harvested features. The V10 rules engine stays
primary; the Student's ceiling is gate-plus-sizing, reached only through shadow.

Acceptance is item 8's, mechanically enforced here, evaluated ONLY through the Stage-0/1 machinery:
  1. OOS Wilson lower bound of the calibrated selection's hit rate exceeds the empirical hurdle
  2. PBO (CPCV, config grid counted as trials) at or below PBO_MAX
  3. Deflated Sharpe positive, with the trials count explicit
  4. beats the rules engine on the SAME purged splits (selection vs executed, pooled OOF)
A run on fewer than GATE_FB feature-bearing graded rows is PROVISIONAL: the full report renders but
the official verdict is withheld. Trained on full history with time-decay weights x uniqueness
weights (no rolling-window amnesia); feature redundancy killed by correlation clustering.

Brain-side only. Writes model artifacts to the workdir and reports only.
"""
import json
import numpy as np
import pandas as pd

from . import ev as EV
from . import harness as H
from . import calibration as CAL
from . import discovery as D

GATE_FB = 8000                 # feature-bearing graded rows below this -> PROVISIONAL, no official verdict
HALF_LIFE_DAYS = 21            # time-decay half-life (pinned; changing it is a counted trial)
CLUSTER_CORR = 0.85            # |spearman| at/above this -> redundant, keep one representative
N_FOLDS, EMBARGO = 5, 0.02
PBO_MAX = 0.20
PBO_GRID = [{"learning_rate": lr, "max_depth": d, "half_life": hl}
            for lr in (0.05, 0.08, 0.12) for d in (2, 3) for hl in (14, 28)]
DAY_MS = 24 * 3600 * 1000


def time_decay(signal_ts, half_life_days, now_ts=None):
    ts = np.asarray(signal_ts, dtype=np.float64)
    now = float(now_ts if now_ts is not None else ts.max())
    age_days = np.maximum(now - ts, 0.0) / DAY_MS
    return 0.5 ** (age_days / float(half_life_days))


def cluster_features(X, kept, corr_threshold=CLUSTER_CORR):
    """Kill redundancy: hierarchical clustering on 1-|spearman|; keep the best-filled column of each
    cluster. Deterministic, label-free (no leakage)."""
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform
    Xv = X[kept].to_numpy(dtype=np.float64)
    fill = np.isfinite(Xv).mean(axis=0)
    rho = pd.DataFrame(Xv, columns=kept).corr(method="spearman").to_numpy()
    rho = np.where(np.isfinite(rho), rho, 0.0)
    np.fill_diagonal(rho, 1.0)
    dist = 1.0 - np.abs(rho)
    dist = (dist + dist.T) / 2.0
    np.fill_diagonal(dist, 0.0)
    labels = fcluster(linkage(squareform(dist, checks=False), method="average"),
                      t=1.0 - corr_threshold, criterion="distance")
    reduced, dropped = [], {}
    for cl in np.unique(labels):
        members = np.where(labels == cl)[0]
        rep = members[int(np.argmax(fill[members]))]
        reduced.append(kept[rep])
        for m in members:
            if m != rep:
                dropped[kept[m]] = kept[rep]
    return sorted(reduced, key=kept.index), dropped


def _fit_config(Xv, y, w, cfg, seed, trials):
    from sklearn.ensemble import HistGradientBoostingClassifier
    m = D.Learner("gbm", seed)
    finite = np.isfinite(Xv)
    nunique = np.array([np.unique(Xv[finite[:, j], j]).size for j in range(Xv.shape[1])])
    m.keep = np.where(nunique >= 2)[0]
    m.model = HistGradientBoostingClassifier(
        max_depth=cfg["max_depth"], max_iter=120, learning_rate=cfg["learning_rate"],
        l2_regularization=1.0, min_samples_leaf=30, early_stopping=False, random_state=seed)
    m.model.fit(Xv[:, m.keep], y, sample_weight=w)
    trials.bump("student_fits")
    return m


def train_student(df, X, kept, trials, seed=7):
    """Train + OOF-evaluate the Student under PurgedKFold. Selection policy: calibrated win-probability
    at or above the empirical cost-inclusive hurdle (take only EV-positive candidates)."""
    reduced, dropped = cluster_features(X, kept)
    trials.bump("features_clustered_out", len(dropped))
    Xv = X[reduced].to_numpy(dtype=np.float64)
    y = df["y_up"].to_numpy(dtype=np.float64)
    uniq = df["weight"].to_numpy(dtype=np.float64)
    decay = time_decay(df["signal_ts"].to_numpy(), HALF_LIFE_DAYS)
    w = uniq * decay
    starts = df["window_start"].to_numpy(dtype=np.float64)
    ends = df["window_end"].to_numpy(dtype=np.float64)
    net = df["net_ret"].to_numpy(dtype=np.float64)
    cost = EV.cost_model(df["cost_base"].to_numpy())
    hurdle = EV.solve_threshold(df["realized_return"].to_numpy(), cost=cost)

    oof = np.full(len(y), np.nan)
    folds = []
    for tr, te in H.PurgedKFold(N_FOLDS, EMBARGO).split(starts, ends):
        if len(tr) < D.MIN_TRAIN // 2 or np.unique(y[tr]).size < 2:
            continue
        m = _fit_config(Xv[tr], y[tr], w[tr], {"learning_rate": 0.08, "max_depth": 3}, seed, trials)
        oof[te] = m.predict_proba(Xv[te])
        folds.append((tr, te, m))
    fin = np.isfinite(oof)
    cal = CAL.calibrate(oof[fin], y[fin]) if fin.sum() >= 50 else None
    p_cal = np.full(len(y), np.nan)
    if cal:
        p_cal[fin] = cal["predict"](oof[fin])

    sel = fin & (p_cal >= hurdle["threshold"])
    p_sel, neff_sel = D.weighted_rate(y[sel], uniq[sel]) if sel.any() else (float("nan"), 0.0)
    lo_sel, hi_sel = D.wilson_eff(p_sel, neff_sel)
    net_sel = float((uniq[sel] * net[sel]).sum() / max(uniq[sel].sum(), 1e-12)) if sel.any() else float("nan")
    # the rules engine on the SAME purged splits: its executed picks among OOF-scored rows
    eng = fin & (df["executed"].to_numpy() == 1)
    p_eng, neff_eng = D.weighted_rate(y[eng], uniq[eng]) if eng.any() else (float("nan"), 0.0)
    net_eng = float((uniq[eng] * net[eng]).sum() / max(uniq[eng].sum(), 1e-12)) if eng.any() else float("nan")

    auc = D.weighted_auc(y[fin], oof[fin], uniq[fin]) if fin.any() else float("nan")
    final = _fit_config(Xv, y, w, {"learning_rate": 0.08, "max_depth": 3}, seed, trials)
    medians = np.nanmedian(Xv, axis=0)
    return {
        "features": reduced, "dropped": dropped, "model": final, "calibration": cal,
        "medians": medians, "hurdle": hurdle, "cost": cost, "oof": oof, "p_cal": p_cal,
        "auc": auc, "n_oof": int(fin.sum()),
        "selection": {"n": int(sel.sum()), "n_eff": round(neff_sel, 1),
                      "hit": None if not np.isfinite(p_sel) else round(p_sel, 4),
                      "wilson_lo": None if not np.isfinite(lo_sel) else round(lo_sel, 4),
                      "wilson_hi": None if not np.isfinite(hi_sel) else round(hi_sel, 4),
                      "net_ret": None if not np.isfinite(net_sel) else round(net_sel, 4)},
        "engine_same_splits": {"n": int(eng.sum()), "n_eff": round(neff_eng, 1),
                               "hit": None if not np.isfinite(p_eng) else round(p_eng, 4),
                               "net_ret": None if not np.isfinite(net_eng) else round(net_eng, 4)},
        "config": {"half_life_days": HALF_LIFE_DAYS, "cluster_corr": CLUSTER_CORR,
                   "n_folds": N_FOLDS, "embargo": EMBARGO, "seed": seed,
                   "learning_rate": 0.08, "max_depth": 3},
    }


def cpcv_pbo(df, X, features, trials, n_groups=6, seed=7):
    """The Student's own CPCV path performance: the config grid trained per split, OOS selection
    return per config -> the PBO the weekly report has been rendering as 'pending'. Also the pinned
    config's per-split OOS series for the Deflated Sharpe."""
    Xv = X[features].to_numpy(dtype=np.float64)
    y = df["y_up"].to_numpy(dtype=np.float64)
    uniq = df["weight"].to_numpy(dtype=np.float64)
    net = df["net_ret"].to_numpy(dtype=np.float64)
    starts = df["window_start"].to_numpy(dtype=np.float64)
    cost = EV.cost_model(df["cost_base"].to_numpy())
    hurdle_t = EV.solve_threshold(df["realized_return"].to_numpy(), cost=cost)["threshold"]
    order = np.argsort(starts, kind="mergesort")
    groups = np.array_split(order, n_groups)
    combos, n_paths = H.cpcv_splits(n_groups, 2)
    M = np.full((len(combos), len(PBO_GRID)), np.nan)
    pinned = []
    for si, test_groups in enumerate(combos):
        te = np.concatenate([groups[g] for g in test_groups])
        tr = np.concatenate([groups[g] for g in range(n_groups) if g not in test_groups])
        if np.unique(y[tr]).size < 2:
            continue
        for ci, cfg in enumerate(PBO_GRID):
            w_tr = uniq[tr] * time_decay(df["signal_ts"].to_numpy()[tr], cfg["half_life"])
            m = _fit_config(Xv[tr], y[tr], w_tr, cfg, seed, trials)
            p = m.predict_proba(Xv[te])
            selm = p >= np.nanquantile(p, 0.8)
            trials.bump("thresholds")
            if selm.sum() < D.MIN_TAKES // 2:
                continue
            perf = float((uniq[te][selm] * net[te][selm]).sum() / max(uniq[te][selm].sum(), 1e-12))
            M[si, ci] = perf
            if cfg["learning_rate"] == 0.08 and cfg["max_depth"] == 3 and cfg["half_life"] == 28:
                pinned.append(perf)
    keep = ~np.all(np.isnan(M), axis=0)
    Mc = np.where(np.isnan(M), np.nanmin(M) if np.isfinite(M).any() else 0.0, M)
    pbo, note = H.probability_of_backtest_overfitting(Mc[:, keep] if keep.any() else Mc, min_trials=2)
    r = np.asarray(pinned, dtype=np.float64)
    if r.size >= 4 and r.std(ddof=1) > 1e-12:
        sr = float(r.mean() / r.std(ddof=1))
        # sr_variance must be the variance of the trials' SHARPE RATIOS, not of the raw return cells
        # (fixed 2026-07-25: passing raw cells put the deflation benchmark in return units).
        dsr, sr0, dnote = H.deflated_sharpe_ratio(sr, n_trials=max(trials.total, 1),
                                                  sr_variance=H.sharpe_variance_across_trials(Mc),
                                                  n_obs=int(r.size))
    else:
        dsr, sr0, dnote = None, None, f"UNDERPOWERED ({r.size} pinned CPCV paths; needs >= 4)"
    return {"pbo": pbo, "pbo_note": note, "dsr": dsr, "dsr_benchmark": sr0, "dsr_note": dnote,
            "n_splits": len(combos), "n_paths": n_paths, "grid_size": len(PBO_GRID),
            "hurdle": hurdle_t}


def acceptance(trained, pbo_out, n_fb, trials):
    """Item 8's gates, mechanically. Official verdict only at/above GATE_FB feature-bearing rows."""
    s = trained["selection"]
    g1 = s["wilson_lo"] is not None and s["wilson_lo"] > trained["hurdle"]["threshold"]
    g2 = pbo_out["pbo"] is not None and pbo_out["pbo"] <= PBO_MAX
    g3 = pbo_out["dsr"] is not None and pbo_out["dsr"] > 0.5
    e = trained["engine_same_splits"]
    g4 = (s["net_ret"] is not None and e["net_ret"] is not None and s["net_ret"] > e["net_ret"])
    provisional = n_fb < GATE_FB
    return {
        "provisional": provisional,
        "status": "PROVISIONAL (below gate)" if provisional else "OFFICIAL",
        "gates": {
            "1_oos_wilson_lo_above_hurdle": bool(g1),
            "2_pbo_at_or_below_0.20": bool(g2),
            "3_deflated_sharpe_positive": bool(g3),
            "4_beats_engine_same_splits": bool(g4),
        },
        "all_gates_pass": bool(g1 and g2 and g3 and g4),
        "verdict": ("WITHHELD - PROVISIONAL run below the " + str(GATE_FB) + " feature-bearing gate"
                    if provisional else
                    ("STUDENT ACCEPTED - eligible for shadow" if (g1 and g2 and g3 and g4)
                     else "STUDENT REJECTED - gates failed")),
        "trials_total": trials.total,
    }


def calibration_map(p_cal, hurdle, top=8):
    """School priority-2 (2026-07-28, report-only): the step-cliff visibility map. Isotonic
    calibration produces probability PLATEAUS; selection counts jump discontinuously as plateaus
    cross the bar (the mechanism behind the 3->54 selection explosion of 07-26). This renders where
    the plateaus sit and how much mass is near the bar, so the mechanism is visible BEFORE it
    misbehaves. No decision impact; calibration-method changes remain separate counted trials."""
    p = np.asarray(p_cal, float)
    p = p[np.isfinite(p)]
    if p.size == 0:
        return None
    vals, counts = np.unique(np.round(p, 4), return_counts=True)
    order = np.argsort(-counts)
    plateaus = [{"p": float(vals[i]), "n": int(counts[i]),
                 "vs_bar": round(float(vals[i] - hurdle), 4)} for i in order[:top]]
    bands = {"at_or_above_bar": int((p >= hurdle).sum()),
             "within_5pts_below": int(((p >= hurdle - 0.05) & (p < hurdle)).sum()),
             "5_to_10_below": int(((p >= hurdle - 0.10) & (p < hurdle - 0.05)).sum()),
             "10_to_20_below": int(((p >= hurdle - 0.20) & (p < hurdle - 0.10)).sum())}
    cliff = bands["within_5pts_below"] == 0 and bands["5_to_10_below"] == 0
    return {"n": int(p.size), "n_distinct_levels": int(vals.size), "plateaus": plateaus,
            "bands": bands, "max_p": float(p.max()), "cliff": bool(cliff)}


def shadow_table(trained, df, X, days=5):
    """What the frozen Student WOULD say about the most recent candidates - the shadow report.
    Reporting only; nothing here touches the engine."""
    features = trained["features"]
    Xv = X[features].to_numpy(dtype=np.float64)
    ts = df["signal_ts"].to_numpy(dtype=np.float64)
    cutoff = ts.max() - days * DAY_MS
    idx = np.where(ts >= cutoff)[0]
    if idx.size == 0:
        return pd.DataFrame()
    p_raw = trained["model"].predict_proba(Xv[idx])
    p = trained["calibration"]["predict"](p_raw) if trained["calibration"] else p_raw
    thr = trained["hurdle"]["threshold"]
    mda_idx = list(range(min(12, len(features))))
    rows = []
    dt = pd.to_datetime(ts[idx], unit="ms", utc=True)
    for k, i in enumerate(idx):
        take = p[k] >= thr
        reason = D.local_attribution(trained["model"], Xv[i], trained["medians"], features, mda_idx) \
            if take else ""
        rows.append({"date": str(dt[k])[:16], "ticker": df["ticker"].iloc[i],
                     "occ": df["occ_symbol"].iloc[i], "engine_took": int(df["executed"].iloc[i]),
                     "student_p": round(float(p[k]), 3),
                     "student_says": "TAKE" if take else "VETO", "reason": reason,
                     "outcome": df["outcome"].iloc[i],
                     "net_return": round(float(df["net_ret"].iloc[i]), 4)})
    return pd.DataFrame(rows)


def save_artifact(trained, out_dir, snapshot_id):
    import os
    import joblib
    path = os.path.join(out_dir, f"student_{snapshot_id}.joblib")
    joblib.dump({"model": trained["model"], "calibration_params": trained["calibration"]["params"]
                 if trained["calibration"] else None,
                 "selected_family": trained["calibration"]["selected"] if trained["calibration"] else None,
                 "features": trained["features"], "medians": trained["medians"],
                 "hurdle": trained["hurdle"], "config": trained["config"],
                 "snapshot_id": snapshot_id}, path)
    return path
