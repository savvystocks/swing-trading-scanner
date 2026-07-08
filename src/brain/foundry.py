"""Stage 0 - the Data Foundry. build_dataset() joins candidates <-> labels, derives per-row metrics
from the stored bid_path, expands the payload JSON into a feature matrix with an auto-generated feature
dictionary, preserves full provenance, applies GATE-1 overlap weights, runs the quality gates, and
writes a deterministic versioned parquet + a dataset card.

Executed and skipped rows stay together, distinguished only by `executed` and `sample_tier`. Censored
and still-open rows are excluded. Imports no execution module (weights is a sibling brain module).
"""
import os
import json
import sqlite3
import numpy as np
import pandas as pd

from . import weights as W

PROVENANCE = ["candidate_id", "feature_set_version", "sample_tier", "executed", "params_hash",
              "rule_score", "signal_ts", "ticker", "occ_symbol", "spread_pct"]
DERIVED = ["outcome", "label", "realized_return", "time_to_resolution_min", "mfe", "mae",
           "resolution_ts", "window_start", "window_end", "mean_concurrency", "avg_uniqueness",
           "weight", "half_spread"]


def _flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}{k}."))
    elif isinstance(obj, (list, tuple)):
        out[prefix[:-1]] = json.dumps(obj)                   # keep lists atomic (rare in the payload)
    else:
        out[prefix[:-1]] = obj
    return out


def _read(con, table):
    try:
        return pd.read_sql_query(f"SELECT * FROM {table}", con)
    except Exception:
        return pd.DataFrame()


def _bidpath_metrics(bid_path, candidates):
    """MFE/MAE recomputed independently from the raw bid_path (no barrier logic, so no execution
    import). return_t = (bid - entry_ref)/entry_ref over non-stale bids up to resolution."""
    if bid_path.empty:
        return {}
    entry = candidates.set_index("candidate_id")["entry_ref"].to_dict()
    res = candidates.set_index("candidate_id")["resolution_ts"].to_dict()
    bp = bid_path[(bid_path["bid"].notna()) & (bid_path.get("stale", 0).fillna(0) == 0)].copy()
    metrics = {}
    for cid, grp in bp.groupby("candidate_id"):
        e = entry.get(cid)
        if not e or e <= 0:
            continue
        r = res.get(cid)
        g = grp[grp["poll_ts_utc"] <= r] if r is not None and not np.isnan(r) else grp
        if g.empty:
            continue
        rets = (g["bid"].to_numpy(dtype=float) - e) / e
        metrics[cid] = (float(np.max(rets)), float(np.min(rets)))
    return metrics


def _feature_dictionary(feat_df, fsv):
    d = {}
    for col in feat_df.columns:
        s = feat_df[col]
        nonnull = s.notna()
        first_seen = None
        if nonnull.any() and fsv is not None:
            fv = fsv[nonnull.to_numpy()]
            first_seen = str(min([x for x in fv if x is not None])) if any(x is not None for x in fv) else None
        d[col] = {"dtype": str(s.dtype), "null_rate": float(1 - nonnull.mean()),
                  "first_seen_feature_set_version": first_seen}
    return d


def _quality_gates(df, feat_cols, baseline_null_rates=None, spike=0.20):
    warnings, hard_fail = [], []
    dup = df["candidate_id"].duplicated().sum()
    if dup:
        hard_fail.append(f"{dup} duplicate candidate_id(s)")
    if not df.empty:
        day = pd.to_datetime(df["signal_ts"], unit="ms", utc=True).dt.date
        rnd = df["sample_tier"] == "random"
        per_day = rnd.groupby(day).sum()
        zero_days = [str(d) for d, c in per_day.items() if c == 0]
        if zero_days:
            warnings.append(f"{len(zero_days)} day(s) with zero random-tier rows: {zero_days[:5]}")
    if baseline_null_rates and feat_cols:
        for c in feat_cols:
            base = baseline_null_rates.get(c)
            if base is None:
                continue
            cur = float(df[c].isna().mean()) if c in df else 1.0
            if cur > base + spike:
                warnings.append(f"null-rate spike {c}: {base:.2f} -> {cur:.2f}")
    return warnings, hard_fail


def build_dataset(snapshot, out_dir, cache=None, baseline_null_rates=None):
    """Build the versioned dataset from a loaded snapshot dict (loader.load_snapshot output).
    Returns dict: df, feature_cols, feature_dict, card, warnings, dataset_version, parquet_path,
    feature_dict_path, weight_cache, hard_fail."""
    os.makedirs(out_dir, exist_ok=True)
    db_path = snapshot["db_path"] if isinstance(snapshot, dict) else snapshot
    snapshot_id = snapshot.get("snapshot_id", "unknown") if isinstance(snapshot, dict) else "unknown"
    con = sqlite3.connect(db_path)
    try:
        cand = _read(con, "candidates")
        lab = _read(con, "labels")
        bid = _read(con, "bid_path")
    finally:
        con.close()

    feat_cols = []
    if cand.empty or lab.empty:
        df = pd.DataFrame(columns=PROVENANCE + DERIVED)
    else:
        df = cand.merge(lab, on="candidate_id", how="inner", suffixes=("", "_lab"))
        df = df.rename(columns={"signal_ts_utc": "signal_ts"})
        # exclude censored + still-open
        keep = (~df["outcome"].isin(["censored", "open"])) & df["label"].notna() & df["censored_reason"].isna()
        df = df[keep].copy()
        df["resolution_ts"] = df["touch_ts_utc"].where(df["touch_ts_utc"].notna(), df["vertical_barrier_ts"])
        df["time_to_resolution_min"] = df["time_to_touch_min"].where(
            df["time_to_touch_min"].notna(), (df["resolution_ts"] - df["signal_ts"]) / 60000.0)
        # params_hash is PROVENANCE ONLY: the Foundry pools EVERY row across ALL params_hash values and
        # NEVER groups/filters/segments by it. Load-bearing invariant - params_hash fingerprints the whole
        # tunables dict, so an operational-config change (e.g. a backstop canary swap) rotates it WITHOUT
        # any change to the trading recipe; segmenting by it would fragment the brain's training sample.
        # Locked by test_brain.test_foundry_pools_across_params_hash. (Line below is column-existence only.)
        if "params_hash" not in df:
            df["params_hash"] = None
        # half-spread at signal, as a FRACTION of premium (spread_pct is a percentage). Cost placeholder.
        df["half_spread"] = df.get("spread_pct", pd.Series(np.nan, index=df.index)).astype(float) / 2.0 / 100.0
        # MFE/MAE recomputed from bid_path (independent), else labels' own values
        df["resolution_ts"] = df["resolution_ts"].astype(float)
        cand_for_bp = df[["candidate_id", "entry_ref", "resolution_ts"]]
        mm = _bidpath_metrics(bid, cand_for_bp)
        df["mfe"] = [mm.get(c, (r_mfe, None))[0] if c in mm else r_mfe
                     for c, r_mfe in zip(df["candidate_id"], df.get("mfe", pd.Series(np.nan, index=df.index)))]
        df["mae"] = [mm.get(c, (None, r_mae))[1] if c in mm else r_mae
                     for c, r_mae in zip(df["candidate_id"], df.get("mae", pd.Series(np.nan, index=df.index)))]
        # expand payload JSON
        feats = []
        for raw in df["features"].fillna("{}"):
            try:
                feats.append(_flatten(json.loads(raw) if isinstance(raw, str) else (raw or {})))
            except Exception:
                feats.append({})
        feat_df = pd.json_normalize(feats).reset_index(drop=True)
        feat_cols = list(feat_df.columns)
        df = pd.concat([df.reset_index(drop=True), feat_df.add_prefix("f.")], axis=1)
        feat_cols = ["f." + c for c in feat_cols]

    # GATE 1 weights (per-underlying average uniqueness) + incremental cache
    weight_cache = cache or {}
    if not df.empty:
        newest = float(df["signal_ts"].max())
        df, weight_cache = W.compute_weights(df, signal_col="signal_ts", resolution_col="resolution_ts",
                                             group_col="ticker", id_col="candidate_id",
                                             cache=cache, newest_signal_ts=newest)
    else:
        for c in ["window_start", "window_end", "mean_concurrency", "avg_uniqueness", "weight"]:
            df[c] = pd.Series(dtype=float)

    warnings, hard_fail = _quality_gates(df, feat_cols, baseline_null_rates)
    if hard_fail:
        raise ValueError("Foundry HARD-FAIL: " + "; ".join(hard_fail))

    fsv = df["feature_set_version"].to_numpy() if "feature_set_version" in df else np.array([])
    feature_dict = _feature_dictionary(df[feat_cols], fsv) if feat_cols else {}
    dataset_version = snapshot_id

    keep_cols = [c for c in PROVENANCE + DERIVED if c in df.columns] + feat_cols
    df_out = df[keep_cols].copy() if keep_cols else df.copy()
    parquet_path = os.path.join(out_dir, f"dataset_{dataset_version}.parquet")
    df_out.to_parquet(parquet_path, index=False)
    feat_dict_path = os.path.join(out_dir, f"feature_dict_{dataset_version}.json")
    json.dump(feature_dict, open(feat_dict_path, "w"), indent=2, default=str)

    card = _dataset_card(df_out, snapshot, dataset_version, feature_dict, warnings)
    json.dump(card, open(os.path.join(out_dir, f"card_{dataset_version}.json"), "w"), indent=2, default=str)
    return {"df": df_out, "feature_cols": feat_cols, "feature_dict": feature_dict, "card": card,
            "warnings": warnings, "dataset_version": dataset_version, "parquet_path": parquet_path,
            "feature_dict_path": feat_dict_path, "weight_cache": weight_cache, "hard_fail": hard_fail}


def _dataset_card(df, snapshot, version, feature_dict, warnings):
    def counts(col):
        return df[col].value_counts(dropna=False).to_dict() if col in df and not df.empty else {}
    date_range = None
    if not df.empty and "signal_ts" in df:
        ts = pd.to_datetime(df["signal_ts"], unit="ms", utc=True)
        date_range = [str(ts.min()), str(ts.max())]
    null_report = {k: v["null_rate"] for k, v in feature_dict.items()}
    return {
        "dataset_version": version,
        "snapshot_id": snapshot.get("snapshot_id") if isinstance(snapshot, dict) else None,
        "snapshot_row_counts": snapshot.get("row_counts") if isinstance(snapshot, dict) else None,
        "rows": int(len(df)),
        "rows_by_tier": {str(k): int(v) for k, v in counts("sample_tier").items()},
        "rows_by_outcome": {str(k): int(v) for k, v in counts("outcome").items()},
        "rows_by_executed": {str(k): int(v) for k, v in counts("executed").items()},
        "date_range": date_range,
        "n_features": len(feature_dict),
        "null_report": null_report,
        "warnings": warnings,
    }
