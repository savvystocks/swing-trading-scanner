"""GATE 1 - overlap weights via average uniqueness (Lopez de Prado, Advances in Financial Machine
Learning, ch. 4).

Every label's information window is its own exact [signal_ts, resolution_ts] (truncated at the first
barrier touch - it never runs to expiry if it resolved earlier). Concurrency is counted across rows
that share the same UNDERLYING whose windows intersect, regardless of contract/strike/expiry/direction
- contract-level isolation is forbidden. Different horizons are handled naturally by average
uniqueness: the mean, over each label's own lifespan, of 1/concurrency. A short contract nested inside
a long one weights down hard; the long one barely.

Pure numpy/pandas. Imports no execution module.
"""
import numpy as np
import pandas as pd

WEEK_MS = 7 * 24 * 3600 * 1000          # ~ one trading week - the maximum label horizon (GATE 4a)


def _group_stats(starts, ends):
    """Per-underlying sweep-line. Returns (avg_uniqueness, mean_concurrency) arrays.

    c(t) = number of windows covering instant t. Over each row's [start, end]:
      avg_uniqueness = (integral of 1/c(t) dt) / window_length     -> in (0, 1], 1.0 when never overlapped
      mean_concurrency = (integral of c(t) dt) / window_length     -> >= 1.0
    Piecewise-constant c(t) changes only at window boundaries, so we integrate segment by segment.
    """
    starts = np.asarray(starts, dtype=np.float64)
    ends = np.asarray(ends, dtype=np.float64)
    ends = np.maximum(ends, starts + 1.0)                # clamp zero-length windows to 1 ms
    n = len(starts)
    uniq_num = np.zeros(n)
    conc_num = np.zeros(n)
    bounds = np.unique(np.concatenate([starts, ends]))
    for a, b in zip(bounds[:-1], bounds[1:]):
        active = (starts <= a) & (ends >= b)             # rows covering the whole segment [a, b)
        c = int(active.sum())
        if c == 0:
            continue
        width = b - a
        uniq_num[active] += width / c                    # 1/c integrated over [a, b)
        conc_num[active] += width * c                    # c integrated over [a, b)
    length = ends - starts
    return uniq_num / length, conc_num / length


def compute_weights(df, signal_col="signal_ts", resolution_col="resolution_ts", group_col="ticker",
                    id_col="candidate_id", cache=None, newest_signal_ts=None, max_horizon_ms=WEEK_MS):
    """Attach window_start, window_end, mean_concurrency, avg_uniqueness, weight to `df`.

    weight == raw average uniqueness (UNNORMALISED: a non-overlapping row weights exactly 1.0).

    GATE 4a incremental cache: a row's weight is FINAL once
        newest_signal_ts > window_end + max_horizon_ms
    (no later row can start before this window ends, so its concurrency can never change again).
    Underlying groups all of whose rows are final are loaded from `cache`; any group containing an
    unstable row is fully recomputed (concurrency needs the whole group). `cache` maps
    candidate_id -> {"weight", "window_start", "window_end", "mean_concurrency", "avg_uniqueness"}.
    Returns (df_with_weights, new_cache).
    """
    out = df.copy()
    starts = out[signal_col].to_numpy(dtype=np.float64)
    ends = out[resolution_col].to_numpy(dtype=np.float64)
    ends = np.maximum(ends, starts + 1.0)
    out["window_start"] = starts
    out["window_end"] = ends
    if newest_signal_ts is None:
        newest_signal_ts = float(starts.max()) if len(starts) else 0.0

    stable = ends + max_horizon_ms < newest_signal_ts
    uniq = np.full(len(out), np.nan)
    conc = np.full(len(out), np.nan)

    groups = out.groupby(group_col, sort=False).indices        # underlying -> row positions
    new_cache = {}
    for _, idx in groups.items():
        idx = np.asarray(idx)
        group_all_stable = bool(stable[idx].all())
        cached_ok = cache is not None and group_all_stable and all(
            out[id_col].iloc[i] in cache for i in idx)
        if cached_ok:
            for i in idx:
                rec = cache[out[id_col].iloc[i]]
                uniq[i] = rec["avg_uniqueness"]
                conc[i] = rec["mean_concurrency"]
        else:
            u, c = _group_stats(starts[idx], ends[idx])
            uniq[idx] = u
            conc[idx] = c

    out["avg_uniqueness"] = uniq
    out["mean_concurrency"] = conc
    out["weight"] = uniq                                       # raw average uniqueness

    for i in range(len(out)):
        cid = out[id_col].iloc[i]
        new_cache[cid] = {
            "weight": float(uniq[i]), "avg_uniqueness": float(uniq[i]),
            "mean_concurrency": float(conc[i]),
            "window_start": float(starts[i]), "window_end": float(ends[i]),
            "final": bool(stable[i]),
        }
    return out, new_cache


def windows_overlap(a_start, a_end, b_start, b_end):
    """True if the two half-open information windows intersect."""
    return a_start < b_end and b_start < a_end
