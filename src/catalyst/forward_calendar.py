from datetime import datetime, timedelta

from src.catalyst.calendar import upcoming_earnings


FOMC_DATES_2026 = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
]

CPI_DATES_2026 = [
    "2026-01-14", "2026-02-11", "2026-03-12", "2026-04-10",
    "2026-05-13", "2026-06-11", "2026-07-15", "2026-08-12",
    "2026-09-11", "2026-10-15", "2026-11-13", "2026-12-10",
]

JOBS_DATES_2026 = [
    "2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03",
    "2026-05-01", "2026-06-05", "2026-07-02", "2026-08-07",
    "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04",
]


def _within_window(date_str, today, days_ahead=7):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None
    diff = (d - today).days
    if 0 <= diff <= days_ahead:
        return diff
    return None


def get_macro_events_this_week(today=None, days_ahead=7):
    if today is None:
        today = datetime.utcnow().date()
    out = []
    for d in FOMC_DATES_2026:
        days = _within_window(d, today, days_ahead)
        if days is not None:
            out.append({"label": "FOMC decision", "date": d, "days_until": days, "type": "macro"})
    for d in CPI_DATES_2026:
        days = _within_window(d, today, days_ahead)
        if days is not None:
            out.append({"label": "CPI release", "date": d, "days_until": days, "type": "macro"})
    for d in JOBS_DATES_2026:
        days = _within_window(d, today, days_ahead)
        if days is not None:
            out.append({"label": "Non-farm payrolls", "date": d, "days_until": days, "type": "macro"})
    out.sort(key=lambda x: x["days_until"])
    return out


def get_earnings_this_week(client, watchlist_tickers=None, days_ahead=5, target_date=None):
    earnings = upcoming_earnings(client, days_ahead=days_ahead, target_date=target_date)
    watchlist_set = set((watchlist_tickers or []))
    watchlist_set_us = {t.replace(".US", "") for t in watchlist_set}
    on_watchlist = []
    other_count = 0
    for e in earnings:
        bare = e["ticker"].replace(".US", "").replace(".LSE", "")
        if bare in watchlist_set_us:
            on_watchlist.append({
                "ticker": bare,
                "report_date": e["report_date"],
                "before_after_market": e.get("before_after_market") or "",
                "days_until": e.get("days_until"),
            })
        else:
            other_count += 1
    return {
        "total_earnings": len(earnings),
        "on_watchlist_count": len(on_watchlist),
        "on_watchlist": on_watchlist[:15],
        "other_count": other_count,
    }


def build_forward_calendar(client, watchlist_tickers=None, days_ahead=5, target_date=None):
    today = datetime.utcnow().date()
    if target_date:
        if isinstance(target_date, str):
            try:
                today = datetime.strptime(target_date, "%Y-%m-%d").date()
            except Exception:
                pass
        else:
            today = target_date
    earnings_summary = get_earnings_this_week(client, watchlist_tickers, days_ahead, target_date)
    macro_events = get_macro_events_this_week(today, days_ahead)
    return {
        "earnings": earnings_summary,
        "macro_events": macro_events,
        "scan_date": today.strftime("%Y-%m-%d"),
        "days_ahead": days_ahead,
    }
