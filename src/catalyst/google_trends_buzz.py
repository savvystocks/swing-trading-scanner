"""Google Trends ticker search-volume signal via pytrends.

Detects when retail interest in a ticker is spiking vs its 90-day
baseline. Uses pytrends (unofficial Google Trends API). No key needed
but rate-limited and occasionally hits 429 - we cache aggressively.
"""

import json
import os
import time
from datetime import datetime, timedelta


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "cache_gtrends")
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


def compute_trends_signal(ticker):
    cached = _read_cache(ticker)
    if cached is not None:
        return cached

    try:
        from pytrends.request import TrendReq
    except ImportError:
        return {"_skipped": "pytrends not installed"}

    if len(ticker) <= 2:
        return {"_skipped": "ticker too short for trends"}

    try:
        pt = TrendReq(hl="en-US", tz=0, timeout=(8, 20))
        query = f"{ticker} stock"
        pt.build_payload([query], timeframe="today 3-m")
        df = pt.interest_over_time()
        if df is None or df.empty:
            result = {"_skipped": "no trends data"}
            _write_cache(ticker, result)
            return result
        values = df[query].tolist()
        if len(values) < 8:
            result = {"_skipped": "insufficient history"}
            _write_cache(ticker, result)
            return result
        recent = values[-7:]
        baseline = values[-30:-7] if len(values) >= 30 else values[:-7]
        recent_avg = sum(recent) / len(recent) if recent else 0
        baseline_avg = sum(baseline) / len(baseline) if baseline else 0
        spike_ratio = recent_avg / baseline_avg if baseline_avg > 0 else 0

        if recent_avg < 5:
            verdict = "NO_INTEREST"
        elif spike_ratio >= 2.0:
            verdict = "TRENDING_UP"
        elif spike_ratio >= 1.3:
            verdict = "ELEVATED"
        elif spike_ratio <= 0.6:
            verdict = "FADING"
        else:
            verdict = "STEADY"

        result = {
            "verdict": verdict,
            "recent_7d_avg": round(recent_avg, 1),
            "baseline_avg": round(baseline_avg, 1),
            "spike_ratio": round(spike_ratio, 2),
        }
        _write_cache(ticker, result)
        return result
    except Exception as e:
        result = {"_error": f"{type(e).__name__}: {str(e)[:80]}"}
        _write_cache(ticker, result)
        return result


def apply_google_trends(picks, max_picks=10, verbose=False):
    if not picks:
        return
    try:
        import pytrends  # noqa
    except ImportError:
        if verbose:
            print("  google_trends: pytrends not installed, skipping. Add to requirements.txt to enable.")
        return
    enriched = 0
    trending = 0
    for p in picks[:max_picks]:
        try:
            ticker = p.get("ticker", "")
            if not ticker or "." in ticker:
                continue
            sig = compute_trends_signal(ticker)
            if sig and "_error" not in sig and "_skipped" not in sig:
                p["_google_trends"] = sig
                enriched += 1
                if sig["verdict"] == "TRENDING_UP":
                    trending += 1
            time.sleep(1.2)
        except Exception:
            continue
    if verbose:
        print(f"  google_trends: enriched {enriched}/{max_picks}, {trending} TRENDING_UP")
