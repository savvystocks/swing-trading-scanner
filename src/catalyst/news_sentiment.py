import re


BULLISH_TERMS = {
    "beat", "beats", "exceeds", "exceeded", "raised", "upgrades", "upgraded",
    "outperform", "strong buy", "buy rating", "record", "growth", "expansion",
    "approves", "approved", "fda approval", "breakthrough", "partnership",
    "acquisition", "merger", "buyback", "dividend hike", "positive data",
    "positive results", "phase 3 success", "phase 2 success", "topline beat",
    "guidance raised", "raises forecast", "stronger than expected", "soared",
    "rally", "surged", "jumped", "rallied",
}
BEARISH_TERMS = {
    "misses", "missed", "miss", "downgrade", "downgraded", "underperform",
    "sell rating", "lowered", "cut", "cuts", "warns", "warning", "concern",
    "investigation", "lawsuit", "fraud", "restate", "restatement",
    "delisting", "going concern", "dilution", "offering", "secondary",
    "ceo steps down", "ceo resigns", "cfo resigns", "auditor resigns",
    "fda rejects", "fda crl", "complete response letter", "phase 3 fails",
    "phase 2 fails", "missed primary endpoint", "trial halted", "recall",
    "subpoena", "sec inquiry", "guidance cut", "lowered forecast",
    "weaker than expected", "plunged", "crashed", "tumbled", "slid",
    "tanked", "selloff",
}


def score_headline_text(text):
    if not text:
        return 0.0
    t = text.lower()
    bull = 0
    bear = 0
    for term in BULLISH_TERMS:
        if term in t:
            bull += 1
    for term in BEARISH_TERMS:
        if term in t:
            bear += 1
    if bull == 0 and bear == 0:
        return 0.0
    return (bull - bear) / (bull + bear)


def compute_pick_sentiment(pick):
    news = pick.get("news") or {}
    headlines = []
    if isinstance(news, dict):
        headlines = news.get("headlines") or news.get("recent") or []
    elif isinstance(news, list):
        headlines = news
    if not headlines:
        return None

    scores = []
    for h in headlines[:30]:
        if isinstance(h, dict):
            title = h.get("title") or h.get("headline") or ""
        else:
            title = str(h)
        s = score_headline_text(title)
        if s != 0.0:
            scores.append(s)

    if not scores:
        return {
            "avg_sentiment": 0.0,
            "n_scored": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "verdict": "neutral",
        }

    avg = sum(scores) / len(scores)
    bull_n = sum(1 for s in scores if s > 0)
    bear_n = sum(1 for s in scores if s < 0)

    if avg > 0.4:
        verdict = "strongly_bullish"
    elif avg > 0.1:
        verdict = "bullish"
    elif avg > -0.1:
        verdict = "neutral"
    elif avg > -0.4:
        verdict = "bearish"
    else:
        verdict = "strongly_bearish"

    return {
        "avg_sentiment": round(avg, 2),
        "n_scored": len(scores),
        "bullish_count": bull_n,
        "bearish_count": bear_n,
        "verdict": verdict,
    }


def apply_news_sentiment(candidates, verbose=False):
    if not candidates:
        return
    enriched = 0
    for c in candidates:
        try:
            sent = compute_pick_sentiment(c)
            if sent and sent["n_scored"] > 0:
                existing = c.get("_news_quality") or {}
                existing.update(sent)
                c["_news_quality"] = existing
                enriched += 1
        except Exception:
            continue
    if verbose:
        print(f"  news_sentiment: scored {enriched} picks via keyword model")
