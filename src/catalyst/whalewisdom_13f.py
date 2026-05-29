"""WhaleWisdom 13F tracker — free hedge fund position changes scraper.

whalewisdom.com publishes free stock pages showing recent hedge fund 13F
filings: which funds added the stock, dropped it, or increased/decreased
positions in the latest quarterly filing.

This is a SLOW signal (quarterly, 45-day lag) but useful for confirming
that smart money is positioning in a name — particularly when 3+ top-tier
funds added simultaneously.

Cached 7 days since 13F data only changes quarterly.
"""

import json
import os
import re
import time

import requests


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "cache_ww")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_DAYS = 7

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"


def _cache_path(ticker):
    safe = "".join(c if c.isalnum() else "_" for c in ticker)[:30]
    return os.path.join(CACHE_DIR, f"{safe}.json")


def _read_cache(ticker):
    p = _cache_path(ticker)
    if not os.path.exists(p):
        return None
    age_days = (time.time() - os.path.getmtime(p)) / 86400
    if age_days > CACHE_TTL_DAYS:
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


def fetch_13f_summary(ticker):
    cached = _read_cache(ticker)
    if cached is not None:
        return cached

    url = f"https://whalewisdom.com/stock/{ticker.lower()}"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if r.status_code != 200:
            return None
        html = r.text
    except Exception:
        return None

    holders_match = re.search(r"(?:Holders?|Number of Funds)[^<]*?<[^>]*?>\s*([\d,]+)", html, re.IGNORECASE | re.DOTALL)
    new_match = re.search(r"New Position[s]?[^<]*?<[^>]*?>\s*([\d,]+)", html, re.IGNORECASE | re.DOTALL)
    closed_match = re.search(r"(?:Closed Position[s]?|Sold Out)[^<]*?<[^>]*?>\s*([\d,]+)", html, re.IGNORECASE | re.DOTALL)
    increased_match = re.search(r"(?:Added|Increased)[^<]*?<[^>]*?>\s*([\d,]+)", html, re.IGNORECASE | re.DOTALL)
    decreased_match = re.search(r"(?:Reduced|Decreased)[^<]*?<[^>]*?>\s*([\d,]+)", html, re.IGNORECASE | re.DOTALL)

    def _parse(m):
        if not m:
            return None
        try:
            return int(m.group(1).replace(",", ""))
        except (ValueError, AttributeError):
            return None

    holders = _parse(holders_match)
    new_positions = _parse(new_match)
    closed_positions = _parse(closed_match)
    increased = _parse(increased_match)
    decreased = _parse(decreased_match)

    if all(v is None for v in (holders, new_positions, closed_positions, increased, decreased)):
        result = None
    else:
        net_funds_added = (new_positions or 0) - (closed_positions or 0)
        net_position_change = (increased or 0) - (decreased or 0)

        if (new_positions or 0) >= 5 and (closed_positions or 0) < (new_positions or 0):
            verdict = "FUND_ACCUMULATION"
            score = 70
        elif net_funds_added >= 3:
            verdict = "MILD_ACCUMULATION"
            score = 55
        elif net_funds_added <= -3:
            verdict = "FUND_DISTRIBUTION"
            score = 20
        else:
            verdict = "NEUTRAL"
            score = 50

        result = {
            "verdict": verdict,
            "score": score,
            "total_holders": holders,
            "new_positions": new_positions,
            "closed_positions": closed_positions,
            "increased_positions": increased,
            "decreased_positions": decreased,
            "net_funds_added": net_funds_added,
            "net_position_change": net_position_change,
        }
    _write_cache(ticker, result)
    return result


def apply_whalewisdom(picks, max_picks=15, verbose=False):
    if not picks:
        return
    enriched = 0
    accum = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker", "")
        if not ticker or "." in ticker:
            continue
        try:
            ww = fetch_13f_summary(ticker)
            if ww and ww.get("verdict") in ("FUND_ACCUMULATION", "MILD_ACCUMULATION", "FUND_DISTRIBUTION"):
                p["_whalewisdom_13f"] = ww
                enriched += 1
                if ww["verdict"] == "FUND_ACCUMULATION":
                    accum += 1
            time.sleep(0.8)
        except Exception:
            continue
    if verbose:
        print(f"  whalewisdom_13f: enriched {enriched} picks, {accum} FUND_ACCUMULATION")
