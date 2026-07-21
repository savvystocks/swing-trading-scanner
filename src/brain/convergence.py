"""Part 5 - the Convergence Protocol: the full search re-run under ten deliberately varied
configurations, one dial changed per angle. No single angle's result is ever "the finding" - the
deliverable is the CONVERGENCE MATRIX and its three lists:

    SURVIVORS  present (confirmed) in >= 8 of 10 angles - the only shortlist eligible for the
               Student SHADOW path (promotion rule in ROADMAP; never a live deployment from here)
    FLICKERS   4-7 - watch, don't act
    MIRAGES    <= 3 - named and buried so they are never "rediscovered"

The trials counter aggregates across ALL angles into one global PBO / Deflated-Sharpe accounting.
The matrix accretes across weekly runs (reports/discovery/convergence_state.json): a survivor must
KEEP surviving to remain one. Brain-side only; writes only report artifacts.
"""
import os
import json
import numpy as np
import pandas as pd

from . import ev as EV
from . import harness as H
from . import discovery as D

BASE_CFG = {"seed": 7, "scheme": "terciles", "learner": "gbm", "wcol": "weight",
            "cost_mult": 1.0, "label": "current", "population": "full", "target": "up",
            "regime": "all", "slice": "purged_folds", "ycol": "y_up"}

ANGLES = [
    ("1 seeds", [{"seed": 7}, {"seed": 77}, {"seed": 777}]),
    ("2 time slices", [{"slice": "first_to_second"}, {"slice": "second_to_first"},
                       {"slice": "leave_one_week_out"}]),
    ("3 bands", [{"scheme": "terciles"}, {"scheme": "quartiles"}, {"scheme": "tree"}]),
    ("4 learner", [{"learner": "gbm"}, {"learner": "logistic"}, {"learner": "rules"}]),
    ("5 weighting", [{"wcol": "weight"}, {"wcol": "w_raw"}]),
    ("6 costs", [{"cost_mult": 1.0}, {"cost_mult": 2.0}]),
    ("7 labels", [{"label": "current"}, {"label": "iv_scaled"}]),
    ("8 population", [{"population": "full"}, {"population": "executed"},
                      {"population": "real_spread"}, {"population": "dense"}]),
    ("9 target", [{"target": "up"}, {"target": "net_pos"}]),
    ("10 regime", [{"regime": "all"}, {"regime": "low_vix"}, {"regime": "high_vix"}]),
]

SURVIVOR_MIN, FLICKER_MIN = 8, 4
MODEL_SIG = "model_top_quintile"


def prepare_frame(ds, snap_db_path):
    """The feature-bearing working frame + numeric feature matrix + the columns the angles vary over.
    Rows without a feature vector (the 'none' prefilter tier) cannot be modeled and are excluded here;
    their share is reported, not hidden."""
    df = ds["df"].copy()
    n_all = len(df)
    fb = df[df["sample_tier"].isin(["topn", "executed", "random"])].reset_index(drop=True)
    X, kept = D.numeric_features(fb, ds["feature_cols"])
    fb["y_up"] = (fb["outcome"] == "up").astype(float)
    fb["cost_base"] = pd.to_numeric(fb["half_spread"], errors="coerce").fillna(0.0)
    fb["w_raw"] = 1.0
    fb["weight"] = pd.to_numeric(fb["weight"], errors="coerce").fillna(1.0)
    vix_col = next((c for c in kept if c.endswith("macro.vix") or c.endswith("vix_level")), None)
    iv_col = next((c for c in kept if c.endswith("vrp.front_iv") or c.endswith("iv_term.iv_front")), None)
    dense = X[kept].notna().mean(axis=1) >= 0.6
    meta = {"n_all_graded": n_all, "n_feature_bearing": len(fb),
            "fb_share": round(len(fb) / max(n_all, 1), 4), "vix_col": vix_col, "iv_col": iv_col,
            "dense_mask": dense.to_numpy(), "snap_db_path": snap_db_path}
    return fb, X, kept, meta


def variant_frame(fb, X, kept, meta, cfg, iv_cache):
    """Apply one configuration's dials (population / labels / target / cost / regime) and return the
    ready-to-search frame. Returns None when the slice is too thin (the cell renders UNDERPOWERED)."""
    df = fb.copy()
    df["net_ret"] = df["realized_return"] - df["cost_base"] * cfg["cost_mult"]
    if cfg["label"] == "iv_scaled":
        if iv_cache.get("y2") is None:
            return None
        df["y_up"] = iv_cache["y2"]
        df["net_ret"] = iv_cache["r2"] - df["cost_base"] * cfg["cost_mult"]
        df = df[np.isfinite(df["y_up"])]
    if cfg["target"] == "net_pos":
        df["y_up"] = (df["net_ret"] > 0).astype(float)
    mask = np.ones(len(df), dtype=bool)
    if cfg["population"] == "executed":
        mask &= df["executed"].to_numpy() == 1
    elif cfg["population"] == "real_spread":
        mask &= df["signal_ts"].to_numpy(dtype=np.float64) >= D.REAL_SPREAD_SINCE_MS
    elif cfg["population"] == "dense":
        mask &= meta["dense_mask"][df.index.to_numpy()] if cfg["label"] != "iv_scaled" else \
            meta["dense_mask"][df.index.to_numpy()]
    if cfg["regime"] != "all":
        if meta["vix_col"] is None:
            return None
        vix = pd.to_numeric(X[meta["vix_col"]], errors="coerce").reindex(df.index)
        med = np.nanmedian(vix)
        mask &= (vix < med).to_numpy() if cfg["regime"] == "low_vix" else (vix >= med).to_numpy()
    df = df[mask]
    if len(df) < 2 * D.MIN_TRAIN // 3 or df["y_up"].nunique() < 2:
        return None
    Xv = X.loc[df.index]
    cfg = {**cfg, "ycol": "y_up"}
    return df.reset_index(drop=True), Xv.reset_index(drop=True), cfg


def _two_block_split(starts, ends, reverse=False):
    """Discovery on one time half, grading on the other, purged at the boundary; `reverse` grades the
    PAST from the future (a deliberate regime-fragility probe)."""
    order = np.argsort(starts, kind="mergesort")
    half = len(order) // 2
    a, b = order[:half], order[half:]
    tr, te = (b, a) if reverse else (a, b)
    t0, t1 = starts[te].min(), ends[te].max()
    keep = ~((starts[tr] < t1) & (ends[tr] > t0))
    return [(tr[keep], te)]


def _splits_for(cfg, df):
    starts = df["window_start"].to_numpy(dtype=np.float64)
    ends = df["window_end"].to_numpy(dtype=np.float64)
    if cfg["slice"] == "first_to_second":
        return _two_block_split(starts, ends)
    if cfg["slice"] == "second_to_first":
        return _two_block_split(starts, ends, reverse=True)
    if cfg["slice"] == "leave_one_week_out":
        wk = D.week_key(df["signal_ts"])
        n = max(2, min(len(np.unique(wk)), 6))
        return list(H.PurgedKFold(n, 0.02).split(starts, ends))
    return list(H.PurgedKFold(4, 0.02).split(starts, ends))


def run_variant(df, Xv, kept, cfg, trials):
    """One configuration's search: rules mined on train folds, graded on test folds only; the model's
    top-quintile OOF selection graded the same way. Returns finding-signature -> pooled OOS stats."""
    y = df[cfg["ycol"]].to_numpy(dtype=np.float64)
    w = df[cfg["wcol"]].to_numpy(dtype=np.float64)
    Xm = Xv[kept].to_numpy(dtype=np.float64)
    starts = df["window_start"].to_numpy(dtype=np.float64)
    ends = df["window_end"].to_numpy(dtype=np.float64)
    acc = {}
    base_num = base_den = 0.0
    n_splits_run = 0
    for tr, te in _splits_for(cfg, df):
        if len(tr) < D.MIN_TRAIN // 2 or len(te) == 0 or np.unique(y[tr]).size < 2:
            continue
        n_splits_run += 1
        cuts, band_counts = [], []
        for j in range(len(kept)):
            cs = D.band_cuts(Xm[tr][:, j], cfg["scheme"], y=y[tr], w=w[tr])
            cuts.append(cs)
            band_counts.append(len(cs) + 1 if cs else 0)
        B_tr = np.column_stack([D.band_assign(Xm[tr][:, j], cuts[j]) if cuts[j] else
                                np.full(len(tr), -1) for j in range(len(kept))])
        B_te = np.column_stack([D.band_assign(Xm[te][:, j], cuts[j]) if cuts[j] else
                                np.full(len(te), -1) for j in range(len(kept))])
        for r in D.mine_rules(B_tr, band_counts, y[tr], w[tr], kept, trials, top_n=5):
            sig = D.rule_signature(r["clause"], band_counts, kept)
            m = D.rule_mask(B_te, r["clause"])
            a = acc.setdefault(sig, {"wy": 0.0, "w": 0.0, "w2": 0.0, "folds": 0})
            a["folds"] += 1
            if m.any():
                a["wy"] += float((w[te][m] * y[te][m]).sum())
                a["w"] += float(w[te][m].sum())
                a["w2"] += float((w[te][m] ** 2).sum())
        if cfg["learner"] != "rules":
            m_oof = np.full(len(te), np.nan)
            model = D.Learner(cfg["learner"], cfg["seed"]).fit(Xm[tr], y[tr], w[tr])
            trials.bump("model_fits")
            m_oof = model.predict_proba(Xm[te])
            q = np.nanquantile(m_oof, 0.8)
            trials.bump("thresholds")
            m = m_oof >= q
            a = acc.setdefault(MODEL_SIG, {"wy": 0.0, "w": 0.0, "w2": 0.0, "folds": 0})
            a["folds"] += 1
            if m.any():
                a["wy"] += float((w[te][m] * y[te][m]).sum())
                a["w"] += float(w[te][m].sum())
                a["w2"] += float((w[te][m] ** 2).sum())
        base_num += float((w[te] * y[te]).sum())
        base_den += float(w[te].sum())
    if base_den <= 0:
        return None
    base = base_num / base_den
    out = {}
    for sig, a in acc.items():
        if a["w"] <= 0:
            out[sig] = {"status": "absent", "p": None, "n_eff": 0.0, "lift": None}
            continue
        p = a["wy"] / a["w"]
        n_eff = a["w"] * a["w"] / max(a["w2"], 1e-12)
        lift = p / base if base > 0 else float("nan")
        if n_eff < D.MIN_BAND:
            status = "underpowered"
        elif lift >= 1.5 and a["folds"] >= min(2, n_splits_run):
            status = "confirmed"
        elif lift >= 1.1:
            status = "weak"
        else:
            status = "absent"
        out[sig] = {"status": status, "p": round(p, 4), "n_eff": round(n_eff, 1),
                    "lift": round(lift, 3) if np.isfinite(lift) else None}
    return out


def run_campaign(fb, X, kept, meta, trials):
    """All ten angles. Returns (matrix, angle_notes) where matrix maps finding -> angle -> cell."""
    iv_cache = {"y2": None, "r2": None}
    if meta["iv_col"] is not None:
        iv_vals = pd.to_numeric(X[meta["iv_col"]], errors="coerce").to_numpy()
        y2, r2 = D.iv_scaled_labels(meta["snap_db_path"], fb, iv_vals)
        iv_cache = {"y2": y2, "r2": r2}
    matrix = {}
    angle_notes = {}
    for angle_name, variants in ANGLES:
        variant_results = []
        for ov in variants:
            cfg = {**BASE_CFG, **ov}
            vf = variant_frame(fb, X, kept, meta, cfg, iv_cache)
            trials.bump("angle_runs")
            if vf is None:
                variant_results.append(None)
                continue
            dfv, Xv, cfgv = vf
            variant_results.append(run_variant(dfv, Xv, kept, cfgv, trials))
        angle_notes[angle_name] = f"{sum(1 for r in variant_results if r is not None)}/{len(variants)} variants had sample"
        sigs = set()
        for r in variant_results:
            if r:
                sigs.update(r.keys())
        for sig in sigs:
            cells = matrix.setdefault(sig, {})
            statuses = [r.get(sig, {"status": "absent"})["status"] if r else "underpowered"
                        for r in variant_results]
            powered = [s for s in statuses if s != "underpowered"]
            if not powered:
                cells[angle_name] = "UNDERPOWERED"
            elif all(s == "confirmed" for s in powered):
                cells[angle_name] = "confirmed"
            elif any(s in ("confirmed", "weak") for s in powered):
                cells[angle_name] = "weak"
            else:
                cells[angle_name] = "absent"
    return matrix, angle_notes


def classify(matrix):
    survivors, flickers, mirages = [], [], []
    for sig, cells in matrix.items():
        n_conf = sum(1 for a, _ in ANGLES if cells.get(a) == "confirmed")
        entry = (sig, n_conf, cells)
        if n_conf >= SURVIVOR_MIN:
            survivors.append(entry)
        elif n_conf >= FLICKER_MIN:
            flickers.append(entry)
        else:
            mirages.append(entry)
    key = lambda e: -e[1]
    return sorted(survivors, key=key), sorted(flickers, key=key), sorted(mirages, key=key)


def accrete(state_path, snapshot_id, matrix, survivors):
    """The matrix accretes across weekly runs; a survivor must KEEP surviving to remain one."""
    state = {"findings": {}}
    if os.path.exists(state_path):
        try:
            state = json.load(open(state_path, encoding="utf-8"))
        except Exception:
            pass
    surv_sigs = {s for s, _, _ in survivors}
    for sig, cells in matrix.items():
        n_conf = sum(1 for a, _ in ANGLES if cells.get(a) == "confirmed")
        rec = state["findings"].setdefault(sig, {"first_seen": snapshot_id, "history": []})
        if not any(h["snapshot"] == snapshot_id for h in rec["history"]):
            rec["history"].append({"snapshot": snapshot_id, "confirmed_angles": n_conf,
                                   "survivor": sig in surv_sigs})
    standing = {}
    for sig, rec in state["findings"].items():
        hist = rec["history"]
        ever = [h["survivor"] for h in hist]
        if ever and all(ever):
            standing[sig] = f"SURVIVOR x{len(hist)} run(s)"
        elif any(ever):
            standing[sig] = "LAPSED (survived before, not always)"
    json.dump(state, open(state_path, "w", encoding="utf-8"), indent=2)
    return standing
