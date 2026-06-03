"""Master Confluence Scoring Engine.

Stacks all 7 patterns + positioning + macro alignment into a single 0-250 score
that drives the trade tier and sizing decision.

PATTERN POINTS (when fires):
  NOPE Extreme (Tier S)              25
  Gamma Flip Magnet (Tier S)         25
  Sweeps Followed by Floor (Tier A)  20
  Volume > OI (Tier A)               20
  Above-Ask Urgency (Tier B)         15
  Institutional $250k+ (Tier B)      15-20
  Whisper Delta (Tier C, situational) 15
  Market Tide Alignment              +10 / -10
  positioning_first.score            (0-100, scaled in)

TIER MAPPING (total score):
  200-250    GAMMA_BOMB        15% size, 0-3 DTE far OTM
  160-200    MAX_CONVICTION    40% size, 0.5 ITM call/put
  130-160    ELITE             30% size, ATM call/put
  100-130    STRONG            20% size, ATM call/put
  70-100     MODERATE          10% size, debit spread
  <70        PASS              skip
"""

from src.catalyst.patterns import (
    nope_extreme,
    gamma_flip_magnet,
    sweeps_followed_by_floor,
    volume_vs_oi,
    above_ask_urgency,
    institutional_size,
    whisper_delta,
    market_tide_alignment,
)


PATTERNS = [
    ("nope", nope_extreme.detect),
    ("gamma_flip", gamma_flip_magnet.detect),
    ("sweeps_floor", sweeps_followed_by_floor.detect),
    ("volume_oi", volume_vs_oi.detect),
    ("above_ask", above_ask_urgency.detect),
    ("institutional", institutional_size.detect),
    ("whisper", whisper_delta.detect),
]


def _tier_from_score(score):
    """Pure flow-based tiers (macro stripped from scoring).
    Max possible from 7 patterns: ~140 (25+25+20+20+20+15+15).
    Realistic on a strong day: 60-80 (3-4 patterns firing in unison)."""
    if score >= 100:
        return ("GAMMA_BOMB", 15)
    if score >= 80:
        return ("MAX_CONVICTION", 40)
    if score >= 60:
        return ("ELITE", 30)
    if score >= 45:
        return ("STRONG", 20)
    if score >= 30:
        return ("MODERATE", 10)
    return ("PASS", 0)


def _vehicle_for_tier(tier):
    return {
        "GAMMA_BOMB": "0-3 DTE far OTM call/put",
        "MAX_CONVICTION": "0.5 ITM call/put, 21-30d",
        "ELITE": "ATM call/put, 21-30d",
        "STRONG": "ATM call/put, 21-30d",
        "MODERATE": "ATM debit spread, 21-30d",
        "PASS": "skip",
    }.get(tier, "skip")


def _rr_for_tier(tier):
    """Target gain / max loss for the tier."""
    return {
        "GAMMA_BOMB": {"target_pct": 500, "stop_pct": -100, "max_hold_days": 3},
        "MAX_CONVICTION": {"target_pct": 200, "stop_pct": -50, "max_hold_days": 14},
        "ELITE": {"target_pct": 150, "stop_pct": -50, "max_hold_days": 14},
        "STRONG": {"target_pct": 100, "stop_pct": -50, "max_hold_days": 10},
        "MODERATE": {"target_pct": 75, "stop_pct": -50, "max_hold_days": 7},
        "PASS": {"target_pct": 0, "stop_pct": 0, "max_hold_days": 0},
    }.get(tier, {})


def compute_confluence(pick, uw_client, macro=None, verbose=False):
    """Score a single ticker against all confluence patterns.

    Returns dict with:
      score: total confluence score
      side: 'CALL' or 'PUT' (whichever side has more agreement)
      tier: GAMMA_BOMB / MAX_CONVICTION / ELITE / STRONG / MODERATE / PASS
      size_pct: recommended account % for the trade
      vehicle: suggested option structure
      target_pct / stop_pct / max_hold_days
      patterns_fired: list of pattern results
      thesis: one-sentence summary
    """
    ticker = pick.get("ticker")
    if not ticker or not uw_client.enabled:
        return None

    # Run each pattern detector
    patterns_fired = []
    call_score = 0
    put_score = 0
    pattern_log = {}

    for key, detect_fn in PATTERNS:
        try:
            result = detect_fn(uw_client, ticker, pick=pick)
        except Exception as e:
            if verbose:
                print(f"  pattern {key} failed for {ticker}: {type(e).__name__}: {e}")
            result = {"fires": False, "side": None, "score": 0, "label": f"{key} error", "details": None}
        pattern_log[key] = result
        if result.get("fires"):
            pts = result.get("score", 0)
            side = result.get("side")
            if side == "CALL":
                call_score += pts
            elif side == "PUT":
                put_score += pts
            patterns_fired.append({
                "key": key, "side": side, "score": pts,
                "label": result.get("label"), "details": result.get("details"),
            })

    # Determine dominant side
    if call_score > put_score:
        side = "CALL"
        base_pattern_score = call_score
    elif put_score > call_score:
        side = "PUT"
        base_pattern_score = put_score
    else:
        side = None
        base_pattern_score = max(call_score, put_score)

    # Macro stripped from scoring per user direction - we follow whales, not tea leaves.
    # positioning_first (CFTC/AAII/FINRA) and market_tide remain INFORMATIONAL ONLY
    # in the email banner for context, but do NOT affect tier/size.
    positioning_contribution = 0
    tide_score = 0

    # Still compute tide for display (no score impact)
    if side:
        tide_result = market_tide_alignment.detect(uw_client, ticker, pick=pick, intended_side=side)
        if tide_result.get("fires") or tide_result.get("score", 0) != 0:
            patterns_fired.append({
                "key": "market_tide_info", "side": side, "score": 0,
                "label": f"[INFO] {tide_result.get('label')}",
                "details": tide_result.get("details"),
            })

    total_score = base_pattern_score
    total_score = max(0, total_score)

    tier, size_pct = _tier_from_score(total_score)
    rr = _rr_for_tier(tier)
    vehicle = _vehicle_for_tier(tier)

    # Build plain-English thesis
    fired_labels = [p["label"] for p in patterns_fired if p.get("fires") != False and p.get("label")]
    top_3 = fired_labels[:3]
    if side and top_3:
        thesis = f"{ticker} {side} ({tier}): " + "; ".join(top_3)
    else:
        thesis = f"{ticker}: insufficient confluence - PASS"

    return {
        "ticker": ticker,
        "score": int(total_score),
        "side": side,
        "tier": tier,
        "size_pct": size_pct,
        "vehicle": vehicle,
        "target_pct": rr.get("target_pct"),
        "stop_pct": rr.get("stop_pct"),
        "max_hold_days": rr.get("max_hold_days"),
        "patterns_fired": patterns_fired,
        "call_score": call_score,
        "put_score": put_score,
        "positioning_contribution": positioning_contribution,
        "tide_score": tide_score,
        "thesis": thesis,
    }


def apply_confluence_scoring(picks, uw_client, macro=None, verbose=False):
    """Apply confluence scoring to every pick. Attaches `_confluence` dict."""
    if not picks:
        return picks
    if not uw_client.enabled:
        if verbose:
            print("  confluence_score: UW token missing - skipping")
        return picks

    scored = 0
    by_tier = {}
    for p in picks:
        try:
            res = compute_confluence(p, uw_client, macro=macro, verbose=verbose)
            if res:
                p["_confluence"] = res
                scored += 1
                by_tier[res["tier"]] = by_tier.get(res["tier"], 0) + 1
        except Exception as e:
            if verbose:
                print(f"  confluence fail for {p.get('ticker')}: {type(e).__name__}: {e}")
            continue

    if verbose:
        tier_str = " ".join(f"{t}={c}" for t, c in sorted(by_tier.items()))
        print(f"  confluence_score: scored {scored} picks. Tiers: {tier_str}")

    return picks


def rank_picks_by_confluence(picks, top_n=10):
    """Sort picks by confluence score (highest first). Return top N."""
    scored = [p for p in picks if p.get("_confluence", {}).get("tier") != "PASS"]
    scored.sort(key=lambda p: p.get("_confluence", {}).get("score", 0), reverse=True)
    return scored[:top_n]
