"""STRATEGY BAKE-OFF (research only, ROADMAP Lane A).

Recomputes every historical candidate under each STRUCTURE, on the same stored signal features, the
same real price paths, and the same executable-price cost model (buy at ask, mark/sell on bid).
Produces an in-sample column and an honest out-of-sample column side by side, so a structure that
looks good in-sample and collapses out-of-sample is SEEN collapsing.

Structures are mechanical rules, not fitted models, so "out-of-sample" here means:
  - WALK-FORWARD: the structure measured on the later time half only (a structure that worked in one
    stretch and died in the next is exposed), and
  - PBO / Deflated Sharpe across the whole structure SET (they measure whether the best of N is a
    fluke - which is a property of the search, not of one rule), and
  - for model-GATED variants, genuine purged out-of-fold selection probabilities.

Nothing here recommends or deploys anything. Evidence only.
"""
import numpy as np
from collections import defaultdict

from . import discovery as D
from . import harness as H

LEG_BUDGET = 800.0
REAL_SPREAD_SINCE_MS = D.REAL_SPREAD_SINCE_MS


# ---------------------------------------------------------------- data prep
def load_frame(db_path):
    """candidates + non-stale executable paths + uniqueness weights + synthesized strike pairs."""
    import sqlite3
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cands = {}
    for r in con.execute("""SELECT candidate_id, ticker, occ_symbol, expiry, strike, "right",
                            signal_ts_utc, entry_ref, bid, ask, spread_pct, executed, features,
                            vertical_barrier_ts, sample_tier
                            FROM candidates WHERE occ_symbol IS NOT NULL AND entry_ref > 0"""):
        cands[r["candidate_id"]] = dict(r)
    paths = defaultdict(list)
    for r in con.execute("""SELECT candidate_id, poll_ts_utc, bid, ask, stale FROM bid_path
                            WHERE bid IS NOT NULL ORDER BY candidate_id, poll_ts_utc"""):
        if not r["stale"]:
            paths[r["candidate_id"]].append((r["poll_ts_utc"], r["bid"], r["ask"]))
    con.close()
    cands = {k: v for k, v in cands.items() if k in paths}

    clusters = defaultdict(list)                       # the 0.099 lesson: a ticker-day is ~one bet
    for cid, c in cands.items():
        clusters[(c["ticker"], int(c["signal_ts_utc"] // 86400000))].append(cid)
    weights = {cid: 1.0 / len(v) for v in clusters.values() for cid in v}
    cluster_of = {cid: k for k, v in clusters.items() for cid in v}
    return cands, paths, weights, _strike_pairs(cands, paths), cluster_of


def _strike_pairs(cands, paths):
    """Adjacent-strike pairs on the same ticker/expiry/right/day, both with overlapping paths.
    This is the ONLY honest basis for a synthesized spread - and it covers a biased subset (the
    most-harvested, most-liquid names). Coverage is reported, never hidden."""
    by = defaultdict(list)
    for cid, c in cands.items():
        if c["strike"]:
            by[(c["ticker"], c["expiry"], str(c["right"]).lower(),
                int(c["signal_ts_utc"] // 86400000))].append(cid)
    pairs = []
    for (tk, exp, right, day), ids in by.items():
        if len(ids) < 2:
            continue
        ids.sort(key=lambda i: cands[i]["strike"])
        for i in range(len(ids) - 1):
            a, b = ids[i], ids[i + 1]
            # further OTM = higher strike for calls, lower strike for puts
            signal_leg, otm_leg = (a, b) if right.startswith("c") else (b, a)
            width = abs(cands[b]["strike"] - cands[a]["strike"])
            if width <= 0:
                continue
            ta = {t: (bid, ask) for t, bid, ask in paths[signal_leg]}
            tb = {t: (bid, ask) for t, bid, ask in paths[otm_leg]}
            common = sorted(set(ta) & set(tb))
            if common:
                pairs.append({"signal": signal_leg, "otm": otm_leg, "width": width,
                              "ts": common, "pa": ta, "pb": tb})
    return pairs


# ---------------------------------------------------------------- structures
def naked_long(c, path, up=0.30, dn=-0.50, horizon_h=None):
    """Buy at the ask, mark/sell on the bid. Returns (pct_return_on_capital, dollars_per_800)."""
    e = c["entry_ref"]
    t0 = c["signal_ts_utc"]
    r = None
    for ts, bid, ask in path:
        if horizon_h is not None and (ts - t0) > horizon_h * 3600000:
            break
        rr = (bid - e) / e
        if up is not None and rr >= up:
            r = up
            break
        if dn is not None and rr <= dn:
            r = dn
            break
    if r is None:
        sel = [b for ts, b, a in path
               if horizon_h is None or (ts - t0) <= horizon_h * 3600000] or [path[0][1]]
        r = (sel[-1] - e) / e
    return r, r * LEG_BUDGET


def debit_spread(pair, cands, up=None, dn=None):
    """Buy the nearer-the-money strike at the ask, sell one strike further OTM at the bid. Same
    direction as the flow, cost-capped. Exit marks the long leg on the bid, covers the short on the ask.

    FIXED 2026-07-25 (adversarial verification): (a) BOTH entry legs are now priced off one common
    timestamp - previously each leg used its own signal snapshot, which on 79.5% of pairs were
    different instants (median 69 min apart), fabricating impossible entry prices; (b) the payoff is
    clamped to [0, width] at BOTH ends - the floor was missing, so 13.8% of trades booked losses worse
    than -100% on a structure that mathematically cannot lose more than its debit."""
    t0 = pair["ts"][0]                                 # one instant, both legs
    debit = (pair["pa"][t0][1] or 0) - (pair["pb"][t0][0] or 0)   # buy long at ask, sell short at bid
    if debit <= 0.01:
        return None
    width = pair["width"]
    if debit >= width:                                 # nothing to win; a quote artefact
        return None

    def value_at(t):                                   # bounded by construction: a vertical is [0, width]
        v = (pair["pa"][t][0] or 0) - (pair["pb"][t][1] or 0)
        return min(max(v, 0.0), width)

    for t in pair["ts"]:
        r = (value_at(t) - debit) / debit
        if up is not None and r >= up:
            return up, up * LEG_BUDGET
        if dn is not None and r <= dn:
            return dn, dn * LEG_BUDGET
    best = (value_at(pair["ts"][-1]) - debit) / debit
    return best, best * LEG_BUDGET


def credit_spread_fade(pair, cands, tp=None, sl=None):
    """FADE the flow: sell the signal strike at the bid, buy one further OTM at the ask as defined
    risk. Capital at risk = (width - credit) * 100. Return is on capital at risk.
    ASSUMPTION (unmodellable from quotes): closed before expiry, no early assignment, no pin risk."""
    t0 = pair["ts"][0]                                 # FIXED: one instant for both entry legs
    credit = (pair["pa"][t0][0] or 0) - (pair["pb"][t0][1] or 0)   # sell near leg at bid, buy far at ask
    if credit <= 0.01:
        return None
    width = pair["width"]
    risk = width - credit
    if risk <= 0.05 * width:                           # FIXED: a collapsed denominator explodes the
        return None                                    # return ratio; reject rather than fabricate
    for t in pair["ts"]:
        # closing genuinely crosses two spreads; the cost is charged in full and bounded only by the
        # structure's real maximum (width), not softened by a hold-to-expiry floor
        cost_to_close = min(max((pair["pa"][t][1] or 0) - (pair["pb"][t][0] or 0), 0.0), width)
        r = (credit - cost_to_close) / risk
        if tp is not None and r >= tp:
            return tp, tp * LEG_BUDGET
        if sl is not None and r <= sl:
            return sl, sl * LEG_BUDGET
    t = pair["ts"][-1]
    cost_to_close = min(max((pair["pa"][t][1] or 0) - (pair["pb"][t][0] or 0), 0.0), width)
    best = (credit - cost_to_close) / risk
    return best, best * LEG_BUDGET


# ---------------------------------------------------------------- evaluation
def summarize(rets, dollars, weights, label, note="", clusters=None):
    """FIXED 2026-07-25: n_eff is now computed on CLUSTER-aggregated weights. Kish's formula is
    invariant to rescaling within equal-sized clusters, so applying it to per-row 1/n weights returned
    the raw trade count - the very inflation the weights exist to remove - and that number was then
    used as the sample size for the Wilson bound."""
    if not rets:
        return {"label": label, "n": 0, "note": note or "no applicable trades"}
    r = np.asarray(rets, float)
    d = np.asarray(dollars, float)
    w = np.asarray(weights, float)
    if clusters is not None and len(clusters) == len(r):
        agg = {}
        for c, wi in zip(clusters, w):
            agg[c] = agg.get(c, 0.0) + float(wi)
        cw = np.asarray(list(agg.values()), float)
        neff = float(cw.sum() ** 2 / max((cw ** 2).sum(), 1e-12))
    else:
        neff = float(w.sum() ** 2 / max((w ** 2).sum(), 1e-12))
    hit_w = float((w * (r > 0)).sum() / w.sum())
    lo, _ = D.wilson_eff(hit_w, neff)
    return {"label": label, "n": len(r), "n_eff": round(neff, 1),
            "hit_raw": round(float((r > 0).mean()), 4), "hit_wt": round(hit_w, 4),
            "hit_wt_lo95": round(float(lo), 4),
            "mean_raw": round(float(r.mean()), 4),
            "mean_wt": round(float((w * r).sum() / w.sum()), 4),
            "total_usd": round(float(d.sum()), 0),
            "usd_per_trade": round(float(d.mean()), 1), "note": note}


def evaluate_structure(name, fn_rows, weights_map, split_ms, cluster_of=None):
    """fn_rows = [(candidate_id, signal_ts, ret, usd)]. Returns whole-sample + later-half summaries.

    FIXED 2026-07-25: `split_ms` is now REQUIRED and supplied globally by the caller. Each structure
    previously split at the median of its OWN rows, so the two report tables compared different
    calendar windows across structures and were not comparable."""
    ids = [r[0] for r in fn_rows]
    ts = np.array([r[1] for r in fn_rows], float)
    rets = [r[2] for r in fn_rows]
    usd = [r[3] for r in fn_rows]
    w = [weights_map.get(i, 1.0) for i in ids]
    cl = [(cluster_of or {}).get(i, i) for i in ids]
    out = {"name": name, "in_sample": summarize(rets, usd, w, name, clusters=cl)}
    late = ts > float(split_ms)
    if int(late.sum()) >= 30:
        out["oos_late_half"] = summarize([r for r, m in zip(rets, late) if m],
                                         [u for u, m in zip(usd, late) if m],
                                         [x for x, m in zip(w, late) if m],
                                         name + " [later half]",
                                         clusters=[c for c, m in zip(cl, late) if m])
    else:
        out["oos_late_half"] = {"label": name + " [later half]", "n": 0,
                                "note": f"only {int(late.sum())} trades after the global split"}
    return out


def pbo_over_structures(per_structure_rows, weights_map, n_groups=6):
    """PBO across the STRUCTURE SET: rows = time groups, cols = structures. Answers 'is the best of
    these N structures likely a fluke?' - a property of the search, which is where PBO belongs."""
    names = [n for n, rows in per_structure_rows.items() if len(rows) >= 60]
    if len(names) < 2:
        return {"pbo": None, "note": "fewer than 2 structures with enough trades", "dsr": None}
    all_ts = np.concatenate([np.array([r[1] for r in per_structure_rows[n]], float) for n in names])
    edges = np.quantile(all_ts, np.linspace(0, 1, n_groups + 1))
    M = np.full((n_groups, len(names)), np.nan)
    for ci, n in enumerate(names):
        rows = per_structure_rows[n]
        ts = np.array([r[1] for r in rows], float)
        usd = np.array([r[3] for r in rows], float)
        w = np.array([weights_map.get(r[0], 1.0) for r in rows], float)
        for gi in range(n_groups):
            m = (ts >= edges[gi]) & (ts <= edges[gi + 1])
            if m.sum() >= 10:
                M[gi, ci] = float((w[m] * usd[m]).sum() / max(w[m].sum(), 1e-12))
    # FIXED 2026-07-25: keep only structures with FULL group coverage rather than imputing missing
    # cells with the global minimum (which biased the ranking); the CSCV routine handles NaN natively.
    keep = ~np.any(np.isnan(M), axis=0)
    if keep.sum() < 2:
        keep = ~np.all(np.isnan(M), axis=0)             # fall back, but never impute
    if keep.sum() < 2:
        return {"pbo": None, "note": "insufficient per-group coverage", "dsr": None}
    Mc = M[:, keep]
    pbo, note = H.probability_of_backtest_overfitting(Mc, min_trials=2)
    champ = int(np.nanargmax(np.nanmean(Mc, axis=0)))
    series = Mc[:, champ]
    series = series[np.isfinite(series)]
    if series.size >= 4 and series.std(ddof=1) > 1e-12:
        sr = float(series.mean() / series.std(ddof=1))
        dsr, sr0, dnote = H.deflated_sharpe_ratio(sr, n_trials=max(len(names), 1),
                                                  sr_variance=H.sharpe_variance_across_trials(Mc),
                                                  n_obs=int(series.size))
    else:
        dsr, sr0, dnote = None, None, "UNDERPOWERED (needs >= 4 time groups)"
    return {"pbo": None if pbo is None else round(pbo, 4), "pbo_note": note,
            "dsr": None if dsr is None else round(dsr, 4), "dsr_note": dnote,
            "champion": [n for n, k in zip(names, keep) if k][champ],
            "n_structures": int(keep.sum())}
