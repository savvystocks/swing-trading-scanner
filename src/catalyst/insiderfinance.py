"""InsiderFinance integration - flow + dark pool + GEX + insider in one API.

Path 2 subscription ($55/mo annual ~£44). Replaces Unusual Whales for value
because it bundles options flow + dark pool + GEX + insider trades + congress
+ technical analysis in a single subscription.

Activate by setting INSIDERFINANCE_TOKEN env var (get from your account at
insiderfinance.io after subscribing).

Endpoints (per InsiderFinance API docs):
- /v1/options/flow?ticker=X - options sweeps/blocks
- /v1/darkpool/prints?ticker=X - large dark pool prints
- /v1/options/gex?ticker=X - dealer gamma exposure
- /v1/insider/cluster?ticker=X - insider buying clusters

When INSIDERFINANCE_TOKEN is unset, every function returns None gracefully.
"""

import os
from datetime import datetime, timedelta


API_BASE = "https://api.insiderfinance.io/v1"


def _headers():
    token = os.environ.get("INSIDERFINANCE_TOKEN", "").strip()
    if not token:
        return None
    return {"Accept": "application/json", "Authorization": f"Bearer {token}"}


def get_options_flow(ticker, days_back=2, min_premium_usd=50_000):
    headers = _headers()
    if not headers:
        return None
    try:
        import requests
        r = requests.get(
            f"{API_BASE}/options/flow",
            headers=headers,
            params={"ticker": ticker, "limit": 50},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        rows = data.get("data") or data.get("flow") or []
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        out = []
        for row in rows:
            ts_str = row.get("timestamp") or row.get("ts") or row.get("created_at", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue
            if ts < cutoff:
                continue
            premium = float(row.get("premium") or row.get("total_premium") or 0)
            if premium < min_premium_usd:
                continue
            out.append({
                "ts": ts_str,
                "side": row.get("side") or row.get("type"),
                "strike": row.get("strike"),
                "expiry": row.get("expiry") or row.get("expiration"),
                "volume": row.get("volume") or row.get("size"),
                "premium_usd": premium,
                "alert_type": row.get("alert_type") or row.get("rule"),
                "sentiment": row.get("sentiment"),
            })
        return out
    except Exception:
        return None


def get_dark_pool_prints(ticker, days_back=1, min_value_usd=1_000_000):
    headers = _headers()
    if not headers:
        return None
    try:
        import requests
        r = requests.get(
            f"{API_BASE}/darkpool/prints",
            headers=headers,
            params={"ticker": ticker, "limit": 30},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        rows = data.get("data") or data.get("prints") or []
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        out = []
        for row in rows:
            ts_str = row.get("timestamp") or row.get("ts", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue
            if ts < cutoff:
                continue
            value = float(row.get("value") or (float(row.get("size") or 0) * float(row.get("price") or 0)))
            if value < min_value_usd:
                continue
            out.append({
                "ts": ts_str,
                "size": row.get("size"),
                "price": row.get("price"),
                "value_usd": round(value, 2),
            })
        return out
    except Exception:
        return None


def get_gex(ticker):
    headers = _headers()
    if not headers:
        return None
    try:
        import requests
        r = requests.get(
            f"{API_BASE}/options/gex",
            headers=headers,
            params={"ticker": ticker},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return {
            "net_gex": data.get("net_gex"),
            "gex_per_strike": data.get("strike_levels"),
            "zero_gamma_strike": data.get("zero_gamma"),
            "regime": "NEGATIVE_AMP" if (data.get("net_gex") or 0) < 0 else "POSITIVE_PIN",
        }
    except Exception:
        return None


def get_insider_cluster(ticker, days_back=14):
    headers = _headers()
    if not headers:
        return None
    try:
        import requests
        r = requests.get(
            f"{API_BASE}/insider/cluster",
            headers=headers,
            params={"ticker": ticker, "days": days_back},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return {
            "buyer_count": data.get("buyers"),
            "total_value_usd": data.get("total_value"),
            "ceo_or_cfo_bought": data.get("ceo_or_cfo"),
            "recent_filings": data.get("filings", [])[:5],
        }
    except Exception:
        return None


def annotate_picks_with_insiderfinance(picks, verbose=False):
    if not _headers():
        if verbose:
            print("  insiderfinance: INSIDERFINANCE_TOKEN not set, skipping")
        return picks
    enriched = 0
    for p in picks:
        t = p.get("ticker")
        if not t or "." in t:
            continue
        flow = get_options_flow(t)
        dp = get_dark_pool_prints(t)
        gex = get_gex(t)
        insider = get_insider_cluster(t)
        if flow:
            p["_if_flow"] = flow
        if dp:
            p["_if_dark_pool"] = dp
        if gex:
            p["_if_gex"] = gex
        if insider:
            p["_if_insider_cluster"] = insider
        if any([flow, dp, gex, insider]):
            enriched += 1
    if verbose:
        print(f"  insiderfinance: enriched {enriched}/{len(picks)} picks (flow + dark pool + GEX + insider)")
    return picks
