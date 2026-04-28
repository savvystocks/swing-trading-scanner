from datetime import datetime, timedelta

POSITIVE_WORDS = {
    "beat", "beats", "exceeds", "exceeded", "raises", "raised", "upgrade", "upgrades",
    "approval", "approved", "breakthrough", "milestone", "win", "wins", "record",
    "surge", "surges", "soars", "rally", "outperform", "buy", "bullish", "strong",
    "strongest", "growth", "expanding", "expansion", "agreement", "partnership",
    "acquisition", "acquires", "buyout", "merger", "ipo", "launch", "launching",
    "patent", "fda", "phase 3", "phase 2", "positive", "successful", "success",
    "profitable", "profit", "earnings beat", "raised guidance", "raised forecast",
    "dividend", "buyback", "repurchase", "innovative", "leader", "leadership",
}

NEGATIVE_WORDS = {
    "miss", "misses", "missed", "loss", "losses", "downgrade", "downgrades",
    "rejection", "rejected", "delay", "delays", "delayed", "investigation",
    "lawsuit", "fraud", "bankruptcy", "bankrupt", "going concern", "default",
    "warning", "warned", "risk", "decline", "declines", "fell", "drop", "drops",
    "weak", "weakness", "concern", "concerns", "below estimates", "below expectations",
    "delisting", "halted", "suspended", "fired", "resigned", "stepping down",
    "subpoena", "settlement", "fine", "penalty", "violation", "missed estimates",
    "guidance cut", "lowered guidance", "reduced", "loss widened",
}


def fetch_recent_news(client, ticker, max_age_days=7, limit=10):
    try:
        news = client.news(ticker, limit=limit)
    except Exception:
        return []
    if not news:
        return []
    cutoff = datetime.utcnow() - timedelta(days=max_age_days)
    out = []
    for item in news:
        date_str = item.get("date") or ""
        try:
            d = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            try:
                d = datetime.strptime(date_str[:10], "%Y-%m-%d")
            except Exception:
                continue
        if d < cutoff:
            continue
        out.append({
            "title": item.get("title") or "",
            "content": (item.get("content") or "")[:500],
            "date": date_str,
            "link": item.get("link") or "",
            "_dt": d,
        })
    out.sort(key=lambda x: x["_dt"], reverse=True)
    return out


def score_sentiment(headlines):
    if not headlines:
        return 0.0, 0, []
    pos = 0
    neg = 0
    matched = []
    for h in headlines[:10]:
        text = f"{h.get('title', '')} {h.get('content', '')}".lower()
        h_pos = sum(1 for w in POSITIVE_WORDS if w in text)
        h_neg = sum(1 for w in NEGATIVE_WORDS if w in text)
        if h_pos > 0 or h_neg > 0:
            matched.append({
                "title": h.get("title", "")[:80],
                "pos": h_pos,
                "neg": h_neg,
            })
        pos += h_pos
        neg += h_neg
    if pos + neg == 0:
        return 0.0, len(headlines), matched
    raw = (pos - neg) / (pos + neg)
    return raw, len(headlines), matched


def news_score(client, ticker_short, eodhd_ticker=None, points_max=15.0):
    full = eodhd_ticker or f"{ticker_short}.US"
    headlines = fetch_recent_news(client, full)
    if not headlines and full.endswith(".US"):
        headlines = fetch_recent_news(client, f"{ticker_short}.LSE")
    raw, count, matched = score_sentiment(headlines)
    points = (raw + 1) / 2 * points_max if count > 0 else 0
    return {
        "points": round(points, 2),
        "raw_sentiment": round(raw, 3),
        "headline_count": count,
        "matched_headlines": matched[:3],
        "headlines": [{"title": h["title"][:120], "date": h["date"][:10]} for h in headlines[:5]],
    }
