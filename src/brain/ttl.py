"""School addendum Section 2 - FEATURE TTL enforcement, shared by the Council (shadow) and the
dormant gate-mode decision path so harvest-time and decision-time use the IDENTICAL rule.

At harvest time every feature block's asof is the row's signal_ts (sensors compute at scan time).
At decision time, a block older than its TTL becomes MISSING (NaN) and flows through the model's
native missing-data path. Values are NEVER carried forward or substituted. Component failure is a
VETO handled by the caller - this module only nulls stale FEATURES.
"""
import os
import json
import numpy as np

_REGISTRY = None


def _load():
    global _REGISTRY
    if _REGISTRY is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "feature_ttl.json")
        try:
            _REGISTRY = json.load(open(path)).get("ttl_minutes", {})
        except Exception:
            _REGISTRY = {}
    return _REGISTRY


def _block_of(col):
    """Feature column names are '<block>.<name>' or bare '<name>'; map to the TTL block key."""
    head = col.split(".")[0]
    return head


def ttl_minutes(col):
    reg = _load()
    return reg.get(_block_of(col))


def apply_ttl(X, cols, signal_ts_ms, asof_ms=None, decision_ms=None):
    """Return a COPY of X with columns whose block is stale-past-TTL set to NaN for the affected rows.

    asof_ms / decision_ms may be scalars or per-row arrays. When either is None the asof defaults to
    each row's own signal_ts and the decision time to that same instant - i.e. the retrospective
    shadow case where nothing is stale by construction, so the frame is returned unchanged.
    """
    if asof_ms is None or decision_ms is None:
        return X.copy()
    signal_ts_ms = np.asarray(signal_ts_ms, dtype=np.float64)
    asof = np.broadcast_to(np.asarray(asof_ms, dtype=np.float64), signal_ts_ms.shape)
    dec = np.broadcast_to(np.asarray(decision_ms, dtype=np.float64), signal_ts_ms.shape)
    age_min = (dec - asof) / 60000.0
    Xc = X.copy()
    for col in cols:
        ttl = ttl_minutes(col)
        if ttl is None:
            continue
        stale = age_min > ttl
        if stale.any():
            vals = Xc[col].to_numpy(dtype=np.float64).copy()
            vals[stale] = np.nan
            Xc[col] = vals
    return Xc
