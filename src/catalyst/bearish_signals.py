"""Bearish setup detection - mirror image of bullish Stage 2 + smart-money signals.

For each pick we identify whether it's setting up for a BREAKDOWN (puts edge)
vs a BREAKOUT (calls edge). The output feeds into bear_conviction_score so
each pick gets BOTH a call_conviction AND a put_conviction. Whichever is
higher wins for that ticker.

Bearish setups we detect:
- Stage 4 zone (below 50dMA, below 200dMA, 50d crossing below 200d)
- Insider SELLING cluster (mirror of insider buying)
- Earnings MISS + holding the drop (mirror of PEAD)
- Dilutive offering / shelf S-3 filed
- Going concern language
- Downgrade cluster (already detected in analyst_rating_news)
- Trends FADING + Stage 4 + LLM SKIP = breakdown imminent
"""


def detect_stage4(pick):
    """Stage 4 = uptrend exhausted, now in decline."""
    above_50 = pick.get("above_50dma")
    above_200 = pick.get("above_200dma")
    pct_above_50 = pick.get("pct_above_50dma")
    ret_5d = pick.get("ret_5d")
    ret_30d = pick.get("ret_30d")
    ret_90d = pick.get("ret_90d")

    try:
        pct = float(pct_above_50) if pct_above_50 is not None else None
    except (TypeError, ValueError):
        pct = None
    try:
        ret5 = float(ret_5d) if ret_5d is not None else None
    except (TypeError, ValueError):
        ret5 = None
    try:
        ret30 = float(ret_30d) if ret_30d is not None else None
    except (TypeError, ValueError):
        ret30 = None
    try:
        ret90 = float(ret_90d) if ret_90d is not None else None
    except (TypeError, ValueError):
        ret90 = None

    if not above_50 and not above_200 and ret30 is not None and ret30 <= -10:
        return {"zone": "STAGE_4_DECLINE", "score": 90, "note": f"Below 50d & 200dMA, {ret30:.0f}% 30d - confirmed decline"}
    if not above_200 and ret90 is not None and ret90 <= -15:
        return {"zone": "STAGE_4_EARLY", "score": 75, "note": f"Below 200dMA, {ret90:.0f}% 90d - early breakdown"}
    if not above_50 and ret5 is not None and ret5 <= -7:
        return {"zone": "BREAKDOWN_FRESH", "score": 70, "note": f"Just broke 50dMA, {ret5:.0f}% in 5d - momentum breakdown"}
    if above_50 and above_200 and pct is not None and pct > 22 and ret30 is not None and ret30 > 30:
        return {"zone": "EXHAUSTION_TOP", "score": 60, "note": f"+{pct:.0f}% above 50dMA + {ret30:.0f}% 30d - parabolic, mean-reversion risk"}
    return None


def detect_insider_selling(pick):
    """Mirror of insider cluster - detect insider SELLING activity.

    OpenInsider data we currently pull is only BUYS. To detect sells we'd need
    to add a sells scraper. For now we rely on landmine flags and any insider
    selling signals already in the pick.
    """
    landmines = pick.get("_landmine_flags") or []
    for f in landmines:
        if isinstance(f, dict):
            label = (f.get("label") or "").lower()
            if "insider" in label and ("selling" in label or "sale" in label or "dump" in label):
                return {"verdict": "INSIDER_SELLING_CLUSTER", "score": 75, "label": f.get("label")}
    cats = pick.get("catalysts") or []
    for c in cats:
        if isinstance(c, dict) and c.get("key") == "insider_selling_cluster":
            return {"verdict": "INSIDER_SELLING_CLUSTER", "score": 75, "label": c.get("details", "")}
    return None


def detect_dilution_risk(pick):
    landmines = pick.get("_landmine_flags") or []
    for f in landmines:
        if isinstance(f, dict):
            label = (f.get("label") or "").lower()
            if any(k in label for k in ("shelf", "s-3", "atm offering", "dilutive", "secondary offering")):
                return {"verdict": "DILUTION_RISK", "score": 80, "label": f.get("label")}
    cats = pick.get("catalysts") or []
    for c in cats:
        if isinstance(c, dict) and c.get("key") in ("dilutive_offering", "private_placement", "secondary_offering"):
            return {"verdict": "DILUTION_RISK", "score": 80, "label": c.get("key")}
    return None


def detect_going_concern(pick):
    if pick.get("going_concern"):
        return {"verdict": "GOING_CONCERN", "score": 95, "label": "Going-concern flag"}
    cats = pick.get("catalysts") or []
    for c in cats:
        if isinstance(c, dict) and c.get("key") == "going_concern":
            return {"verdict": "GOING_CONCERN", "score": 95, "label": c.get("details", "")}
    return None


def detect_earnings_miss_drift(pick):
    """Mirror of PEAD - missed earnings + price still drifting down."""
    cats = pick.get("catalysts") or []
    has_miss_guide_down = any(
        isinstance(c, dict) and c.get("key") == "earnings_miss_with_guide_down"
        for c in cats
    )
    if has_miss_guide_down:
        try:
            ret5 = float(pick.get("ret_5d") or 0)
            ret30 = float(pick.get("ret_30d") or 0)
        except (TypeError, ValueError):
            return {"verdict": "EARNINGS_MISS", "score": 75}
        if ret5 < -3 or ret30 < -8:
            return {"verdict": "POST_MISS_DRIFT", "score": 85, "label": f"Earnings miss + still drifting down ({ret30:.0f}% 30d)"}
        return {"verdict": "EARNINGS_MISS", "score": 70}
    return None


def detect_strong_downgrade_cluster(pick):
    analyst = pick.get("_analyst_rating_changes") or {}
    if analyst.get("verdict") == "DOWNGRADE_CLUSTER":
        return {"verdict": "DOWNGRADE_CLUSTER", "score": 80, "examples": analyst.get("downgrade_examples", [])}
    si = pick.get("_streetinsider") or {}
    if si.get("downgrade"):
        return {"verdict": "DOWNGRADE_SI", "score": 70, "label": si.get("downgrade", "")[:120]}
    return None


def apply_bearish_signals(picks, verbose=False):
    if not picks:
        return
    counts = {"stage4": 0, "selling": 0, "dilution": 0, "going_concern": 0, "miss_drift": 0, "downgrades": 0}
    for p in picks:
        try:
            bearish = {}
            s4 = detect_stage4(p)
            if s4:
                bearish["stage4"] = s4
                counts["stage4"] += 1
            sell = detect_insider_selling(p)
            if sell:
                bearish["insider_selling"] = sell
                counts["selling"] += 1
            dil = detect_dilution_risk(p)
            if dil:
                bearish["dilution"] = dil
                counts["dilution"] += 1
            gc = detect_going_concern(p)
            if gc:
                bearish["going_concern"] = gc
                counts["going_concern"] += 1
            miss = detect_earnings_miss_drift(p)
            if miss:
                bearish["earnings_miss"] = miss
                counts["miss_drift"] += 1
            down = detect_strong_downgrade_cluster(p)
            if down:
                bearish["downgrade_cluster"] = down
                counts["downgrades"] += 1
            if bearish:
                p["_bearish_signals"] = bearish
        except Exception:
            continue
    if verbose:
        print(f"  bearish_signals: stage4={counts['stage4']} insider_selling={counts['selling']} "
              f"dilution={counts['dilution']} going_concern={counts['going_concern']} "
              f"miss_drift={counts['miss_drift']} downgrades={counts['downgrades']}")
