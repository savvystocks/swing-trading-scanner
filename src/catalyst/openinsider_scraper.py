"""OpenInsider.com scraper for real-time insider cluster buys.

OpenInsider is a free service that aggregates SEC Form 4 filings with
quality filters (cluster size, CEO/CFO weighting, dollar amounts). We
scrape their "Latest Insider Buying" feed and enrich our pick scoring
with high-quality insider signals beyond what EODHD's basic data shows.

Cached for 30 min per call so we don't hammer the site.
"""

import json
import os
import time
from datetime import datetime, timedelta

import requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "cache_openinsider")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_MIN = 30

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def _cache_path(key):
    safe = "".join(c if c.isalnum() else "_" for c in key)[:80]
    return os.path.join(CACHE_DIR, f"{safe}.json")


def _read_cache(key):
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    age_min = (time.time() - os.path.getmtime(path)) / 60
    if age_min > CACHE_TTL_MIN:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(key, data):
    try:
        with open(_cache_path(key), "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)
    except Exception:
        pass


def fetch_recent_cluster_buys(days_back=14, min_buyers=2, min_value_usd=50_000):
    """Pull OpenInsider 'Latest Cluster Buys' filtered to evidence-based signals.

    Returns a dict {ticker: {buyers, total_value, ceo_or_cfo, recency_days}}.
    """
    cache_key = f"cluster_buys_{days_back}_{min_buyers}_{min_value_usd}"
    cached = _read_cache(cache_key)
    if cached is not None:
        return cached

    min_val_k = max(1, int(min_value_usd / 1000))
    url = (
        f"http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh="
        f"&fd={days_back}&fdr=&td=0&tdr=&fdlyl=&fdlyh="
        f"&daysago=&xp=1&vl={min_val_k}&vh=&ocl=&och=&sic1=-1"
        f"&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh="
        f"&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=300&page=1"
    )
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}

    rows = _parse_table(html)
    by_ticker = {}
    for row in rows:
        t = row.get("ticker")
        if not t:
            continue
        d = by_ticker.setdefault(t, {
            "ticker": t,
            "buyers": set(),
            "total_value_usd": 0,
            "ceo_or_cfo_bought": False,
            "most_recent_date": None,
            "filings": [],
        })
        d["buyers"].add(row.get("insider_name", ""))
        d["total_value_usd"] += row.get("value_usd", 0) or 0
        if row.get("title", "").upper() in ("CEO", "CFO", "PRES", "PRESIDENT", "CHIEF EXECUTIVE OFFICER", "CHIEF FINANCIAL OFFICER"):
            d["ceo_or_cfo_bought"] = True
        rd = row.get("trade_date")
        if rd and (d["most_recent_date"] is None or rd > d["most_recent_date"]):
            d["most_recent_date"] = rd
        d["filings"].append(row)

    out = {}
    for t, d in by_ticker.items():
        buyers = list(d["buyers"])
        if len(buyers) < min_buyers:
            continue
        recency = None
        if d["most_recent_date"]:
            try:
                rd = datetime.strptime(d["most_recent_date"], "%Y-%m-%d")
                recency = (datetime.utcnow().date() - rd.date()).days
            except Exception:
                pass
        out[t] = {
            "buyers_count": len(buyers),
            "total_value_usd": int(d["total_value_usd"]),
            "ceo_or_cfo_bought": d["ceo_or_cfo_bought"],
            "most_recent_buy_date": d["most_recent_date"],
            "recency_days": recency,
            "_source": "openinsider",
        }

    _write_cache(cache_key, out)
    return out


def _parse_table(html):
    """Parse OpenInsider HTML table into row dicts. Avoid heavy HTML libs."""
    rows = []
    # The table rows we want are inside <table class="tinytable"> ... </table>
    import re
    table_match = re.search(r'<table[^>]*class="tinytable"[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
    if not table_match:
        return rows
    table_html = table_match.group(1)
    row_matches = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE)
    for row_html in row_matches:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE)
        if len(cells) < 12:
            continue
        try:
            # Trade date is cells[2] (cells[1] is filing date)
            trade_date_match = re.search(r"<div>(\d{4}-\d{2}-\d{2})</div>", cells[2])
            trade_date = trade_date_match.group(1) if trade_date_match else ""

            # Ticker is the href in cells[3]: <a href="/TICKER" ...>
            ticker_match = re.search(r'href="/([A-Z0-9.]+)"', cells[3])
            ticker = ticker_match.group(1).upper() if ticker_match else ""

            # Insider name is text inside the <a> tag in cells[5]
            insider_text = re.sub(r"<[^>]+>", "", cells[5], flags=re.DOTALL)
            insider_name = re.sub(r"\s+", " ", insider_text).strip()[:50]

            # Title is cells[6] - plain text
            title = re.sub(r"<[^>]+>", "", cells[6]).strip()[:30]

            # Trade type is cells[7] - must be "P - Purchase" not sells
            trade_type = re.sub(r"<[^>]+>", "", cells[7]).strip()
            if "Purchase" not in trade_type:
                continue

            # Value is cells[12] - format: "+$262,949"
            value_text = re.sub(r"<[^>]+>", "", cells[12])
            value_clean = re.sub(r"[^0-9.-]", "", value_text)
            try:
                value = int(float(value_clean)) if value_clean else 0
            except ValueError:
                value = 0
            value = abs(value)

            if not ticker or value <= 0:
                continue

            rows.append({
                "trade_date": trade_date,
                "ticker": ticker,
                "insider_name": insider_name,
                "title": title,
                "value_usd": value,
            })
        except Exception:
            continue
    return rows


def apply_openinsider_signals(picks, days_back=14, min_buyers=2, min_value_usd=50_000, verbose=False):
    """Enrich picks with OpenInsider cluster-buy data."""
    if not picks:
        return
    try:
        cluster_data = fetch_recent_cluster_buys(days_back=days_back, min_buyers=min_buyers, min_value_usd=min_value_usd)
    except Exception as e:
        if verbose:
            print(f"  openinsider failed (non-fatal): {type(e).__name__}: {e}")
        return
    if isinstance(cluster_data, dict) and "_error" in cluster_data:
        if verbose:
            print(f"  openinsider error: {cluster_data['_error']}")
        return

    enriched = 0
    for p in picks:
        t = p.get("ticker", "").upper()
        if t in cluster_data:
            p["_openinsider"] = cluster_data[t]
            enriched += 1

    if verbose:
        total_clusters = len(cluster_data) if isinstance(cluster_data, dict) else 0
        print(f"  openinsider: {total_clusters} stocks with recent cluster buys, {enriched} matched our picks")
