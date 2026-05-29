"""EDGAR full-text scanner for high-edge keyword catalysts.

Detects buyback authorizations, guidance raises, and other definite-positive
events from 8-K filings. Uses SEC EDGAR's full-text search API (free,
official, no auth needed).

These catalyst types have strong documented edge:
- Buyback announcement: +5-10% pop typically, mechanical buying for weeks
- Guidance raise: +8-15% pop typically, pre-confirmed positive surprise
- Capital return increase: positive signal
- Spinoff announcement: value-unlocking event
"""

import json
import os
import re
import time

import requests


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "cache_edgar_kw")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_HR = 6

USER_AGENT = "Swing Trading Scanner research@savvystocks.invalid"

BUYBACK_PATTERNS = [
    r"share\s+repurchase\s+program",
    r"stock\s+repurchase\s+program",
    r"authoriz(?:e|ed|es|ing)\s+(?:the\s+)?repurchase",
    r"increase[d]?\s+(?:its\s+)?(?:share\s+)?buyback",
    r"buyback\s+(?:program|authorization)",
    r"approved\s+(?:a\s+)?\$\d+\s*(?:million|billion)\s+(?:share\s+)?repurchase",
]

GUIDANCE_RAISE_PATTERNS = [
    r"rais(?:e[ds]?|ing)\s+(?:full[\s-]?year\s+)?(?:annual\s+)?(?:fiscal\s+\d{4}\s+)?(?:earnings\s+|revenue\s+|sales\s+)?(?:outlook|guidance|forecast|estimates?)",
    r"increases?\s+(?:its\s+)?(?:full[\s-]?year\s+|annual\s+)?(?:guidance|outlook)",
    r"upward\s+revision",
    r"narrows?\s+(?:guidance|outlook)\s+to\s+the\s+(?:high|upper)\s+end",
    r"now\s+expects?\s+(?:revenue|earnings|EPS)\s+(?:of\s+)?\$[\d.]+\s*to\s*\$[\d.]+",
]

SPINOFF_PATTERNS = [
    r"spin[\s-]?off",
    r"separat(?:e|ion)\s+of\s+(?:the\s+)?(?:business|division|segment)",
    r"intent\s+to\s+separate",
]


def _cache_path(ticker, kind):
    safe = "".join(c if c.isalnum() else "_" for c in f"{ticker}_{kind}")[:50]
    return os.path.join(CACHE_DIR, f"{safe}.json")


def _read_cache(ticker, kind):
    p = _cache_path(ticker, kind)
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


def _write_cache(ticker, kind, data):
    try:
        with open(_cache_path(ticker, kind), "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)
    except Exception:
        pass


def search_edgar_full_text(query, ticker=None, days_back=30, max_hits=10):
    """SEC EDGAR full-text search API.

    https://efts.sec.gov/LATEST/search-index?q=...&forms=8-K
    """
    from datetime import datetime, timedelta
    dateRange = "custom"
    end = datetime.utcnow().date()
    start = end - timedelta(days=days_back)

    params = {
        "q": f'"{query}"',
        "forms": "8-K",
        "dateRange": dateRange,
        "startdt": str(start),
        "enddt": str(end),
    }
    if ticker:
        params["ciks"] = ticker

    try:
        r = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        hits = (data.get("hits") or {}).get("hits") or []
        return hits[:max_hits]
    except Exception:
        return []


def detect_buyback_for_ticker(ticker, days_back=30):
    cached = _read_cache(ticker, "buyback")
    if cached is not None:
        return cached
    hits = search_edgar_full_text("share repurchase program", ticker=ticker, days_back=days_back, max_hits=5)
    if hits:
        most_recent = hits[0]
        adsh = (most_recent.get("_source") or {}).get("adsh") or ""
        filed = (most_recent.get("_source") or {}).get("file_date") or ""
        result = {
            "verdict": "BUYBACK_ANNOUNCED",
            "filed_date": filed[:10] if filed else None,
            "filing_id": adsh,
            "score": 75,
        }
    else:
        result = None
    _write_cache(ticker, "buyback", result)
    return result


def detect_guidance_raise_for_ticker(ticker, days_back=14):
    cached = _read_cache(ticker, "guidance")
    if cached is not None:
        return cached
    queries = ["raises full-year guidance", "raises outlook", "increases guidance"]
    best_hit = None
    for q in queries:
        hits = search_edgar_full_text(q, ticker=ticker, days_back=days_back, max_hits=3)
        if hits:
            best_hit = hits[0]
            break
        time.sleep(0.5)
    if best_hit:
        filed = (best_hit.get("_source") or {}).get("file_date") or ""
        result = {
            "verdict": "GUIDANCE_RAISED",
            "filed_date": filed[:10] if filed else None,
            "score": 85,
        }
    else:
        result = None
    _write_cache(ticker, "guidance", result)
    return result


def detect_spinoff_for_ticker(ticker, days_back=60):
    cached = _read_cache(ticker, "spinoff")
    if cached is not None:
        return cached
    hits = search_edgar_full_text("spin-off", ticker=ticker, days_back=days_back, max_hits=3)
    if hits:
        filed = (hits[0].get("_source") or {}).get("file_date") or ""
        result = {
            "verdict": "SPINOFF_ANNOUNCED",
            "filed_date": filed[:10] if filed else None,
            "score": 70,
        }
    else:
        result = None
    _write_cache(ticker, "spinoff", result)
    return result


def apply_edgar_keyword_scanner(picks, max_picks=25, verbose=False):
    if not picks:
        return
    enriched = 0
    counts = {"buyback": 0, "guidance": 0, "spinoff": 0}
    for p in picks[:max_picks]:
        ticker = p.get("ticker", "")
        if not ticker or "." in ticker:
            continue
        try:
            bb = detect_buyback_for_ticker(ticker)
            if bb:
                p["_edgar_buyback"] = bb
                counts["buyback"] += 1
            time.sleep(0.4)
            gd = detect_guidance_raise_for_ticker(ticker)
            if gd:
                p["_edgar_guidance_raise"] = gd
                counts["guidance"] += 1
            time.sleep(0.4)
            if bb or gd:
                enriched += 1
        except Exception:
            continue
    if verbose:
        print(f"  edgar_keyword_scanner: {enriched} picks with new buyback/guidance filings "
              f"(buyback={counts['buyback']}, guidance={counts['guidance']})")
