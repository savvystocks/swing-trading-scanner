"""Final Score - Output of all due diligence (Rebuild B3).

Per Savvas's directive: score is OUTPUT, not input. Don't pre-rank by score, then
filter by score; score should be the verdict computed once at the END after all
data is collected.

Components (each 0-100):
  POSITIONING        (40 pts) - positioning_first.score directly. The leading signal.
  CONFLUENCE         (15 pts) - confluence detector count (positioning category required)
  LLM_VERDICT        (15 pts) - Haiku synthesis + bear verification net edge
  TECHNICAL          (10 pts) - VCP/pocket pivot/quiet RS/auction (already half-weight inside positioning)
  SURVIVAL           (10 pts) - trade survival score (drawdown probability)
  EARNINGS_QUALITY   ( 5 pts) - earnings beat history / guidance pattern
  CATALYST           ( 5 pts) - catalyst tier from news_score detectors

Total: 100.

Verdict tiers:
  >= 80: TAKE THIS (high conviction)
  >= 67: GOOD SETUP (worth normal-sized position)
  >= 52: BORDERLINE (size down or use defined risk)
  >= 38: WAIT FOR BETTER
  < 38: AVOID

This module REPLACES overall_score for the rebuilt pipeline. The old initial
score from Step 3 no longer drives anything - final_score is the one number that
matters.
"""

from datetime import datetime


COMPONENT_WEIGHTS = {
    "positioning": 0.40,
    "confluence": 0.15,
    "llm_verdict": 0.15,
    "technical": 0.10,
    "survival": 0.10,
    "earnings_quality": 0.05,
    "catalyst": 0.05,
}


def _positioning_component(pick):
    pf = pick.get("_positioning_first") or {}
    score = pf.get("score") or 0
    try:
        return float(score)
    except (TypeError, ValueError):
        return 0.0


def _confluence_component(pick):
    conf = pick.get("_confluence") or {}
    tier_score = {
        "ELITE": 90,
        "STRONG": 78,
        "STRONG_BACKWARD_ONLY": 62,
        "MODERATE": 55,
        "WEAK": 40,
        "NONE": 25,
    }.get(conf.get("sizing_tier") or "NONE", 25)
    return float(tier_score)


def _llm_verdict_component(pick):
    haiku = pick.get("haiku_synthesis") or {}
    bear = pick.get("bear_verification") or {}
    forensic = pick.get("unified_forensic") or {}
    is_trap = bear.get("is_this_trade_a_trap") or False
    if is_trap:
        return 5.0

    verdict = forensic.get("verdict") or haiku.get("verdict")
    if verdict == "STRONG_BUY":
        base = 90
    elif verdict == "BUY":
        base = 75
    elif verdict in ("HOLD", "WATCH"):
        base = 50
    elif verdict in ("SELL", "STRONG_SELL", "SKIP"):
        base = 15
    else:
        base = 50

    bear_conv = bear.get("bear_conviction_pct") or 0
    try:
        bear_conv = float(bear_conv)
    except (TypeError, ValueError):
        bear_conv = 0
    net = base - bear_conv * 0.5
    return max(0.0, min(100.0, net))


def _technical_component(pick):
    pf = pick.get("_positioning_first") or {}
    tech_half = pf.get("technical_half_weight_score") or 0
    try:
        # tech_half_weight is already 0-25 inside positioning_first; rescale to 0-100
        return min(100.0, float(tech_half) * 4)
    except (TypeError, ValueError):
        return 0.0


def _survival_component(pick):
    surv = pick.get("_survival_score") or {}
    score = surv.get("score")
    if score is None:
        return 60.0
    try:
        return float(score)
    except (TypeError, ValueError):
        return 60.0


def _earnings_quality_component(pick):
    eq = pick.get("_earnings_quality") or {}
    rating = eq.get("rating")
    rating_map = {"HIGH": 90, "MED": 70, "LOW": 45, "RED_FLAG": 15}
    if rating in rating_map:
        return float(rating_map[rating])
    score = eq.get("earnings_quality_score")
    if score is not None:
        try:
            return max(0.0, min(100.0, float(score)))
        except (TypeError, ValueError):
            pass
    return 60.0


def _catalyst_component(pick):
    cats = pick.get("catalysts") or []
    if not cats:
        return 30.0
    # Best catalyst tier in the stack
    tiers = []
    for c in cats:
        if isinstance(c, dict):
            t = c.get("tier")
            if t:
                tiers.append(t)
    if not tiers:
        return 35.0
    best = max(tiers, key=lambda t: {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}.get(t, 0))
    return float({"S": 95, "A": 80, "B": 65, "C": 50, "D": 35}.get(best, 35))


def compute_final_score(pick):
    """Compute the one number that matters. Called at the very end of the pipeline."""
    components = {
        "positioning": _positioning_component(pick),
        "confluence": _confluence_component(pick),
        "llm_verdict": _llm_verdict_component(pick),
        "technical": _technical_component(pick),
        "survival": _survival_component(pick),
        "earnings_quality": _earnings_quality_component(pick),
        "catalyst": _catalyst_component(pick),
    }

    weighted = sum(components[k] * COMPONENT_WEIGHTS[k] for k in COMPONENT_WEIGHTS)

    # Hard floor: bear-verified trap caps the final score
    bear = pick.get("bear_verification") or {}
    if bear.get("is_this_trade_a_trap"):
        weighted = min(weighted, 22)

    final = round(weighted, 0)

    if final >= 80:
        verdict = "TAKE THIS"
        verdict_class = "overall-strong"
        plain = "Strong setup. Multiple signals aligned with manageable risk."
    elif final >= 67:
        verdict = "GOOD SETUP"
        verdict_class = "overall-good"
        plain = "Solid edge. Worth a normal-sized position."
    elif final >= 52:
        verdict = "BORDERLINE"
        verdict_class = "overall-borderline"
        plain = "Some edge but watch the listed risks. Size down or use defined risk."
    elif final >= 38:
        verdict = "WAIT FOR BETTER"
        verdict_class = "overall-watch"
        plain = "Mixed signals. Better to wait for cleaner setup."
    else:
        verdict = "AVOID"
        verdict_class = "overall-avoid"
        plain = "Too many red flags. Skip this name."

    # Probability of profit (PoP) - directional, used in email
    base_prob = 50 + (components["positioning"] - 50) * 0.4
    llm_adj = (components["llm_verdict"] - 50) * 0.3
    survival_adj = (components["survival"] - 60) * 0.15
    probability = max(20, min(85, base_prob + llm_adj + survival_adj))

    return {
        "score": int(final),
        "verdict": verdict,
        "verdict_class": verdict_class,
        "plain_english": plain,
        "probability_of_profit_pct": int(probability),
        "components": {k: int(round(v, 0)) for k, v in components.items()},
        "weights": COMPONENT_WEIGHTS,
        "computed_at": datetime.utcnow().isoformat() + "Z",
    }


def apply_final_scores(picks, verbose=False, max_picks=60):
    """Compute final_score on the top N picks at the END of the pipeline.

    This is the ONLY score computation that matters - everything upstream is
    just data gathering and pre-ranking by positioning_first.score.
    """
    if not picks:
        return picks
    n = 0
    for p in picks[:max_picks]:
        try:
            p["_final_score"] = compute_final_score(p)
            # Also write to _overall_score for backward compat with email template
            p["_overall_score"] = p["_final_score"]
            n += 1
        except Exception as e:
            if verbose:
                print(f"  final_score fail {p.get('ticker')}: {type(e).__name__}: {e}")
    if verbose and n:
        scores = [p.get("_final_score", {}).get("score") for p in picks[:max_picks]]
        scores = [s for s in scores if s is not None]
        if scores:
            print(f"  final_score: scored {len(scores)} picks, max={max(scores)}, avg={sum(scores)/len(scores):.0f}")
            takes = sum(1 for s in scores if s >= 67)
            print(f"  final_score: {takes} picks at GOOD SETUP or better (>= 67)")
    return picks
