from datetime import datetime, timedelta


ALLOWED_EXCHANGES = (".US", ".LSE")


def upcoming_earnings(client, days_ahead=2, target_date=None):
    today = datetime.utcnow().date()
    if isinstance(target_date, str):
        today = datetime.strptime(target_date, "%Y-%m-%d").date()
    elif target_date:
        today = target_date
    end = today + timedelta(days=days_ahead)
    data = client.earnings_calendar(today.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    if not data:
        return []
    earnings = data.get("earnings") or []
    out = []
    for e in earnings:
        report_date = e.get("report_date") or e.get("date")
        if not report_date:
            continue
        try:
            rd = datetime.strptime(report_date, "%Y-%m-%d").date()
        except Exception:
            continue
        days_until = (rd - today).days
        if days_until < 0 or days_until > days_ahead:
            continue
        ticker = e.get("code") or e.get("symbol")
        if not ticker:
            continue
        if not ticker.endswith(ALLOWED_EXCHANGES):
            continue
        out.append({
            "ticker": ticker,
            "report_date": report_date,
            "before_after_market": e.get("before_after_market") or "",
            "estimate_eps": e.get("estimate") or e.get("estimate_eps"),
            "actual_eps": e.get("actual") or e.get("actual_eps"),
            "days_until": days_until,
        })
    return out


def earnings_signals_for_tomorrow(client, target_date=None):
    today = datetime.utcnow().date()
    if isinstance(target_date, str):
        today = datetime.strptime(target_date, "%Y-%m-%d").date()
    elif target_date:
        today = target_date
    tomorrow = today + timedelta(days=1)
    out = {}
    earnings = upcoming_earnings(client, days_ahead=2, target_date=today)
    for e in earnings:
        rd = datetime.strptime(e["report_date"], "%Y-%m-%d").date()
        if rd != tomorrow:
            continue
        bam = (e.get("before_after_market") or "").lower()
        if "after" in bam:
            label = "earnings_amc_today"
            if rd != today:
                continue
        else:
            label = "earnings_bmo_tomorrow"
        ticker = e["ticker"]
        out[ticker] = {
            "ticker": ticker,
            "label": label,
            "report_date": e["report_date"],
            "before_after_market": e.get("before_after_market"),
            "estimate_eps": e.get("estimate_eps"),
        }
    today_earnings = [e for e in earnings if datetime.strptime(e["report_date"], "%Y-%m-%d").date() == today]
    for e in today_earnings:
        bam = (e.get("before_after_market") or "").lower()
        if "after" in bam:
            ticker = e["ticker"]
            out[ticker] = {
                "ticker": ticker,
                "label": "earnings_amc_today",
                "report_date": e["report_date"],
                "before_after_market": e.get("before_after_market"),
                "estimate_eps": e.get("estimate_eps"),
            }
    return out
