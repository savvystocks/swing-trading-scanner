"""Barchart Premier integration - IV rank + unusual options activity.

Activate by setting BARCHART_API_KEY env var (get from your Barchart Premier
account settings page after subscribing).

Endpoints used (Barchart Market Data API):
- /v2/getQuote with fields=ivRank,impliedVolatility
- /v2/getOptionsUnusualActivity?symbol=X (Premium tier)

Cost: Barchart Premier annual ~£16/mo. API access is included on the
Premier tier (some endpoints require the Premier API add-on at higher
cost - confirm in your dashboard before relying on UOA endpoint).

When BARCHART_API_KEY is unset, every function returns None gracefully so
the rest of the pipeline keeps working without flow data.
"""

import os
from datetime import datetime


def _client():
    key = os.environ.get("BARCHART_API_KEY", "").strip()
    if not key:
        return None
    return key


def get_iv_rank(ticker):
    """Returns dict {iv_rank_pct, iv_pct, source: 'barchart'} or None."""
    key = _client()
    if not key:
        return None
    try:
        import requests
        r = requests.get(
            "https://marketdata.websol.barchart.com/getQuote.json",
            params={
                "apikey": key,
                "symbols": ticker,
                "fields": "ivRank,impliedVolatility,impliedVolatilityRank1y",
            },
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        results = data.get("results") or []
        if not results:
            return None
        row = results[0]
        return {
            "iv_rank_pct": row.get("ivRank") or row.get("impliedVolatilityRank1y"),
            "iv_pct": row.get("impliedVolatility"),
            "source": "barchart",
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        }
    except Exception:
        return None


def get_unusual_options_activity(ticker, min_volume_oi_ratio=3.0):
    """Returns list of dicts [{strike, expiry, side, volume, oi, vol_oi_ratio, premium}] or None."""
    key = _client()
    if not key:
        return None
    try:
        import requests
        r = requests.get(
            "https://marketdata.websol.barchart.com/getOptionsUnusualActivity.json",
            params={"apikey": key, "symbol": ticker},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        results = data.get("results") or []
        out = []
        for row in results:
            vol = row.get("volume") or 0
            oi = row.get("openInterest") or 0
            ratio = vol / oi if oi > 0 else None
            if ratio is None or ratio < min_volume_oi_ratio:
                continue
            out.append({
                "strike": row.get("strike"),
                "expiry": row.get("expirationDate"),
                "side": row.get("putCall"),
                "volume": vol,
                "oi": oi,
                "vol_oi_ratio": round(ratio, 2),
                "premium": row.get("premium"),
            })
        return out
    except Exception:
        return None


def annotate_picks_with_barchart(picks, verbose=False):
    """For each pick, attach _barchart_iv_rank and _barchart_uoa fields."""
    if not _client():
        if verbose:
            print("  barchart: BARCHART_API_KEY not set, skipping")
        return picks
    enriched = 0
    for p in picks:
        t = p.get("ticker")
        if not t or "." in t:
            continue
        iv = get_iv_rank(t)
        if iv:
            p["_barchart_iv_rank"] = iv
        uoa = get_unusual_options_activity(t)
        if uoa:
            p["_barchart_uoa"] = uoa
        if iv or uoa:
            enriched += 1
    if verbose:
        print(f"  barchart: enriched {enriched}/{len(picks)} picks with IV rank + UOA")
    return picks
