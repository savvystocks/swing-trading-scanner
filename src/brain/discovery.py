"""Stage 2 pre-work - the DISCOVERY RIG: a systematic, re-runnable, honesty-first search over the
graded snapshot for a selection strategy that clears the cost-inclusive hurdle out-of-sample.

Brain-side only: reads the snapshot dataset the Foundry built, writes nothing but report artifacts.
Never touches the engine, the labeler, the recipe, or any live path.

Honesty machinery (non-negotiable):
- Discovery and grading never share data: every model is evaluated through PurgedKFold with embargo;
  every rule is MINED on train folds and REPORTED on test folds only; the walk-forward replay trains
  strictly on rows RESOLVED before each test week opens.
- Every attempt is counted: the Trials counter increments for every model fit, every candidate rule
  evaluated, every threshold scanned - across ALL angles - and feeds PBO / Deflated Sharpe.
- Every thin cell renders UNDERPOWERED, never a number.

scikit-learn is a brain-only dependency (requirements-brain.txt). Imports no execution module.
"""
import itertools
import numpy as np
import pandas as pd

from . import ev as EV
from . import harness as H
from . import calibration as CAL

MIN_BAND = 15                     # below this a band/cell renders UNDERPOWERED (mirrors report.py)
MIN_TRAIN = 300                   # walk-forward window needs at least this many resolved train rows
MIN_TAKES = 10                    # a policy must take at least this many trades to be scored
EMBARGO_MS = 24 * 3600 * 1000     # one-day embargo between train resolutions and a test week's open
REAL_SPREAD_SINCE_MS = 1783555200000   # 2026-07-09 00:00 UTC - executed spread real from here


class Trials:
    """The global attempt counter. Ten searches = ten searches' worth of trials; PBO and the Deflated
    Sharpe see the WHOLE campaign, not the winning slice."""

    def __init__(self):
        self.counts = {}

    def bump(self, kind, n=1):
        self.counts[kind] = self.counts.get(kind, 0) + int(n)

    @property
    def total(self):
        return int(sum(self.counts.values()))

    def as_dict(self):
        return {**self.counts, "TOTAL": self.total}


# ---------------------------------------------------------------- features

def numeric_features(df, feat_cols):
    """Coerce f.* leaf columns to numeric; drop the ones that are entirely non-numeric (the per-block
    `source` metadata strings). Returns (numeric frame, kept column list)."""
    X = pd.DataFrame(index=df.index)
    kept = []
    for c in feat_cols:
        v = pd.to_numeric(df[c], errors="coerce")
        if v.notna().sum() > 0:
            X[c] = v
            kept.append(c)
    return X, kept


def feature_block(col):
    parts = col.split(".")
    return parts[1] if len(parts) >= 3 else parts[-1]


# ---------------------------------------------------------------- weighted stats

def weighted_rate(y, w):
    """Weighted proportion + Kish effective sample size (the honest n for a weighted CI)."""
    y = np.asarray(y, dtype=np.float64)
    w = np.asarray(w, dtype=np.float64)
    sw = w.sum()
    if sw <= 0:
        return float("nan"), 0.0
    p = float((w * y).sum() / sw)
    n_eff = float(sw * sw / np.maximum((w * w).sum(), 1e-12))
    return p, n_eff


def wilson_eff(p, n_eff):
    if not np.isfinite(p) or n_eff <= 0:
        return (float("nan"), float("nan"))
    return EV.wilson_interval(p * n_eff, n_eff)


def weighted_auc(y, p, w):
    """Weighted rank AUC (ties get half credit). Separation of the score, weighted by uniqueness."""
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    w = np.asarray(w, dtype=np.float64)
    ok = np.isfinite(p)
    y, p, w = y[ok], p[ok], w[ok]
    pos, neg = y > 0.5, y <= 0.5
    wp, wn = w[pos].sum(), w[neg].sum()
    if wp <= 0 or wn <= 0:
        return float("nan")
    order = np.argsort(p, kind="mergesort")
    ps, ys, ws = p[order], y[order], w[order]
    auc = 0.0
    cum_neg = 0.0
    i = 0
    while i < len(ps):
        j = i
        tie_pos = tie_neg = 0.0
        while j < len(ps) and ps[j] == ps[i]:
            if ys[j] > 0.5:
                tie_pos += ws[j]
            else:
                tie_neg += ws[j]
            j += 1
        auc += tie_pos * (cum_neg + 0.5 * tie_neg)
        cum_neg += tie_neg
        i = j
    return float(auc / (wp * wn))


# ---------------------------------------------------------------- banding

def band_cuts(v, scheme, y=None, w=None, min_band=MIN_BAND):
    """Cut points for one feature's populated values. terciles / quartiles / tree (1-D depth-2
    decision-tree cuts - the data-driven scheme)."""
    x = v[np.isfinite(v)]
    if x.size < 3 * min_band or np.unique(x).size < 3:
        return []
    if scheme == "terciles":
        qs = [1 / 3, 2 / 3]
    elif scheme == "quartiles":
        qs = [0.25, 0.5, 0.75]
    elif scheme == "tree":
        from sklearn.tree import DecisionTreeClassifier
        m = np.isfinite(v) & np.isfinite(np.asarray(y, dtype=np.float64))
        if m.sum() < 3 * min_band:
            return []
        t = DecisionTreeClassifier(max_depth=2, min_samples_leaf=max(min_band, int(0.05 * m.sum())),
                                   random_state=0)
        t.fit(v[m].reshape(-1, 1), np.asarray(y)[m],
              sample_weight=None if w is None else np.asarray(w)[m])
        cuts = sorted(t.tree_.threshold[t.tree_.feature == 0].tolist())
        return [float(c) for c in cuts]
    else:
        raise ValueError(f"unknown band scheme {scheme}")
    cuts = sorted(set(float(np.quantile(x, q)) for q in qs))
    return cuts if len(cuts) >= 1 else []


def band_assign(v, cuts):
    """-1 for missing; else 0..len(cuts)."""
    out = np.full(len(v), -1, dtype=np.int64)
    ok = np.isfinite(v)
    out[ok] = np.searchsorted(np.asarray(cuts, dtype=np.float64), v[ok], side="right")
    return out


def band_label(b, n_bands):
    """Canonical position name so rule signatures compare ACROSS band schemes."""
    if b == 0:
        return "LOW"
    if b == n_bands - 1:
        return "HIGH"
    return "MID"


# ---------------------------------------------------------------- Part 1: verdict table

def verdict_table(df, kept_cols, X, ycol, wcol, cost_col, scheme, trials):
    """Per feature: fill rate first, then per-band uniqueness-weighted up-rate + CI, weighted mean
    realized return, and EV at executable prices. Thin bands print UNDERPOWERED."""
    y = df[ycol].to_numpy(dtype=np.float64)
    w = df[wcol].to_numpy(dtype=np.float64)
    ret = df["realized_return"].to_numpy(dtype=np.float64)
    cost = df[cost_col].to_numpy(dtype=np.float64)
    rows = []
    for c in kept_cols:
        v = X[c].to_numpy(dtype=np.float64)
        fill = float(np.isfinite(v).mean())
        cuts = band_cuts(v, scheme, y=y, w=w)
        if not cuts:
            rows.append({"feature": c, "block": feature_block(c), "fill_rate": fill, "band": "-",
                         "n_eff": 0, "up_rate": None, "ci_lo": None, "ci_hi": None,
                         "mean_ret": None, "ev": None, "note": "UNDERPOWERED (too sparse to band)"})
            continue
        b = band_assign(v, cuts)
        n_bands = len(cuts) + 1
        trials.bump("verdict_bands", n_bands)
        for bi in range(n_bands):
            m = b == bi
            if m.sum() == 0:
                continue
            p, n_eff = weighted_rate(y[m], w[m])
            if n_eff < MIN_BAND:
                rows.append({"feature": c, "block": feature_block(c), "fill_rate": fill,
                             "band": band_label(bi, n_bands), "n_eff": round(n_eff, 1),
                             "up_rate": None, "ci_lo": None, "ci_hi": None, "mean_ret": None,
                             "ev": None, "note": "UNDERPOWERED"})
                continue
            lo, hi = wilson_eff(p, n_eff)
            sw = w[m].sum()
            mean_ret = float((w[m] * ret[m]).sum() / sw)
            wins = ret[m] > 0
            mu_w = float((w[m][wins] * ret[m][wins]).sum() / max(w[m][wins].sum(), 1e-12)) if wins.any() else EV.BINARY_UP
            mu_l = float((w[m][~wins] * ret[m][~wins]).sum() / max(w[m][~wins].sum(), 1e-12)) if (~wins).any() else EV.BINARY_DOWN
            c_band = float(np.nanmean(cost[m]))
            rows.append({"feature": c, "block": feature_block(c), "fill_rate": fill,
                         "band": band_label(bi, n_bands), "n_eff": round(n_eff, 1),
                         "up_rate": round(p, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
                         "mean_ret": round(mean_ret, 4),
                         "ev": round(EV.ev_of_p(p, mu_w, mu_l, c_band), 4), "note": ""})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- Part 2a: learners

class Learner:
    """gbm = HistGradientBoosting (native NaN handling); logistic = median-impute + standardize + L2.
    One interface so the walk-forward and the angles treat families interchangeably."""

    def __init__(self, family, seed):
        self.family = family
        self.seed = seed
        self.model = None
        self.medians = None
        self.scale = None
        self.keep = None

    def fit(self, X, y, w):
        # a walk-forward train slice can hold columns with no (or one) finite value - the binner
        # cannot use them; keep only columns informative in THIS training set
        finite = np.isfinite(X)
        nunique = np.array([np.unique(X[finite[:, j], j]).size for j in range(X.shape[1])])
        self.keep = np.where(nunique >= 2)[0]
        Xk = X[:, self.keep]
        if self.family == "gbm":
            from sklearn.ensemble import HistGradientBoostingClassifier
            self.model = HistGradientBoostingClassifier(
                max_depth=3, max_iter=150, learning_rate=0.08, l2_regularization=1.0,
                min_samples_leaf=30, early_stopping=False, random_state=self.seed)
            self.model.fit(Xk, y, sample_weight=w)
        elif self.family == "logistic":
            from sklearn.linear_model import LogisticRegression
            med = np.nanmedian(Xk, axis=0)
            self.medians = np.where(np.isfinite(med), med, 0.0)
            Xi = np.where(np.isfinite(Xk), Xk, self.medians)
            mu, sd = Xi.mean(axis=0), Xi.std(axis=0)
            sd[sd < 1e-9] = 1.0
            self.scale = (mu, sd)
            self.model = LogisticRegression(C=0.5, max_iter=300, random_state=self.seed)
            self.model.fit((Xi - mu) / sd, y, sample_weight=w)
        else:
            raise ValueError(f"unknown learner family {self.family}")
        return self

    def predict_proba(self, X):
        Xk = X[:, self.keep]
        if self.family == "gbm":
            return self.model.predict_proba(Xk)[:, 1]
        Xi = np.where(np.isfinite(Xk), Xk, self.medians)
        mu, sd = self.scale
        return self.model.predict_proba((Xi - mu) / sd)[:, 1]


def oof_predict(X, y, w, starts, ends, family, seed, trials, n_splits=4, embargo=0.02):
    """Out-of-fold probabilities under PurgedKFold. Returns (oof, folds) where folds carry the fitted
    per-fold models for MDA and attribution."""
    n = len(y)
    oof = np.full(n, np.nan)
    folds = []
    if np.unique(y).size < 2:
        return oof, folds
    for tr, te in H.PurgedKFold(n_splits, embargo).split(starts, ends):
        if len(tr) < MIN_TRAIN // 2 or len(te) == 0 or np.unique(y[tr]).size < 2:
            continue
        m = Learner(family, seed).fit(X[tr], y[tr], w[tr])
        trials.bump("model_fits")
        oof[te] = m.predict_proba(X[te])
        folds.append((tr, te, m))
    return oof, folds


def mda_importance(X, y, w, folds, kept_cols, seed):
    """MDA permutation importance on the TEST folds only - the out-of-sample predictive contribution
    that ranks Part 1's table (never in-sample correlation)."""
    rng = np.random.default_rng(seed)
    deltas = np.zeros(len(kept_cols))
    counts = np.zeros(len(kept_cols))
    for tr, te, m in folds:
        base = weighted_auc(y[te], m.predict_proba(X[te]), w[te])
        if not np.isfinite(base):
            continue
        for j in range(len(kept_cols)):
            Xp = X[te].copy()
            Xp[:, j] = Xp[rng.permutation(len(te)), j]
            a = weighted_auc(y[te], m.predict_proba(Xp), w[te])
            if np.isfinite(a):
                deltas[j] += base - a
                counts[j] += 1
    out = np.where(counts > 0, deltas / np.maximum(counts, 1), np.nan)
    return pd.Series(out, index=kept_cols).sort_values(ascending=False)


def local_attribution(model, x_row, medians, kept_cols, top_idx, k=3):
    """Median-substitution attribution (NOT SHAP - the honest poor-man's local reason): the k features
    whose replacement by the training median moves this row's probability most."""
    base = float(model.predict_proba(x_row.reshape(1, -1))[0])
    effects = []
    for j in top_idx:
        sub = x_row.copy()
        sub[j] = medians[j]
        d = base - float(model.predict_proba(sub.reshape(1, -1))[0])
        effects.append((abs(d), d, kept_cols[j]))
    effects.sort(reverse=True)
    parts = [f"{name.replace('f.', '')}{'+' if d > 0 else '-'}" for _, d, name in effects[:k]]
    return f"p={base:.2f} [" + " ".join(parts) + "]"


# ---------------------------------------------------------------- Part 2b: rule mining

def mine_rules(B, band_counts, y, w, kept_cols, trials, k1=14, k2=20, top_n=10):
    """Shallow readable rules, depth <= 3. Atoms -> pairs from the top atoms -> triples from the top
    pairs. EVERY candidate evaluated is counted. Returns train-side stats only; the caller grades
    out-of-sample."""
    base, base_neff = weighted_rate(y, w)
    if not np.isfinite(base) or base <= 0:
        return []
    atoms = []
    for j in range(B.shape[1]):
        nb = band_counts[j]
        for b in range(nb):
            m = B[:, j] == b
            trials.bump("rules_evaluated")
            if m.sum() == 0:
                continue
            p, n_eff = weighted_rate(y[m], w[m])
            if n_eff >= MIN_BAND and p > base:
                atoms.append({"clause": ((j, b),), "p": p, "n_eff": n_eff, "lift": p / base})
    atoms.sort(key=lambda a: a["lift"], reverse=True)
    top_atoms = atoms[:k1]
    pairs = []
    for a1, a2 in itertools.combinations(top_atoms, 2):
        (j1, b1), (j2, b2) = a1["clause"][0], a2["clause"][0]
        if j1 == j2:
            continue
        m = (B[:, j1] == b1) & (B[:, j2] == b2)
        trials.bump("rules_evaluated")
        p, n_eff = weighted_rate(y[m], w[m]) if m.any() else (float("nan"), 0.0)
        if n_eff >= MIN_BAND and np.isfinite(p) and p > base:
            pairs.append({"clause": tuple(sorted(((j1, b1), (j2, b2)))), "p": p, "n_eff": n_eff,
                          "lift": p / base})
    pairs.sort(key=lambda a: a["lift"], reverse=True)
    triples = []
    for pr in pairs[:k2]:
        used = {j for j, _ in pr["clause"]}
        for at in top_atoms:
            j, b = at["clause"][0]
            if j in used:
                continue
            cl = tuple(sorted(pr["clause"] + ((j, b),)))
            m = np.ones(B.shape[0], dtype=bool)
            for jj, bb in cl:
                m &= B[:, jj] == bb
            trials.bump("rules_evaluated")
            p, n_eff = weighted_rate(y[m], w[m]) if m.any() else (float("nan"), 0.0)
            if n_eff >= MIN_BAND and np.isfinite(p) and p > base:
                triples.append({"clause": cl, "p": p, "n_eff": n_eff, "lift": p / base})
    cand = atoms + pairs + triples
    seen, out = set(), []
    for r in sorted(cand, key=lambda a: a["lift"], reverse=True):
        if r["clause"] in seen:
            continue
        seen.add(r["clause"])
        out.append(r)
        if len(out) >= top_n:
            break
    return out


def rule_mask(B, clause):
    m = np.ones(B.shape[0], dtype=bool)
    for j, b in clause:
        m &= B[:, j] == b
    return m


def rule_signature(clause, band_counts, kept_cols):
    parts = [f"{kept_cols[j].replace('f.', '')}:{band_label(b, band_counts[j])}" for j, b in clause]
    return " & ".join(sorted(parts))


# ---------------------------------------------------------------- angle 7: IV-scaled relabel

def iv_scaled_labels(db_path, df, iv_col_values, cap=(0.5, 2.0)):
    """Replay each candidate's stored bid path against barriers scaled by its front IV relative to the
    pool median (rows without IV keep scale 1.0). This substitutes for the referenced barrier-study
    labels, which do not exist in the repo - formula documented in the report."""
    import sqlite3
    iv = np.asarray(iv_col_values, dtype=np.float64)
    med = np.nanmedian(iv)
    scale = np.where(np.isfinite(iv) & (med > 0), np.clip(iv / med, cap[0], cap[1]), 1.0)
    con = sqlite3.connect(db_path)
    try:
        cand = pd.read_sql_query(
            "SELECT candidate_id, entry_ref, vertical_barrier_ts, barrier_up_pct, barrier_down_pct "
            "FROM candidates", con)
        bp = pd.read_sql_query(
            "SELECT candidate_id, poll_ts_utc, bid, stale FROM bid_path WHERE bid IS NOT NULL", con)
    finally:
        con.close()
    cand = cand.set_index("candidate_id")
    bp = bp[bp["stale"].fillna(0) == 0].sort_values("poll_ts_utc")
    groups = {cid: g for cid, g in bp.groupby("candidate_id")}
    y2 = np.full(len(df), np.nan)
    r2 = np.full(len(df), np.nan)
    ids = df["candidate_id"].tolist()
    for i, cid in enumerate(ids):
        if cid not in cand.index or cid not in groups:
            continue
        row = cand.loc[cid]
        e = row["entry_ref"]
        if not np.isfinite(e) or e <= 0:
            continue
        up = float(row["barrier_up_pct"]) * scale[i]
        dn = float(row["barrier_down_pct"]) * scale[i]
        g = groups[cid]
        g = g[g["poll_ts_utc"] <= row["vertical_barrier_ts"]]
        if g.empty:
            continue
        rets = g["bid"].to_numpy(dtype=np.float64) / e - 1.0
        hit_up = np.where(rets >= up)[0]
        hit_dn = np.where(rets <= dn)[0]
        first_up = hit_up[0] if hit_up.size else np.inf
        first_dn = hit_dn[0] if hit_dn.size else np.inf
        if first_up == np.inf and first_dn == np.inf:
            y2[i] = 1.0 if rets[-1] > 0 else 0.0
            r2[i] = rets[-1]
        elif first_up <= first_dn:
            y2[i] = 1.0
            r2[i] = rets[int(first_up)]
        else:
            y2[i] = 0.0
            r2[i] = rets[int(first_dn)]
    return y2, r2


# ---------------------------------------------------------------- Part 3: walk-forward replay

def week_key(signal_ts):
    dt = pd.DatetimeIndex(pd.to_datetime(np.asarray(signal_ts, dtype=np.float64), unit="ms", utc=True))
    iso = dt.isocalendar()
    return (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()


def walk_forward(df, X, kept_cols, cfg, trials):
    """Learn on everything RESOLVED before week k+1 opens (one-day embargo), apply frozen to week
    k+1's candidates as if live, roll forward. Produces the trade-by-trade ledger."""
    y = df[cfg["ycol"]].to_numpy(dtype=np.float64)
    w = df[cfg["wcol"]].to_numpy(dtype=np.float64)
    net = df["net_ret"].to_numpy(dtype=np.float64)
    starts = df["window_start"].to_numpy(dtype=np.float64)
    ends = df["window_end"].to_numpy(dtype=np.float64)
    Xv = X[kept_cols].to_numpy(dtype=np.float64)
    wk = week_key(df["signal_ts"])
    weeks = sorted(np.unique(wk))
    ledger_rows = []
    window_summaries = []
    champ_window_returns = []
    for test_week in weeks[1:]:
        te = np.where(wk == test_week)[0]
        t_open = float(starts[te].min())
        tr = np.where((ends <= t_open - EMBARGO_MS) & (wk < test_week))[0]
        wk_label = f"{str(test_week)[:4]}-W{str(test_week)[4:]}"
        if len(tr) < MIN_TRAIN or np.unique(y[tr]).size < 2:
            window_summaries.append({"week": wk_label, "n_train": int(len(tr)), "n_test": int(len(te)),
                                     "champion": None, "note": "UNDERPOWERED (train too thin)"})
            continue
        cuts = []
        band_counts = []
        for c in kept_cols:
            cs = band_cuts(Xv[tr][:, kept_cols.index(c)], cfg["scheme"], y=y[tr], w=w[tr])
            cuts.append(cs)
            band_counts.append(len(cs) + 1 if cs else 0)
        B_tr = np.column_stack([band_assign(Xv[tr][:, j], cuts[j]) if cuts[j] else
                                np.full(len(tr), -1) for j in range(len(kept_cols))])
        B_te = np.column_stack([band_assign(Xv[te][:, j], cuts[j]) if cuts[j] else
                                np.full(len(te), -1) for j in range(len(kept_cols))])
        rules = mine_rules(B_tr, band_counts, y[tr], w[tr], kept_cols, trials)
        # champion selection on TRAIN ONLY: internal purged folds score the model policy at each
        # cutoff and the mine-top-rule policy; the better train-OOS policy is frozen for the week
        model_prob_oof, _ = (np.full(len(tr), np.nan), []) if cfg["learner"] == "rules" else \
            oof_predict(Xv[tr], y[tr], w[tr], starts[tr], ends[tr], cfg["learner"], cfg["seed"], trials)
        best_cut, best_cut_ev = None, -np.inf
        if np.isfinite(model_prob_oof).any():
            cal = CAL.calibrate(model_prob_oof[np.isfinite(model_prob_oof)],
                                y[tr][np.isfinite(model_prob_oof)])
            p_cal = np.full(len(tr), np.nan)
            p_cal[np.isfinite(model_prob_oof)] = cal["predict"](model_prob_oof[np.isfinite(model_prob_oof)])
            for cut in np.arange(0.20, 0.75, 0.05):
                trials.bump("thresholds")
                m = p_cal >= cut
                if m.sum() < MIN_TAKES:
                    continue
                ev_c = float((w[tr][m] * net[tr][m]).sum() / max(w[tr][m].sum(), 1e-12))
                if ev_c > best_cut_ev:
                    best_cut, best_cut_ev = float(cut), ev_c
        rule_ev = -np.inf
        best_rule = rules[0] if rules else None
        if best_rule is not None:
            inner_ret = []
            for itr, ite in H.PurgedKFold(3, 0.02).split(starts[tr], ends[tr]):
                if len(itr) < MIN_TRAIN // 2 or np.unique(y[tr][itr]).size < 2:
                    continue
                r_in = mine_rules(B_tr[itr], band_counts, y[tr][itr], w[tr][itr], kept_cols, trials,
                                  top_n=1)
                if not r_in:
                    continue
                m = rule_mask(B_tr[ite], r_in[0]["clause"])
                if m.sum() >= MIN_TAKES // 2:
                    inner_ret.append(float((w[tr][ite][m] * net[tr][ite][m]).sum()
                                           / max(w[tr][ite][m].sum(), 1e-12)))
            rule_ev = float(np.mean(inner_ret)) if inner_ret else -np.inf
        use_model = best_cut is not None and best_cut_ev >= rule_ev and cfg["learner"] != "rules"
        if not use_model and best_rule is None:
            window_summaries.append({"week": wk_label, "n_train": int(len(tr)), "n_test": int(len(te)),
                                     "champion": None, "note": "UNDERPOWERED (no viable policy on train)"})
            continue
        if use_model:
            final = Learner(cfg["learner"], cfg["seed"]).fit(Xv[tr], y[tr], w[tr])
            trials.bump("model_fits")
            cal_f = CAL.calibrate(model_prob_oof[np.isfinite(model_prob_oof)],
                                  y[tr][np.isfinite(model_prob_oof)])
            p_te = cal_f["predict"](final.predict_proba(Xv[te]))
            takes = p_te >= best_cut
            medians = np.nanmedian(Xv[tr], axis=0)
            mda_idx = list(range(min(12, len(kept_cols))))
            champion = f"{cfg['learner']}@p>={best_cut:.2f}"
            reasons = [local_attribution(final, Xv[te][i], medians, kept_cols, mda_idx)
                       if takes[i] else "" for i in range(len(te))]
        else:
            takes = rule_mask(B_te, best_rule["clause"])
            sig = rule_signature(best_rule["clause"], band_counts, kept_cols)
            champion = f"rule[{sig}]"
            reasons = [sig if takes[i] else "" for i in range(len(te))]
        sel = te[takes]
        p_sel, neff_sel = weighted_rate(y[sel], w[sel]) if len(sel) else (float("nan"), 0.0)
        wk_ret = float((w[sel] * net[sel]).sum() / max(w[sel].sum(), 1e-12)) if len(sel) else float("nan")
        underpowered = neff_sel < MIN_BAND
        window_summaries.append({
            "week": wk_label, "n_train": int(len(tr)), "n_test": int(len(te)),
            "champion": champion, "n_takes": int(takes.sum()), "n_eff_takes": round(neff_sel, 1),
            "oos_up_rate": None if underpowered else round(p_sel, 4),
            "oos_net_ret": None if underpowered else round(wk_ret, 4),
            "note": "UNDERPOWERED (takes too thin)" if underpowered else ""})
        if not underpowered and np.isfinite(wk_ret):
            champ_window_returns.append(wk_ret)
        dt = pd.to_datetime(df["signal_ts"].iloc[te].to_numpy(), unit="ms", utc=True)
        for k, i in enumerate(te):
            ledger_rows.append({
                "date": str(dt[k])[:16], "week": wk_label, "ticker": df["ticker"].iloc[i],
                "occ": df["occ_symbol"].iloc[i], "engine_took": int(df["executed"].iloc[i]),
                "decision": "TAKE" if takes[k] else "skip", "reason": reasons[k],
                "outcome": df["outcome"].iloc[i], "realized_return": round(float(df["realized_return"].iloc[i]), 4),
                "net_return": round(float(net[i]), 4), "weight": round(float(w[i]), 4)})
    ledger = pd.DataFrame(ledger_rows)
    return {"ledger": ledger, "windows": window_summaries, "champ_returns": champ_window_returns}


def equity_lines(ledger):
    """Three uniqueness-weighted, cost-inclusive equity lines over the replayed weeks: the engine's
    actual picks, the discovered strategy's OOS picks, the pool baseline."""
    if ledger.empty:
        return pd.DataFrame()
    led = ledger.sort_values("date").reset_index(drop=True)
    led["wnet"] = led["weight"] * led["net_return"]
    out = pd.DataFrame({"date": led["date"]})
    out["engine"] = (led["wnet"] * (led["engine_took"] == 1)).cumsum()
    out["strategy"] = (led["wnet"] * (led["decision"] == "TAKE")).cumsum()
    out["pool"] = led["wnet"].cumsum()
    return out


# ---------------------------------------------------------------- PBO / DSR accounting

def pbo_matrix(df, X, kept_cols, cfg, trials, n_groups=6, max_trials=40):
    """CSCV out-of-sample matrix over time-ordered groups: columns are trial configs (fixed rule
    clauses mined on each split's train + model@cutoff variants), rows are CPCV splits. Feeds
    harness.probability_of_backtest_overfitting."""
    y = df[cfg["ycol"]].to_numpy(dtype=np.float64)
    w = df[cfg["wcol"]].to_numpy(dtype=np.float64)
    net = df["net_ret"].to_numpy(dtype=np.float64)
    starts = df["window_start"].to_numpy(dtype=np.float64)
    Xv = X[kept_cols].to_numpy(dtype=np.float64)
    order = np.argsort(starts, kind="mergesort")
    groups = np.array_split(order, n_groups)
    combos, _ = H.cpcv_splits(n_groups, 2)
    cuts_all = []
    band_counts = []
    for j in range(len(kept_cols)):
        cs = band_cuts(Xv[:, j], cfg["scheme"], y=y, w=w)
        cuts_all.append(cs)
        band_counts.append(len(cs) + 1 if cs else 0)
    B = np.column_stack([band_assign(Xv[:, j], cuts_all[j]) if cuts_all[j] else
                         np.full(len(y), -1) for j in range(len(kept_cols))])
    global_rules = mine_rules(B, band_counts, y, w, kept_cols, trials, top_n=max_trials - 6)
    trial_defs = [("rule", r["clause"]) for r in global_rules]
    for cut in (0.25, 0.35, 0.45, 0.55, 0.65):
        trial_defs.append(("model", float(cut)))
    M = np.full((len(combos), len(trial_defs)), np.nan)
    for si, test_groups in enumerate(combos):
        te = np.concatenate([groups[g] for g in test_groups])
        tr = np.concatenate([groups[g] for g in range(n_groups) if g not in test_groups])
        if np.unique(y[tr]).size < 2:
            continue
        model = None
        for ti, (kind, spec) in enumerate(trial_defs):
            if kind == "rule":
                m = rule_mask(B[te], spec)
            else:
                if model is None:
                    model = Learner("gbm", cfg["seed"]).fit(Xv[tr], y[tr], w[tr])
                    trials.bump("model_fits")
                m = model.predict_proba(Xv[te]) >= spec
                trials.bump("thresholds")
            if m.sum() < MIN_TAKES // 2:
                continue
            M[si, ti] = float((w[te][m] * net[te][m]).sum() / max(w[te][m].sum(), 1e-12))
    keep = ~np.all(np.isnan(M), axis=0)
    M = np.where(np.isnan(M), np.nanmin(M) if np.isfinite(M).any() else 0.0, M)
    return M[:, keep] if keep.any() else M


def dsr_of_champion(champ_returns, n_trials_total):
    """Deflated Sharpe of the walk-forward champion's weekly OOS returns. Thin windows render
    UNDERPOWERED."""
    r = np.asarray(champ_returns, dtype=np.float64)
    r = r[np.isfinite(r)]
    if r.size < 4:
        return None, None, f"UNDERPOWERED ({r.size} OOS windows; needs >= 4)"
    sr = float(r.mean() / max(r.std(ddof=1), 1e-12))
    dsr, sr0, note = H.deflated_sharpe_ratio(sr, n_trials=n_trials_total, sr_variance=0.5,
                                             n_obs=int(r.size))
    return dsr, sr0, note
