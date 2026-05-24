"""Bear Conviction Score - composite bearish edge per pick.

Mirror of conviction_score.py but inverts/reweights signals to detect
breakdown setups. Each pick gets BOTH a Conviction (bullish) and
Bear_Conviction. Whichever is higher determines the trade direction.

Output 0-100. >=70 = strong put setup. >=80 = TAKE_HIGH put.
"""


def _safe(v, default=0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _bearish_llm_component(pick):
    haiku = pick.get("haiku_synthesis") or {}
    verdict = haiku.get("verdict") or ""
    conf = _safe(haiku.get("confidence_pct"), 0)
    bear = pick.get("bear_verification") or {}
    bear_conv = _safe(bear.get("bear_conviction_pct"), 0)

    if not verdict:
        return 50.0

    if verdict in ("SKIP", "STRONG_SELL", "SELL"):
        bear_signal = 50 + (conf * 0.5)
    elif verdict in ("BUY", "STRONG_BUY"):
        bear_signal = 50 - (conf * 0.4)
    else:
        bear_signal = 50

    composite = (bear_signal + bear_conv) / 2 if bear_conv > 0 else bear_signal
    return max(0.0, min(100.0, composite))


def _bearish_stage_component(pick):
    bs = pick.get("_bearish_signals") or {}
    s4 = bs.get("stage4") or {}
    if s4.get("score"):
        return float(s4["score"])
    s2 = pick.get("_stage2_zone") or {}
    zone = s2.get("zone")
    if zone == "CLIMAX":
        return 80
    if zone == "EXTENDED":
        return 65
    if zone == "PRIME_ENTRY":
        return 15
    if zone == "EARLY_CONTINUATION":
        return 25
    if zone == "NOT_IN_STAGE2":
        return 70
    return 50


def _insider_selling_component(pick):
    bs = pick.get("_bearish_signals") or {}
    sell = bs.get("insider_selling") or {}
    if sell.get("score"):
        return float(sell["score"])
    oi = pick.get("_openinsider") or {}
    if oi.get("buyers_count", 0) > 0:
        return 20
    return 50


def _dilution_component(pick):
    bs = pick.get("_bearish_signals") or {}
    dil = bs.get("dilution") or {}
    gc = bs.get("going_concern") or {}
    if gc.get("score"):
        return float(gc["score"])
    if dil.get("score"):
        return float(dil["score"])
    return 50


def _earnings_bear_component(pick):
    bs = pick.get("_bearish_signals") or {}
    miss = bs.get("earnings_miss") or {}
    if miss.get("score"):
        return float(miss["score"])
    w = pick.get("_earnings_whisper") or {}
    if w.get("verdict") == "WHISPER_BELOW_CONSENSUS":
        delta = abs(_safe(w.get("delta_pct"), 0))
        return min(90, 60 + delta * 2)
    pead = pick.get("_pead") or {}
    if pead.get("verdict") == "PEAD_ELIGIBLE":
        return 20
    return 50


def _analyst_bear_component(pick):
    bs = pick.get("_bearish_signals") or {}
    dc = bs.get("downgrade_cluster") or {}
    if dc.get("score"):
        return float(dc["score"])
    a = pick.get("_analyst_rating_changes") or {}
    v = a.get("verdict")
    if v == "DOWNGRADE_CLUSTER":
        return 85
    if v == "BEARISH_LEAN":
        return 65
    if v == "UPGRADE_CLUSTER":
        return 15
    if v == "BULLISH_LEAN":
        return 35
    return 50


def _options_flow_bear_component(pick):
    flow = pick.get("_options_flow_diy") or {}
    if not flow:
        return 50
    pcr = _safe(flow.get("put_call_ratio_vol"), 1.0)
    if pcr >= 1.5:
        return 85
    if pcr >= 1.2:
        return 70
    if pcr <= 0.4:
        return 25
    return 50


def _trends_bear_component(pick):
    t = pick.get("_google_trends") or {}
    v = t.get("verdict")
    if v == "FADING":
        return 75
    if v == "NO_INTEREST":
        return 65
    if v == "STEADY":
        return 50
    if v == "ELEVATED":
        return 35
    if v == "TRENDING_UP":
        return 20
    return 50


def _whalewisdom_bear_component(pick):
    ww = pick.get("_whalewisdom_13f") or {}
    v = ww.get("verdict")
    if v == "FUND_DISTRIBUTION":
        return 80
    if v == "NEUTRAL":
        return 50
    if v == "FUND_ACCUMULATION":
        return 20
    if v == "MILD_ACCUMULATION":
        return 35
    return 50


def _iv_component(pick):
    """High IV percentile = expensive options (bad for puts as buyer).
    Low IV percentile = cheap options (good for puts)."""
    iv_data = pick.get("iv_percentile_analysis") or {}
    iv_pct = iv_data.get("iv_percentile")
    if iv_pct is None:
        return 50
    try:
        iv_pct = float(iv_pct)
    except (TypeError, ValueError):
        return 50
    if iv_pct < 30:
        return 75
    if iv_pct < 50:
        return 60
    if iv_pct < 75:
        return 45
    return 30


WEIGHTS = {
    "llm_bearish": 0.22,
    "stage_bearish": 0.18,
    "insider_selling": 0.12,
    "dilution_going_concern": 0.10,
    "earnings_bearish": 0.10,
    "analyst_bearish": 0.08,
    "options_flow_bearish": 0.06,
    "trends_bearish": 0.06,
    "whalewisdom_bearish": 0.04,
    "iv_for_puts": 0.04,
}


def compute_bear_conviction(pick):
    components = {
        "llm_bearish": _bearish_llm_component(pick),
        "stage_bearish": _bearish_stage_component(pick),
        "insider_selling": _insider_selling_component(pick),
        "dilution_going_concern": _dilution_component(pick),
        "earnings_bearish": _earnings_bear_component(pick),
        "analyst_bearish": _analyst_bear_component(pick),
        "options_flow_bearish": _options_flow_bear_component(pick),
        "trends_bearish": _trends_bear_component(pick),
        "whalewisdom_bearish": _whalewisdom_bear_component(pick),
        "iv_for_puts": _iv_component(pick),
    }
    weighted = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)

    bs = pick.get("_bearish_signals") or {}
    if bs.get("going_concern"):
        weighted = max(weighted, 75)
    if bs.get("dilution"):
        weighted = max(weighted, 65)

    score = round(weighted, 0)
    if score >= 80:
        tier = "TAKE_PUT_HIGH"
    elif score >= 70:
        tier = "TAKE_PUT"
    elif score >= 60:
        tier = "WATCH_PUT"
    elif score >= 45:
        tier = "PUT_WEAK"
    else:
        tier = "NO_PUT_EDGE"

    return {
        "score": int(score),
        "tier": tier,
        "components": {k: int(round(v, 0)) for k, v in components.items()},
        "weights": WEIGHTS,
    }


def apply_bear_conviction(picks, verbose=False, max_picks=60):
    if not picks:
        return
    for p in picks[:max_picks]:
        try:
            p["_bear_conviction"] = compute_bear_conviction(p)
        except Exception:
            continue
    if verbose:
        scored = [p for p in picks[:max_picks] if p.get("_bear_conviction")]
        if scored:
            scores = [p["_bear_conviction"]["score"] for p in scored]
            high = sum(1 for s in scores if s >= 70)
            print(f"  bear_conviction: scored {len(scored)} picks, max={max(scores)}, "
                  f"avg={sum(scores)/len(scores):.0f}, {high} PUT-grade (>=70)")
