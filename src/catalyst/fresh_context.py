"""Pre-fetch fresh context for the LLM without paying for Anthropic web search.

For top-N tradeable picks, we pull recent news + filings + analyst signals
from sources we already have API access to (Alpaca news, EDGAR RSS,
EODHD news), then bundle them into the prompt context. The LLM gets
'web-search-like' freshness for free instead of $1.16/call.

Data sources:
- Alpaca news API (free): last 7 days of headlines per ticker
- EDGAR RSS (free): recent 8-K, 13D, Form 4 filings (already polled hourly)
- EODHD news (paid, already in subscription): up to 50 recent items
"""

import os
from datetime import datetime, timedelta


def fetch_alpaca_news(ticker, days_back=7, limit=10):
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        return []
    try:
        from alpaca.data.historical.news import NewsClient
        from alpaca.data.requests import NewsRequest
    except ImportError:
        return []
    try:
        client = NewsClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
        start = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        req = NewsRequest(symbols=ticker, start=start, limit=limit, sort="desc")
        resp = client.get_news(req)
        items = []
        for n in (resp.data.get("news") or [])[:limit]:
            try:
                items.append({
                    "headline": (n.headline or "")[:200],
                    "summary": (n.summary or "")[:300],
                    "source": n.source or "",
                    "url": n.url or "",
                    "published": n.created_at.isoformat() if hasattr(n, "created_at") and n.created_at else "",
                })
            except Exception:
                continue
        return items
    except Exception:
        return []


def extract_eodhd_news_from_pick(pick, limit=8):
    raw_news = pick.get("news") or {}
    if not raw_news:
        return []
    headlines = raw_news.get("headlines") or raw_news.get("items") or []
    if not headlines:
        return []
    items = []
    for h in headlines[:limit]:
        if isinstance(h, dict):
            items.append({
                "headline": (h.get("title") or h.get("headline") or "")[:200],
                "summary": (h.get("content") or h.get("summary") or "")[:300],
                "source": h.get("source") or "EODHD",
                "published": h.get("date") or h.get("publishedDate") or "",
            })
    return items


def collect_fresh_context(pick, eodhd_client=None, days_back=7):
    ticker = pick.get("ticker", "")
    if not ticker:
        return {}

    alpaca_items = fetch_alpaca_news(ticker, days_back=days_back, limit=8)
    eodhd_items = extract_eodhd_news_from_pick(pick, limit=8)

    edgar_filings = []
    edgar_signals = pick.get("_edgar_filings") or pick.get("edgar_filings") or []
    for f in (edgar_signals or [])[:5]:
        if isinstance(f, dict):
            edgar_filings.append({
                "form_type": f.get("form_type") or f.get("type") or "",
                "filed": f.get("date") or f.get("filed_date") or "",
                "match": (f.get("match") or f.get("label") or "")[:100],
            })

    return {
        "alpaca_news_7d": alpaca_items,
        "eodhd_news": eodhd_items,
        "edgar_filings": edgar_filings,
        "context_fetched_at": datetime.utcnow().isoformat(),
    }


def format_for_prompt(fresh):
    if not fresh:
        return "(no fresh context available)"

    parts = []
    parts.append(f"FRESH CONTEXT (pre-fetched {fresh.get('context_fetched_at', '?')[:19]}):")

    alpaca = fresh.get("alpaca_news_7d") or []
    if alpaca:
        parts.append(f"\nNEWS HEADLINES (Alpaca, last 7 days):")
        for n in alpaca[:6]:
            parts.append(f"- [{n['published'][:10]}] {n['headline']}")
            if n.get("summary"):
                parts.append(f"  {n['summary'][:180]}")

    eodhd = fresh.get("eodhd_news") or []
    if eodhd:
        parts.append(f"\nADDITIONAL NEWS (EODHD):")
        for n in eodhd[:4]:
            parts.append(f"- {n['headline']}")

    edgar = fresh.get("edgar_filings") or []
    if edgar:
        parts.append(f"\nRECENT SEC FILINGS:")
        for f in edgar[:5]:
            parts.append(f"- {f['filed']} {f['form_type']}: {f['match']}")

    return "\n".join(parts) if parts else "(no fresh context)"


def apply_fresh_context(picks, max_picks=10, verbose=False):
    if not picks:
        return
    enriched = 0
    for p in picks[:max_picks]:
        try:
            fresh = collect_fresh_context(p)
            if fresh and (fresh.get("alpaca_news_7d") or fresh.get("eodhd_news") or fresh.get("edgar_filings")):
                p["_fresh_context"] = fresh
                enriched += 1
        except Exception as e:
            if verbose:
                print(f"  fresh_context fail {p.get('ticker')}: {type(e).__name__}: {e}")
    if verbose:
        print(f"  fresh_context: enriched {enriched}/{min(max_picks, len(picks))} picks with live news + filings")
