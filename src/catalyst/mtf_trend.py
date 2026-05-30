"""Multi-Timeframe Trend Alignment.

Daily + Weekly + Monthly trend direction per pick. When all three align UP =
much higher probability of continued upside. Filters fakeout breakouts on
daily that are actually inside a weekly downtrend.

Edge: Schwager (Market Wizards), Linda Raschke, and Trader Vic all hammer
the same point — align with the higher timeframe trend, the win rate of
your lower timeframe setup jumps significantly. Quantified studies show
~+5% win rate lift on momentum trades that have daily+weekly+monthly
alignment vs daily alone.

Method (per timeframe):
  - Daily: close vs 50-day SMA (above = UP)
  - Weekly: close vs 10-week SMA on weekly bars (above = UP)
  - Monthly: close vs 6-month SMA on monthly bars (above = UP)

All three UP = aligned_up.
All three DOWN = aligned_down.
Mixed = neither.

Free data: Alpaca daily bars (we already pull these), aggregated to
weekly + monthly client-side.
"""

from datetime import datetime, timedelta


def _get_daily_bars(ticker, days=420):
    """Pull ~14 months of daily bars. Free Alpaca first, EODHD fallback."""
    try:
        from src.alpaca_ohlcv import get_daily_bars
        from datetime import date
        end = date.today()
        start = end - timedelta(days=days)
        bars = get_daily_bars(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if bars:
            return bars
    except Exception:
        pass
    try:
        from src.eodhd import EODHDClient
        from datetime import date
        client = EODHDClient()
        end = date.today()
        start = end - timedelta(days=days)
        bars = client.ohlcv(f"{ticker}.US" if "." not in ticker else ticker,
                            from_date=start.strftime("%Y-%m-%d"),
                            to_date=end.strftime("%Y-%m-%d"))
        return bars or []
    except Exception:
        return []


def _aggregate_to_weekly(daily_bars):
    """Group daily bars into weekly bars (Mon-Fri sessions). Returns list of weekly closes."""
    if not daily_bars:
        return []
    by_week = {}
    for b in daily_bars:
        try:
            d = datetime.strptime(b.get("date", ""), "%Y-%m-%d").date()
            iso_year, iso_week, _ = d.isocalendar()
            key = (iso_year, iso_week)
            by_week.setdefault(key, []).append({"date": d, "close": float(b.get("close") or 0)})
        except Exception:
            continue
    weekly_closes = []
    for key in sorted(by_week.keys()):
        days_in_week = sorted(by_week[key], key=lambda x: x["date"])
        if days_in_week:
            weekly_closes.append(days_in_week[-1]["close"])
    return weekly_closes


def _aggregate_to_monthly(daily_bars):
    """Group daily bars into monthly bars. Returns list of monthly closes."""
    if not daily_bars:
        return []
    by_month = {}
    for b in daily_bars:
        try:
            d = datetime.strptime(b.get("date", ""), "%Y-%m-%d").date()
            key = (d.year, d.month)
            by_month.setdefault(key, []).append({"date": d, "close": float(b.get("close") or 0)})
        except Exception:
            continue
    monthly_closes = []
    for key in sorted(by_month.keys()):
        days_in_month = sorted(by_month[key], key=lambda x: x["date"])
        if days_in_month:
            monthly_closes.append(days_in_month[-1]["close"])
    return monthly_closes


def _trend_above_sma(closes, sma_period):
    """Returns True if last close > SMA(period), False if below, None if insufficient data."""
    if len(closes) < sma_period:
        return None
    sma = sum(closes[-sma_period:]) / sma_period
    return closes[-1] > sma, round(closes[-1], 2), round(sma, 2)


def analyze_mtf_trend(ticker, bars=None, verbose=False):
    """Returns dict {daily_up, weekly_up, monthly_up, aligned_up, aligned_down}."""
    bars = bars or _get_daily_bars(ticker, days=420)
    if not bars or len(bars) < 50:
        return {"aligned_up": False, "aligned_down": False, "detail": f"insufficient bars ({len(bars)})"}

    daily_closes = []
    for b in bars:
        try:
            daily_closes.append(float(b.get("close") or 0))
        except Exception:
            continue

    weekly_closes = _aggregate_to_weekly(bars)
    monthly_closes = _aggregate_to_monthly(bars)

    daily_check = _trend_above_sma(daily_closes, 50)
    weekly_check = _trend_above_sma(weekly_closes, 10) if len(weekly_closes) >= 10 else None
    monthly_check = _trend_above_sma(monthly_closes, 6) if len(monthly_closes) >= 6 else None

    daily_up = daily_check[0] if daily_check else None
    weekly_up = weekly_check[0] if weekly_check else None
    monthly_up = monthly_check[0] if monthly_check else None

    aligned_up = daily_up is True and weekly_up is True and monthly_up is True
    aligned_down = daily_up is False and weekly_up is False and monthly_up is False

    result = {
        "ticker": ticker,
        "daily_up": daily_up,
        "weekly_up": weekly_up,
        "monthly_up": monthly_up,
        "aligned_up": aligned_up,
        "aligned_down": aligned_down,
        "daily_sma_50": daily_check[2] if daily_check else None,
        "weekly_sma_10": weekly_check[2] if weekly_check else None,
        "monthly_sma_6": monthly_check[2] if monthly_check else None,
        "daily_close": daily_closes[-1] if daily_closes else None,
    }

    if aligned_up:
        result["verdict"] = "ALIGNED_UP"
        result["detail"] = "daily + weekly + monthly all above their MAs - strong trend alignment"
        result["score"] = 85
    elif aligned_down:
        result["verdict"] = "ALIGNED_DOWN"
        result["detail"] = "all three timeframes below MAs - downtrend, avoid longs"
        result["score"] = 20
    else:
        ups = sum(1 for v in (daily_up, weekly_up, monthly_up) if v is True)
        result["verdict"] = "MIXED"
        result["detail"] = f"{ups} of 3 timeframes up - mixed trend signal"
        result["score"] = 50

    if verbose:
        print(f"  mtf_trend {ticker}: {result['verdict']} (D{'+' if daily_up else '-' if daily_up is False else '?'} W{'+' if weekly_up else '-' if weekly_up is False else '?'} M{'+' if monthly_up else '-' if monthly_up is False else '?'})")
    return result


def enrich_picks_with_mtf_trend(picks, max_picks=30, verbose=False):
    if not picks:
        return picks
    aligned_up_count = 0
    aligned_down_count = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        try:
            res = analyze_mtf_trend(ticker, verbose=False)
        except Exception:
            continue
        p["_mtf_trend"] = res
        if res.get("aligned_up"):
            aligned_up_count += 1
        elif res.get("aligned_down"):
            aligned_down_count += 1
    if verbose:
        print(f"  mtf_trend: {aligned_up_count} ALIGNED_UP, {aligned_down_count} ALIGNED_DOWN out of {min(max_picks, len(picks))} checked")
    return picks
