"""WallStreetBets mention rate detector.

Uses Reddit's public JSON endpoint (no auth needed for search) to count
mentions of $TICKER on r/wallstreetbets in the last 7 days vs the last 30.
A 3x+ spike = retail momentum confirmation signal.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta

import requests


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "cache_wsb")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_HR = 4
USER_AGENT = "swing-trading-scanner/1.0 (research; +github.com/savvystocks)"


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


def _search_count(ticker, days_back):
    queries = [f"${ticker}", ticker]
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    count = 0
    upvote_sum = 0
    sample_titles = []
    for q in queries[:1]:
        url = f"https://www.reddit.com/r/wallstreetbets/search.json?q={q}&restrict_sr=on&sort=new&limit=100&t=month"
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=12)
            if r.status_code != 200:
                continue
            data = r.json()
            children = data.get("data", {}).get("children", [])
            for c in children:
                post = c.get("data", {})
                created = datetime.utcfromtimestamp(post.get("created_utc", 0))
                if created < cutoff:
                    continue
                count += 1
                upvote_sum += post.get("score", 0) or 0
                if len(sample_titles) < 3:
                    title = (post.get("title") or "")[:120]
                    sample_titles.append(title)
        except Exception:
            continue
    return count, upvote_sum, sample_titles


def compute_wsb_signal(ticker):
    cached = _read_cache(ticker)
    if cached is not None:
        return cached

    if len(ticker) <= 2 or ticker in ("ON", "IT", "BE", "ALL", "FOR", "AND", "ARE", "USE", "WAY", "DAY"):
        result = {"_skipped": "too-common ticker symbol"}
        _write_cache(ticker, result)
        return result

    count_7d, upvotes_7d, samples = _search_count(ticker, 7)
    count_30d, upvotes_30d, _ = _search_count(ticker, 30)

    baseline_per_week = max(1, count_30d / 4.3)
    spike_ratio = count_7d / baseline_per_week if baseline_per_week > 0 else 0

    if count_7d == 0:
        verdict = "NO_BUZZ"
    elif spike_ratio >= 3.0 and count_7d >= 5:
        verdict = "HEAVY_BUZZ"
    elif spike_ratio >= 1.8 and count_7d >= 3:
        verdict = "ELEVATED_BUZZ"
    elif count_7d >= 2:
        verdict = "NORMAL_BUZZ"
    else:
        verdict = "LOW_BUZZ"

    result = {
        "verdict": verdict,
        "mentions_7d": count_7d,
        "mentions_30d": count_30d,
        "spike_ratio": round(spike_ratio, 1),
        "upvotes_7d": upvotes_7d,
        "sample_titles": samples,
    }
    _write_cache(ticker, result)
    return result


def apply_wsb_mentions(picks, max_picks=15, verbose=False):
    if not picks:
        return
    enriched = 0
    heavy = 0
    for p in picks[:max_picks]:
        try:
            ticker = p.get("ticker", "")
            if not ticker or "." in ticker:
                continue
            sig = compute_wsb_signal(ticker)
            if sig and "_skipped" not in sig:
                p["_wsb_mentions"] = sig
                enriched += 1
                if sig["verdict"] == "HEAVY_BUZZ":
                    heavy += 1
            time.sleep(0.6)
        except Exception:
            continue
    if verbose:
        print(f"  wsb_mentions: scanned {enriched} picks, {heavy} HEAVY_BUZZ")
