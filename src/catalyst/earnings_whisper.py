"""Earnings Whisper scraper - whisper EPS vs analyst consensus.

The 'whisper number' is the unofficial street estimate that often differs
from published consensus. Historically, stocks beating the whisper (not
just consensus) drift up post-earnings. Stocks beating consensus but
missing the whisper often sell off.

We scrape earningswhispers.com for top picks with imminent earnings to
get the whisper number. Cached 6 hr.
"""

import json
import os
import re
import time

import requests


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "cache_whisper")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_HR = 6
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"


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


def fetch_whisper(ticker):
    cached = _read_cache(ticker)
    if cached is not None:
        return cached

    url = f"https://www.earningswhispers.com/stocks/{ticker.lower()}"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=12)
        if r.status_code != 200:
            return None
        html = r.text
    except Exception:
        return None

    whisper_match = re.search(r'(?:Whisper Number|whisper)[^<]*?<[^>]*?>\s*\$?(-?\d+\.\d+)', html, re.IGNORECASE | re.DOTALL)
    consensus_match = re.search(r'(?:Consensus|consensus)[^<]*?<[^>]*?>\s*\$?(-?\d+\.\d+)', html, re.IGNORECASE | re.DOTALL)
    date_match = re.search(r'(?:Earnings Date|earnings date)[^<]*?<[^>]*?>\s*([A-Z][a-z]+\s+\d{1,2}(?:,\s*\d{4})?)', html, re.IGNORECASE | re.DOTALL)

    if not whisper_match and not consensus_match:
        result = {"_error": "could not parse whisper page"}
        _write_cache(ticker, result)
        return result

    try:
        whisper = float(whisper_match.group(1)) if whisper_match else None
        consensus = float(consensus_match.group(1)) if consensus_match else None
        delta = (whisper - consensus) if (whisper is not None and consensus is not None) else None
        delta_pct = (delta / abs(consensus) * 100) if (delta is not None and consensus and abs(consensus) > 0.01) else None

        if delta is None:
            verdict = "UNKNOWN"
        elif delta_pct is not None and delta_pct >= 5:
            verdict = "WHISPER_ABOVE_CONSENSUS"
        elif delta_pct is not None and delta_pct <= -5:
            verdict = "WHISPER_BELOW_CONSENSUS"
        else:
            verdict = "WHISPER_NEUTRAL"

        result = {
            "whisper_eps": whisper,
            "consensus_eps": consensus,
            "delta": round(delta, 4) if delta is not None else None,
            "delta_pct": round(delta_pct, 1) if delta_pct is not None else None,
            "verdict": verdict,
            "earnings_date": date_match.group(1) if date_match else None,
        }
        _write_cache(ticker, result)
        return result
    except Exception as e:
        result = {"_error": f"{type(e).__name__}: {e}"}
        _write_cache(ticker, result)
        return result


EARNINGS_CATALYST_KEYS = {
    "earnings_bmo_tomorrow", "earnings_amc_today", "earnings_imminent_5_9d",
    "earnings_lead_up_10_15d", "earnings_peak_iv_3_4d",
}


def apply_earnings_whisper(picks, max_picks=15, verbose=False):
    if not picks:
        return
    enriched = 0
    for p in picks[:max_picks]:
        try:
            cats = p.get("catalysts") or []
            has_earnings_soon = any(
                isinstance(c, dict) and c.get("key") in EARNINGS_CATALYST_KEYS for c in cats
            )
            if not has_earnings_soon:
                continue
            ticker = p.get("ticker", "")
            if not ticker:
                continue
            w = fetch_whisper(ticker)
            if w and "_error" not in w:
                p["_earnings_whisper"] = w
                enriched += 1
        except Exception:
            continue
    if verbose:
        print(f"  earnings_whisper: pulled whisper numbers for {enriched} picks with imminent earnings")
