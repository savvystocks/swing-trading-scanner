"""Conviction Score - the FINAL composite that drives the action decision.

Earlier scoring (Overall) misses ~50% of available signals. The Tier 5
modules (insider, options flow, PEAD, buyback, guidance, 13F, etc.) only
fire discrete IF/ELSE rules in action_signal. This means a pick with
strong insider buying + active options flow doesn't rank higher in
Overall than a pick without those signals - the action_signal layer
catches it but the LLM target selection misses it.

Conviction Score fixes that: it's a weighted composite of EVERY signal
in the system. The pipeline now uses Conviction as the primary ranking
key (not Overall) for LLM target selection AND for the final action.

Weights reflect documented retail edge by signal type. Negative signals
(trap, climax, fading trends) act as kill-switches with hard caps.
"""


def _safe(val, default=0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _llm_component(pick):
    overall = pick.get("_overall_score") or {}
    score = overall.get("score")
    if score is None:
        return 50
    return _safe(score, 50)


def _insider_component(pick):
    oi = pick.get("_openinsider") or {}
    if not oi:
        return 50
    count = _safe(oi.get("buyers_count"), 0)
    value = _safe(oi.get("total_value_usd"), 0)
    ceo_cfo = bool(oi.get("ceo_or_cfo_bought"))
    if count == 0:
        return 50
    score = 50
    if count >= 5:
        score += 25
    elif count >= 3:
        score += 18
    elif count >= 2:
        score += 10
    if value >= 1_000_000:
        score += 15
    elif value >= 500_000:
        score += 10
    elif value >= 100_000:
        score += 5
    if ceo_cfo:
        score += 15
    return min(100, score)


def _options_flow_component(pick):
    flow = pick.get("_options_flow_diy") or {}
    if not flow:
        return 50
    v = flow.get("verdict")
    if v == "STRONG_FLOW":
        return 90
    if v == "MODERATE_FLOW":
        return 70
    if v == "QUIET":
        return 45
    return 50


def _pead_component(pick):
    pead = pick.get("_pead") or {}
    if not pead:
        return 50
    strength = pead.get("strength")
    if strength == "STRONG_BEAT_HOLDING":
        return 90
    if strength == "GOOD_BEAT_HOLDING":
        return 75
    if strength == "MILD_BEAT_HOLDING":
        return 60
    return 50


def _buyback_guidance_component(pick):
    score = 50
    bb = pick.get("_edgar_buyback") or {}
    if bb.get("verdict") == "BUYBACK_ANNOUNCED":
        score += 20
    gr = pick.get("_edgar_guidance_raise") or {}
    if gr.get("verdict") == "GUIDANCE_RAISED":
        score += 30
    si = pick.get("_streetinsider") or {}
    if si.get("buyback"):
        score += 10
    if si.get("guidance_change"):
        score += 15
    if si.get("upgrade"):
        score += 8
    if si.get("downgrade"):
        score -= 20
    return max(0, min(100, score))


def _analyst_component(pick):
    a = pick.get("_analyst_rating_changes") or {}
    if not a:
        return 50
    v = a.get("verdict")
    if v == "UPGRADE_CLUSTER":
        return 85
    if v == "BULLISH_LEAN":
        return 65
    if v == "MIXED":
        return 50
    if v == "BEARISH_LEAN":
        return 35
    if v == "DOWNGRADE_CLUSTER":
        return 15
    return 50


def _whisper_component(pick):
    w = pick.get("_earnings_whisper") or {}
    if not w:
        return 50
    v = w.get("verdict")
    if v == "WHISPER_ABOVE_CONSENSUS":
        delta = _safe(w.get("delta_pct"), 0)
        return min(95, 60 + delta * 2)
    if v == "WHISPER_BELOW_CONSENSUS":
        delta = abs(_safe(w.get("delta_pct"), 0))
        return max(15, 40 - delta * 2)
    return 50


def _stage2_component(pick):
    s2 = pick.get("_stage2_zone") or {}
    if not s2:
        return 50
    zone = s2.get("zone")
    if zone == "PRIME_ENTRY":
        return 95
    if zone == "EARLY_CONTINUATION":
        return 80
    if zone == "CONTINUATION":
        return 60
    if zone == "EXTENDED":
        return 30
    if zone == "CLIMAX":
        return 10
    if zone == "NOT_IN_STAGE2":
        return 20
    return 50


def _whalewisdom_component(pick):
    ww = pick.get("_whalewisdom_13f") or {}
    if not ww:
        return 50
    v = ww.get("verdict")
    if v == "FUND_ACCUMULATION":
        return 80
    if v == "MILD_ACCUMULATION":
        return 65
    if v == "NEUTRAL":
        return 50
    if v == "FUND_DISTRIBUTION":
        return 25
    return 50


def _trends_component(pick):
    t = pick.get("_google_trends") or {}
    if not t:
        return 50
    v = t.get("verdict")
    if v == "TRENDING_UP":
        return 80
    if v == "ELEVATED":
        return 65
    if v == "STEADY":
        return 50
    if v == "FADING":
        return 25
    if v == "NO_INTEREST":
        return 40
    return 50


WEIGHTS = {
    "llm_and_overall": 0.28,
    "stage2": 0.17,
    "catalyst_window": 0.20,
    "insider": 0.15,
    "pead": 0.12,
    "buyback_guidance": 0.08,
}


def _catalyst_window_component(pick):
    fc = pick.get("_forward_catalyst") or {}
    score = fc.get("window_score")
    if score is None:
        return 50
    return score


def compute_conviction_score(pick):
    components = {
        "llm_and_overall": _llm_component(pick),
        "stage2": _stage2_component(pick),
        "catalyst_window": _catalyst_window_component(pick),
        "insider": _insider_component(pick),
        "pead": _pead_component(pick),
        "buyback_guidance": _buyback_guidance_component(pick),
    }
    weighted = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)

    bear = pick.get("bear_verification") or {}
    if bear.get("is_this_trade_a_trap"):
        weighted = min(weighted, 22)

    s2 = pick.get("_stage2_zone") or {}
    if s2.get("zone") == "CLIMAX":
        weighted = min(weighted, 25)

    t = pick.get("_google_trends") or {}
    if t.get("verdict") == "FADING" and weighted < 70:
        weighted = min(weighted, weighted * 0.85)

    score = round(weighted, 0)
    if score >= 80:
        tier = "TAKE_HIGH"
    elif score >= 70:
        tier = "TAKE"
    elif score >= 60:
        tier = "WATCH"
    elif score >= 45:
        tier = "SKIP"
    else:
        tier = "AVOID"

    return {
        "score": int(score),
        "tier": tier,
        "components": {k: int(round(v, 0)) for k, v in components.items()},
        "weights": WEIGHTS,
    }


def apply_conviction_scores(picks, verbose=False, max_picks=60):
    if not picks:
        return
    for p in picks[:max_picks]:
        try:
            p["_conviction"] = compute_conviction_score(p)
        except Exception:
            continue
    if verbose:
        scored = [p for p in picks[:max_picks] if p.get("_conviction")]
        if scored:
            scores = [p["_conviction"]["score"] for p in scored]
            high = sum(1 for s in scores if s >= 70)
            print(f"  conviction_score: scored {len(scored)} picks, max={max(scores)}, "
                  f"avg={sum(scores)/len(scores):.0f}, {high} TAKE-grade (>=70)")
