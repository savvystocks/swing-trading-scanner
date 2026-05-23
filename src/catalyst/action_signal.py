"""Aggregate all signals into a single tradeable action per pick.

Too many numbers on the dashboard creates analysis paralysis. This module
collapses Overall + PoP + LLM + Bear + Stage 2 + Speculative + Trap + Live
quote (if available) into ONE recommendation with a single-sentence why.
"""


def compute_action(pick, live_change_pct=None):
    overall_obj = pick.get("_overall_score") or {}
    overall = overall_obj.get("score") or 0
    pop = overall_obj.get("probability_of_profit_pct") or 0
    haiku = pick.get("haiku_synthesis") or {}
    llm_verdict = haiku.get("verdict") or ""
    llm_conf = haiku.get("confidence_pct") or 0
    bear = pick.get("bear_verification") or {}
    is_trap = bool(bear.get("is_this_trade_a_trap"))
    bear_conv = bear.get("bear_conviction_pct") or 0
    stage2 = pick.get("_stage2_zone") or {}
    stage2_zone = stage2.get("zone") or ""
    stage2_tradeable = stage2.get("tradeable", True)

    try:
        from src.catalyst.catalyst_quality import is_speculative_only
        speculative = is_speculative_only(pick)
    except Exception:
        speculative = False

    if speculative:
        return _wrap("AVOID", "speculative", "Only catalysts are FDA/clinical/M&A rumours — no information edge.")

    if is_trap:
        killer = (bear.get("killer_thesis") or "")[:120]
        return _wrap("AVOID", "trap", f"Bear-case flagged TRAP at {bear_conv}% — {killer}")

    if stage2_zone == "CLIMAX":
        return _wrap("AVOID", "climax", "Already parabolic +25%+ above 50dMA — distribution risk, mean reversion likely.")

    if stage2_zone == "EXTENDED":
        return _wrap("WATCH", "extended", "Already extended above 50dMA — wait for pullback to 50dMA before entry.")

    if not stage2_tradeable and stage2_zone == "NOT_IN_STAGE2":
        if live_change_pct is not None and live_change_pct >= 5:
            return _wrap("WATCH", "gap_up_from_below_ma", f"Was below 50/200dMA at scan close, but live gap +{live_change_pct:.1f}% likely cleared the MA. Confirm trend before chasing.")
        return _wrap("AVOID", "no_trend", "Below 50dMA or 200dMA at scan close - not in confirmed uptrend.")

    if live_change_pct is not None and live_change_pct <= -3:
        return _wrap("WATCH", "premarket_down", f"Down {live_change_pct:+.1f}% in pre-market - thesis has moved against you since scan ran. Wait for stabilisation.")

    if live_change_pct is not None and live_change_pct >= 7:
        return _wrap("WATCH", "gap_up_chase", f"Gapped up {live_change_pct:+.1f}% live - catalyst already played out, chasing the move is high-risk. Wait for pullback.")

    oi = pick.get("_openinsider") or {}
    insider_value = oi.get("total_value_usd", 0) or 0
    insider_count = oi.get("buyers_count", 0) or 0
    ceo_cfo = bool(oi.get("ceo_or_cfo_bought"))
    insider_recency = oi.get("recency_days")
    has_strong_insider = (insider_count >= 3 and insider_value >= 200_000) or (ceo_cfo and insider_value >= 100_000)

    if llm_verdict in ("STRONG_BUY",) and overall >= 65 and not is_trap:
        return _wrap("TAKE", "strong_buy", f"LLM strong BUY at {llm_conf}% + Overall {overall:.0f} + bear cleared. High-confidence setup.")

    if llm_verdict == "BUY" and llm_conf >= 55 and overall >= 65 and bear_conv < 60:
        return _wrap("TAKE", "buy_confirmed", f"LLM BUY at {llm_conf}% + Overall {overall:.0f} + bear NEUTRAL. Clear edge.")

    if has_strong_insider and overall >= 60 and not is_trap:
        ceo_note = " (CEO/CFO buying)" if ceo_cfo else ""
        rec_note = f" {insider_recency}d ago" if insider_recency is not None else ""
        return _wrap("TAKE", "insider_cluster", f"Strong insider cluster: {insider_count} buyers, ${insider_value/1000:.0f}k total{ceo_note}{rec_note} + Overall {overall:.0f}. Smart money confirming.")

    if llm_verdict == "BUY" and overall >= 60:
        return _wrap("WATCH", "weak_buy", f"LLM weakly bullish ({llm_conf}% BUY) — wait for confirming volume or news.")

    if llm_verdict in ("SKIP", "STRONG_SELL") and llm_conf >= 60:
        return _wrap("SKIP", "llm_skip_strong", f"LLM {llm_verdict} at {llm_conf}% — multiple bear factors. Don't trade.")

    if llm_verdict in ("SKIP", "STRONG_SELL") and llm_conf < 40 and overall >= 65 and pop >= 60:
        return _wrap("WATCH", "soft_skip_good_data", f"LLM weakly bearish ({llm_conf}% SKIP) but other signals strong (Overall {overall:.0f}, PoP {pop:.0f}%). Borderline.")

    if overall >= 70 and pop >= 65:
        return _wrap("TAKE", "data_strong", f"Strong evidence stack (Overall {overall:.0f}, PoP {pop:.0f}%) even with cautious LLM.")

    if overall >= 60 and pop >= 55:
        return _wrap("WATCH", "borderline", f"Borderline (Overall {overall:.0f}, PoP {pop:.0f}%) — not a clear edge.")

    return _wrap("SKIP", "weak", f"Weak across the board (Overall {overall:.0f}, PoP {pop:.0f}%).")


def _wrap(action, reason_code, why):
    badge = {
        "TAKE": "🟢 TAKE",
        "WATCH": "🟡 WATCH",
        "SKIP": "⚪ SKIP",
        "AVOID": "🔴 AVOID",
    }.get(action, "⚪")
    return {
        "action": action,
        "badge": badge,
        "reason_code": reason_code,
        "why": why,
    }


def apply_action_signals(picks, verbose=False):
    if not picks:
        return
    counts = {"TAKE": 0, "WATCH": 0, "SKIP": 0, "AVOID": 0}
    for p in picks:
        try:
            sig = compute_action(p)
            p["_action_signal"] = sig
            counts[sig["action"]] = counts.get(sig["action"], 0) + 1
        except Exception:
            continue
    if verbose:
        print(f"  action_signal: TAKE={counts['TAKE']} WATCH={counts['WATCH']} SKIP={counts['SKIP']} AVOID={counts['AVOID']}")
