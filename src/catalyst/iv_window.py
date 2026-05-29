"""Module 3: IV-cheap pre-earnings window.

The cleanest documented options edge for retail: buy calls when IV is in the
bottom of its range BEFORE the catalyst pumps it up. Sell into the IV
expansion in the 5-14 days leading up to the event.

Three checks combined:
1. Earnings 14-21 days out (catalyst is close enough to pump IV soon)
2. IV percentile in bottom 30% of last 6 months
3. Implied move (from straddle pricing) is reasonable vs historical earnings move

Picks meeting 2/3 get an "IV CHEAP" tag and structure recommendation:
- LOW IV rank (<30) -> buy long calls/puts (pay for vol expansion)
- HIGH IV rank (>70) -> sell credit spreads / strangles (collect premium)

Works without Barchart (uses Alpaca chain data we already pull). Better
accuracy when Barchart Premier subscription provides true IV rank.
"""

from datetime import datetime, timedelta


def _compute_iv_percentile_from_chain_history(ticker, current_iv, days_back=126):
    """Approximate IV percentile from recent chain snapshots.

    Without Barchart Premier or paid IV history, this is a rough proxy
    based on the current IV alone (no history to compare). When Barchart
    is wired in (env BARCHART_API_KEY), use the real rank instead.
    Returns None if we can't compute.
    """
    try:
        from src.catalyst.barchart_premier import get_iv_rank
        rank = get_iv_rank(ticker)
        if rank and rank.get("iv_rank_pct") is not None:
            return float(rank["iv_rank_pct"])
    except Exception:
        pass

    if current_iv is None:
        return None

    try:
        iv_f = float(current_iv)
    except (TypeError, ValueError):
        return None

    if iv_f <= 20:
        return 15
    if iv_f <= 35:
        return 30
    if iv_f <= 50:
        return 50
    if iv_f <= 70:
        return 70
    if iv_f <= 90:
        return 85
    return 95


def check_earnings_window(pick):
    fc = pick.get("_forward_catalyst") or {}
    if fc.get("type") != "earnings":
        return {"pass": None, "verdict": "NO_EARNINGS", "detail": "no upcoming earnings catalyst"}
    days = fc.get("days_until")
    if days is None:
        return {"pass": None, "verdict": "NO_DATE", "detail": "earnings date unknown"}
    if 7 <= days <= 21:
        return {"pass": True, "verdict": "IN_WINDOW", "detail": f"earnings {days}d away - in the IV-expansion sweet spot", "days": days}
    if 4 <= days <= 6:
        return {"pass": None, "verdict": "LATE", "detail": f"earnings {days}d away - IV may already be pumped, check premium", "days": days}
    if days < 4:
        return {"pass": False, "verdict": "IV_CRUSH_RISK", "detail": f"earnings {days}d away - too late to buy vol, IV crush imminent", "days": days}
    return {"pass": None, "verdict": "TOO_EARLY", "detail": f"earnings {days}d away - too far for IV to pump yet", "days": days}


def check_iv_cheap(pick):
    live_option = pick.get("_live_option") or {}
    current_iv = live_option.get("iv_pct") or pick.get("iv_percentile_analysis", {}).get("iv_percentile") if isinstance(pick.get("iv_percentile_analysis"), dict) else None
    if current_iv is None:
        ivp = pick.get("iv_percentile_analysis") or {}
        current_iv = ivp.get("iv_percentile")
    ticker = pick.get("ticker")
    rank = _compute_iv_percentile_from_chain_history(ticker, current_iv)
    if rank is None:
        return {"pass": None, "verdict": "UNKNOWN", "detail": "no IV data available"}
    if rank <= 30:
        return {"pass": True, "verdict": "IV_CHEAP", "detail": f"IV rank {rank:.0f} (bottom 30%) - vol underpriced, calls cheap", "iv_rank": rank, "structure": "LONG_CALLS"}
    if rank >= 70:
        return {"pass": False, "verdict": "IV_EXPENSIVE", "detail": f"IV rank {rank:.0f} (top 30%) - vol overpriced, prefer credit spreads", "iv_rank": rank, "structure": "CREDIT_SPREADS"}
    return {"pass": None, "verdict": "IV_NEUTRAL", "detail": f"IV rank {rank:.0f} (middle) - no clear vol edge", "iv_rank": rank, "structure": "LONG_CALLS_OK"}


def check_implied_vs_historical_move(pick):
    """Compare straddle-implied earnings move vs historical avg.

    If implied < historical -> market under-pricing the surprise (buy calls)
    If implied > historical -> market expecting too much (sell premium)
    """
    live_option = pick.get("_live_option") or {}
    iv = live_option.get("iv_pct")
    if iv is None:
        return {"pass": None, "verdict": "UNKNOWN", "detail": "no IV available"}
    fc = pick.get("_forward_catalyst") or {}
    days = fc.get("days_until")
    if not days or days < 1:
        return {"pass": None, "verdict": "NO_DATE", "detail": "no earnings date"}
    try:
        iv_f = float(iv)
        implied_move_pct = iv_f * (days / 365) ** 0.5
    except Exception:
        return {"pass": None, "verdict": "PARSE_ERROR", "detail": "iv parse failed"}

    historical_avg = pick.get("_historical_earnings_move_avg_pct")
    if historical_avg is None:
        if 4 <= implied_move_pct <= 8:
            return {"pass": True, "verdict": "REASONABLE", "detail": f"implied move {implied_move_pct:.1f}% - in normal range, calls fairly priced", "implied_move_pct": round(implied_move_pct, 2)}
        if implied_move_pct < 4:
            return {"pass": True, "verdict": "UNDER_PRICING", "detail": f"implied move only {implied_move_pct:.1f}% - market may be under-pricing surprise", "implied_move_pct": round(implied_move_pct, 2)}
        return {"pass": False, "verdict": "OVER_PRICING", "detail": f"implied move {implied_move_pct:.1f}% - market pricing big surprise, premium expensive", "implied_move_pct": round(implied_move_pct, 2)}

    try:
        hist_f = float(historical_avg)
    except Exception:
        hist_f = None
    if hist_f is None:
        return {"pass": None, "verdict": "UNKNOWN", "detail": "historical move parse failed"}

    ratio = implied_move_pct / hist_f if hist_f > 0 else 1.0
    if ratio < 0.85:
        return {"pass": True, "verdict": "MARKET_UNDER_PRICING", "detail": f"implied {implied_move_pct:.1f}% < historical avg {hist_f:.1f}% - edge to buying calls", "implied_move_pct": round(implied_move_pct, 2), "historical_pct": round(hist_f, 2)}
    if ratio > 1.3:
        return {"pass": False, "verdict": "MARKET_OVER_PRICING", "detail": f"implied {implied_move_pct:.1f}% > historical {hist_f:.1f}% - sell premium instead", "implied_move_pct": round(implied_move_pct, 2), "historical_pct": round(hist_f, 2)}
    return {"pass": None, "verdict": "FAIR", "detail": f"implied {implied_move_pct:.1f}% ≈ historical {hist_f:.1f}% - fairly priced", "implied_move_pct": round(implied_move_pct, 2), "historical_pct": round(hist_f, 2)}


def analyze_iv_window(pick, verbose=False):
    """Run all 3 IV-window checks. Returns dict with overall verdict + structure recommendation."""
    earnings_check = check_earnings_window(pick)
    iv_check = check_iv_cheap(pick)
    move_check = check_implied_vs_historical_move(pick)

    pass_count = sum(1 for c in [earnings_check, iv_check, move_check] if c.get("pass") is True)
    fail_count = sum(1 for c in [earnings_check, iv_check, move_check] if c.get("pass") is False)

    if pass_count >= 2 and earnings_check.get("pass") is True:
        verdict = "IV_CHEAP_WINDOW"
        badge = "IV CHEAP — BUY CALLS"
        score = 85
        structure = iv_check.get("structure", "LONG_CALLS")
    elif fail_count >= 2:
        verdict = "IV_TRAP"
        badge = "IV EXPENSIVE — SELL PREMIUM"
        score = 35
        structure = iv_check.get("structure", "CREDIT_SPREADS")
    elif pass_count >= 1:
        verdict = "MIXED"
        badge = None
        score = 55
        structure = iv_check.get("structure", "LONG_CALLS_OK")
    else:
        verdict = "NO_SIGNAL"
        badge = None
        score = 50
        structure = None

    result = {
        "verdict": verdict,
        "badge_label": badge,
        "iv_window_score": score,
        "structure_recommendation": structure,
        "pass_count": pass_count,
        "factors": {
            "earnings_window": earnings_check,
            "iv_cheap": iv_check,
            "implied_vs_historical": move_check,
        },
    }
    if verbose:
        print(f"  iv_window {pick.get('ticker')}: {verdict} ({pass_count}p/{fail_count}f) score={score} struct={structure}")
        for fk, fv in result["factors"].items():
            symbol = "+" if fv.get("pass") is True else ("-" if fv.get("pass") is False else "?")
            print(f"    [{symbol}] {fk}: {fv.get('detail')}")
    return result


def enrich_picks_with_iv_window(picks, max_picks=30, verbose=False):
    if not picks:
        return picks
    enriched = 0
    cheap_count = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        try:
            res = analyze_iv_window(p, verbose=False)
        except Exception:
            continue
        p["_iv_window"] = res
        enriched += 1
        if res["verdict"] == "IV_CHEAP_WINDOW":
            cheap_count += 1
    if verbose:
        print(f"  iv_window: enriched {enriched}/{min(max_picks, len(picks))} picks, {cheap_count} in IV-cheap pre-earnings window")
    return picks
