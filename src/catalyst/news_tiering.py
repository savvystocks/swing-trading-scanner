SOURCE_TIERS = {
    "reuters": 1, "bloomberg": 1, "wall street journal": 1, "wsj": 1,
    "financial times": 1, "ft.com": 1, "barron's": 1, "the economist": 1,
    "associated press": 1, "ap news": 1, "bbc": 1,
    "cnbc": 2, "marketwatch": 2, "yahoo finance": 2, "yahoo": 2,
    "fortune": 2, "forbes": 2, "business insider": 2,
    "seeking alpha": 3, "motley fool": 3, "investorplace": 3, "thestreet": 3,
    "benzinga": 3, "stocktitan": 3, "guru focus": 3, "simply wall st": 3,
    "barchart": 3, "tipranks": 3,
}


def tier_source(source):
    if not source:
        return 4
    s = source.lower()
    for key, tier in SOURCE_TIERS.items():
        if key in s:
            return tier
    return 4


def score_news_quality(headlines):
    if not headlines:
        return {"avg_source_tier": 4, "tier_1_count": 0, "novelty_score": 0, "story_count": 0}
    tiers = []
    titles_seen = set()
    novel_count = 0
    for h in headlines:
        if not isinstance(h, dict):
            continue
        source = h.get("source") or ""
        title = (h.get("title") or "").strip().lower()
        normalized = title[:60]
        if normalized in titles_seen:
            continue
        titles_seen.add(normalized)
        novel_count += 1
        tiers.append(tier_source(source))
    if not tiers:
        return {"avg_source_tier": 4, "tier_1_count": 0, "novelty_score": 0, "story_count": 0}
    return {
        "avg_source_tier": round(sum(tiers) / len(tiers), 1),
        "tier_1_count": sum(1 for t in tiers if t == 1),
        "tier_2_count": sum(1 for t in tiers if t == 2),
        "story_count": len(tiers),
        "novelty_score": round(novel_count / max(len(headlines), 1) * 100, 0),
    }


def enrich_news_quality(candidates, verbose=False):
    for s in candidates:
        news = s.get("news") or {}
        headlines = news.get("headlines") or []
        result = score_news_quality(headlines)
        news["quality"] = result
        s["news"] = news
    if verbose:
        tier1 = sum(1 for s in candidates if ((s.get("news") or {}).get("quality") or {}).get("tier_1_count", 0) >= 1)
        print(f"  news_tiering: {tier1} candidates with Tier-1 source coverage")
    return candidates
