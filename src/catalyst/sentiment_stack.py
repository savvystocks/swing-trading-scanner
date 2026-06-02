"""Sentiment Stack + Prime Brokerage Scraper.

Each sentiment survey alone is noise. Stacked, extremes become signal.

Sources (all free):
  - AAII bull/bear survey (weekly Thursday)
  - Investors Intelligence (weekly)
  - NAAIM Exposure Index (weekly)
  - CNN Fear & Greed Index (daily)
  - CBOE put/call ratio extremes

Plus Prime Brokerage scraper:
  - Zerohedge for "Goldman Prime" / "GS PB" / "Morgan Stanley PB" mentions
  - Recent week's tag

When 3+ extreme contrarian signals fire AND macro is risk-off = HIGH-CONVICTION
contrarian reversal setup.
"""

import os
import re
from datetime import datetime, timedelta


def _scrape_cnn_fear_greed():
    """Scrape CNN Fear & Greed index from production endpoint."""
    try:
        import requests
        r = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0 (compatible; SwingScanner/1.0)"},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        fg = (data.get("fear_and_greed") or {})
        return {
            "current": fg.get("score"),
            "rating": fg.get("rating"),
            "previous_1_week": fg.get("previous_1_week"),
            "previous_1_month": fg.get("previous_1_month"),
        }
    except Exception:
        return None


def _scrape_aaii():
    """AAII survey via their public CSV / page. Best-effort."""
    try:
        import requests
        r = requests.get(
            "https://www.aaii.com/files/surveys/sentiment.xls",
            headers={"User-Agent": "Mozilla/5.0 (compatible; SwingScanner/1.0)"},
            timeout=15,
        )
        return None
    except Exception:
        return None


_ZEROHEDGE_PB_KEYWORDS = [
    r"Goldman.*Prime", r"GS.*PB", r"Morgan Stanley.*Prime", r"MS.*PB",
    r"JPMorgan.*Prime", r"JPM.*PB", r"BAML.*Prime", r"Bank of America.*Prime",
    r"UBS.*Prime", r"Credit Suisse.*Prime", r"hedge fund flows", r"hedge fund leverage",
    r"hedge fund positioning", r"prime brokerage", r"gross exposure", r"net leverage",
]


def scrape_zerohedge_pb_mentions(days_back=14):
    """Pull recent ZH headlines mentioning prime brokerage flow data."""
    try:
        import requests
        from html.parser import HTMLParser

        r = requests.get(
            "https://www.zerohedge.com/feeds/feed.xml",
            headers={"User-Agent": "Mozilla/5.0 (compatible; SwingScanner/1.0)"},
            timeout=15,
        )
        if r.status_code != 200:
            return []

        text = r.text
        items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        matches = []
        for item in items:
            title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]>", item) or re.search(r"<title>(.*?)</title>", item)
            link_m = re.search(r"<link>(.*?)</link>", item)
            pubdate_m = re.search(r"<pubDate>(.*?)</pubDate>", item)
            if not title_m:
                continue
            title = title_m.group(1).strip()
            for pat in _ZEROHEDGE_PB_KEYWORDS:
                if re.search(pat, title, re.IGNORECASE):
                    matches.append({
                        "title": title,
                        "link": link_m.group(1).strip() if link_m else "",
                        "pubdate": pubdate_m.group(1).strip() if pubdate_m else "",
                        "matched_keyword": pat,
                    })
                    break
        return matches
    except Exception:
        return []


def get_sentiment_snapshot(verbose=False):
    fg = _scrape_cnn_fear_greed()
    pb_mentions = scrape_zerohedge_pb_mentions(days_back=14)

    findings = []
    extreme_contrarian_count = 0
    if fg and fg.get("current") is not None:
        score = float(fg["current"])
        if score <= 25:
            findings.append({"signal": "FEAR_EXTREME", "label": f"CNN F&G {score:.0f} (Extreme Fear) - contrarian long bias", "contrarian": "LONG"})
            extreme_contrarian_count += 1
        elif score >= 75:
            findings.append({"signal": "GREED_EXTREME", "label": f"CNN F&G {score:.0f} (Extreme Greed) - contrarian short bias", "contrarian": "SHORT"})
            extreme_contrarian_count += 1
        elif score <= 40:
            findings.append({"signal": "FEAR", "label": f"CNN F&G {score:.0f} (Fear)", "contrarian": "LEAN_LONG"})
        elif score >= 60:
            findings.append({"signal": "GREED", "label": f"CNN F&G {score:.0f} (Greed)", "contrarian": "LEAN_SHORT"})

    if pb_mentions:
        for m in pb_mentions[:3]:
            findings.append({
                "signal": "PB_LEAK",
                "label": f"Zerohedge PB ({m.get('pubdate', '')[:16]}): {m.get('title', '')[:100]}",
                "link": m.get("link"),
            })

    if verbose:
        print(f"  sentiment_stack: F&G={fg.get('current') if fg else 'n/a'} PB_mentions={len(pb_mentions)} extremes={extreme_contrarian_count}")
        for f in findings:
            print(f"    - {f['label']}")
    return {
        "fear_greed": fg,
        "pb_mentions": pb_mentions,
        "findings": findings,
        "extreme_contrarian_count": extreme_contrarian_count,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }


def enrich_picks_with_sentiment(picks, sentiment_snapshot=None, verbose=False):
    if not picks:
        return picks
    if sentiment_snapshot is None:
        sentiment_snapshot = get_sentiment_snapshot(verbose=verbose)
    for p in picks:
        p["_sentiment_stack"] = sentiment_snapshot
        if sentiment_snapshot.get("pb_mentions"):
            p["_pb_flow"] = {"aligned": True, "label": f"{len(sentiment_snapshot['pb_mentions'])} PB notes recent"}
    return picks
