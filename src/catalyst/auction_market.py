"""Auction Market Theory - Volume Profile + POC + Anchored VWAP.

Steidlmayer's framework. Where institutions are positioned in price/volume
WITHOUT needing leaked data. Computes Point of Control (highest volume strike),
Value Area High/Low (70% of volume), and anchored VWAP from key events.

Free data from Alpaca daily bars.
"""

from datetime import datetime, timedelta


def _get_bars(ticker, days=90, pick=None):
    """Get OHLCV bars. Prefer reuse of already-fetched data on the pick to avoid
    duplicate Alpaca calls during a single scan."""
    # First try to reuse OHLCV from the pick's _enriched_data (already pulled in Step 2)
    if pick is not None:
        enriched = pick.get("_enriched_data") or {}
        df = enriched.get("df")
        if df is not None and len(df) >= 20:
            # Convert the trailing `days` of dataframe rows to list-of-dict shape
            tail = df.tail(min(days, len(df)))
            bars = []
            for idx, row in tail.iterrows():
                try:
                    bars.append({
                        "date": str(idx)[:10],
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row.get("volume") or 0),
                    })
                except Exception:
                    continue
            if bars:
                return bars

    # Fallback: fresh Alpaca call (kept for backward compat when caller can't pass pick)
    try:
        from src.alpaca_ohlcv import get_daily_bars
        from datetime import date
        end = date.today()
        start = end - timedelta(days=days + 10)
        bars = get_daily_bars(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        return bars or []
    except Exception:
        return []


def compute_volume_profile(bars, num_bins=30):
    """Compute volume profile from bars. Returns POC, VAH, VAL."""
    if not bars or len(bars) < 20:
        return None
    prices = []
    volumes = []
    for b in bars:
        try:
            high = float(b["high"])
            low = float(b["low"])
            close = float(b["close"])
            vol = float(b.get("volume") or 0)
            if vol <= 0:
                continue
            typical = (high + low + close) / 3
            prices.append(typical)
            volumes.append(vol)
        except Exception:
            continue
    if not prices:
        return None

    p_min = min(prices)
    p_max = max(prices)
    if p_max <= p_min:
        return None
    bin_width = (p_max - p_min) / num_bins
    bin_volumes = [0.0] * num_bins
    bin_centers = [p_min + (i + 0.5) * bin_width for i in range(num_bins)]
    for price, vol in zip(prices, volumes):
        idx = min(int((price - p_min) / bin_width), num_bins - 1)
        bin_volumes[idx] += vol

    poc_idx = bin_volumes.index(max(bin_volumes))
    poc = bin_centers[poc_idx]

    total_vol = sum(bin_volumes)
    target = total_vol * 0.7
    left, right = poc_idx, poc_idx
    accumulated = bin_volumes[poc_idx]
    while accumulated < target and (left > 0 or right < num_bins - 1):
        l_vol = bin_volumes[left - 1] if left > 0 else 0
        r_vol = bin_volumes[right + 1] if right < num_bins - 1 else 0
        if l_vol >= r_vol and left > 0:
            left -= 1
            accumulated += l_vol
        elif right < num_bins - 1:
            right += 1
            accumulated += r_vol
        else:
            break

    return {
        "poc": round(poc, 2),
        "value_area_high": round(bin_centers[right], 2),
        "value_area_low": round(bin_centers[left], 2),
        "total_volume": int(total_vol),
        "bins_analyzed": num_bins,
    }


def compute_anchored_vwap(bars, anchor_date_str):
    """Anchored VWAP from a specific date forward."""
    if not bars:
        return None
    try:
        anchor_date = datetime.strptime(anchor_date_str, "%Y-%m-%d").date()
    except Exception:
        return None
    cum_pv = 0.0
    cum_v = 0.0
    for b in bars:
        try:
            d = datetime.strptime(b.get("date", ""), "%Y-%m-%d").date()
        except Exception:
            continue
        if d < anchor_date:
            continue
        try:
            typical = (float(b["high"]) + float(b["low"]) + float(b["close"])) / 3
            vol = float(b.get("volume") or 0)
        except Exception:
            continue
        cum_pv += typical * vol
        cum_v += vol
    if cum_v <= 0:
        return None
    return round(cum_pv / cum_v, 2)


def analyze_auction_levels(ticker, current_price=None, verbose=False, pick=None):
    bars = _get_bars(ticker, days=90, pick=pick)
    if len(bars) < 20:
        return None
    profile = compute_volume_profile(bars)
    if not profile:
        return None

    if current_price is None:
        try:
            current_price = float(bars[-1]["close"])
        except Exception:
            return None

    poc = profile["poc"]
    vah = profile["value_area_high"]
    val = profile["value_area_low"]

    if current_price > vah:
        position = "ABOVE_VALUE"
        bias = "trending up out of value area"
    elif current_price < val:
        position = "BELOW_VALUE"
        bias = "trending down below value area"
    else:
        if abs(current_price - poc) / poc * 100 < 1:
            position = "AT_POC"
            bias = "balance at point of control"
        else:
            position = "IN_VALUE"
            bias = "rotating in value area"

    if verbose:
        print(f"  auction {ticker}: {position} (POC ${poc} VAH ${vah} VAL ${val}, spot ${current_price:.2f})")

    return {
        "current_price": current_price,
        "poc": poc,
        "value_area_high": vah,
        "value_area_low": val,
        "position": position,
        "bias": bias,
    }


def enrich_picks_with_auction_levels(picks, max_picks=20, verbose=False):
    if not picks:
        return picks
    enriched = 0
    skipped_no_data = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        try:
            res = analyze_auction_levels(
                ticker,
                current_price=p.get("live_spot") or p.get("price"),
                verbose=False,
                pick=p,  # reuse OHLCV from _enriched_data.df to avoid fresh Alpaca call
            )
        except Exception:
            res = None
        if res:
            p["_auction_levels"] = res
            enriched += 1
        else:
            skipped_no_data += 1
    if verbose:
        print(f"  auction_market: {enriched} picks analyzed ({skipped_no_data} skipped - insufficient data)")
    return picks
