"""Post-Earnings Announcement Drift (PEAD) scanner.

The single strongest documented retail edge in liquid US equities. A
stock that BEAT consensus AND held the gap up the day after often drifts
+3-8% over the next 30 days as Wall Street slowly revises models. The
PEAD anomaly has been replicated in academic literature since the 1960s.

This module identifies picks currently in the PEAD window:
- Earnings reported 3-25 days ago (recent enough to drift, not stale)
- Actual EPS beat consensus
- Stock price held at or above pre-earnings level (no fade)

Free data via EODHD fundamentals (we already subscribe).
"""

import os
from datetime import datetime, timedelta


def is_pead_eligible(pick, today=None):
    """Return PEAD signal dict if pick qualifies, else None."""
    today = today or datetime.utcnow().date()

    raw_fund = pick.get("_raw_fundamentals") or {}
    earnings_hist = (raw_fund.get("Earnings") or {}).get("History") if raw_fund else None
    if not earnings_hist:
        earnings_hist = pick.get("earnings_history")
    if not earnings_hist:
        return None

    if isinstance(earnings_hist, dict):
        items = list(earnings_hist.values())
    elif isinstance(earnings_hist, list):
        items = earnings_hist
    else:
        return None

    most_recent = None
    most_recent_date = None
    for item in items:
        if not isinstance(item, dict):
            continue
        report_str = item.get("reportDate") or item.get("date")
        if not report_str:
            continue
        try:
            report_date = datetime.strptime(report_str[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if report_date > today:
            continue
        if most_recent_date is None or report_date > most_recent_date:
            most_recent_date = report_date
            most_recent = item

    if most_recent is None:
        return None

    days_since = (today - most_recent_date).days
    if days_since < 3 or days_since > 25:
        return None

    try:
        actual = most_recent.get("epsActual")
        estimate = most_recent.get("epsEstimate")
        if actual is None or estimate is None:
            return None
        actual = float(actual)
        estimate = float(estimate)
    except (TypeError, ValueError):
        return None

    if estimate == 0:
        beat_pct = None
    else:
        beat_pct = (actual - estimate) / abs(estimate) * 100

    if actual <= estimate:
        return None
    if beat_pct is not None and beat_pct < 2:
        return None

    ret_5d = pick.get("ret_5d")
    ret_30d = pick.get("ret_30d")
    try:
        ret_5d_val = float(ret_5d) if ret_5d is not None else None
    except (TypeError, ValueError):
        ret_5d_val = None
    try:
        ret_30d_val = float(ret_30d) if ret_30d is not None else None
    except (TypeError, ValueError):
        ret_30d_val = None

    held_the_gap = True
    if ret_5d_val is not None and ret_5d_val < -5:
        held_the_gap = False
    if ret_30d_val is not None and ret_30d_val < -3:
        held_the_gap = False
    if not held_the_gap:
        return None

    if beat_pct is not None and beat_pct >= 15:
        strength = "STRONG_BEAT_HOLDING"
        score = 90
    elif beat_pct is not None and beat_pct >= 5:
        strength = "GOOD_BEAT_HOLDING"
        score = 75
    else:
        strength = "MILD_BEAT_HOLDING"
        score = 60

    return {
        "verdict": "PEAD_ELIGIBLE",
        "strength": strength,
        "score": score,
        "report_date": str(most_recent_date),
        "days_since_earnings": days_since,
        "actual_eps": actual,
        "estimate_eps": estimate,
        "beat_pct": round(beat_pct, 1) if beat_pct is not None else None,
        "ret_5d_post_earnings": ret_5d_val,
        "ret_30d_post_earnings": ret_30d_val,
        "drift_window_remaining_days": 30 - days_since,
    }


def apply_pead_scanner(picks, verbose=False):
    if not picks:
        return
    enriched = 0
    strong = 0
    for p in picks:
        try:
            sig = is_pead_eligible(p)
            if sig:
                p["_pead"] = sig
                enriched += 1
                if sig["strength"] == "STRONG_BEAT_HOLDING":
                    strong += 1
        except Exception:
            continue
    if verbose:
        print(f"  pead_scanner: {enriched} picks in PEAD drift window ({strong} STRONG_BEAT_HOLDING)")
