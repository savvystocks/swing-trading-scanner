"""Higher-Frequency Forward Data + Analyst Revision Flow.

Sector-specific forward data feeds:
  - TSMC monthly revenue (leads semis cycle)
  - Tesla quarterly delivery reports (leads auto/EV)
  - EIA weekly inventories (energy)
  - DoD daily contract awards (defense)

Analyst revision flow:
  - 3-month forward EPS revision trend
  - Price target velocity
  - Analyst rating changes

Mostly from EODHD analyst data + public scrapes.
"""

from datetime import datetime, timedelta


SEMI_LEADERS = {"TSM": "TSMC", "FOXCONN": "Foxconn"}
AUTO_DELIVERY_DATES = {
    "TSLA": ["2026-07-02", "2026-10-02", "2027-01-02"],
    "GM": ["2026-07-01", "2026-10-01"],
    "F": ["2026-07-03", "2026-10-03"],
}

DEFENSE_TICKERS = ("LMT", "RTX", "NOC", "GD", "HII", "BA", "LDOS", "BAH", "KTOS", "AVAV")


def get_upcoming_auto_deliveries(days_ahead=30):
    today = datetime.utcnow().date()
    cutoff = today + timedelta(days=days_ahead)
    out = []
    for ticker, dates in AUTO_DELIVERY_DATES.items():
        for d_str in dates:
            try:
                d = datetime.strptime(d_str, "%Y-%m-%d").date()
            except Exception:
                continue
            if today <= d <= cutoff:
                out.append({"ticker": ticker, "event": "quarterly_delivery", "date": d_str, "days_until": (d - today).days})
    out.sort(key=lambda x: x["days_until"])
    return out


def get_analyst_revision_flow(ticker, fundamentals=None):
    """Get 3-month forward EPS revision trend from EODHD."""
    try:
        if fundamentals is None:
            from src.eodhd import EODHDClient
            client = EODHDClient()
            fundamentals = client.fundamentals(f"{ticker}.US" if "." not in ticker else ticker)
    except Exception:
        return None
    if not fundamentals:
        return None
    earnings = fundamentals.get("Earnings") or {}
    trend = earnings.get("Trend") or {}
    if not trend:
        return None
    sorted_keys = sorted(trend.keys(), reverse=True)
    recent_periods = sorted_keys[:4]

    revisions_up = 0
    revisions_down = 0
    for period in recent_periods:
        data = trend[period] or {}
        try:
            up = int(data.get("epsTrendUp7daysAgo") or data.get("epsTrendUp30daysAgo") or 0)
            down = int(data.get("epsTrendDown7daysAgo") or data.get("epsTrendDown30daysAgo") or 0)
        except (TypeError, ValueError):
            continue
        revisions_up += up
        revisions_down += down

    if revisions_up == 0 and revisions_down == 0:
        return None
    net_revisions = revisions_up - revisions_down
    if net_revisions >= 3:
        verdict = "POSITIVE_REVISIONS"
        label = f"{revisions_up} up vs {revisions_down} down forward EPS revisions"
        score = 75
    elif net_revisions <= -3:
        verdict = "NEGATIVE_REVISIONS"
        label = f"{revisions_down} down vs {revisions_up} up forward EPS revisions"
        score = 25
    else:
        verdict = "MIXED_REVISIONS"
        label = f"{revisions_up}/{revisions_down} mixed revisions"
        score = 50
    return {
        "verdict": verdict,
        "revisions_up": revisions_up,
        "revisions_down": revisions_down,
        "net_revisions": net_revisions,
        "label": label,
        "score": score,
    }


def enrich_picks_with_forward_data(picks, max_picks=20, verbose=False):
    if not picks:
        return picks
    upcoming_auto = get_upcoming_auto_deliveries(days_ahead=30)
    analyst_revisions_count = 0
    auto_tagged = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        for ev in upcoming_auto:
            if ev["ticker"] == ticker:
                fc = p.get("_forward_catalyst") or {}
                if not fc.get("type"):
                    p["_forward_catalyst"] = {
                        "type": "delivery_report", "days_until": ev["days_until"],
                        "date": ev["date"], "details": "Quarterly delivery report",
                        "window_score": 80 if 5 <= ev["days_until"] <= 21 else 60,
                    }
                auto_tagged += 1
                break
        try:
            # Use already-fetched fundamentals from Step 2 enrichment (correct field is _raw_fundamentals)
            pre_fetched = p.get("_raw_fundamentals") or p.get("_fundamentals")
            ar = get_analyst_revision_flow(ticker, fundamentals=pre_fetched)
        except Exception:
            ar = None
        if ar:
            p["_analyst_revisions"] = ar
            analyst_revisions_count += 1
    if verbose:
        print(f"  forward_data: {auto_tagged} auto delivery tagged, {analyst_revisions_count} analyst revisions")
    return picks
