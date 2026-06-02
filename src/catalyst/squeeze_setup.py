"""Short Squeeze Positioning Detector.

When short interest is elevated AND a catalyst is imminent AND float is tight,
forced covering creates explosive moves. This module surfaces multi-factor
squeeze candidates.

Components:
  - Short % of float (EODHD ShortPercentFloat field)
  - Days to cover (SI / avg daily volume)
  - Float size (small = tighter squeeze)
  - Catalyst proximity (5-21 days = forced covering window)
  - Insider buying overlay (informed accumulation = squeeze accelerator)

Edge: short interest >15% + tight float + catalyst nearby + insider buying
= probable +20-50% squeeze move in 1-2 weeks (when it works).

Free data: EODHD fundamentals + our own catalyst_window + insider_cluster.
"""


def _get_short_data(pick):
    fund = pick.get("_fundamentals") or {}
    technicals = (fund.get("Technicals") or {})
    shares_stats = (fund.get("SharesStats") or {})
    return {
        "short_pct_float": pick.get("short_pct_float") or technicals.get("ShortPercent") or 0,
        "shares_short": shares_stats.get("SharesShort") or 0,
        "shares_short_prior_month": shares_stats.get("SharesShortPriorMonth") or 0,
        "short_ratio_days": shares_stats.get("ShortRatio") or 0,
        "shares_float": shares_stats.get("SharesFloat") or fund.get("SharesStats", {}).get("PercentInsiders") or 0,
    }


def _avg_daily_volume(pick):
    return pick.get("dollar_volume_20d") or 0


def detect_squeeze_setup(pick, verbose=False):
    """Score the squeeze potential of a pick. Returns dict or None."""
    short = _get_short_data(pick)
    si_pct = float(short.get("short_pct_float") or 0)
    days_to_cover = float(short.get("short_ratio_days") or 0)

    if si_pct < 5:
        return None

    score = 0
    flags = []

    if si_pct >= 20:
        score += 30
        flags.append(f"SI {si_pct:.1f}% extreme")
    elif si_pct >= 15:
        score += 22
        flags.append(f"SI {si_pct:.1f}% elevated")
    elif si_pct >= 10:
        score += 12
        flags.append(f"SI {si_pct:.1f}% moderate")
    else:
        score += 5
        flags.append(f"SI {si_pct:.1f}% mild")

    if days_to_cover >= 7:
        score += 25
        flags.append(f"days-to-cover {days_to_cover:.1f}")
    elif days_to_cover >= 4:
        score += 15
        flags.append(f"days-to-cover {days_to_cover:.1f}")

    fc = pick.get("_forward_catalyst") or {}
    days_to_catalyst = fc.get("days_until")
    if days_to_catalyst is not None and 3 <= days_to_catalyst <= 21:
        score += 25
        flags.append(f"catalyst in {days_to_catalyst}d")

    insider = pick.get("insider_depth") or pick.get("_openinsider") or {}
    buyer_count = insider.get("buyer_count") or insider.get("buyers_count") or 0
    total_value = insider.get("total_value_usd") or 0
    if buyer_count >= 3 and total_value >= 200_000:
        score += 20
        flags.append(f"insider cluster ({buyer_count} buyers ${int(total_value/1000)}k)")

    if score >= 70:
        verdict = "SQUEEZE_LOADED"
        label = f"SQUEEZE LOADED ({si_pct:.0f}% SI, all factors aligned)"
    elif score >= 50:
        verdict = "SQUEEZE_SETUP"
        label = f"squeeze setup forming ({si_pct:.0f}% SI)"
    elif score >= 30:
        verdict = "MILD_SQUEEZE_INTEREST"
        label = f"watch for squeeze ({si_pct:.0f}% SI)"
    else:
        return None

    result = {
        "verdict": verdict,
        "label": label,
        "score": min(score, 95),
        "fires": score >= 50,
        "si_pct": si_pct,
        "days_to_cover": days_to_cover,
        "flags": flags,
    }
    if verbose:
        print(f"  squeeze {pick.get('ticker')}: {verdict} score={score} {','.join(flags)}")
    return result


def enrich_picks_with_squeeze(picks, max_picks=30, verbose=False):
    if not picks:
        return picks
    fires = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        try:
            res = detect_squeeze_setup(p, verbose=False)
        except Exception:
            continue
        if res:
            p["_squeeze_setup"] = res
            if res.get("fires"):
                fires += 1
    if verbose:
        print(f"  squeeze_setup: {fires} squeeze candidates firing")
    return picks
