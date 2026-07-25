"""NEW-SOURCE EDGE HUNT (research only, Lane A).

Asks one question: does any alternative signal separate winners from losers materially better than
the current public options flow? The bar is PRE-REGISTERED from the flow baseline measured
2026-07-25 on harvest_20260724_2130: best single-feature separation |d| = 0.541, median 0.084.

Three families are engineered here, all from data already owned (GBP 0, no new provider):

  NORMALIZED  - the flow's apparent top separators are price LEVELS (macro.spot, liquidity.bid,
                vwma_20, zero_gamma_strike). Those separate largely because a $2 option is not a $200
                option - a scale artifact, not a signal. This family re-expresses every feature as a
                cross-sectional daily rank and a per-ticker z-score, killing the artifact.
  STRUCTURAL  - basic option characteristics absent from the harvested set: days to expiry,
                moneyness, premium relative to spot, spread relative to premium.
  PERSISTENCE - what the flow does NOT currently read: repeat flow on the same name, signal
                clustering within a day, premium rank within the day, time since the last signal on
                that ticker, direction agreement between repeats.

Separation is measured OUT-OF-FOLD: the winning feature is chosen on the early period and its
separation is then measured on the later period it never saw. In-sample maxima always look good;
that is the trap this module exists to avoid. Every feature tested is counted as a trial.
"""
import numpy as np
import pandas as pd

# Pre-registered baseline from the flow (2026-07-25, harvest_20260724_2130). The bar to beat.
FLOW_BEST_D = 0.541
FLOW_MEDIAN_D = 0.084
DAY_MS = 86400000


def cohens_d(values, win_mask):
    v = np.asarray(values, float)
    m = np.isfinite(v)
    a, b = v[m & win_mask], v[m & ~win_mask]
    if len(a) < 50 or len(b) < 50:
        return np.nan
    sd = np.sqrt((a.var() + b.var()) / 2.0)
    if not np.isfinite(sd) or sd < 1e-12:
        return np.nan
    return float(abs(a.mean() - b.mean()) / sd)


def build_normalized(fb, X, kept):
    """Cross-sectional daily rank + per-ticker z-score of every existing feature."""
    out = {}
    day = (fb["signal_ts"].to_numpy(float) // DAY_MS).astype(np.int64)
    tick = fb["ticker"].to_numpy()
    d_ser = pd.Series(day)
    t_ser = pd.Series(tick)
    for c in kept:
        v = pd.to_numeric(X[c], errors="coerce")
        if v.notna().sum() < 500 or v.nunique(dropna=True) < 5:
            continue
        out[f"rank_day::{c}"] = v.groupby(d_ser).rank(pct=True).to_numpy()
        g = v.groupby(t_ser)
        mu, sd = g.transform("mean"), g.transform("std")
        z = (v - mu) / sd.replace(0, np.nan)
        out[f"z_ticker::{c}"] = z.to_numpy()
    return out


def build_structural(fb, cands_meta):
    """Basic option characteristics that the harvested feature set does not carry."""
    out = {}
    spot = pd.to_numeric(cands_meta["underlying_last"], errors="coerce").to_numpy(float)
    strike = pd.to_numeric(cands_meta["strike"], errors="coerce").to_numpy(float)
    entry = pd.to_numeric(cands_meta["entry_ref"], errors="coerce").to_numpy(float)
    spread = pd.to_numeric(cands_meta["spread_pct"], errors="coerce").to_numpy(float)
    right = cands_meta["right"].astype(str).str.lower().str.startswith("c").to_numpy()
    sig = fb["signal_ts"].to_numpy(float)
    exp = pd.to_datetime(cands_meta["expiry"], errors="coerce", utc=True)
    dte = (exp.astype("int64").to_numpy() / 1e6 - sig) / DAY_MS
    with np.errstate(divide="ignore", invalid="ignore"):
        moneyness = np.where(right, (spot - strike) / spot, (strike - spot) / spot)   # +ve = ITM
        out["struct::days_to_expiry"] = dte
        out["struct::log_days_to_expiry"] = np.log1p(np.clip(dte, 0, None))
        out["struct::moneyness_pct"] = moneyness * 100.0
        out["struct::abs_moneyness_pct"] = np.abs(moneyness) * 100.0
        out["struct::premium_over_spot_pct"] = entry / spot * 100.0
        out["struct::spread_over_premium"] = spread / np.maximum(entry, 1e-9)
        out["struct::premium_per_dte"] = entry / np.maximum(dte, 0.5)
        out["struct::is_call"] = right.astype(float)
    return out


def build_persistence(fb, cands_meta):
    """Repeat-flow / clustering signals the current read ignores entirely."""
    out = {}
    ts = fb["signal_ts"].to_numpy(float)
    tick = fb["ticker"].to_numpy()
    right = cands_meta["right"].astype(str).str.lower().str.startswith("c").to_numpy()
    prem = pd.to_numeric(cands_meta["rule_score"], errors="coerce").to_numpy(float)
    order = np.argsort(ts, kind="mergesort")

    n_prior_3d = np.zeros(len(ts))
    n_prior_1d = np.zeros(len(ts))
    since_last = np.full(len(ts), np.nan)
    same_dir_prior = np.zeros(len(ts))
    hist = {}
    for i in order:
        t, tk = ts[i], tick[i]
        prev = hist.get(tk, [])
        n_prior_3d[i] = sum(1 for (pt, _) in prev if t - pt <= 3 * DAY_MS)
        n_prior_1d[i] = sum(1 for (pt, _) in prev if t - pt <= DAY_MS)
        if prev:
            since_last[i] = (t - prev[-1][0]) / 3600000.0
            same_dir_prior[i] = sum(1 for (pt, pr) in prev
                                    if t - pt <= 3 * DAY_MS and pr == right[i])
        prev.append((t, right[i]))
        hist[tk] = prev[-50:]
    out["persist::n_prior_signals_3d"] = n_prior_3d
    out["persist::n_prior_signals_1d"] = n_prior_1d
    out["persist::hours_since_last_on_ticker"] = since_last
    out["persist::same_direction_repeats_3d"] = same_dir_prior
    out["persist::is_repeat"] = (n_prior_3d > 0).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["persist::direction_agreement"] = np.where(n_prior_3d > 0, same_dir_prior / n_prior_3d, np.nan)

    # CAUSAL ONLY (fixed 2026-07-26). The first version of this block used whole-day aggregates -
    # signals_on_ticker_that_day / premium_rank_in_day / ticker_share_of_day_premium - each of which
    # counts signals arriving AFTER the decision point. That is lookahead: at entry you cannot know
    # how many more signals the day will bring. They are replaced by expanding-window equivalents that
    # see only what had already happened. (The contaminated version produced this family's headline
    # 0.465 separation; it was not real.)
    day = (ts // DAY_MS).astype(np.int64)
    n_so_far_ticker = np.zeros(len(ts))
    rank_so_far = np.full(len(ts), np.nan)
    share_so_far = np.full(len(ts), np.nan)
    seen_tk, day_prems, day_prem_sum, tk_prem_sum = {}, {}, {}, {}
    for i in order:                                    # strict time order; only prior rows are visible
        d, tk, p = day[i], tick[i], prem[i]
        key = (d, tk)
        n_so_far_ticker[i] = seen_tk.get(key, 0)
        prior = day_prems.get(d, [])
        if prior and np.isfinite(p):
            rank_so_far[i] = float(np.mean(np.asarray(prior) <= p))
        tot = day_prem_sum.get(d, 0.0)
        if tot > 0:
            share_so_far[i] = tk_prem_sum.get(key, 0.0) / tot
        seen_tk[key] = seen_tk.get(key, 0) + 1
        if np.isfinite(p):
            day_prems.setdefault(d, []).append(p)
            day_prem_sum[d] = tot + p
            tk_prem_sum[key] = tk_prem_sum.get(key, 0.0) + p
    out["persist::prior_signals_on_ticker_today"] = n_so_far_ticker
    out["persist::premium_rank_so_far_today"] = rank_so_far
    out["persist::ticker_share_of_prior_day_premium"] = share_so_far
    return out


CAUSAL_PERSISTENCE = (
    "persist::n_prior_signals_3d", "persist::n_prior_signals_1d",
    "persist::hours_since_last_on_ticker", "persist::same_direction_repeats_3d",
    "persist::is_repeat", "persist::direction_agreement",
    "persist::prior_signals_on_ticker_today", "persist::premium_rank_so_far_today",
    "persist::ticker_share_of_prior_day_premium",
)


def oof_separation(features, win, ts, trials_counter=None, min_early=300):
    """The honest test. Choose the best separator on the EARLY period, then measure that same
    feature's separation on the LATER period it never saw. Returns the full table plus the
    in-sample-vs-out-of-sample pair for the winner."""
    cut = float(np.median(ts))
    early, late = ts <= cut, ts > cut
    rows = []
    for name, v in features.items():
        v = np.asarray(v, float)
        if np.isfinite(v[early]).sum() < min_early:
            continue
        d_e = cohens_d(v[early], win[early])
        d_l = cohens_d(v[late], win[late])
        if trials_counter is not None:
            trials_counter.bump("source_hunt_features")
        if np.isfinite(d_e):
            rows.append({"feature": name, "d_early": d_e,
                         "d_late": d_l if np.isfinite(d_l) else np.nan})
    if not rows:
        return None
    tab = pd.DataFrame(rows).sort_values("d_early", ascending=False).reset_index(drop=True)
    champ = tab.iloc[0]
    return {"table": tab, "champion": champ["feature"],
            "champion_d_in_sample": float(champ["d_early"]),
            "champion_d_out_of_sample": float(champ["d_late"]) if np.isfinite(champ["d_late"]) else None,
            "median_d": float(tab["d_early"].median()),
            "n_features": len(tab)}
