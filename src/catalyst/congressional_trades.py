"""Congressional trades via Quiver Quantitative free API.

Requires QUIVER_API_KEY env var (free signup at api.quiverquant.com).
Without the key the module gracefully skips - no error.

Surfaces stocks where Senators/Representatives have purchased recently,
ranked by aggregate dollar amount and recency. Small but documented edge.
"""

import json
import os
import time
from datetime import datetime, timedelta

import requests


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "cache_quiver")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_HR = 12


def _cache_path(ticker):
    safe = "".join(c if c.isalnum() else "_" for c in ticker)[:30]
    return os.path.join(CACHE_DIR, f"{safe}.json")


def _read_cache(ticker):
    p = _cache_path(ticker)
    if not os.path.exists(p):
        return None
    age_hr = (time.time() - os.path.getmtime(p)) / 3600
    if age_hr > CACHE_TTL_HR:
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(ticker, data):
    try:
        with open(_cache_path(ticker), "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)
    except Exception:
        pass


def fetch_congress_trades(ticker, days_back=60):
    api_key = os.environ.get("QUIVER_API_KEY")
    if not api_key:
        return None

    cached = _read_cache(ticker)
    if cached is not None:
        return cached

    url = f"https://api.quiverquant.com/beta/historical/congresstrading/{ticker}"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=12)
        if r.status_code != 200:
            return None
        items = r.json() or []
    except Exception:
        return None

    cutoff = datetime.utcnow() - timedelta(days=days_back)
    recent = []
    for item in items:
        try:
            traded_str = item.get("TransactionDate") or item.get("traded")
            if not traded_str:
                continue
            traded = datetime.strptime(traded_str[:10], "%Y-%m-%d")
            if traded < cutoff:
                continue
            action = (item.get("Transaction") or "").lower()
            if "purchase" not in action and "buy" not in action:
                continue
            recent.append({
                "name": item.get("Representative") or item.get("Senator"),
                "chamber": "Senate" if "Senator" in str(item) else "House",
                "amount_range": item.get("Range") or item.get("Amount"),
                "traded": traded_str[:10],
                "reported": item.get("ReportDate", "")[:10] if item.get("ReportDate") else None,
            })
        except Exception:
            continue

    result = {
        "purchases_60d": len(recent),
        "unique_members": len({r["name"] for r in recent if r.get("name")}),
        "examples": recent[:5],
    }
    _write_cache(ticker, result)
    return result


def apply_congressional_trades(picks, max_picks=15, verbose=False):
    if not os.environ.get("QUIVER_API_KEY"):
        if verbose:
            print("  congressional_trades: QUIVER_API_KEY not set, skipping (signup free at api.quiverquant.com)")
        return
    if not picks:
        return
    enriched = 0
    cluster_count = 0
    for p in picks[:max_picks]:
        try:
            ticker = p.get("ticker", "")
            if not ticker:
                continue
            data = fetch_congress_trades(ticker)
            if data and data.get("purchases_60d", 0) > 0:
                p["_congressional_trades"] = data
                enriched += 1
                if data.get("unique_members", 0) >= 2:
                    cluster_count += 1
        except Exception:
            continue
    if verbose:
        print(f"  congressional_trades: {enriched} picks with congress purchases, {cluster_count} multi-member clusters")
