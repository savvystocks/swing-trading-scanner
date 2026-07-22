"""GATE 3 - adaptive probability calibration, fitted ONLY on out-of-fold predictions, per model
version (never global).

Two calibrators:
  - Platt / sigmoid : 1-D logistic P = sigmoid(w*s + b), fitted by IRLS. Low variance, good at thin n.
  - Isotonic        : monotone step fit via Pool-Adjacent-Violators. Flexible, good at thick n.
Auto-select: sigmoid when OOF n is below `n_threshold` (default 1,000), isotonic above (a bias/variance
trade-off). Brier score is reported for BOTH in every run as the quality metric.

Pure numpy. Imports no execution module.
"""
import numpy as np


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -60, 60)))


def platt_fit(scores, labels, iters=50, ridge=1e-6):
    """1-D logistic (Platt) fit by IRLS. labels in {0,1}. Returns (w, b)."""
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    X = np.column_stack([s, np.ones_like(s)])
    beta = np.zeros(2)
    for _ in range(iters):
        p = _sigmoid(X @ beta)
        W = np.clip(p * (1 - p), 1e-9, None)
        grad = X.T @ (y - p)
        H = X.T @ (X * W[:, None]) + ridge * np.eye(2)
        step = np.linalg.solve(H, grad)
        beta = beta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return float(beta[0]), float(beta[1])


def platt_predict(params, scores):
    w, b = params
    return _sigmoid(w * np.asarray(scores, dtype=np.float64) + b)


def isotonic_fit(scores, labels):
    """Monotone non-decreasing fit via Pool-Adjacent-Violators. Returns a model dict with sorted
    breakpoints `x` and fitted values `y` (both step-constant between breakpoints)."""
    s = np.asarray(scores, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    order = np.argsort(s, kind="mergesort")
    xs, ys = s[order], y[order]
    # PAV: blocks of (weighted sum, count); merge while a block's mean < the previous block's mean
    sums, counts, right = [], [], []
    for i in range(len(ys)):
        sums.append(ys[i]); counts.append(1.0); right.append(xs[i])
        while len(sums) > 1 and sums[-2] / counts[-2] > sums[-1] / counts[-1]:
            # pop FIRST, then merge into the (new) last block: `sums[-2] += sums.pop()` re-resolves
            # the -2 index against the already-shrunk list - it stored the merge one slot left and
            # crashed outright on a length-2 merge (bug found 2026-07-22 by the Stage-2 OOF fit)
            s_last, c_last, r_last = sums.pop(), counts.pop(), right.pop()
            sums[-1] += s_last; counts[-1] += c_last; right[-1] = r_last
    vals = np.array([sm / c for sm, c in zip(sums, counts)])
    edges = np.array(right)                                   # right edge (score) of each block
    return {"x": edges, "y": vals, "xmin": float(xs[0]), "xmax": float(xs[-1])}


def isotonic_predict(model, scores):
    x, y = model["x"], model["y"]
    s = np.asarray(scores, dtype=np.float64)
    idx = np.searchsorted(x, s, side="left")                 # first block whose right-edge >= score
    idx = np.clip(idx, 0, len(y) - 1)
    return y[idx]


def brier_score(probs, labels):
    p = np.asarray(probs, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    return float(np.mean((p - y) ** 2))


def reliability_curve(probs, labels, n_bins=10):
    p = np.asarray(probs, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    bins = np.linspace(0, 1, n_bins + 1)
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if m.sum() == 0:
            continue
        out.append({"bin_mid": (lo + hi) / 2, "mean_pred": float(p[m].mean()),
                    "frac_pos": float(y[m].mean()), "n": int(m.sum())})
    return out


def calibrate(oof_scores, oof_labels, n_threshold=1000):
    """Fit BOTH calibrators on out-of-fold scores; select the family by OOF n (sigmoid < threshold,
    isotonic above). Returns a dict: selected, reason, briers for both, reliability curves, and a
    `predict(scores)` closure for the selected calibrator."""
    s = np.asarray(oof_scores, dtype=np.float64)
    y = np.asarray(oof_labels, dtype=np.float64)
    n = len(s)
    platt = platt_fit(s, y)
    iso = isotonic_fit(s, y)
    p_platt = platt_predict(platt, s)
    p_iso = isotonic_predict(iso, s)
    b_platt, b_iso = brier_score(p_platt, y), brier_score(p_iso, y)
    selected = "sigmoid" if n < n_threshold else "isotonic"
    reason = f"n={n} {'<' if n < n_threshold else '>='} threshold {n_threshold}"
    if selected == "sigmoid":
        predict = lambda x: platt_predict(platt, x)
        curve = reliability_curve(p_platt, y)
    else:
        predict = lambda x: isotonic_predict(iso, x)
        curve = reliability_curve(p_iso, y)
    return {"selected": selected, "reason": reason, "n": n,
            "brier": {"sigmoid": b_platt, "isotonic": b_iso},
            "reliability": {"sigmoid": reliability_curve(p_platt, y), "isotonic": reliability_curve(p_iso, y)},
            "params": {"sigmoid": platt, "isotonic": iso}, "predict": predict,
            "selected_reliability": curve}
