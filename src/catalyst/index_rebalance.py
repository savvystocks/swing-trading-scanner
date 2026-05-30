"""Index Rebalance Calendar — Russell 2000 + S&P 500/400/600 + Nasdaq 100.

When a stock is ADDED to a major index, mechanical buying pressure from
index-tracking funds drives a predictable 3-7 day pop. The rebalance
schedule is PUBLIC and predictable:

- Russell 2000 / 3000 reconstitution: annual, late June (ranking day = end
  of April, additions/deletions published mid-May, effective ~25-27 June)
- S&P 500 / 400 / 600: quarterly committee changes, announced Friday before
  effective date (third Friday of March/June/September/December)
- Nasdaq 100: annual rebalance in late December

Edge: 3-5% abnormal returns for adds in the 5 days leading to effective
date. Deletions get sold off similarly. Academic studies (Beneish &
Whaley) confirm the effect, though it's eroded somewhat as it became
well-known.

This module:
1. Hardcoded calendar of upcoming rebalance effective dates
2. Identifies picks that are HIGH-PROBABILITY index inclusion candidates
   (based on mcap thresholds + free float + listing requirements)
3. Surfaces "RUSSELL INCLUSION CANDIDATE" or "S&P 500 CANDIDATE" badges
4. Feeds confluence as a CATALYST signal
"""

from datetime import datetime, date, timedelta


# 2026 + 2027 rebalance effective dates (third Friday of month or specific)
INDEX_REBALANCE_CALENDAR = [
    # Russell reconstitution effective date (last Friday of June)
    {"date": "2026-06-26", "index": "RUSSELL_2000", "label": "Russell 2000 / 3000 reconstitution",
     "announcement_date": "2026-05-22", "type": "annual_reconstitution"},
    {"date": "2027-06-25", "index": "RUSSELL_2000", "label": "Russell 2000 / 3000 reconstitution",
     "announcement_date": "2027-05-21", "type": "annual_reconstitution"},

    # S&P committee changes — quarterly effective Friday (third Friday Mar/Jun/Sep/Dec)
    {"date": "2026-06-19", "index": "S&P_500", "label": "S&P 500/400/600 quarterly rebalance",
     "announcement_date": "2026-06-05", "type": "quarterly"},
    {"date": "2026-09-18", "index": "S&P_500", "label": "S&P 500/400/600 quarterly rebalance",
     "announcement_date": "2026-09-04", "type": "quarterly"},
    {"date": "2026-12-18", "index": "S&P_500", "label": "S&P 500/400/600 quarterly rebalance",
     "announcement_date": "2026-12-04", "type": "quarterly"},

    # Nasdaq 100 annual rebalance (mid-December)
    {"date": "2026-12-21", "index": "NASDAQ_100", "label": "Nasdaq 100 annual rebalance",
     "announcement_date": "2026-12-11", "type": "annual"},
]

# Inclusion thresholds (approximate, current rules)
INCLUSION_THRESHOLDS = {
    "RUSSELL_2000": {"min_mcap_usd": 200_000_000, "max_mcap_usd": 6_000_000_000,
                     "min_avg_dollar_volume": 1_000_000},
    "S&P_500": {"min_mcap_usd": 15_000_000_000, "max_mcap_usd": None,
                "min_avg_dollar_volume": 5_000_000},
    "S&P_400": {"min_mcap_usd": 6_700_000_000, "max_mcap_usd": 19_500_000_000,
                "min_avg_dollar_volume": 3_000_000},
    "S&P_600": {"min_mcap_usd": 1_100_000_000, "max_mcap_usd": 7_400_000_000,
                "min_avg_dollar_volume": 1_000_000},
    "NASDAQ_100": {"min_mcap_usd": 10_000_000_000, "max_mcap_usd": None,
                   "listing": "NASDAQ"},
}


def get_upcoming_rebalance_events(days_ahead=45, today=None):
    today = today or date.today()
    cutoff = today + timedelta(days=days_ahead)
    upcoming = []
    for ev in INDEX_REBALANCE_CALENDAR:
        try:
            d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if today <= d <= cutoff:
            days_to = (d - today).days
            ev_copy = dict(ev)
            ev_copy["days_until"] = days_to
            try:
                announce = datetime.strptime(ev["announcement_date"], "%Y-%m-%d").date()
                ev_copy["days_to_announcement"] = (announce - today).days
                ev_copy["announcement_passed"] = today >= announce
            except Exception:
                ev_copy["days_to_announcement"] = None
                ev_copy["announcement_passed"] = False
            upcoming.append(ev_copy)
    upcoming.sort(key=lambda x: x["days_until"])
    return upcoming


def _picks_passes_threshold(pick, threshold):
    if not threshold:
        return False
    mcap = pick.get("market_cap")
    try:
        mcap = float(mcap) if mcap is not None else None
    except Exception:
        mcap = None
    if mcap is None:
        return False
    min_mcap = threshold.get("min_mcap_usd")
    max_mcap = threshold.get("max_mcap_usd")
    if min_mcap and mcap < min_mcap:
        return False
    if max_mcap and mcap > max_mcap:
        return False
    dollar_vol = pick.get("dollar_volume_20d") or 0
    try:
        dollar_vol = float(dollar_vol)
    except Exception:
        dollar_vol = 0
    min_dv = threshold.get("min_avg_dollar_volume", 0)
    if dollar_vol < min_dv:
        return False
    return True


def assess_pick_for_rebalance(pick, upcoming_events):
    """Returns list of {event, qualifies, label} for each upcoming rebalance."""
    matches = []
    for ev in upcoming_events:
        idx = ev["index"]
        threshold = INCLUSION_THRESHOLDS.get(idx)
        if not threshold:
            continue
        if _picks_passes_threshold(pick, threshold):
            label_short = {
                "RUSSELL_2000": "RUSSELL INCLUSION CANDIDATE",
                "S&P_500": "S&P 500 CANDIDATE",
                "S&P_400": "S&P 400 CANDIDATE",
                "S&P_600": "S&P 600 CANDIDATE",
                "NASDAQ_100": "NASDAQ 100 CANDIDATE",
            }.get(idx, f"{idx} CANDIDATE")
            matches.append({
                "event_date": ev["date"],
                "index": idx,
                "label": label_short,
                "days_until": ev["days_until"],
                "announcement_passed": ev.get("announcement_passed", False),
            })
    return matches


def enrich_picks_with_index_rebalance(picks, days_ahead=45, verbose=False):
    if not picks:
        return picks
    upcoming = get_upcoming_rebalance_events(days_ahead=days_ahead)
    if not upcoming:
        if verbose:
            print(f"  index_rebalance: no rebalance events in next {days_ahead}d")
        return picks
    if verbose:
        for ev in upcoming:
            print(f"  index_rebalance: {ev['label']} in {ev['days_until']}d ({ev['date']})")
    candidates = 0
    for p in picks:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        matches = assess_pick_for_rebalance(p, upcoming)
        if matches:
            p["_index_rebalance"] = matches
            candidates += 1
    if verbose:
        print(f"  index_rebalance: {candidates} picks pass inclusion thresholds")
    return picks
