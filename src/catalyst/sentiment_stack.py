"""Sentiment Stack + Prime Brokerage Scraper.

Each sentiment survey alone is noise. Stacked, extremes become signal.

Sources (all free):
  - AAII bull/bear survey (weekly Thursday)
  - Investors Intelligence (weekly)
  - NAAIM Exposure Index (weekly)
  - CNN Fear & Greed Index (daily, scrape works)
  - CBOE put/call ratio extremes (via options_positioning)

Data ingestion priority (each survey):
  1. JSON sidecar at data/sentiment/aaii_naaim.json (manual or Gmail-pumped)
  2. Live scrape attempt (often blocked by Incapsula / Cloudflare)
  3. Fall through to None (non-blocking, signal just doesn't fire)

The JSON sidecar can be updated weekly by:
  - Running scripts/sync_sentiment_from_gmail.py (parses AAII/NAAIM subscription
    emails out of your Gmail inbox and writes the JSON automatically)
  - Manual edit (paste the weekly survey numbers in)

Plus Prime Brokerage scraper:
  - Zerohedge for "Goldman Prime" / "GS PB" / "Morgan Stanley PB" mentions
  - Recent week's tag

When 2+ extreme contrarian signals fire AND macro is risk-off = HIGH-CONVICTION
contrarian reversal setup (STACKED_FEAR_EXTREME / STACKED_GREED_EXTREME).
"""

import json
import os
import pathlib
import re
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
SENTIMENT_SIDECAR_PATH = PROJECT_ROOT / "data" / "sentiment" / "aaii_naaim.json"


def _load_sidecar():
    """Load manual / Gmail-pumped sentiment data from JSON sidecar.

    Expected schema:
      {
        "aaii": {"bullish": 31.2, "bearish": 38.5, "neutral": 30.3, "week_ending": "2026-05-28"},
        "naaim": {"exposure_pct": 72.4, "week_ending": "2026-05-28"},
        "investors_intelligence": {"bull_pct": 56.0, "bear_pct": 21.0, "week_ending": "2026-05-27"},
        "updated_at": "2026-06-01T15:00:00Z",
        "source": "gmail_filter" | "manual"
      }

    Returns dict or None.
    """
    if not SENTIMENT_SIDECAR_PATH.exists():
        return None
    try:
        with open(SENTIMENT_SIDECAR_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        # Validate freshness - older than 30 days = stale, ignore
        updated = data.get("updated_at")
        if updated:
            try:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00")).replace(tzinfo=None)
                if (datetime.utcnow() - ts).days > 30:
                    return None
            except Exception:
                pass
        return data
    except Exception:
        return None


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
    """AAII Investor Sentiment Survey - weekly bull/bear/neutral.

    Priority: JSON sidecar -> live scrape (often 403 due to Incapsula) -> None.
    Returns {bullish, bearish, neutral, bull_minus_bear, week_ending} or None.
    """
    side = _load_sidecar()
    if side and isinstance(side.get("aaii"), dict):
        a = side["aaii"]
        try:
            bull = float(a.get("bullish")) if a.get("bullish") is not None else None
            bear = float(a.get("bearish")) if a.get("bearish") is not None else None
            if bull is not None and bear is not None:
                neut = float(a.get("neutral")) if a.get("neutral") is not None else (100 - bull - bear)
                return {
                    "bullish": bull,
                    "bearish": bear,
                    "neutral": neut,
                    "bull_minus_bear": round(bull - bear, 1),
                    "week_ending": a.get("week_ending"),
                    "source": "sidecar:" + (side.get("source") or "manual"),
                }
        except (TypeError, ValueError):
            pass

    # Live scrape fallback - AAII has Incapsula bot protection, this usually fails.
    try:
        import requests
        r = requests.get(
            "https://www.aaii.com/sentimentsurvey",
            headers={"User-Agent": "Mozilla/5.0 (compatible; SwingScanner/1.0)"},
            timeout=15,
        )
        if r.status_code == 200:
            html = r.text
            bull_m = re.search(r"Bullish[^0-9]*([0-9]+\.?[0-9]*)\s*%", html)
            bear_m = re.search(r"Bearish[^0-9]*([0-9]+\.?[0-9]*)\s*%", html)
            neut_m = re.search(r"Neutral[^0-9]*([0-9]+\.?[0-9]*)\s*%", html)
            if bull_m and bear_m:
                bull = float(bull_m.group(1))
                bear = float(bear_m.group(1))
                neut = float(neut_m.group(1)) if neut_m else (100 - bull - bear)
                return {
                    "bullish": bull,
                    "bearish": bear,
                    "neutral": neut,
                    "bull_minus_bear": round(bull - bear, 1),
                    "week_ending": None,
                    "source": "live:aaii.com",
                }
    except Exception:
        pass
    return None


def _scrape_naaim():
    """NAAIM Exposure Index - weekly Wednesday mean active manager exposure %.

    Range 0-200 (100 = fully long). Extreme readings:
      <30 = extreme defensive (contrarian bullish)
      >100 = extreme aggressive (contrarian bearish)

    Priority: JSON sidecar -> live scrape (often gated) -> None.
    """
    side = _load_sidecar()
    if side and isinstance(side.get("naaim"), dict):
        n = side["naaim"]
        try:
            exp = float(n.get("exposure_pct")) if n.get("exposure_pct") is not None else None
            if exp is not None and 0 <= exp <= 200:
                return {
                    "exposure_pct": exp,
                    "week_ending": n.get("week_ending"),
                    "source": "sidecar:" + (side.get("source") or "manual"),
                }
        except (TypeError, ValueError):
            pass

    # Live scrape fallback - naaim.org and known mirrors are gated, usually 4xx.
    try:
        import requests
        r = requests.get(
            "https://www.naaim.org/programs/naaim-exposure-index/",
            headers={"User-Agent": "Mozilla/5.0 (compatible; SwingScanner/1.0)"},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        html = r.text
        m = re.search(r"NAAIM[\s\S]{0,200}?Exposure Index[\s\S]{0,800}?([0-9]+\.?[0-9]*)\s*</td", html, re.IGNORECASE)
        if not m:
            m = re.search(r"data-naaim[\"']?\s*[:=]\s*[\"']?([0-9]+\.?[0-9]*)", html)
        if m:
            try:
                value = float(m.group(1))
                if 0 <= value <= 200:
                    return {"exposure_pct": value, "source": "live:naaim.org"}
            except (TypeError, ValueError):
                pass
        return None
    except Exception:
        return None


def _scrape_investors_intelligence():
    """Investors Intelligence bull/bear ratio - paid feed.

    Priority: JSON sidecar -> None (no live scrape - II is behind paywall).
    """
    side = _load_sidecar()
    if side and isinstance(side.get("investors_intelligence"), dict):
        ii = side["investors_intelligence"]
        try:
            bull = float(ii.get("bull_pct")) if ii.get("bull_pct") is not None else None
            bear = float(ii.get("bear_pct")) if ii.get("bear_pct") is not None else None
            if bull is not None and bear is not None:
                return {
                    "bull_pct": bull,
                    "bear_pct": bear,
                    "week_ending": ii.get("week_ending"),
                    "source": "sidecar:" + (side.get("source") or "manual"),
                }
        except (TypeError, ValueError):
            pass
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
    aaii = _scrape_aaii()
    naaim = _scrape_naaim()
    ii = _scrape_investors_intelligence()
    pb_mentions = scrape_zerohedge_pb_mentions(days_back=14)

    findings = []
    extreme_contrarian_count = 0
    extreme_count_long = 0
    extreme_count_short = 0

    if fg and fg.get("current") is not None:
        score = float(fg["current"])
        if score <= 25:
            findings.append({"signal": "FEAR_EXTREME", "label": f"CNN F&G {score:.0f} (Extreme Fear) - contrarian long bias", "contrarian": "LONG"})
            extreme_contrarian_count += 1
            extreme_count_long += 1
        elif score >= 75:
            findings.append({"signal": "GREED_EXTREME", "label": f"CNN F&G {score:.0f} (Extreme Greed) - contrarian short bias", "contrarian": "SHORT"})
            extreme_contrarian_count += 1
            extreme_count_short += 1
        elif score <= 40:
            findings.append({"signal": "FEAR", "label": f"CNN F&G {score:.0f} (Fear)", "contrarian": "LEAN_LONG"})
        elif score >= 60:
            findings.append({"signal": "GREED", "label": f"CNN F&G {score:.0f} (Greed)", "contrarian": "LEAN_SHORT"})

    if aaii and aaii.get("bull_minus_bear") is not None:
        spread = aaii["bull_minus_bear"]
        bull = aaii.get("bullish")
        bear = aaii.get("bearish")
        if spread <= -10 or (bear is not None and bear >= 40):
            findings.append({"signal": "AAII_BEAR_EXTREME", "label": f"AAII: bull {bull}% / bear {bear}% (spread {spread}) - retail extreme bearish, contrarian long", "contrarian": "LONG"})
            extreme_contrarian_count += 1
            extreme_count_long += 1
        elif spread >= 25 or (bull is not None and bull >= 50):
            findings.append({"signal": "AAII_BULL_EXTREME", "label": f"AAII: bull {bull}% / bear {bear}% (spread {spread}) - retail extreme bullish, contrarian short", "contrarian": "SHORT"})
            extreme_contrarian_count += 1
            extreme_count_short += 1

    if naaim and naaim.get("exposure_pct") is not None:
        exp = naaim["exposure_pct"]
        if exp <= 30:
            findings.append({"signal": "NAAIM_DEFENSIVE", "label": f"NAAIM exposure {exp:.0f}% - active managers extreme defensive, contrarian long", "contrarian": "LONG"})
            extreme_contrarian_count += 1
            extreme_count_long += 1
        elif exp >= 100:
            findings.append({"signal": "NAAIM_AGGRESSIVE", "label": f"NAAIM exposure {exp:.0f}% - active managers max long, contrarian short", "contrarian": "SHORT"})
            extreme_contrarian_count += 1
            extreme_count_short += 1
        else:
            findings.append({"signal": "NAAIM_MID", "label": f"NAAIM exposure {exp:.0f}% (mid range)", "contrarian": "NEUTRAL"})

    if ii and ii.get("bull_pct") and ii.get("bear_pct"):
        ii_bull = ii["bull_pct"]
        ii_bear = ii["bear_pct"]
        if ii_bull - ii_bear >= 30:
            findings.append({"signal": "II_BULL_EXTREME", "label": f"Investors Intelligence: {ii_bull}% bulls vs {ii_bear}% bears - advisor extreme bullish, contrarian short", "contrarian": "SHORT"})
            extreme_contrarian_count += 1
            extreme_count_short += 1
        elif ii_bear - ii_bull >= 15:
            findings.append({"signal": "II_BEAR_EXTREME", "label": f"Investors Intelligence: {ii_bull}% bulls vs {ii_bear}% bears - advisor extreme bearish, contrarian long", "contrarian": "LONG"})
            extreme_contrarian_count += 1
            extreme_count_long += 1

    if pb_mentions:
        for m in pb_mentions[:3]:
            findings.append({
                "signal": "PB_LEAK",
                "label": f"Zerohedge PB ({m.get('pubdate', '')[:16]}): {m.get('title', '')[:100]}",
                "link": m.get("link"),
            })

    # Stacked extreme signal: when 2+ independent retail/advisor sentiment surveys
    # all point contrarian in the same direction, that's the high-conviction setup.
    if extreme_count_long >= 2:
        findings.append({"signal": "STACKED_FEAR_EXTREME", "label": f"{extreme_count_long} sentiment surveys all extreme fear - high-conviction contrarian LONG setup", "contrarian": "LONG"})
    if extreme_count_short >= 2:
        findings.append({"signal": "STACKED_GREED_EXTREME", "label": f"{extreme_count_short} sentiment surveys all extreme greed - high-conviction contrarian SHORT setup", "contrarian": "SHORT"})

    if verbose:
        print(f"  sentiment_stack: F&G={fg.get('current') if fg else 'n/a'} AAII={aaii.get('bull_minus_bear') if aaii else 'n/a'} "
              f"NAAIM={naaim.get('exposure_pct') if naaim else 'n/a'} II={'live' if ii else 'n/a'} "
              f"PB_mentions={len(pb_mentions)} extremes={extreme_contrarian_count}")
        for f in findings:
            print(f"    - {f['label']}")
    return {
        "fear_greed": fg,
        "aaii": aaii,
        "naaim": naaim,
        "investors_intelligence": ii,
        "pb_mentions": pb_mentions,
        "findings": findings,
        "extreme_contrarian_count": extreme_contrarian_count,
        "extreme_count_long": extreme_count_long,
        "extreme_count_short": extreme_count_short,
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
