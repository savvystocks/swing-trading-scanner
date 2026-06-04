from src.catalyst.exit_policy import ARM_PCT, TRAIL_FRAC, HARD_STOP_PCT


def evaluate(pos, mid, prev):
    entry = pos.get("entry_price")
    if not entry or entry <= 0 or not mid or mid <= 0:
        return None, (prev or {})

    pct = (mid - entry) / entry * 100.0
    prev = prev or {}
    armed = prev.get("armed", False)
    peak = prev.get("peak")
    signaled = prev.get("exit_signaled", False)

    tag = f"{pos.get('ticker', '?')} {pos.get('side', '?')} ${pos.get('strike')}"
    state = {
        "armed": armed,
        "peak": peak,
        "exit_signaled": signaled,
        "last_pct": round(pct, 1),
        "last_mid": round(mid, 2),
    }

    if signaled:
        if armed and (peak is None or pct > peak):
            state["peak"] = round(pct, 1)
        return None, state

    if not armed:
        if pct <= HARD_STOP_PCT:
            state["exit_signaled"] = True
            return (f"<b>SELL - {tag}</b>\n"
                    f"Hard stop hit: {pct:+.0f}% (entry ${entry:.2f} -> mid ${mid:.2f})\n"
                    f"System rule: cut at {HARD_STOP_PCT:.0f}%."), state
        if pct >= ARM_PCT:
            state["armed"] = True
            state["peak"] = round(pct, 1)
            trail_now = pct * (1 - TRAIL_FRAC)
            return (f"<b>{tag} armed at {pct:+.0f}%</b>\n"
                    f"Trailing stop now live - exit if it falls back to {trail_now:+.0f}%.\n"
                    f"The floor rises as it climbs. Hard stop lifted."), state
        return None, state

    peak = pct if peak is None else max(peak, pct)
    state["peak"] = round(peak, 1)
    thr = peak * (1 - TRAIL_FRAC)
    if pct <= thr:
        state["exit_signaled"] = True
        return (f"<b>SELL - {tag}</b>\n"
                f"Trail tripped: {pct:+.0f}% now, peaked {peak:+.0f}% "
                f"(entry ${entry:.2f} -> mid ${mid:.2f})\n"
                f"System rule: exit at {int((1 - TRAIL_FRAC) * 100)}% of peak."), state
    return None, state
