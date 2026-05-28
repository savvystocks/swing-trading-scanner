"""Unusual Whales integration - real-time options flow, dark pool, GEX.

Activate by setting UNUSUAL_WHALES_TOKEN env var (get from
unusualwhales.com/account/api after subscribing).

API base: https://api.unusualwhales.com/api/

Endpoints used:
- /option-trades/flow-alerts?ticker=X (sweep, block, premium >$100k)
- /stock/X/options-volume (call/put volume + put/call ratio)
- /stock/X/dark-pool-prints (large off-exchange prints)
- /market/economic-calendar (GEX day-of-week levels)

Cost: Unusual Whales annual ~£35/mo. API included on all tiers.

When UNUSUAL_WHALES_TOKEN is unset, every function returns None gracefully.
"""

import os
from datetime import datetime, timedelta


API_BASE = "https://api.unusualwhales.com/api"


def _headers():
    token = os.environ.get("UNUSUAL_WHALES_TOKEN", "").strip()
    if not token:
        return None
    return {"Accept": "application/json", "Authorization": f"Bearer {token}"}


def get_flow_alerts(ticker, days_back=2, min_premium_usd=50_000):
    """Return list of significant flow events (sweeps, blocks, large premium trades)."""
    headers = _headers()
    if not headers:
        return None
    try:
        import requests
        r = requests.get(
            f"{API_BASE}/stock/{ticker}/flow-alerts",
            headers=headers,
            params={"limit": 50},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        rows = data.get("data") or []
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        out = []
        for row in rows:
            try:
                ts = datetime.fromisoformat(row.get("created_at", "").replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue
            if ts < cutoff:
                continue
            premium = float(row.get("total_premium") or 0)
            if premium < min_premium_usd:
                continue
            out.append({
                "ts": row.get("created_at"),
                "side": row.get("type"),
                "strike": row.get("strike"),
                "expiry": row.get("expiry"),
                "volume": row.get("volume"),
                "premium_usd": premium,
                "alert_rule": row.get("rule_name"),
                "sentiment": row.get("sentiment"),
            })
        return out
    except Exception:
        return None


def get_put_call_ratio(ticker):
    """Return today's put/call ratio + intraday delta."""
    headers = _headers()
    if not headers:
        return None
    try:
        import requests
        r = requests.get(
            f"{API_BASE}/stock/{ticker}/option-stock-price-levels",
            headers=headers,
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json().get("data") or {}
        return {
            "put_call_ratio": data.get("put_call_ratio"),
            "iv_30d": data.get("iv_30d"),
            "iv_30d_rank": data.get("iv_30d_rank"),
        }
    except Exception:
        return None


def get_dark_pool_prints(ticker, days_back=1, min_size_usd=1_000_000):
    """Return list of large dark pool prints."""
    headers = _headers()
    if not headers:
        return None
    try:
        import requests
        r = requests.get(
            f"{API_BASE}/darkpool/{ticker}",
            headers=headers,
            params={"limit": 30},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        rows = data.get("data") or []
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        out = []
        for row in rows:
            try:
                ts = datetime.fromisoformat(row.get("executed_at", "").replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue
            if ts < cutoff:
                continue
            value = float(row.get("size") or 0) * float(row.get("price") or 0)
            if value < min_size_usd:
                continue
            out.append({
                "ts": row.get("executed_at"),
                "size": row.get("size"),
                "price": row.get("price"),
                "value_usd": round(value, 2),
            })
        return out
    except Exception:
        return None


def annotate_picks_with_flow(picks, verbose=False):
    if not _headers():
        if verbose:
            print("  unusual_whales: UNUSUAL_WHALES_TOKEN not set, skipping")
        return picks
    enriched = 0
    for p in picks:
        t = p.get("ticker")
        if not t or "." in t:
            continue
        flow = get_flow_alerts(t)
        pcr = get_put_call_ratio(t)
        dp = get_dark_pool_prints(t)
        if flow:
            p["_uw_flow"] = flow
        if pcr:
            p["_uw_pcr"] = pcr
        if dp:
            p["_uw_dark_pool"] = dp
        if flow or pcr or dp:
            enriched += 1
    if verbose:
        print(f"  unusual_whales: enriched {enriched}/{len(picks)} picks with flow + PCR + dark pool")
    return picks
