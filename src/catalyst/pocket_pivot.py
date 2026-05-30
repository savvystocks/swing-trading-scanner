"""Pocket Pivot Detector (Gil Morales / Chris Kacher).

The pocket pivot is a precise volume signal: an UP day where volume exceeds
the maximum DOWN-day volume of the prior 10 trading days. This signals
institutional accumulation BEFORE a breakout becomes obvious.

Original definition from "Trade Like an O'Neil Disciple" (Morales, Kacher).
Validated as a leading indicator for the same momentum names that go on to
make standard breakouts. Catching the pocket pivot 3-7 days early
materially shifts entry quality.

Confluence detector reads pick._pocket_pivot.fires.
"""

from datetime import datetime, timedelta


def _get_bars(ticker, days=30):
    try:
        from src.alpaca_ohlcv import get_daily_bars
        from datetime import date
        end = date.today()
        start = end - timedelta(days=days + 10)
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
        start = end - timedelta(days=days + 10)
        bars = client.ohlcv(f"{ticker}.US" if "." not in ticker else ticker,
                            from_date=start.strftime("%Y-%m-%d"),
                            to_date=end.strftime("%Y-%m-%d"))
        return bars or []
    except Exception:
        return []


def detect_pocket_pivot(ticker, bars=None, lookback=10, verbose=False):
    """Returns dict with fires (bool), volume_ratio, label."""
    bars = bars or _get_bars(ticker, days=lookback + 5)
    if len(bars) < lookback + 1:
        return {"fires": False, "label": None, "reason": f"insufficient bars ({len(bars)})"}

    parsed = []
    for b in bars[-(lookback + 1):]:
        try:
            parsed.append({
                "close": float(b.get("close") or 0),
                "open": float(b.get("open") or 0),
                "volume": float(b.get("volume") or 0),
            })
        except Exception:
            continue

    if len(parsed) < lookback + 1:
        return {"fires": False, "label": None, "reason": "parse failure"}

    today = parsed[-1]
    prior = parsed[:-1]

    if today["close"] <= today["open"]:
        return {"fires": False, "label": None, "reason": "today closed red, not an up day"}

    down_day_volumes = []
    for b in prior:
        if b["close"] < b["open"]:
            down_day_volumes.append(b["volume"])

    if not down_day_volumes:
        return {"fires": False, "label": None, "reason": "no down days in lookback to compare"}

    max_down_vol = max(down_day_volumes)
    today_vol = today["volume"]
    if today_vol > max_down_vol and max_down_vol > 0:
        ratio = today_vol / max_down_vol
        if verbose:
            print(f"  pocket_pivot {ticker}: FIRES - up day vol {today_vol:.0f} > max down vol {max_down_vol:.0f} ({ratio:.1f}x)")
        return {
            "fires": True,
            "label": f"pocket pivot ({ratio:.1f}x max down-day vol)",
            "volume_ratio": round(ratio, 2),
            "today_volume": int(today_vol),
            "max_down_volume_10d": int(max_down_vol),
            "reason": "up day on volume exceeding max recent down-day volume",
        }
    return {
        "fires": False,
        "label": None,
        "volume_ratio": round(today_vol / max_down_vol, 2) if max_down_vol > 0 else None,
        "reason": "up day but volume below max down-day in lookback",
    }


def enrich_picks_with_pocket_pivot(picks, max_picks=30, verbose=False):
    if not picks:
        return picks
    fires_count = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        try:
            res = detect_pocket_pivot(ticker, verbose=False)
        except Exception:
            continue
        p["_pocket_pivot"] = res
        if res.get("fires"):
            fires_count += 1
    if verbose:
        print(f"  pocket_pivot: {fires_count} firing out of {min(max_picks, len(picks))} checked")
    return picks
