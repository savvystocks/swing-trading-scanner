"""Bidirectional Output Builder - Path 3 Day 3.

Splits ranked_picks into two parallel streams:
  CALLS: bullish positioning extremes (crowded short, risk-on, GEX amplification)
  PUTS:  bearish positioning extremes (crowded long, risk-off pressure, extension)

The split is driven by `_positioning_first.side` (primary) and falls back to
`_direction.side` (conviction-based) when positioning is NEUTRAL.

Output structure for email/Telegram:
  {
    "calls": [pick, ...],    # top-N CALL picks by positioning conviction
    "puts": [pick, ...],     # top-N PUT picks by positioning conviction
    "summary": {
      "n_calls": int,
      "n_puts": int,
      "elite_calls": int,    # ELITE tier CALL count
      "elite_puts": int,
      "macro_regime": str,
      "thesis_summary": str, # one-line market context
    }
  }

Sizing per pick uses `_positioning_first.recommended_size_pct` (33/25/20/0).
"""


def _pick_side(pick):
    pf = pick.get("_positioning_first") or {}
    side = pf.get("side")
    if side in ("CALL", "PUT"):
        return side
    d = pick.get("_direction") or {}
    return d.get("side") or "NEUTRAL"


def _ranking_score(pick):
    pf = pick.get("_positioning_first") or {}
    pf_score = pf.get("score") or 0
    d = pick.get("_direction") or {}
    d_score = d.get("winning_score") or 0
    try:
        return max(float(pf_score), float(d_score))
    except (TypeError, ValueError):
        return 0


def _conviction_tier(pick):
    pf = pick.get("_positioning_first") or {}
    return pf.get("conviction_tier") or "NONE"


def _build_thesis_summary(macro_regime, n_calls, n_puts, elite_calls, elite_puts):
    if elite_calls > elite_puts:
        bias = f"BULL-LEANING ({elite_calls} elite CALLs vs {elite_puts} elite PUTs)"
    elif elite_puts > elite_calls:
        bias = f"BEAR-LEANING ({elite_puts} elite PUTs vs {elite_calls} elite CALLs)"
    else:
        bias = f"BALANCED ({elite_calls} elite CALLs, {elite_puts} elite PUTs)"

    macro_desc = {
        "RISK_ON": "Risk-on macro regime - tailwind for long-beta exposure.",
        "RISK_OFF_PRESSURE": "Risk-off pressure - macro headwind, defensive bias.",
        "NEUTRAL": "Neutral macro regime - positioning extremes drive selection.",
    }.get(macro_regime, "Unknown macro regime.")

    return f"{bias}. {macro_desc}"


def build_bidirectional(ranked_picks, macro=None, max_calls=10, max_puts=5,
                         min_call_score=40, min_put_score=40, verbose=False):
    """Build CALL and PUT streams from ranked_picks.

    Args:
      ranked_picks: list of picks with _positioning_first attached
      macro: macro snapshot (for regime context)
      max_calls / max_puts: cap per side
      min_call_score / min_put_score: minimum positioning_first score to include
    """
    if not ranked_picks:
        return {
            "calls": [],
            "puts": [],
            "summary": {"n_calls": 0, "n_puts": 0, "elite_calls": 0, "elite_puts": 0,
                        "macro_regime": "NEUTRAL", "thesis_summary": "No candidates produced."},
        }

    call_pool = []
    put_pool = []
    for p in ranked_picks:
        side = _pick_side(p)
        score = _ranking_score(p)
        if side == "CALL" and score >= min_call_score:
            call_pool.append(p)
        elif side == "PUT" and score >= min_put_score:
            put_pool.append(p)

    call_pool.sort(key=_ranking_score, reverse=True)
    put_pool.sort(key=_ranking_score, reverse=True)

    calls = call_pool[:max_calls]
    puts = put_pool[:max_puts]

    elite_calls = sum(1 for p in calls if _conviction_tier(p) == "ELITE")
    elite_puts = sum(1 for p in puts if _conviction_tier(p) == "ELITE")

    macro_regime = "NEUTRAL"
    if isinstance(macro, dict):
        mp = macro.get("macro_positioning") or {}
        macro_regime = mp.get("regime") or macro_regime
        if macro_regime not in ("RISK_ON", "RISK_OFF_PRESSURE", "NEUTRAL"):
            mr = macro.get("macro_regime") or {}
            raw = (mr.get("regime") or "").upper()
            if "RISK_ON" in raw:
                macro_regime = "RISK_ON"
            elif "RISK_OFF" in raw:
                macro_regime = "RISK_OFF_PRESSURE"

    thesis_summary = _build_thesis_summary(macro_regime, len(calls), len(puts), elite_calls, elite_puts)

    if verbose:
        print(f"  bidirectional_output: {len(calls)} CALLs (elite {elite_calls}), "
              f"{len(puts)} PUTs (elite {elite_puts}) | macro: {macro_regime}")
        print(f"    {thesis_summary}")

    return {
        "calls": calls,
        "puts": puts,
        "summary": {
            "n_calls": len(calls),
            "n_puts": len(puts),
            "elite_calls": elite_calls,
            "elite_puts": elite_puts,
            "strong_calls": sum(1 for p in calls if _conviction_tier(p) == "STRONG"),
            "strong_puts": sum(1 for p in puts if _conviction_tier(p) == "STRONG"),
            "macro_regime": macro_regime,
            "thesis_summary": thesis_summary,
        },
    }


def summarize_for_telegram(bidir, max_per_side=3):
    """Format bidirectional output for telegram alert. Returns plain text."""
    if not bidir:
        return "No bidirectional output."

    lines = []
    summary = bidir.get("summary") or {}
    lines.append(summary.get("thesis_summary") or "")
    lines.append("")

    calls = bidir.get("calls") or []
    if calls:
        lines.append(f"CALL CANDIDATES ({summary.get('n_calls', 0)} total, {summary.get('elite_calls', 0)} elite)")
        for c in calls[:max_per_side]:
            pf = c.get("_positioning_first") or {}
            tier = pf.get("conviction_tier", "?")
            score = pf.get("score", 0)
            top_signals = [s.get("key") for s in (pf.get("positioning_signals") or [])[:2]]
            lines.append(f"  {c.get('ticker', '?'):7} {tier:6} score={score} ({', '.join(top_signals)})")
        lines.append("")

    puts = bidir.get("puts") or []
    if puts:
        lines.append(f"PUT CANDIDATES ({summary.get('n_puts', 0)} total, {summary.get('elite_puts', 0)} elite)")
        for c in puts[:max_per_side]:
            pf = c.get("_positioning_first") or {}
            tier = pf.get("conviction_tier", "?")
            score = pf.get("score", 0)
            top_signals = [s.get("key") for s in (pf.get("positioning_signals") or [])[:2]]
            lines.append(f"  {c.get('ticker', '?'):7} {tier:6} score={score} ({', '.join(top_signals)})")

    return "\n".join(lines)
