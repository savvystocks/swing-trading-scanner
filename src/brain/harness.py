"""Stage 1 - the Truth Harness: model-agnostic evaluation machinery.

- PurgedKFold with embargo (Lopez de Prado ch. 7): a train row is PURGED if its information window
  overlaps any test row's window; an embargo of `embargo_frac` of the rows immediately after each
  test block is also dropped. This is what stops overlapping labels leaking train->test.
- CPCV (ch. 12): combinatorial purged cross-validation. With N groups and k test groups per split:
      number of splits          = C(N, k)
      each group is tested in    = C(N-1, k-1) splits
      number of backtest paths   = k * C(N, k) / N
  Defaults N=10, k=2  ->  C(10,2)=45 splits, 2*45/10 = 9 paths.
- GATE 4b compute guard: wall-clock / memory budget; degrade N stepwise 10->8->6 rather than dying.
- Probability of Backtest Overfitting (CSCV) and the Deflated Sharpe Ratio (trials as explicit input).

Pure numpy/pandas + stdlib math. Imports no execution module.
"""
import math
import itertools
import numpy as np

EULER_MASCHERONI = 0.5772156649015329


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p):
    """Inverse standard-normal CDF (Acklam's rational approximation, |err| < 1.15e-9)."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


class PurgedKFold:
    """K folds over time-ordered rows, purging train rows whose window overlaps a test row's window,
    plus an embargo after each test block. `split` takes window start/end arrays (same order as X)."""

    def __init__(self, n_splits=5, embargo_frac=0.01):
        if n_splits < 2:
            raise ValueError("n_splits must be >= 2")
        self.n_splits = n_splits
        self.embargo_frac = embargo_frac

    def split(self, starts, ends):
        starts = np.asarray(starts, dtype=np.float64)
        ends = np.asarray(ends, dtype=np.float64)
        n = len(starts)
        order = np.argsort(starts, kind="mergesort")        # evaluate folds in time order
        folds = np.array_split(order, self.n_splits)
        embargo = int(n * self.embargo_frac)
        for test_idx in folds:
            if len(test_idx) == 0:
                continue
            t0 = starts[test_idx].min()
            t1 = ends[test_idx].max()
            # PURGE: drop any train row whose window overlaps the test window [t0, t1]
            overlap = (starts < t1) & (ends > t0)
            train_mask = np.ones(n, dtype=bool)
            train_mask[test_idx] = False
            train_mask &= ~overlap
            # EMBARGO: drop the `embargo` rows (in time order) immediately after the test block
            if embargo > 0:
                last_pos = int(np.searchsorted(starts[order], t1, side="right"))
                emb = order[last_pos:last_pos + embargo]
                train_mask[emb] = False
            yield np.where(train_mask)[0], np.asarray(test_idx)


def cpcv_splits(n_groups=10, k=2):
    """Return (list of test-group tuples, n_paths). Groups are 0..n_groups-1; each split TESTS the k
    groups in the tuple and TRAINS on the rest. n_paths = k*C(N,k)/N (documented above)."""
    combos = list(itertools.combinations(range(n_groups), k))
    n_paths = k * len(combos) // n_groups
    return combos, n_paths


def cpcv_math(n_groups=10, k=2):
    C = math.comb(n_groups, k)
    return {"n_groups": n_groups, "k": k, "n_splits": C,
            "tests_per_group": math.comb(n_groups - 1, k - 1), "n_paths": k * C // n_groups}


def compute_guard(n_rows, seconds_budget=1800, mb_budget=6000, n_ladder=(10, 8, 6)):
    """GATE 4b. Pick a CPCV group count that fits the budget. At this system's realistic scale (tens of
    thousands of rows, ~50 features) a free GHA runner is nowhere near its limits - this is insurance,
    not a current constraint. Returns (n_groups, note)."""
    # crude cost proxy: splits x rows. Degrade N only if the proxy blows the (very loose) budget.
    for n in n_ladder:
        est_seconds = math.comb(n, 2) * n_rows / 5e5        # ~5e5 rows/sec/split for LightGBM-scale work
        if est_seconds <= seconds_budget:
            note = "" if n == n_ladder[0] else f"CPCV N degraded to {n} (budget guard, est {est_seconds:.0f}s)"
            return n, note
    return n_ladder[-1], f"CPCV N floored at {n_ladder[-1]} (budget guard)"


def probability_of_backtest_overfitting(oos_matrix, min_trials=2, min_rows=1000):
    """CSCV PBO (de Prado). `oos_matrix` is rows=CSCV splits, cols=trials/configs of an out-of-sample
    performance stat. Returns (pbo, note). Renders N/A until the CPCV minimums are met."""
    M = np.asarray(oos_matrix, dtype=np.float64)
    if M.ndim != 2 or M.shape[1] < min_trials or M.shape[0] < 2:
        return None, f"N/A (needs >= {min_trials} trials and CSCV splits; got shape {M.shape})"
    logits = []
    for r in range(M.shape[0]):
        best = int(np.argmax(M[r]))                          # in-sample winner for this split
        col = M[:, best]
        rank = (col < col[r]).sum() / max(len(col) - 1, 1)   # its OOS rank among all splits
        rank = min(max(rank, 1e-6), 1 - 1e-6)
        logits.append(math.log(rank / (1 - rank)))
    pbo = float(np.mean(np.asarray(logits) <= 0))            # fraction where OOS rank below median
    return pbo, ""


def deflated_sharpe_ratio(sr, n_trials, sr_variance, skew=0.0, kurt=3.0, n_obs=0, sr_benchmark=None):
    """Deflated Sharpe (Bailey & de Prado). `n_trials` is the number of configurations tried (explicit
    input). The deflation benchmark is the expected maximum SR of `n_trials` independent trials with
    the given SR variance. Returns (dsr_prob, expected_max_sr, note)."""
    if n_obs < 2 or n_trials < 1:
        return None, None, "N/A (needs >= 2 observations and >= 1 trial)"
    if sr_benchmark is None:
        v = math.sqrt(max(sr_variance, 1e-12))
        if n_trials == 1:
            sr0 = 0.0
        else:
            sr0 = v * ((1 - EULER_MASCHERONI) * _norm_ppf(1 - 1.0 / n_trials)
                       + EULER_MASCHERONI * _norm_ppf(1 - 1.0 / (n_trials * math.e)))
    else:
        sr0 = sr_benchmark
    denom = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4.0 * sr * sr, 1e-12))
    z = (sr - sr0) * math.sqrt(n_obs - 1) / denom
    return _norm_cdf(z), sr0, ""
