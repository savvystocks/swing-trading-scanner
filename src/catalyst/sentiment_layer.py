import os
import re
import json
import time
import pathlib
import logging
from collections import Counter
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SENTIMENT_CACHE = CACHE_DIR / "sentiment_buzz.json"
SENTIMENT_TTL_SECONDS = 6 * 3600

REDDIT_UA = "swing-trading-scanner/1.0 by savvastgeorgiou"
SUBREDDITS = ["wallstreetbets", "stocks", "options"]
BUZZ_THRESHOLD_MENTIONS = 5
STOCKTWITS_TRENDING_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"

TICKER_RE_CASHTAG = re.compile(r"\$([A-Z]{1,5})\b")
TICKER_RE_PLAIN = re.compile(r"(?:^|\s|\()([A-Z]{3,5})(?=\s|$|[\.\,\!\?\:\;\)])")
UNIVERSE_PATH = PROJECT_ROOT / "data" / "universe" / "universe.json"

ENGLISH_STOPLIST = {
    "ON", "OFF", "FOR", "AS", "IS", "IT", "AT", "BE", "OR", "TO", "OF", "IN",
    "AN", "SO", "NO", "GO", "DO", "BY", "MY", "WE", "US", "HE", "ME", "AM", "PM",
    "AND", "BUT", "NOT", "ALL", "OUT", "ANY", "ARE", "WAS", "HAD", "HAS", "GET", "GOT", "PUT", "CAN", "BIG",
    "WAY", "WHY", "HOW", "NEW", "OLD", "YOU", "DAY", "NOW", "TWO", "ONE", "ITS", "OUR", "HIM", "HER", "WHO",
    "OWN", "TOO", "AGO", "TOP", "LOW", "OFF", "WIN", "BUY", "RUN", "DUE", "USE", "SAY", "LET", "YET", "BAD",
    "FIVE", "FOUR", "MOON", "GAIN", "LOSE", "WANT", "HOLD", "TIME", "MAKE", "DEAL", "BANK", "PLAY", "HIGH",
    "GOOD", "ONLY", "DOWN", "OPEN", "SOLD", "RISE", "FELL", "STOP", "EVEN", "REAL", "WELL", "MUCH", "MOST",
    "ABOUT", "AFTER", "AGAIN", "BEING", "EVERY", "FIRST", "GOING", "GREAT", "GROUP", "HOUSE", "MIGHT", "MONEY",
    "NEVER", "OTHER", "PRICE", "RIGHT", "SINCE", "STILL", "STOCK", "THERE", "THESE", "THINK", "WORTH", "WOULD",
    "WSB", "DD", "TLDR", "FUD", "FOMO", "YOLO", "ATH", "ATL", "EPS", "PE", "EV", "FCF", "USD",
    "CEO", "CFO", "COO", "CTO", "IPO", "ETF", "FED", "FOMC", "CPI", "PPI", "GDP", "TIPS",
    "POST", "NEXT", "CASH", "FAST", "BOOM", "JUMP", "DROP", "RUSH", "RISK", "EARN", "LOSS", "GAIN",
    "TRUE", "FALSE", "FREE", "RARE", "FOUR", "FIVE", "JUST", "EVER", "OVER", "UNDER", "INTO", "ONTO",
    "BACK", "NEXT", "MORE", "LESS", "VERY", "SAME", "HUGE", "LONG", "SHORT", "FULL", "HALF", "NEAR",
}


def _is_likely_ticker(s):
    if not s or len(s) < 2 or len(s) > 5:
        return False
    if s in ENGLISH_STOPLIST:
        return False
    return True

_universe_cache = None


def _load_universe_tickers():
    global _universe_cache
    if _universe_cache is not None:
        return _universe_cache
    try:
        with open(UNIVERSE_PATH) as f:
            universe = json.load(f)
        _universe_cache = {row["ticker"].split(".")[0] for row in universe if isinstance(row, dict) and row.get("ticker")}
    except Exception:
        _universe_cache = set()
    return _universe_cache


def _load_cache():
    if not SENTIMENT_CACHE.exists():
        return None
    try:
        with open(SENTIMENT_CACHE) as f:
            data = json.load(f)
        age = time.time() - data.get("cached_at", 0)
        if age < SENTIMENT_TTL_SECONDS:
            return data
    except Exception:
        pass
    return None


def _save_cache(data):
    data["cached_at"] = time.time()
    try:
        with open(SENTIMENT_CACHE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _extract_tickers(text):
    if not text:
        return []
    universe = _load_universe_tickers()
    candidates = []
    text_upper = text.upper()

    for m in TICKER_RE_CASHTAG.finditer(text_upper):
        tk = m.group(1)
        if _is_likely_ticker(tk) and tk in universe:
            candidates.append(tk)

    for m in TICKER_RE_PLAIN.finditer(text_upper):
        tk = m.group(1)
        if not _is_likely_ticker(tk):
            continue
        if tk not in universe:
            continue
        candidates.append(tk)

    return candidates


def fetch_reddit_buzz(verbose=False):
    counts = Counter()
    posts_seen = 0
    for sub in SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit=50"
        try:
            r = requests.get(url, headers={"User-Agent": REDDIT_UA}, timeout=10)
            if r.status_code != 200:
                if verbose:
                    print(f"  reddit /r/{sub}: HTTP {r.status_code}")
                continue
            data = r.json()
        except Exception as e:
            if verbose:
                print(f"  reddit /r/{sub} fail: {type(e).__name__}: {e}")
            continue

        for post_wrapper in (data.get("data") or {}).get("children") or []:
            post = post_wrapper.get("data") or {}
            title = post.get("title", "")
            selftext = post.get("selftext", "") or ""
            score = post.get("score", 0)
            comments = post.get("num_comments", 0)
            weight = 1 + min(score / 1000, 3) + min(comments / 100, 2)
            tickers = _extract_tickers(title + " " + selftext[:500])
            for t in set(tickers):
                counts[t] += weight
            posts_seen += 1
        time.sleep(0.5)

    if verbose:
        top10 = counts.most_common(10)
        print(f"  reddit buzz: {posts_seen} posts scanned, top 10: {top10}")
    return dict(counts), posts_seen


def fetch_stocktwits_trending(verbose=False):
    try:
        r = requests.get(STOCKTWITS_TRENDING_URL, timeout=10)
        if r.status_code != 200:
            if verbose:
                print(f"  stocktwits trending: HTTP {r.status_code}")
            return {}
        data = r.json()
    except Exception as e:
        if verbose:
            print(f"  stocktwits trending fail: {type(e).__name__}: {e}")
        return {}

    symbols = data.get("symbols") or []
    out = {}
    for i, s in enumerate(symbols[:30]):
        tk = s.get("symbol", "")
        if not tk:
            continue
        out[tk.upper()] = max(0, 30 - i)
    if verbose:
        print(f"  stocktwits trending: {len(out)} symbols (top 5: {list(out.keys())[:5]})")
    return out


def gather_sentiment_buzz(verbose=False):
    cached = _load_cache()
    if cached:
        if verbose:
            print(f"  sentiment buzz: cache hit ({(time.time() - cached.get('cached_at', 0)) / 60:.0f}min old)")
        return cached

    reddit_counts, posts_seen = fetch_reddit_buzz(verbose=verbose)
    st_trending = fetch_stocktwits_trending(verbose=verbose)

    combined = {}
    all_tickers = set(reddit_counts.keys()) | set(st_trending.keys())
    for t in all_tickers:
        reddit_score = reddit_counts.get(t, 0)
        st_score = st_trending.get(t, 0)
        combined_score = reddit_score + (st_score * 0.5)
        combined[t] = {
            "reddit": round(reddit_score, 1),
            "stocktwits": round(st_score, 1),
            "combined": round(combined_score, 1),
        }

    out = {
        "tickers": combined,
        "reddit_posts_scanned": posts_seen,
        "stocktwits_count": len(st_trending),
        "buzz_threshold": BUZZ_THRESHOLD_MENTIONS,
    }
    _save_cache(out)
    if verbose:
        top10 = sorted(combined.items(), key=lambda kv: -kv[1]["combined"])[:10]
        print(f"  sentiment buzz top 10: {[(t, s['combined']) for t, s in top10]}")
    return out


def apply_sentiment_buzz_catalyst(candidates, verbose=False):
    if not candidates:
        return

    try:
        buzz_data = gather_sentiment_buzz(verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  sentiment buzz fetch failed (non-fatal): {type(e).__name__}: {e}")
        return

    tickers_buzz = buzz_data.get("tickers", {})
    added = 0
    for c in candidates:
        ticker = c.get("ticker")
        if not ticker:
            continue
        buzz = tickers_buzz.get(ticker.upper())
        if not buzz:
            continue
        combined_score = buzz.get("combined", 0)
        if combined_score < BUZZ_THRESHOLD_MENTIONS:
            continue
        existing_cats = c.get("catalysts") or []
        existing_keys = {cat.get("key") for cat in existing_cats if isinstance(cat, dict)}
        if "cohort_retail_buzz" in existing_keys:
            continue
        existing_cats.append({
            "key": "cohort_retail_buzz",
            "tier": "C",
            "label": f"Retail buzz cohort (Reddit {buzz['reddit']}, StockTwits {buzz['stocktwits']})",
            "score": combined_score,
        })
        c["catalysts"] = existing_cats
        c["_retail_buzz_score"] = combined_score
        added += 1
    if verbose:
        print(f"  sentiment_buzz: tagged {added} candidates with cohort_retail_buzz")
