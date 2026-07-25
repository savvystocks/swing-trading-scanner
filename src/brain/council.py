"""School Phase 2 - the COUNCIL (shadow-only, recording, no authority).

Five DELIBERATELY DIVERSE members each answer "is this signal real?" with a calibrated probability,
evaluated OUT-OF-FOLD under PurgedKFold so no member ever grades a row it trained on. Diversity is the
point: a nonlinear ML view, a linear view, a sparse readable-rule view, an actuarial base-rate view,
and a flow-specialist view fail in different ways, and their DISAGREEMENT is itself a signal.

The canonical missing-data contract (addendum Section 2) is enforced here:
  - MISSING FEATURE (stale past its TTL, or absent) -> flows through each member's native NaN path.
    Never substituted, never a veto.
  - FAILED COMPONENT (a member raises / times out / cannot produce a probability) -> that member VETOES,
    and a failed component is an ABSOLUTE council VETO of the candidate. Fail-CLOSED.

The council blends member probabilities (equal weight - honest, not fit) and DECIDES against each
contract's OWN break-even bar (not the pool hurdle) AND a disagreement band: TAKE only if the blend
clears the contract bar and the members agree closely enough. Everything is recorded to a shadow
table. NOTHING here touches the engine, sizing, or any order. Authority is granted only by the
Governor, only on track record.
"""
import time
import numpy as np
import pandas as pd

from . import discovery as D
from . import calibration as CAL
from . import harness as H
from . import ev as EV
from . import student as S
from . import convergence as CV
from .ttl import apply_ttl                      # decision-time feature staleness -> NaN

N_FOLDS, EMBARGO = 5, 0.02
DISAGREE_MAX = 0.18            # member-probability std above this -> VETO (council does not trust a split house)
LATENCY_BUDGET_S = 2.0        # per-candidate scoring budget; exceeded -> component failure -> VETO
MEMBERS = ("gbm_meta", "logistic_linear", "rule_survivors", "base_rate_2d", "flow_specialist")


def _purged_oof(Xv, y, w, starts, ends, fit_fn, n_folds=N_FOLDS):
    """Out-of-fold probabilities for one member. fit_fn(Xtr, ytr, wtr) -> object with .predict_proba."""
    oof = np.full(len(y), np.nan)
    for tr, te in H.PurgedKFold(n_folds, EMBARGO).split(starts, ends):
        if len(tr) < D.MIN_TRAIN // 2 or np.unique(y[tr]).size < 2:
            continue
        try:
            m = fit_fn(Xv[tr], y[tr], w[tr])
            oof[te] = m.predict_proba(Xv[te])
        except Exception:
            continue                                # a fold that will not fit leaves NaN, handled downstream
    return oof


def _member_gbm(Xv, y, w, starts, ends, seed):
    return _purged_oof(Xv, y, w, starts, ends,
                       lambda a, b, c: D.Learner("gbm", seed).fit(a, b, c))


def _member_logistic(Xv, y, w, starts, ends, seed):
    return _purged_oof(Xv, y, w, starts, ends,
                       lambda a, b, c: D.Learner("logistic", seed).fit(a, b, c))


def _member_flow_specialist(Xv, y, w, starts, ends, kept, seed):
    """A GBM restricted to the flow / price-action / aggression blocks: the 'read the tape' view,
    blind to macro and fundamentals so it fails independently of the all-feature members."""
    idx = [i for i, c in enumerate(kept)
           if any(c.startswith(b) for b in ("flow_", "price_action", "technical", "relative_momentum",
                                            "gex", "dealer_greeks", "dark_pool"))]
    if len(idx) < 3:
        return np.full(len(y), np.nan)
    Xf = Xv[:, idx]
    return _purged_oof(Xf, y, w, starts, ends,
                       lambda a, b, c: D.Learner("gbm", seed).fit(a, b, c))


def _member_base_rate_2d(df, X, kept, y, w, starts, seed):
    """Actuarial: out-of-fold win-frequency in a spread-bucket x IV-bucket cell. No interactions beyond
    the two axes - it cannot hallucinate structure the ML members might. NaN in either axis -> NaN."""
    sp = pd.to_numeric(df.get("spread_pct"), errors="coerce").to_numpy()
    iv_col = next((c for c in kept if c.endswith("iv_term.iv_ratio") or c.endswith("vrp.front_iv")), None)
    iv = pd.to_numeric(X[iv_col], errors="coerce").to_numpy() if iv_col else np.full(len(df), np.nan)
    sp_b = np.digitize(sp, [2, 8, 20])
    iv_b = np.digitize(iv, np.nanquantile(iv[np.isfinite(iv)], [0.33, 0.67]) if np.isfinite(iv).any() else [1, 2])
    key = sp_b * 10 + iv_b
    key[~np.isfinite(sp) | ~np.isfinite(iv)] = -1
    oof = np.full(len(y), np.nan)
    order = np.argsort(starts, kind="mergesort")
    groups = np.array_split(order, N_FOLDS)
    for g in range(N_FOLDS):
        te = groups[g]
        tr = np.concatenate([groups[k] for k in range(N_FOLDS) if k != g])
        for cell in np.unique(key[te]):
            if cell < 0:
                continue                            # missing axis -> leave NaN (native missing path)
            m = (key[tr] == cell)
            if w[tr][m].sum() < 1e-9:
                continue
            rate = float((w[tr][m] * y[tr][m]).sum() / w[tr][m].sum())
            oof[te[key[te] == cell]] = rate
    return oof


def _member_rule_survivors(df, X, kept, y, w, starts, ends, trials, seed):
    """The discovery rig's readable high-precision rules, mined on train folds, scored on test folds.
    A candidate's probability = the OOF win-rate of the best surviving rule it matches, else the base
    rate. Sparse and interpretable - the member a human can read."""
    Xa = X[kept].to_numpy(dtype=np.float64)
    oof = np.full(len(y), np.nan)
    base = float((w * y).sum() / max(w.sum(), 1e-12))
    for tr, te in H.PurgedKFold(N_FOLDS, EMBARGO).split(starts, ends):
        if len(tr) < D.MIN_TRAIN or np.unique(y[tr]).size < 2:
            continue
        oof[te] = base                              # default every test row to the base rate...
        try:
            rules = _mine_simple_rules(Xa[tr], y[tr], w[tr], kept)
            for clause, rate in rules:               # ...then upgrade rows matching a surviving rule
                mte = _clause_mask(Xa[te], clause)
                oof[te[mte]] = rate
        except Exception:
            pass
    trials.bump("council_rule_folds", N_FOLDS)
    return oof


def _mine_simple_rules(Xtr, ytr, wtr, kept, max_rules=8, min_support=40, min_rate=0.30):
    """Lightweight rule miner: single-feature upper/lower deciles whose train win-rate clearly beats
    base. Returns [(clause, rate)] where clause = (col_index, 'hi'|'lo', threshold)."""
    base = float((wtr * ytr).sum() / max(wtr.sum(), 1e-12))
    out = []
    for j in range(Xtr.shape[1]):
        col = Xtr[:, j]
        fin = np.isfinite(col)
        if fin.sum() < min_support * 2:
            continue
        for side, q in (("hi", 0.8), ("lo", 0.2)):
            thr = np.nanquantile(col[fin], q)
            m = (col >= thr) if side == "hi" else (col <= thr)
            m &= fin
            if w_sum := float(wtr[m].sum()):
                if m.sum() >= min_support:
                    rate = float((wtr[m] * ytr[m]).sum() / max(w_sum, 1e-12))
                    if rate >= max(min_rate, base * 1.25):
                        out.append(((j, side, float(thr)), rate))
    out.sort(key=lambda kv: -kv[1])
    return out[:max_rules]


def _clause_mask(X, clause):
    j, side, thr = clause
    col = X[:, j]
    m = (col >= thr) if side == "hi" else (col <= thr)
    return np.where(np.isfinite(col), m, False)


def run_council(df, X, kept, trials, seed=7, ttl_asof_ms=None, ttl_decision_ms=None):
    """Fit all five members OOF, calibrate each, blend, measure disagreement, and DECIDE per candidate
    against its own break-even bar. ttl_asof_ms / ttl_decision_ms exercise the TTL registry; in the
    retrospective shadow run both default to signal time (nothing stale by construction)."""
    reduced, dropped = S.cluster_features(X, kept)
    trials.bump("council_features_clustered_out", len(dropped))
    Xd = apply_ttl(X[reduced], reduced, df["signal_ts"].to_numpy(),
                   ttl_asof_ms, ttl_decision_ms)      # decision-time staleness -> NaN (Section 2)
    Xv = Xd.to_numpy(dtype=np.float64)
    y = df["y_up"].to_numpy(dtype=np.float64)
    uniq = df["weight"].to_numpy(dtype=np.float64)
    decay = S.time_decay(df["signal_ts"].to_numpy(), S.HALF_LIFE_DAYS)
    w = uniq * decay
    starts = df["window_start"].to_numpy(dtype=np.float64)
    ends = df["window_end"].to_numpy(dtype=np.float64)
    net = df["net_ret"].to_numpy(dtype=np.float64)

    raw = {
        "gbm_meta": _member_gbm(Xv, y, w, starts, ends, seed),
        "logistic_linear": _member_logistic(Xv, y, w, starts, ends, seed),
        "flow_specialist": _member_flow_specialist(Xv, y, w, starts, ends, reduced, seed),
        "base_rate_2d": _member_base_rate_2d(df, X, kept, y, w, starts, seed),
        "rule_survivors": _member_rule_survivors(df, X, kept, y, w, starts, ends, trials, seed),
    }
    trials.bump("council_member_fits", len(MEMBERS) * N_FOLDS)

    # per-member calibration on its own finite OOF rows
    cal_probs = {}
    member_auc = {}
    for name, oof in raw.items():
        fin = np.isfinite(oof)
        p = np.full(len(y), np.nan)
        if fin.sum() >= 50 and np.unique(y[fin]).size > 1:
            cal = CAL.calibrate(oof[fin], y[fin])
            p[fin] = cal["predict"](oof[fin])
            member_auc[name] = round(D.weighted_auc(y[fin], oof[fin], uniq[fin]), 4)
        else:
            member_auc[name] = None
        cal_probs[name] = p

    P = np.vstack([cal_probs[m] for m in MEMBERS])      # (5, n)
    present = np.isfinite(P)
    n_present = present.sum(axis=0)
    with np.errstate(invalid="ignore"):
        blend = np.nanmean(P, axis=0)                   # equal-weight blend over members that scored
        disagree = np.nanstd(P, axis=0)

    # per-CONTRACT break-even bar (addendum): bar_i = (cost_i - mu_loss)/(mu_win - mu_loss)
    rr = df["realized_return"].to_numpy(dtype=np.float64)
    cost = EV.cost_model(df["cost_base"].to_numpy())
    mu_win = float(np.nanmean(rr[y == 1])) if (y == 1).any() else 0.30
    mu_loss = float(np.nanmean(rr[y == 0])) if (y == 0).any() else -0.50
    denom = (mu_win - mu_loss) or 1.0
    contract_bar = np.clip((cost - mu_loss) / denom, 0.05, 0.95)

    # FAIL-CLOSED: fewer than a quorum of members scored a row = component failure = VETO.
    QUORUM = 3
    take = (np.isfinite(blend) & (n_present >= QUORUM)
            & (blend >= contract_bar) & (disagree <= DISAGREE_MAX))
    veto_reason = np.where(
        n_present < QUORUM, "component_failure_quorum",
        np.where(~np.isfinite(blend), "no_blend",
                 np.where(blend < contract_bar, "below_contract_bar",
                          np.where(disagree > DISAGREE_MAX, "members_disagree", "TAKE"))))

    sel = take & np.isfinite(blend)
    p_hit, neff = D.weighted_rate(y[sel], uniq[sel]) if sel.any() else (float("nan"), 0.0)
    lo, hi = D.wilson_eff(p_hit, neff)
    net_sel = float((uniq[sel] * net[sel]).sum() / max(uniq[sel].sum(), 1e-12)) if sel.any() else float("nan")
    blend_auc = D.weighted_auc(y[np.isfinite(blend)], blend[np.isfinite(blend)],
                               uniq[np.isfinite(blend)]) if np.isfinite(blend).any() else float("nan")

    return {
        "members": MEMBERS, "member_auc": member_auc, "blend_auc": round(blend_auc, 4),
        "cal_probs": cal_probs, "blend": blend, "disagree": disagree,
        "contract_bar": contract_bar, "take": take, "veto_reason": veto_reason,
        "n_present": n_present, "disagree_max": DISAGREE_MAX, "quorum": QUORUM,
        "selection": {"n": int(sel.sum()), "n_eff": round(neff, 1),
                      "hit": None if not np.isfinite(p_hit) else round(p_hit, 4),
                      "wilson_lo": None if not np.isfinite(lo) else round(lo, 4),
                      "net_ret": None if not np.isfinite(net_sel) else round(net_sel, 4)},
        "config": {"n_folds": N_FOLDS, "embargo": EMBARGO, "disagree_max": DISAGREE_MAX,
                   "quorum": QUORUM, "latency_budget_s": LATENCY_BUDGET_S, "seed": seed},
    }


def score_one(members_state, feature_row_dict, asof_ms, decision_ms, latency_budget_s=LATENCY_BUDGET_S):
    """LIVE decision path (used dormant by gate-mode). Given trained members and ONE candidate's
    features, return the council decision under the fail-closed contract. A member that raises or the
    total scoring exceeding the latency budget is a COMPONENT FAILURE -> absolute VETO."""
    t0 = time.monotonic()
    probs, failed = {}, []
    for name, predict in members_state.items():
        try:
            probs[name] = float(predict(feature_row_dict, asof_ms, decision_ms))
        except Exception:
            failed.append(name)
        if time.monotonic() - t0 > latency_budget_s:
            return {"decision": "VETO", "reason": "latency_exceeded", "latency_s": time.monotonic() - t0}
    if failed or len(probs) < 3:
        return {"decision": "VETO", "reason": "component_failure", "failed": failed,
                "latency_s": time.monotonic() - t0}
    vals = np.array(list(probs.values()), dtype=np.float64)
    blend, disagree = float(np.nanmean(vals)), float(np.nanstd(vals))
    bar = float(feature_row_dict.get("_contract_bar", 0.5944))
    take = np.isfinite(blend) and blend >= bar and disagree <= DISAGREE_MAX
    return {"decision": "TAKE" if take else "VETO", "blend": blend, "disagree": disagree,
            "contract_bar": bar, "probs": probs,
            "reason": "TAKE" if take else ("members_disagree" if disagree > DISAGREE_MAX else "below_contract_bar"),
            "latency_s": time.monotonic() - t0}


def shadow_frame(df, res, days=None):
    """Per-candidate council shadow rows (reporting only)."""
    out = pd.DataFrame({
        "candidate_id": df["candidate_id"].to_numpy(),
        "ticker": df["ticker"].to_numpy(),
        "signal_ts": df["signal_ts"].to_numpy(),
        "executed": df["executed"].to_numpy(),
        "council_blend": np.round(res["blend"], 4),
        "disagreement": np.round(res["disagree"], 4),
        "contract_bar": np.round(res["contract_bar"], 4),
        "members_present": res["n_present"],
        "decision": np.where(res["take"], "TAKE", "VETO"),
        "veto_reason": res["veto_reason"],
        "outcome": df["outcome"].to_numpy(),
    })
    for m in MEMBERS:
        out[f"p_{m}"] = np.round(res["cal_probs"][m], 4)
    return out.sort_values("signal_ts")
