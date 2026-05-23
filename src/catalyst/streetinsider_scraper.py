"""StreetInsider free real-time news feed scraper.

streetinsider.com publishes a free real-time news page with analyst rating
changes, buyback announcements, and guidance changes. We scrape the
categorised pages once per scan and index by ticker, then enrich our picks
with any items found.

Pages we pull:
- /upgrades.php (analyst upgrades)
- /downgrades.php (analyst downgrades)
- /Insider+Trades.php (insider buy/sell large)
- /News/Buybacks.html (buyback announcements)
- /News/Guidance.html (guidance changes)

Cached 30 min.
"""

import json
import os
import re
import time

import requests


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "cache_si")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_MIN = 30

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"


def _cache_path(name):
    return os.path.join(CACHE_DIR, f"{name}.json")


def _read_cache(name):
    p = _cache_path(name)
    if not os.path.exists(p):
        return None
    age_min = (time.time() - os.path.getmtime(p)) / 60
    if age_min > CACHE_TTL_MIN:
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(name, data):
    try:
        with open(_cache_path(name), "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)
    except Exception:
        pass


def _scrape_streetinsider(category):
    """Scrape one StreetInsider news page and return ticker -> headline map."""
    cached = _read_cache(category)
    if cached is not None:
        return cached

    page_urls = {
        "upgrades": "https://www.streetinsider.com/upgrades.php",
        "downgrades": "https://www.streetinsider.com/downgrades.php",
        "buybacks": "https://www.streetinsider.com/News/Buybacks.html",
        "guidance": "https://www.streetinsider.com/News/Guidance.html",
    }
    url = page_urls.get(category)
    if not url:
        return {}

    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if r.status_code != 200:
            return {}
        html = r.text
    except Exception:
        return {}

    by_ticker = {}
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE)
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 3:
            continue
        ticker_match = re.search(r">([A-Z]{1,5})</a>", cells[0]) or re.search(r"\b([A-Z]{2,5})\b", re.sub(r"<[^>]+>", " ", cells[0]))
        if not ticker_match:
            continue
        ticker = ticker_match.group(1).strip().upper()
        if not ticker or not (1 < len(ticker) <= 5):
            continue
        full_text = " ".join(re.sub(r"<[^>]+>", " ", c) for c in cells)
        full_text = re.sub(r"\s+", " ", full_text).strip()[:300]
        if ticker not in by_ticker:
            by_ticker[ticker] = {"category": category, "headline": full_text[:200]}

    _write_cache(category, by_ticker)
    return by_ticker


def apply_streetinsider(picks, verbose=False):
    if not picks:
        return
    upgrades = _scrape_streetinsider("upgrades")
    buybacks = _scrape_streetinsider("buybacks")
    guidance = _scrape_streetinsider("guidance")
    downgrades = _scrape_streetinsider("downgrades")

    enriched = 0
    counts = {"upgrade": 0, "buyback": 0, "guidance": 0, "downgrade": 0}
    for p in picks:
        ticker = (p.get("ticker") or "").upper()
        if not ticker:
            continue
        si = {}
        if ticker in upgrades:
            si["upgrade"] = upgrades[ticker]["headline"]
            counts["upgrade"] += 1
        if ticker in buybacks:
            si["buyback"] = buybacks[ticker]["headline"]
            counts["buyback"] += 1
        if ticker in guidance:
            si["guidance_change"] = guidance[ticker]["headline"]
            counts["guidance"] += 1
        if ticker in downgrades:
            si["downgrade"] = downgrades[ticker]["headline"]
            counts["downgrade"] += 1
        if si:
            p["_streetinsider"] = si
            enriched += 1

    if verbose:
        print(f"  streetinsider: enriched {enriched} picks "
              f"(upgrades={counts['upgrade']}, buybacks={counts['buyback']}, "
              f"guidance={counts['guidance']}, downgrades={counts['downgrade']})")
