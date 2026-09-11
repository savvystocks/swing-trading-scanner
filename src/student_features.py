"""STUDENT FEATURES - one vector, two callers (owner order 2026-09-11: put the student's picks
live). Every feature is knowable AT THE MOMENT the alert qualifies (cumulative premium first
reaches the 50k band floor). The archive side builds it from the per-print table up to the
qualifying print plus PRIOR-day contract fields; the live side builds it from the Unusual Whales
alert row, the engine's regime readings and the broker quote. Same order, same units, NaN for
unknown; the model imputes. A parity fixture in the MOT asserts both builders agree.

Also carries a dependency-free evaluator for exported gradient-boosting models (JSON of the tree
nodes) so the engine on GitHub Actions needs no scikit-learn."""
import json
import math
from datetime import date

QUAL_PREM = 50000.0
FEATS = ["side", "dte", "hour", "dow", "reg", "sp", "smd", "entry_ask", "spread_frac",
         "cum_prem", "ask_share", "mins_since_first", "oi_prev", "prem_oi_asof", "iv_prev"]
# 15 features (panel 2026-09-11): dropped price_drift, delta_prev, gamma_prev, abs_delta_prev
# (structurally NaN on the live path) and n_prints, cum_size, vol_oi_asof (archive = prints to
# the 50k crossing, live = one alert burst - different objects). reg/sp/smd are D-1 close on
# BOTH sides.


def _f(v):
    return float(v) if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)) else float("nan")


def dte_of(occ, day):
    try:
        exp = date(2000 + int(occ[-15:-13]), int(occ[-13:-11]), int(occ[-11:-9]))
        return float((exp - date.fromisoformat(day)).days)
    except Exception:
        return float("nan")


def asof_from_prints(prints, qual_prem=QUAL_PREM):
    """prints: list of (executed_at, price, size, premium, nbbo_bid, nbbo_ask, side_hint) in
    time order for ONE contract-day. Returns the as-of block at the qualifying print, or None
    if the day's prints never reach qual_prem."""
    cum_p = cum_s = ask_p = 0.0
    n = 0
    first_ts = None
    first_px = None
    for ts, px, size, prem, bid, ask, side_hint in prints:
        prem = float(prem or 0.0)
        if first_ts is None:
            first_ts, first_px = ts, float(px or 0.0)
        cum_p += prem
        cum_s += float(size or 0)
        n += 1
        if side_hint == "ask":
            ask_p += prem
        if cum_p >= qual_prem:
            try:
                h = int(ts[11:13]) + int(ts[14:16]) / 60.0
                m0 = int(first_ts[11:13]) * 60 + int(first_ts[14:16])
                m1 = int(ts[11:13]) * 60 + int(ts[14:16])
                mins = float(m1 - m0)
            except Exception:
                h, mins = float("nan"), float("nan")
            a, b = _f(ask), _f(bid)
            spread = ((a - b) / a) if (a == a and b == b and a > 0) else float("nan")
            drift = ((float(px or 0.0) / first_px) - 1.0) if first_px else float("nan")
            return {"hour": h, "entry_ask": a, "spread_frac": spread, "cum_prem": cum_p,
                    "cum_size": cum_s, "n_prints": float(n), "ask_share": (ask_p / cum_p) if cum_p else float("nan"),
                    "mins_since_first": mins, "price_drift": drift, "qual_ts": ts}
    return None


def vector(side, occ, day, reg, sp, smd, asof, oi_prev, iv_prev):
    """The canonical 15-float vector. side: 'C'/'P' (or 'call'/'put'). asof: dict from
    asof_from_prints (archive) or asof_from_alert (engine). reg/sp/smd must be PRIOR-close
    readings on both sides. NaN where unknown; the model imputes."""
    s = 1.0 if str(side).upper().startswith("C") else -1.0
    d = date.fromisoformat(day)
    oi = _f(oi_prev)
    cp = _f(asof.get("cum_prem"))
    return [s, dte_of(occ, day), _f(asof.get("hour")), float(d.weekday()), _f(reg), _f(sp), _f(smd),
            _f(asof.get("entry_ask")), _f(asof.get("spread_frac")), cp, _f(asof.get("ask_share")),
            _f(asof.get("mins_since_first")), oi,
            (cp / oi) if (oi == oi and oi > 0 and cp == cp) else float("nan"), _f(iv_prev)]


def asof_from_alert(alert, quote_bid, quote_ask, first_seen_iso):
    """Live: the same block from a UW flow alert row + the broker quote at cycle time.
    first_seen_iso: created_at of the earliest alert the engine has seen for this contract today
    (the engine keeps a per-day map)."""
    ca = str(alert.get("created_at") or "")
    try:
        h = int(ca[11:13]) + int(ca[14:16]) / 60.0
        m1 = int(ca[11:13]) * 60 + int(ca[14:16])
        m0 = int(first_seen_iso[11:13]) * 60 + int(first_seen_iso[14:16]) if first_seen_iso else m1
        mins = float(m1 - m0)
    except Exception:
        h, mins = float("nan"), float("nan")
    tp = _f(alert.get("total_premium"))
    ap = _f(alert.get("total_ask_side_prem")); bp = _f(alert.get("total_bid_side_prem"))
    a, b = _f(quote_ask), _f(quote_bid)
    spread = ((a - b) / a) if (a == a and b == b and a > 0) else float("nan")
    return {"hour": h, "entry_ask": a, "spread_frac": spread, "cum_prem": tp,
            "cum_size": _f(alert.get("total_size")), "n_prints": _f(alert.get("trade_count")),
            "ask_share": (ap / (ap + bp)) if (ap == ap and bp == bp and (ap + bp) > 0) else float("nan"),
            "mins_since_first": mins}


# ---------------------------------------------------------------------------------------------
# dependency-free evaluator for an exported sklearn HistGradientBoosting model
# ---------------------------------------------------------------------------------------------
def export_hgb(model):
    """Serialise a fitted HistGradientBoostingClassifier/Regressor to plain lists."""
    trees = []
    for stage in model._predictors:
        for pred in stage:
            nodes = pred.nodes
            trees.append([{"v": float(n["value"]), "f": int(n["feature_idx"]), "t": float(n["num_threshold"]),
                           "ml": bool(n["missing_go_to_left"]), "l": int(n["left"]), "r": int(n["right"]),
                           "leaf": bool(n["is_leaf"])} for n in nodes])
    base = model._baseline_prediction
    try:
        base = float(base.ravel()[0])
    except Exception:
        base = float(base)
    kind = "classifier" if hasattr(model, "classes_") else "regressor"
    return {"kind": kind, "baseline": base, "trees": trees, "n_features": int(model.n_features_in_)}


def _tree_value(nodes, x):
    i = 0
    while True:
        n = nodes[i]
        if n["leaf"]:
            return n["v"]
        v = x[n["f"]]
        if v != v:                        # NaN
            i = n["l"] if n["ml"] else n["r"]
        elif v <= n["t"]:
            i = n["l"]
        else:
            i = n["r"]


def predict(exported, x):
    """Score one vector. Classifier -> probability; regressor -> raw prediction."""
    raw = exported["baseline"] + sum(_tree_value(t, x) for t in exported["trees"])
    if exported["kind"] == "classifier":
        return 1.0 / (1.0 + math.exp(-raw)) if raw > -700 else 0.0
    return raw


def load_model(path):
    return json.load(open(path, encoding="utf-8"))
