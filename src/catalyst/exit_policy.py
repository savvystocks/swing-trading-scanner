ARM_PCT = 25.0
TRAIL_FRAC = 0.40
HARD_STOP_PCT = -50.0


def simulate(entry_mid, days, arm_pct=ARM_PCT, trail_frac=TRAIL_FRAC, hard_stop_pct=HARD_STOP_PCT):
    if not entry_mid or not days:
        return None

    def pct(p):
        return (p - entry_mid) / entry_mid * 100.0

    window_peak = pct(days[0]["high"])
    window_peak_date = days[0]["date"]
    window_trough = pct(days[0]["low"])
    for d in days:
        hp, lp = pct(d["high"]), pct(d["low"])
        if hp > window_peak:
            window_peak, window_peak_date = hp, d["date"]
        if lp < window_trough:
            window_trough = lp
    window_end = pct(days[-1]["close"])

    armed = False
    peak = None
    exit_reason = None
    realized = None
    exit_date = None
    for d in days:
        hp, lp, op = pct(d["high"]), pct(d["low"]), pct(d["open"])
        if not armed:
            if lp <= hard_stop_pct:
                exit_reason, realized, exit_date = "HARD_STOP", min(hard_stop_pct, op), d["date"]
                break
            if hp >= arm_pct:
                armed, peak = True, hp
            continue
        thr = peak * (1 - trail_frac)
        if lp <= thr:
            exit_reason, realized, exit_date = "ARM_TRAIL", min(thr, op), d["date"]
            break
        if hp > peak:
            peak = hp

    exited = exit_reason is not None
    return {
        "exited": exited,
        "exit_reason": exit_reason,
        "realized_pct": round(realized, 1) if realized is not None else None,
        "exit_date": exit_date,
        "armed": armed or exit_reason == "ARM_TRAIL",
        "peak_pct": round(window_peak, 1),
        "peak_date": window_peak_date,
        "trough_pct": round(window_trough, 1),
        "end_pct": round(window_end, 1),
        "end_date": days[-1]["date"],
    }
