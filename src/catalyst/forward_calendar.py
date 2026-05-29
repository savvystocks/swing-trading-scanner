from datetime import datetime, timedelta

from src.catalyst.calendar import upcoming_earnings


# === Module 1: Per-ticker forward catalyst lookup ===

def get_next_earnings_date(ticker, fundamentals=None):
    """Return next earnings date (datetime.date) for a ticker, or None."""
    try:
        if fundamentals is None:
            from src.eodhd import EODHDClient
            client = EODHDClient()
            fundamentals = client.fundamentals(f"{ticker}.US" if "." not in ticker else ticker)
    except Exception:
        return None
    if not fundamentals:
        return None
    history = ((fundamentals.get("Earnings") or {}).get("History")) or {}
    today = datetime.utcnow().date()
    soonest = None
    for _k, v in history.items():
        rd = v.get("reportDate")
        if not rd:
            continue
        try:
            d = datetime.strptime(rd, "%Y-%m-%d").date()
        except Exception:
            continue
        if d > today and (soonest is None or d < soonest):
            soonest = d
    return soonest


_FDA_CACHE = {"data": None, "fetched_at": None}


def _fetch_fda_pdufa_calendar():
    """Scrape biopharmcatalyst.com PDUFA calendar (free, no auth).

    Returns list of {ticker, date, drug, indication}. Cached 6 hours."""
    if _FDA_CACHE["fetched_at"]:
        age = (datetime.utcnow() - _FDA_CACHE["fetched_at"]).total_seconds()
        if age < 21600:
            return _FDA_CACHE["data"] or []
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SwingScanner/1.0)"}
        r = requests.get("https://www.biopharmcatalyst.com/calendars/fda-calendar", headers=headers, timeout=15)
        if r.status_code != 200:
            return _FDA_CACHE["data"] or []
        soup = BeautifulSoup(r.text, "html.parser")
        rows = []
        for tr in soup.select("table.events-table tr, table tbody tr"):
            cells = [c.get_text(strip=True) for c in tr.select("td")]
            if len(cells) < 3:
                continue
            ticker_match = None
            for c in cells:
                if c.isupper() and 2 <= len(c) <= 5 and c.isalpha():
                    ticker_match = c
                    break
            date_str = None
            for c in cells:
                try:
                    d = datetime.strptime(c, "%m/%d/%Y").date()
                    date_str = d.isoformat()
                    break
                except Exception:
                    continue
            if ticker_match and date_str:
                rows.append({
                    "ticker": ticker_match,
                    "date": date_str,
                    "details": " | ".join(cells[:4]),
                })
        _FDA_CACHE["data"] = rows
        _FDA_CACHE["fetched_at"] = datetime.utcnow()
        return rows
    except Exception:
        return _FDA_CACHE["data"] or []


def get_next_fda_event(ticker):
    today = datetime.utcnow().date()
    cal = _fetch_fda_pdufa_calendar()
    soonest = None
    soonest_details = None
    for row in cal:
        if row["ticker"] != ticker:
            continue
        try:
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if d > today and (soonest is None or d < soonest):
            soonest = d
            soonest_details = row.get("details")
    if soonest:
        return {"date": soonest, "type": "fda_pdufa", "details": soonest_details}
    return None


def get_next_catalyst_for_ticker(ticker, fundamentals=None, sector=None):
    """Find the nearest dated catalyst across earnings/FDA/macro for this ticker."""
    candidates = []
    earn = get_next_earnings_date(ticker, fundamentals)
    if earn:
        candidates.append({"date": earn, "type": "earnings", "details": "Quarterly earnings"})

    if sector and any(s in (sector or "").lower() for s in ("biotech", "pharma", "drug")):
        fda = get_next_fda_event(ticker)
        if fda:
            candidates.append(fda)

    if not candidates:
        return None

    today = datetime.utcnow().date()
    candidates.sort(key=lambda c: c["date"])
    chosen = candidates[0]
    days = (chosen["date"] - today).days
    return {
        "type": chosen["type"],
        "date": chosen["date"].isoformat(),
        "days_until": days,
        "details": chosen.get("details", ""),
        "all_candidates": [
            {"type": c["type"], "date": c["date"].isoformat(), "days_until": (c["date"] - today).days}
            for c in candidates
        ],
    }


def catalyst_window_score(days_until):
    """Convert days-to-next-catalyst into a 0-100 conviction component.

    Sweet spot 5-21 days (IV expansion zone, time to play out):
      5-21 days   -> 75-90 (best - catalyst run-up trade)
      22-45 days  -> 55-70 (good - thesis anchor)
      <5 days     -> 30-40 (IV crush risk, theta cliff)
      >45 days    -> 40-50 (too far to drive a 1-2 week move)
      None        -> 50 (neutral)
    """
    if days_until is None:
        return 50
    if 5 <= days_until <= 21:
        if 10 <= days_until <= 16:
            return 90
        return 75
    if 22 <= days_until <= 45:
        return 65
    if days_until < 5:
        if days_until <= 2:
            return 30
        return 40
    return 45


def enrich_picks_with_forward_catalyst(picks, max_picks=30, verbose=False):
    """Attach _forward_catalyst dict to top picks. Free data only."""
    if not picks:
        return picks
    enriched = 0
    catalyst_within_window = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        sector = p.get("sector", "")
        fund = p.get("_fundamentals") or p.get("_raw_fundamentals")
        try:
            cat = get_next_catalyst_for_ticker(ticker, fundamentals=fund, sector=sector)
        except Exception:
            cat = None
        if cat:
            cat["window_score"] = catalyst_window_score(cat["days_until"])
            p["_forward_catalyst"] = cat
            enriched += 1
            if 5 <= cat["days_until"] <= 21:
                catalyst_within_window += 1
    if verbose:
        print(f"  forward_calendar: enriched {enriched}/{min(max_picks, len(picks))} picks, {catalyst_within_window} in 5-21d sweet spot")
    return picks


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


MACRO_TRADE_PLAYBOOK = {
    "CPI release": {
        "vehicles": ["QQQ", "SPY"],
        "structure": "long straddle / iron condor depending on IV",
        "dte_target": "0-3 days",
        "rationale": "Inflation prints typically move SPY ±0.8-2%. Hot print = AI/growth sells off, cool = rip. Asymmetric on either side.",
        "specific_strikes": "ATM weekly straddle if QQQ IV percentile < 50, otherwise 1-2% OTM strangle",
    },
    "FOMC decision": {
        "vehicles": ["SPY", "TLT", "XLF"],
        "structure": "straddle SPY + directional TLT (rate-sensitive)",
        "dte_target": "0-7 days",
        "rationale": "Powell pressers tend to whipsaw. SPY ±1.5% typical, TLT moves on dot plot shift. Bank sector follows yields.",
        "specific_strikes": "ATM SPY weekly straddle, or 25-delta strangle for 2x premium",
    },
    "Non-farm payrolls": {
        "vehicles": ["SPY", "TLT"],
        "structure": "directional or fade",
        "dte_target": "0-2 days",
        "rationale": "Strong jobs = bond selloff (yields up, growth sells off), weak jobs = the reverse. SPY ±0.6-1.5% typical.",
        "specific_strikes": "5-10% OTM directional based on whisper number",
    },
}


def build_macro_trade_suggestions(macro_events, vix_level=None):
    suggestions = []
    for ev in macro_events:
        label = ev.get("label", "")
        playbook = MACRO_TRADE_PLAYBOOK.get(label)
        if not playbook:
            continue
        urgency = "HIGH" if ev["days_until"] <= 1 else ("MEDIUM" if ev["days_until"] <= 3 else "LOW")
        regime_note = ""
        if vix_level:
            if vix_level < 15:
                regime_note = "VIX low — straddles are cheap, options market underpricing risk"
            elif vix_level > 25:
                regime_note = "VIX elevated — straddles expensive, prefer credit spreads"
        suggestions.append({
            "event": label,
            "event_date": ev["date"],
            "days_until": ev["days_until"],
            "urgency": urgency,
            "vehicles": playbook["vehicles"],
            "structure": playbook["structure"],
            "dte_target": playbook["dte_target"],
            "rationale": playbook["rationale"],
            "specific_strikes": playbook["specific_strikes"],
            "regime_note": regime_note,
        })
    return suggestions


def build_forward_calendar(client, watchlist_tickers=None, days_ahead=5, target_date=None, vix_level=None):
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
    macro_trades = build_macro_trade_suggestions(macro_events, vix_level=vix_level)
    return {
        "earnings": earnings_summary,
        "macro_events": macro_events,
        "macro_trade_suggestions": macro_trades,
        "scan_date": today.strftime("%Y-%m-%d"),
        "days_ahead": days_ahead,
    }
