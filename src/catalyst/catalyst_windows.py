import os
import json
from datetime import datetime, timedelta


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COHORTS_PATH = os.path.join(PROJECT_ROOT, "data", "catalyst", "cohorts.json")


def _load_cohorts():
    try:
        with open(COHORTS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _cohort_membership(ticker):
    cohorts = _load_cohorts()
    in_cohorts = []
    for name, c in cohorts.items():
        tickers = c.get("tickers") or []
        if ticker in tickers:
            in_cohorts.append(name)
    return in_cohorts


def detect_earnings_spillover(candidate, all_candidates, days_ahead=3):
    ticker = candidate.get("ticker")
    if not ticker:
        return None
    candidate_cohorts = set(_cohort_membership(ticker))
    if not candidate_cohorts:
        return None
    today = datetime.utcnow().date()
    cutoff = today + timedelta(days=days_ahead)

    spillover_sources = []
    for other in all_candidates or []:
        ot = other.get("ticker")
        if not ot or ot == ticker:
            continue
        other_cohorts = set(_cohort_membership(ot))
        shared = candidate_cohorts & other_cohorts
        if not shared:
            continue
        earnings_date = other.get("next_earnings_date") or other.get("earnings_date")
        if not earnings_date:
            continue
        try:
            edate = datetime.strptime(earnings_date[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        if today <= edate <= cutoff:
            spillover_sources.append({
                "peer_ticker": ot,
                "peer_earnings_date": earnings_date,
                "shared_cohort": list(shared)[0],
                "days_until": (edate - today).days,
            })

    if not spillover_sources:
        return None
    return {
        "key": "earnings_spillover",
        "tier": "B",
        "label": f"earnings spillover from {spillover_sources[0]['peer_ticker']} in {spillover_sources[0]['days_until']}d",
        "sources": spillover_sources[:3],
    }


def detect_sympathy_continuation(candidate, all_candidates, gap_threshold_pct=10.0):
    ticker = candidate.get("ticker")
    if not ticker:
        return None
    candidate_cohorts = set(_cohort_membership(ticker))
    if not candidate_cohorts:
        return None

    sympathy_sources = []
    for other in all_candidates or []:
        ot = other.get("ticker")
        if not ot or ot == ticker:
            continue
        other_cohorts = set(_cohort_membership(ot))
        shared = candidate_cohorts & other_cohorts
        if not shared:
            continue
        today_move = other.get("today_pct_change") or other.get("intraday_pct") or 0
        try:
            today_move = float(today_move)
        except (TypeError, ValueError):
            today_move = 0
        if today_move >= gap_threshold_pct:
            sympathy_sources.append({
                "peer_ticker": ot,
                "peer_move_pct": round(today_move, 1),
                "shared_cohort": list(shared)[0],
            })

    if not sympathy_sources:
        return None
    sympathy_sources.sort(key=lambda s: s["peer_move_pct"], reverse=True)
    return {
        "key": "sympathy_continuation",
        "tier": "B",
        "label": f"sympathy to {sympathy_sources[0]['peer_ticker']} +{sympathy_sources[0]['peer_move_pct']}% today",
        "sources": sympathy_sources[:3],
    }


def detect_earnings_lead_up(candidate, earnings_lookup):
    if not earnings_lookup:
        return None
    ticker = candidate.get("ticker")
    if not ticker:
        return None
    info = earnings_lookup.get(ticker)
    if not info:
        return None
    days_until = info.get("days_until")
    if days_until is None:
        return None
    if 10 <= days_until <= 15:
        return {
            "key": "earnings_lead_up_10_15d",
            "tier": "B",
            "label": f"earnings in {days_until}d (institutional positioning window)",
            "report_date": info.get("report_date"),
            "days_until": days_until,
        }
    if 5 <= days_until <= 9:
        return {
            "key": "earnings_imminent_5_9d",
            "tier": "B",
            "label": f"earnings in {days_until}d (IV expansion zone)",
            "report_date": info.get("report_date"),
            "days_until": days_until,
        }
    if 3 <= days_until <= 4:
        return {
            "key": "earnings_peak_iv_3_4d",
            "tier": "C",
            "label": f"earnings in {days_until}d (peak IV, late entry)",
            "report_date": info.get("report_date"),
            "days_until": days_until,
        }
    return None


def detect_insider_window(candidate, days_back=14):
    ticker = candidate.get("ticker")
    if not ticker:
        return None
    insider_data = candidate.get("insider_transactions") or candidate.get("insider_depth") or {}
    recent_buys = insider_data.get("recent_buys") or []
    if not recent_buys:
        ttb = insider_data.get("total_buy_value_usd") or insider_data.get("total_value_usd") or 0
        buyer_count = insider_data.get("buyer_count") or 0
        if ttb >= 50_000 and buyer_count >= 1:
            return {
                "key": "insider_window",
                "tier": "C",
                "label": f"recent insider buying (${ttb/1000:.0f}k by {buyer_count})",
                "value_usd": ttb,
            }
        return None

    today = datetime.utcnow().date()
    cutoff = today - timedelta(days=days_back)
    in_window = []
    total_value = 0
    for tx in recent_buys:
        try:
            d = datetime.strptime((tx.get("date") or "")[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        if d < cutoff:
            continue
        try:
            val = float(tx.get("value") or tx.get("total_value") or 0)
        except (TypeError, ValueError):
            val = 0
        in_window.append({"date": d.isoformat(), "value": val, "name": tx.get("name")})
        total_value += val

    if not in_window:
        return None
    if total_value < 25_000:
        return None
    return {
        "key": "insider_window",
        "tier": "B" if total_value >= 250_000 else "C",
        "label": f"insider buys (${total_value/1000:.0f}k in last {days_back}d, {len(in_window)} txns)",
        "value_usd": total_value,
        "txn_count": len(in_window),
    }


def apply_catalyst_windows(candidates, verbose=False, earnings_lookup=None):
    if not candidates:
        return
    added_spillover = 0
    added_sympathy = 0
    added_insider_window = 0
    added_lead_up = 0
    added_imminent = 0
    added_peak_iv = 0

    for c in candidates:
        existing_cats = c.get("catalysts") or []
        existing_keys = {cat.get("key") for cat in existing_cats if isinstance(cat, dict)}

        spillover = detect_earnings_spillover(c, candidates)
        if spillover and spillover["key"] not in existing_keys:
            existing_cats.append(spillover)
            added_spillover += 1

        sympathy = detect_sympathy_continuation(c, candidates)
        if sympathy and sympathy["key"] not in existing_keys:
            existing_cats.append(sympathy)
            added_sympathy += 1

        insider = detect_insider_window(c)
        if insider and insider["key"] not in existing_keys:
            existing_cats.append(insider)
            added_insider_window += 1

        if earnings_lookup:
            lead_up = detect_earnings_lead_up(c, earnings_lookup)
            if lead_up and lead_up["key"] not in existing_keys:
                existing_cats.append(lead_up)
                if lead_up["key"] == "earnings_lead_up_10_15d":
                    added_lead_up += 1
                elif lead_up["key"] == "earnings_imminent_5_9d":
                    added_imminent += 1
                else:
                    added_peak_iv += 1

        c["catalysts"] = existing_cats

    if verbose:
        print(f"  catalyst windows: +{added_spillover} earnings_spillover, +{added_sympathy} sympathy_continuation, +{added_insider_window} insider_window, +{added_lead_up} earnings_lead_up_10_15d, +{added_imminent} earnings_imminent_5_9d, +{added_peak_iv} earnings_peak_iv_3_4d")
