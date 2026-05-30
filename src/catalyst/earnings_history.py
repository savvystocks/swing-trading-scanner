"""Earnings Reaction History per ticker.

For each pick with an earnings catalyst, look at the LAST 4 quarterly
reactions: which way did the stock move on print day + 5 days after?
What was the magnitude? Did it tend to beat-and-rip vs sell-the-news?

This gives every pick context on how the market typically reacts to that
specific ticker's prints. Same earnings setup looks different on a name
that's beat-and-ripped 4 quarters in a row vs one that's sold-off
post-earnings 3 of last 4.

Edge: per-ticker base rate is a documented refinement over generic PEAD
(Foster, Olsen, Shevlin 1984 - reactions cluster by company-specific
patterns due to investor familiarity + management style).

Free data from EODHD historical bars. Requires the next-earnings date
field (which we have via forward_calendar).
"""

from datetime import datetime, timedelta


def _fetch_bars(ticker, from_date, to_date):
    """Pull OHLCV bars. Prefer Alpaca free, fall back to EODHD."""
    try:
        from src.alpaca_ohlcv import get_daily_bars
        bars = get_daily_bars(ticker, from_date, to_date)
        if bars:
            return bars
    except Exception:
        pass
    try:
        from src.eodhd import EODHDClient
        client = EODHDClient()
        eo_t = ticker if "." in ticker else f"{ticker}.US"
        bars = client.ohlcv(eo_t, from_date=from_date, to_date=to_date)
        return bars or []
    except Exception:
        return []


def _get_past_earnings_dates(ticker, fundamentals=None):
    """Return list of past 4 earnings dates (as date objects, most recent first)."""
    try:
        if fundamentals is None:
            from src.eodhd import EODHDClient
            client = EODHDClient()
            fundamentals = client.fundamentals(f"{ticker}.US" if "." not in ticker else ticker)
    except Exception:
        return []
    if not fundamentals:
        return []
    history = ((fundamentals.get("Earnings") or {}).get("History")) or {}
    today = datetime.utcnow().date()
    past_dates = []
    for _k, v in history.items():
        rd = v.get("reportDate")
        if not rd:
            continue
        try:
            d = datetime.strptime(rd, "%Y-%m-%d").date()
        except Exception:
            continue
        if d <= today:
            past_dates.append(d)
    past_dates.sort(reverse=True)
    return past_dates[:4]


def _compute_reaction(bars, earnings_date):
    """Given bars and a print date, compute reaction stats.

    Returns dict {pct_day_of, pct_5d_after, won (Bool), pct_drift_continued}
    or None if data is insufficient.
    """
    if not bars:
        return None
    bar_by_date = {}
    for b in bars:
        try:
            d = datetime.strptime(b.get("date", ""), "%Y-%m-%d").date()
            bar_by_date[d] = {
                "open": float(b.get("open") or 0),
                "high": float(b.get("high") or 0),
                "low": float(b.get("low") or 0),
                "close": float(b.get("close") or 0),
            }
        except Exception:
            continue

    print_day = None
    for offset in range(0, 5):
        cand = earnings_date + timedelta(days=offset)
        if cand in bar_by_date:
            print_day = cand
            break
    if print_day is None:
        return None
    prior_day = None
    for offset in range(1, 5):
        cand = earnings_date - timedelta(days=offset)
        if cand in bar_by_date:
            prior_day = cand
            break
    if prior_day is None:
        return None

    prior_close = bar_by_date[prior_day]["close"]
    print_close = bar_by_date[print_day]["close"]
    if prior_close <= 0:
        return None
    pct_day_of = (print_close - prior_close) / prior_close * 100

    after_5d_date = print_day + timedelta(days=7)
    after_5d_close = None
    for offset in range(0, 5):
        cand = after_5d_date + timedelta(days=offset)
        if cand in bar_by_date:
            after_5d_close = bar_by_date[cand]["close"]
            break
    if after_5d_close is None:
        return None
    pct_5d_after = (after_5d_close - prior_close) / prior_close * 100
    drift_continued = (pct_day_of > 0 and pct_5d_after > pct_day_of) or (pct_day_of < 0 and pct_5d_after < pct_day_of)
    return {
        "earnings_date": earnings_date.isoformat(),
        "pct_day_of": round(pct_day_of, 2),
        "pct_5d_after": round(pct_5d_after, 2),
        "drift_continued": drift_continued,
        "won": pct_day_of > 0,
    }


def get_earnings_reaction_history(ticker, fundamentals=None):
    """Pull last 4 earnings reactions. Returns dict with summary stats + per-quarter list."""
    past_dates = _get_past_earnings_dates(ticker, fundamentals)
    if not past_dates:
        return None

    earliest = past_dates[-1]
    from_date = (earliest - timedelta(days=10)).strftime("%Y-%m-%d")
    to_date = datetime.utcnow().date().strftime("%Y-%m-%d")
    bars = _fetch_bars(ticker, from_date, to_date)
    if not bars:
        return None

    reactions = []
    for d in past_dates:
        r = _compute_reaction(bars, d)
        if r:
            reactions.append(r)

    if not reactions:
        return None

    wins = sum(1 for r in reactions if r["won"])
    avg_move = sum(abs(r["pct_day_of"]) for r in reactions) / len(reactions)
    avg_signed = sum(r["pct_day_of"] for r in reactions) / len(reactions)
    drift_count = sum(1 for r in reactions if r["drift_continued"])

    return {
        "ticker": ticker,
        "n_quarters": len(reactions),
        "post_earnings_win_rate": round(wins / len(reactions), 2),
        "avg_move_pct": round(avg_move, 2),
        "avg_signed_move_pct": round(avg_signed, 2),
        "drift_rate": round(drift_count / len(reactions), 2),
        "pattern": _classify_pattern(reactions),
        "history": reactions,
        "summary_string": _format_summary(reactions),
    }


def _classify_pattern(reactions):
    """Label the pattern: BEAT_AND_RIP / SELL_THE_NEWS / VOLATILE / MIXED."""
    if not reactions:
        return "UNKNOWN"
    win_rate = sum(1 for r in reactions if r["won"]) / len(reactions)
    drift_rate = sum(1 for r in reactions if r["drift_continued"]) / len(reactions)
    avg_abs = sum(abs(r["pct_day_of"]) for r in reactions) / len(reactions)

    if win_rate >= 0.75 and drift_rate >= 0.5:
        return "BEAT_AND_RIP"
    if win_rate <= 0.25:
        return "SELL_THE_NEWS"
    if avg_abs >= 10:
        return "VOLATILE"
    if win_rate >= 0.5:
        return "POSITIVE_LEAN"
    return "MIXED"


def _format_summary(reactions):
    """e.g. 'last 4 prints: +12%, +8%, -4%, +18%' (most recent first)."""
    parts = []
    for r in reactions:
        v = r["pct_day_of"]
        parts.append(f"{v:+.0f}%")
    return f"last {len(reactions)} prints: " + ", ".join(parts)


def enrich_picks_with_earnings_history(picks, max_picks=20, verbose=False):
    """Attach _earnings_history to picks with an earnings catalyst."""
    if not picks:
        return picks
    enriched = 0
    beat_and_rip = 0
    sell_the_news = 0
    for p in picks[:max_picks]:
        fc = p.get("_forward_catalyst") or {}
        if fc.get("type") != "earnings":
            continue
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        try:
            res = get_earnings_reaction_history(ticker, fundamentals=p.get("_fundamentals"))
        except Exception:
            res = None
        if not res:
            continue
        p["_earnings_history"] = res
        enriched += 1
        if res["pattern"] == "BEAT_AND_RIP":
            beat_and_rip += 1
        elif res["pattern"] == "SELL_THE_NEWS":
            sell_the_news += 1
    if verbose:
        print(f"  earnings_history: enriched {enriched} picks, {beat_and_rip} beat-and-rip, {sell_the_news} sell-the-news patterns")
    return picks
