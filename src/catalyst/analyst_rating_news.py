"""Detect analyst rating changes by scanning recent news headlines.

We already pull news for top picks via fresh_context (Alpaca + EODHD).
This module scans those headlines for upgrade/downgrade patterns and
quantifies the bullish/bearish lean. Free, no separate API needed.
"""

import re


UPGRADE_PATTERNS = [
    r"\bupgraded?\b",
    r"\bupgrad(?:e|ing)\b",
    r"raised? (?:price )?target",
    r"raises? (?:its )?(?:price )?target",
    r"price target (?:hike|raise|increase)",
    r"\bbuy rating\b",
    r"\b(?:initiated?|starts) (?:with )?(?:buy|outperform|overweight)\b",
    r"\boutperform rating\b",
    r"\boverweight rating\b",
    r"reiterates? (?:buy|outperform|overweight)",
    r"top pick",
]

DOWNGRADE_PATTERNS = [
    r"\bdowngraded?\b",
    r"\bdowngrad(?:e|ing)\b",
    r"cut(?:s)? (?:price )?target",
    r"lowered? (?:price )?target",
    r"price target (?:cut|lower|reduce|reduction)",
    r"\bsell rating\b",
    r"\b(?:initiated?|starts) (?:with )?(?:sell|underperform|underweight)\b",
    r"\bunderperform rating\b",
    r"\bunderweight rating\b",
    r"reiterates? (?:sell|underperform|underweight)",
]


def _count_matches(text, patterns):
    t = (text or "").lower()
    return sum(1 for p in patterns if re.search(p, t))


def scan_news_for_ratings(news_items):
    if not news_items:
        return None
    up_total = 0
    down_total = 0
    up_examples = []
    down_examples = []
    for item in news_items:
        headline = (item.get("headline") or "") + " " + (item.get("summary") or "")
        ups = _count_matches(headline, UPGRADE_PATTERNS)
        downs = _count_matches(headline, DOWNGRADE_PATTERNS)
        if ups > downs and ups > 0:
            up_total += 1
            if len(up_examples) < 3:
                up_examples.append(item.get("headline", "")[:120])
        elif downs > ups and downs > 0:
            down_total += 1
            if len(down_examples) < 3:
                down_examples.append(item.get("headline", "")[:120])

    if up_total + down_total == 0:
        return None

    net = up_total - down_total
    if net >= 2:
        verdict = "UPGRADE_CLUSTER"
    elif net == 1:
        verdict = "BULLISH_LEAN"
    elif net == 0:
        verdict = "MIXED"
    elif net == -1:
        verdict = "BEARISH_LEAN"
    else:
        verdict = "DOWNGRADE_CLUSTER"

    return {
        "verdict": verdict,
        "upgrades_count": up_total,
        "downgrades_count": down_total,
        "net": net,
        "upgrade_examples": up_examples,
        "downgrade_examples": down_examples,
    }


def apply_analyst_rating_news(picks, max_picks=15, verbose=False):
    if not picks:
        return
    counts = {"UPGRADE_CLUSTER": 0, "BULLISH_LEAN": 0, "MIXED": 0, "BEARISH_LEAN": 0, "DOWNGRADE_CLUSTER": 0}
    enriched = 0
    for p in picks[:max_picks]:
        try:
            fresh = p.get("_fresh_context") or {}
            news = (fresh.get("alpaca_news_7d") or []) + (fresh.get("eodhd_news") or [])
            if not news:
                continue
            result = scan_news_for_ratings(news)
            if result:
                p["_analyst_rating_changes"] = result
                counts[result["verdict"]] = counts.get(result["verdict"], 0) + 1
                enriched += 1
        except Exception:
            continue
    if verbose:
        print(f"  analyst_rating_news: enriched {enriched}, "
              f"upgrades={counts['UPGRADE_CLUSTER']+counts['BULLISH_LEAN']} "
              f"downgrades={counts['DOWNGRADE_CLUSTER']+counts['BEARISH_LEAN']}")
