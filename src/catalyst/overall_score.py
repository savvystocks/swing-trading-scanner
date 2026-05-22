def _survival_component(pick):
    surv = pick.get("_survival_score") or {}
    score = surv.get("score")
    if score is None:
        return 60.0
    try:
        return float(score)
    except (TypeError, ValueError):
        return 60.0


def _llm_edge_component(pick):
    forensic = pick.get("unified_forensic") or pick.get("haiku_synthesis") or {}
    bear = pick.get("bear_verification") or {}

    if bear.get("is_this_trade_a_trap"):
        return 5.0

    verdict = forensic.get("verdict")
    conf = forensic.get("confidence_pct")
    try:
        conf = float(conf) if conf is not None else 0
    except (TypeError, ValueError):
        conf = 0
    bear_conv = bear.get("bear_conviction_pct")
    try:
        bear_conv = float(bear_conv) if bear_conv is not None else 0
    except (TypeError, ValueError):
        bear_conv = 0

    if not verdict:
        return 50.0

    if verdict in ("STRONG_BUY",):
        bull_signal = 50 + (conf * 0.5)
    elif verdict in ("BUY",):
        bull_signal = 50 + (conf * 0.4)
    elif verdict in ("SKIP", "STRONG_SELL", "SELL"):
        bull_signal = 50 - (conf * 0.5)
    elif verdict in ("HOLD", "WATCH"):
        bull_signal = 50
    else:
        bull_signal = 50

    net = bull_signal - bear_conv
    scaled = 50 + net * 0.625
    return max(0.0, min(100.0, scaled))


def _earnings_quality_component(pick):
    eq = pick.get("_earnings_quality") or {}
    rating = eq.get("rating")
    score = eq.get("earnings_quality_score")
    rating_map = {"HIGH": 90, "MED": 70, "LOW": 45, "RED_FLAG": 15}
    if rating in rating_map:
        return float(rating_map[rating])
    if score is not None:
        try:
            return max(0.0, min(100.0, float(score)))
        except (TypeError, ValueError):
            pass
    return 60.0


def _catalyst_stack_component(pick):
    cat_count = pick.get("_category_count") or len(pick.get("catalysts") or [])
    stack_score = pick.get("_stacked_score") or pick.get("score") or 0
    try:
        stack_score = float(stack_score)
    except (TypeError, ValueError):
        stack_score = 0

    if stack_score >= 350:
        s = 95
    elif stack_score >= 250:
        s = 85
    elif stack_score >= 175:
        s = 72
    elif stack_score >= 125:
        s = 60
    elif stack_score >= 75:
        s = 50
    else:
        s = 35

    try:
        cat_count = int(cat_count or 0)
    except (TypeError, ValueError):
        cat_count = 0
    if cat_count >= 5:
        s = min(100, s + 6)
    elif cat_count >= 4:
        s = min(100, s + 3)
    return float(s)


def _iv_positioning_component(pick):
    iv_data = pick.get("iv_percentile_analysis") or {}
    iv_pct = iv_data.get("iv_percentile")
    if iv_pct is None:
        return 60.0
    try:
        iv_pct = float(iv_pct)
    except (TypeError, ValueError):
        return 60.0
    if iv_pct < 25:
        return 92.0
    if iv_pct < 45:
        return 78.0
    if iv_pct < 65:
        return 60.0
    if iv_pct < 80:
        return 42.0
    return 25.0


def _llm_verdict_component(pick):
    forensic = pick.get("unified_forensic") or {}
    haiku = pick.get("haiku_synthesis") or {}
    verdict = forensic.get("verdict") or haiku.get("verdict")
    return float({"STRONG_BUY": 95, "BUY": 80, "HOLD": 50, "WATCH": 45, "SKIP": 10}.get(verdict, 55))


WEIGHTS = {
    "survival": 0.25,
    "llm_edge": 0.25,
    "earnings_quality": 0.15,
    "catalyst_stack": 0.15,
    "iv_positioning": 0.10,
    "llm_verdict": 0.10,
}


def compute_overall_score(pick):
    components = {
        "survival": _survival_component(pick),
        "llm_edge": _llm_edge_component(pick),
        "earnings_quality": _earnings_quality_component(pick),
        "catalyst_stack": _catalyst_stack_component(pick),
        "iv_positioning": _iv_positioning_component(pick),
        "llm_verdict": _llm_verdict_component(pick),
    }

    weighted = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)

    bear = pick.get("bear_verification") or {}
    if bear.get("is_this_trade_a_trap"):
        weighted = min(weighted, 22)

    overall = round(weighted, 0)

    if overall >= 80:
        label = "TAKE THIS"
        klass = "overall-strong"
        plain = "Strong setup. Multiple signals aligned with manageable risk."
    elif overall >= 67:
        label = "GOOD SETUP"
        klass = "overall-good"
        plain = "Solid edge. Worth a normal-sized position."
    elif overall >= 52:
        label = "BORDERLINE"
        klass = "overall-borderline"
        plain = "Some edge but watch the listed risks. Size down or use defined risk."
    elif overall >= 38:
        label = "WAIT FOR BETTER"
        klass = "overall-watch"
        plain = "Mixed signals. Better to wait for cleaner setup."
    else:
        label = "AVOID"
        klass = "overall-avoid"
        plain = "Too many red flags. Skip this name."

    bull = components["llm_edge"]
    bull_minus_50 = bull - 50
    base_prob = 50 + bull_minus_50 * 0.4
    quality_adj = (components["earnings_quality"] - 60) * 0.06
    survival_adj = (components["survival"] - 60) * 0.10
    iv_adj = (components["iv_positioning"] - 60) * 0.03
    probability = round(max(20, min(85, base_prob + quality_adj + survival_adj + iv_adj)), 0)
    if bear.get("is_this_trade_a_trap"):
        probability = min(probability, 25)

    return {
        "score": int(overall),
        "verdict": label,
        "verdict_class": klass,
        "plain_english": plain,
        "probability_of_profit_pct": int(probability),
        "components": {k: int(round(v, 0)) for k, v in components.items()},
        "weights": WEIGHTS,
    }


def apply_overall_scores(picks, verbose=False, max_picks=15):
    if not picks:
        return
    n = 0
    for p in picks[:max_picks]:
        try:
            p["_overall_score"] = compute_overall_score(p)
            n += 1
        except Exception as e:
            if verbose:
                print(f"  overall_score fail {p.get('ticker')}: {type(e).__name__}: {e}")
    if verbose and n:
        scores = [p.get("_overall_score", {}).get("score") for p in picks[:max_picks]]
        scores = [s for s in scores if s is not None]
        if scores:
            print(f"  overall_score: scored {len(scores)} picks, max={max(scores)}, avg={sum(scores)/len(scores):.0f}")
