import re
import pandas as pd


HYPERSCALERS = (
    "microsoft", "amazon", "amazon web services", "aws",
    "google", "alphabet", "google cloud", "gcp",
    "meta", "facebook", "oracle", "oci",
    "nvidia", "nvda", "openai", "anthropic",
    "tesla", "apple", "broadcom",
)

CAPEX_VERBS = (
    "invest", "invests", "invested", "investment",
    "partnership", "partner", "partners", "partnered",
    "customer", "select", "selects", "selected", "chose", "chosen",
    "deploy", "deployed", "deployment", "deploying",
    "purchase", "purchases", "purchased", "purchasing",
    "order", "orders", "ordered",
    "contract", "deal", "agreement", "supply",
    "win", "wins", "won", "design win",
    "expand", "expands", "expanding", "scale", "scaling",
)

BACKLOG_TERMS = (
    "backlog", "order book", "rpo", "remaining performance obligation",
    "order intake", "bookings", "book-to-bill", "book to bill",
    "fully booked", "sold out", "capacity sold",
    "demand exceeds supply", "supply constrained",
)

BACKLOG_VERBS = (
    "record", "all-time high", "all time high",
    "grew", "growing", "grew to", "jumped", "surged",
    "doubled", "tripled", "expanded", "increased", "up",
    "exceeded", "ahead of", "above", "above guidance",
)

STRATEGIC_INVEST_PATTERNS = (
    r"(?:nvidia|microsoft|amazon|google|alphabet|meta|oracle|tesla|apple|openai|anthropic|broadcom)\s+(?:has\s+)?(?:invests?|investing|invested|takes?|taken|taking|acquires?|acquiring|acquired)\s+(?:a\s+)?(?:\$[\d.]+\s*(?:billion|million|b|m)?\s+)?(?:equity|stake|position|interest)?",
    r"\$[\d.]+\s*(?:billion|million|b|m)\s+(?:strategic\s+)?investment\s+(?:from|by)\s+(?:nvidia|microsoft|amazon|google|alphabet|meta|oracle|openai|anthropic|tesla|apple|broadcom)",
    r"strategic\s+investment\s+from\s+(?:nvidia|microsoft|amazon|google|alphabet|meta|oracle|openai|anthropic)",
    r"(?:nvidia|microsoft|amazon|google|alphabet|meta|oracle|openai|anthropic)\s+(?:to\s+)?(?:invest|purchase|buy)\s+\$[\d.]+\s*(?:billion|million)",
)

SPINOFF_PATTERNS = (
    r"\b(?:plans?|intends?|intend|to|will|expects?|announces?|announced|set\s+to|completes?|completed)\s+(?:the\s+)?(?:spin[\s-]?off|spinoff|separation|demerge|demerger)\b",
    r"\b(?:tax[\s-]?free\s+)?(?:spin[\s-]?off|spinoff)\s+(?:of|into|from|completion|completes?|completed|approved)\b",
    r"\bcompletes?\s+(?:the\s+)?separation\b",
    r"\bdemerger\s+(?:approved|completed|filed|effective)\b",
    r"\bbreak[\s-]?up\s+(?:plan|approved|of)\b",
    r"\bcarve[\s-]?out\s+(?:announced|approved|completed|of)\b",
)

CAPEX_DOLLAR_PATTERN = re.compile(
    r"\$[\d.]+\s*(?:billion|million|b|m)\b",
    re.IGNORECASE,
)

PCT_GROWTH_PATTERN = re.compile(
    r"(?:up|grew|increased|jumped|surged|rose|gained)\s+\d+(?:\.\d+)?%",
    re.IGNORECASE,
)


def _texts_from_news(news_items, max_items=30):
    texts = []
    for n in (news_items or [])[:max_items]:
        title = (n.get("title") or "").strip()
        content = (n.get("content") or "")[:600]
        date = n.get("date") or ""
        texts.append({"title": title, "content": content, "date": date, "blob": f"{title} {content}".lower()})
    return texts


def _is_recent(date_str, days=14):
    if not date_str:
        return True
    try:
        d = pd.Timestamp(date_str).tz_localize(None) if pd.Timestamp(date_str).tz else pd.Timestamp(date_str)
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        return d >= cutoff
    except Exception:
        return True


def capex_echo(news_items, lookback_days=14):
    texts = _texts_from_news(news_items)
    hits = []
    hyperscaler_set = set()
    for t in texts:
        if not _is_recent(t["date"], lookback_days):
            continue
        blob = t["blob"]
        matched_hs = [h for h in HYPERSCALERS if h in blob]
        if not matched_hs:
            continue
        verb_hit = any(v in blob for v in CAPEX_VERBS)
        if not verb_hit:
            continue
        dollar_hit = bool(CAPEX_DOLLAR_PATTERN.search(t["title"] + " " + t["content"]))
        for h in matched_hs:
            hyperscaler_set.add(h)
        hits.append({
            "title": t["title"][:120],
            "date": t["date"],
            "hyperscalers": matched_hs[:3],
            "has_dollar_amount": dollar_hit,
        })

    if not hits:
        return {"fired": False, "score": 0, "headline_count": 0, "hyperscalers_named": [], "evidence": []}

    score = 1
    if any(h["has_dollar_amount"] for h in hits):
        score = 2
    if len(hits) >= 2 and len(hyperscaler_set) >= 2:
        score = 3

    return {
        "fired": True,
        "score": score,
        "headline_count": len(hits),
        "hyperscalers_named": sorted(hyperscaler_set)[:5],
        "evidence": hits[:3],
    }


def backlog_surge(news_items, fundamentals, lookback_days=21):
    texts = _texts_from_news(news_items)
    hits = []
    for t in texts:
        if not _is_recent(t["date"], lookback_days):
            continue
        blob = t["blob"]
        backlog_term_hit = any(term in blob for term in BACKLOG_TERMS)
        if not backlog_term_hit:
            continue
        positive_verb = any(v in blob for v in BACKLOG_VERBS)
        pct_match = PCT_GROWTH_PATTERN.search(t["title"] + " " + t["content"])
        if not (positive_verb or pct_match):
            continue
        hits.append({
            "title": t["title"][:120],
            "date": t["date"],
            "pct_match": pct_match.group(0) if pct_match else None,
        })

    revenue_surprise = None
    earnings = (fundamentals or {}).get("Earnings", {}) or {}
    history = earnings.get("History", {}) or {}
    if history:
        recent = sorted(history.items(), reverse=True)[:1]
        if recent:
            row = recent[0][1]
            actual = row.get("epsActual")
            estimate = row.get("epsEstimate")
            if actual is not None and estimate is not None:
                try:
                    actual = float(actual)
                    estimate = float(estimate)
                    if estimate != 0:
                        revenue_surprise = (actual - estimate) / abs(estimate) * 100
                except (TypeError, ValueError):
                    pass

    if not hits and (revenue_surprise is None or revenue_surprise < 5):
        return {"fired": False, "score": 0, "headline_count": 0, "evidence": []}

    score = 0
    if hits:
        score = 1
        if len(hits) >= 2:
            score = 2
        if any("record" in (h["title"] or "").lower() or "all-time" in (h["title"] or "").lower() for h in hits):
            score = 3
    if revenue_surprise is not None and revenue_surprise >= 15:
        score = max(score, 2)
    if revenue_surprise is not None and revenue_surprise >= 25:
        score = 3

    return {
        "fired": score >= 1,
        "score": score,
        "headline_count": len(hits),
        "last_eps_surprise_pct": round(revenue_surprise, 1) if revenue_surprise is not None else None,
        "evidence": hits[:3],
    }


def revision_spike(fundamentals):
    earnings = (fundamentals or {}).get("Earnings", {}) or {}
    trend = earnings.get("Trend", {}) or {}
    if not trend:
        return {"fired": False, "score": 0, "reason": "no Earnings.Trend data"}

    trend_items = sorted(trend.items())
    if not trend_items:
        return {"fired": False, "score": 0, "reason": "empty trend"}
    first_period = trend_items[0][1] or {}

    def _num(v):
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    up_7 = _num(first_period.get("epsRevisionsUpLast7days")) or 0
    up_30 = _num(first_period.get("epsRevisionsUpLast30days")) or 0
    down_7 = _num(first_period.get("epsRevisionsDownLast7days")) or 0
    down_30 = _num(first_period.get("epsRevisionsDownLast30days")) or 0

    eps_now = _num(first_period.get("earningsEstimateAvg"))
    eps_30d_ago = _num(first_period.get("earningsEstimateAvg30daysAgo"))
    eps_60d_ago = _num(first_period.get("earningsEstimateAvg60daysAgo"))
    eps_90d_ago = _num(first_period.get("earningsEstimateAvg90daysAgo"))

    pct_change_30d = None
    pct_change_90d = None
    if eps_now is not None and eps_30d_ago and eps_30d_ago != 0:
        pct_change_30d = (eps_now - eps_30d_ago) / abs(eps_30d_ago) * 100
    if eps_now is not None and eps_90d_ago and eps_90d_ago != 0:
        pct_change_90d = (eps_now - eps_90d_ago) / abs(eps_90d_ago) * 100

    score = 0
    reasons = []

    if pct_change_30d is not None and pct_change_30d >= 40:
        score = 3
        reasons.append(f"EPS estimate +{pct_change_30d:.0f}% in 30d")
    elif pct_change_30d is not None and pct_change_30d >= 20:
        score = max(score, 2)
        reasons.append(f"EPS estimate +{pct_change_30d:.0f}% in 30d")
    elif pct_change_30d is not None and pct_change_30d >= 10:
        score = max(score, 1)
        reasons.append(f"EPS estimate +{pct_change_30d:.0f}% in 30d")

    if up_7 >= 5 and down_7 == 0:
        score = max(score, 3)
        reasons.append(f"{int(up_7)} up-revisions, 0 down in 7d")
    elif up_7 >= 3 and down_7 == 0:
        score = max(score, 2)
        reasons.append(f"{int(up_7)} up-revisions in 7d, no down")
    elif up_30 >= 5 and up_30 > down_30 * 3:
        score = max(score, 2)
        reasons.append(f"{int(up_30)} up vs {int(down_30)} down in 30d")
    elif up_30 >= 2 and down_30 == 0:
        score = max(score, 1)
        reasons.append(f"{int(up_30)} up-revisions in 30d, no down")

    if down_30 > up_30 * 2 and down_30 >= 3:
        score = 0
        reasons = [f"NEGATIVE: {int(down_30)} down-revisions in 30d"]

    return {
        "fired": score >= 1,
        "score": score,
        "up_7d": int(up_7),
        "up_30d": int(up_30),
        "down_7d": int(down_7),
        "down_30d": int(down_30),
        "pct_change_30d": round(pct_change_30d, 1) if pct_change_30d is not None else None,
        "pct_change_90d": round(pct_change_90d, 1) if pct_change_90d is not None else None,
        "reasons": reasons,
    }


def strategic_investment(news_items, lookback_days=30):
    texts = _texts_from_news(news_items)
    hits = []
    for t in texts:
        if not _is_recent(t["date"], lookback_days):
            continue
        blob = t["title"] + " " + t["content"]
        for pattern in STRATEGIC_INVEST_PATTERNS:
            m = re.search(pattern, blob, re.IGNORECASE)
            if m:
                hits.append({
                    "title": t["title"][:120],
                    "date": t["date"],
                    "match": m.group(0)[:80],
                })
                break

    if not hits:
        return {"fired": False, "score": 0, "headline_count": 0, "evidence": []}

    score = 2
    if any(re.search(r"\$[\d.]+\s*billion", h["match"], re.IGNORECASE) for h in hits):
        score = 3
    if len(hits) == 1 and not any(re.search(r"\$[\d.]+", h["match"]) for h in hits):
        score = 1

    return {
        "fired": True,
        "score": score,
        "headline_count": len(hits),
        "evidence": hits[:3],
    }


def spinoff_catalyst(news_items, fundamentals, lookback_days=120):
    texts = _texts_from_news(news_items, max_items=50)
    hits = []
    for t in texts:
        if not _is_recent(t["date"], lookback_days):
            continue
        blob = t["title"] + " " + t["content"]
        for pattern in SPINOFF_PATTERNS:
            m = re.search(pattern, blob, re.IGNORECASE)
            if m:
                hits.append({
                    "title": t["title"][:120],
                    "date": t["date"],
                    "match": m.group(0),
                })
                break

    if not hits:
        return {"fired": False, "score": 0, "headline_count": 0, "evidence": []}

    most_recent = None
    for h in hits:
        try:
            d = pd.Timestamp(h["date"]).tz_localize(None) if pd.Timestamp(h["date"]).tz else pd.Timestamp(h["date"])
            if most_recent is None or d > most_recent:
                most_recent = d
        except Exception:
            pass

    days_since = None
    if most_recent is not None:
        days_since = (pd.Timestamp.now() - most_recent).days

    score = 1
    if days_since is not None and days_since <= 30:
        score = 3
    elif days_since is not None and days_since <= 60:
        score = 2

    if any("completed" in (h["title"] or "").lower() or "completes" in (h["title"] or "").lower() for h in hits):
        score = 3

    return {
        "fired": True,
        "score": score,
        "headline_count": len(hits),
        "days_since_most_recent": days_since,
        "evidence": hits[:3],
    }


def insider_cluster_60d(insider_txns, lookback_days=60, min_buyers=3, min_value_usd=200_000):
    if not insider_txns:
        return {"fired": False, "score": 0, "buyer_count": 0, "total_value_usd": 0}

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
    unique_buyers = set()
    total_value = 0.0
    txn_count = 0
    biggest_buy = 0.0
    for tx in insider_txns:
        try:
            d = pd.Timestamp(tx.get("transactionDate"))
            if d < cutoff:
                continue
            if str(tx.get("transactionAcquiredDisposed", "")).upper() != "A":
                continue
            name = (tx.get("ownerName") or "").strip()
            if name:
                unique_buyers.add(name)
            txn_count += 1
            shares = float(tx.get("transactionAmount") or 0)
            price = float(tx.get("transactionPrice") or 0)
            value = shares * price
            total_value += value
            if value > biggest_buy:
                biggest_buy = value
        except Exception:
            pass

    score = 0
    if len(unique_buyers) >= min_buyers and total_value >= min_value_usd:
        score = 1
    if len(unique_buyers) >= min_buyers and total_value >= min_value_usd * 5:
        score = 2
    if len(unique_buyers) >= min_buyers + 2 and total_value >= min_value_usd * 10:
        score = 3
    if biggest_buy >= 1_000_000:
        score = max(score, 2)

    return {
        "fired": score >= 1,
        "score": score,
        "buyer_count": len(unique_buyers),
        "total_value_usd": round(total_value, 0),
        "biggest_buy_usd": round(biggest_buy, 0),
        "transaction_count": txn_count,
    }


def run_all_catalyst_detectors(news_items, fundamentals, insider_txns=None):
    return {
        "capex_echo": capex_echo(news_items),
        "backlog_surge": backlog_surge(news_items, fundamentals),
        "revision_spike": revision_spike(fundamentals),
        "strategic_investment": strategic_investment(news_items),
        "spinoff_catalyst": spinoff_catalyst(news_items, fundamentals),
    }


def catalyst_signal_count(detector_results):
    return sum(1 for d in detector_results.values() if d.get("fired"))


def catalyst_total_score(detector_results):
    return sum(d.get("score", 0) for d in detector_results.values())


SIGNAL_KEY_MAP = {
    "capex_echo": "capex_echo",
    "backlog_surge": "backlog_surge",
    "revision_spike": "revision_spike",
    "strategic_investment": "strategic_investment",
    "spinoff_catalyst": "spinoff_catalyst",
}


def _build_details(det_name, det_result):
    if det_name == "capex_echo":
        hs = det_result.get("hyperscalers_named") or []
        n = det_result.get("headline_count", 0)
        return f"{n} headline(s), named: {', '.join(hs[:3])}" if hs else f"{n} headline(s)"
    if det_name == "backlog_surge":
        n = det_result.get("headline_count", 0)
        sp = det_result.get("last_eps_surprise_pct")
        if sp is not None:
            return f"{n} headline(s), last EPS surprise {sp:+.1f}%"
        return f"{n} headline(s)"
    if det_name == "revision_spike":
        up7 = det_result.get("up_7d", 0)
        up30 = det_result.get("up_30d", 0)
        pct = det_result.get("pct_change_30d")
        base = f"up7={up7}/up30={up30}"
        if pct is not None:
            base += f", est {pct:+.1f}% in 30d"
        return base
    if det_name == "strategic_investment":
        n = det_result.get("headline_count", 0)
        return f"{n} headline(s)"
    if det_name == "spinoff_catalyst":
        ds = det_result.get("days_since_most_recent")
        n = det_result.get("headline_count", 0)
        if ds is not None:
            return f"{n} headline(s), most recent {ds}d ago"
        return f"{n} headline(s)"
    return ""


def detector_hits_to_signal_entries(detector_results):
    entries = []
    for det_name, det_result in detector_results.items():
        if not det_result.get("fired"):
            continue
        key = SIGNAL_KEY_MAP.get(det_name)
        if not key:
            continue
        entries.append({
            "key": key,
            "details": _build_details(det_name, det_result),
        })
    return entries


def append_signals_and_rescore(scored_ticker, new_entries, catalyst_tiers, weight_catalyst):
    if not new_entries:
        return False
    catalysts_full = scored_ticker["components"]["catalyst_quality"].get("catalysts_full") or []
    existing_keys = {c.get("key") for c in catalysts_full}
    added = []
    for entry in new_entries:
        if entry["key"] in existing_keys:
            continue
        meta = catalyst_tiers.get(entry["key"])
        if not meta:
            continue
        added.append({
            "key": entry["key"],
            "tier": meta["tier"],
            "points": meta["points"],
            "label": meta["label"],
            "details": entry.get("details", ""),
            "direction": meta.get("direction", "bull"),
            "event_timing": meta.get("event_timing", "ongoing"),
        })
        existing_keys.add(entry["key"])
    if not added:
        return False

    catalysts_full = catalysts_full + added
    catalysts_full.sort(key=lambda x: x["points"], reverse=True)
    primary = catalysts_full[0]["points"]
    secondary_bonus = sum(c["points"] for c in catalysts_full[1:]) * 0.25
    base = min(primary + secondary_bonus, 5.0)
    new_catalyst_pts = base * weight_catalyst

    old_catalyst_pts = scored_ticker["components"]["catalyst_quality"].get("points", 0) or 0
    scored_ticker["components"]["catalyst_quality"]["points"] = round(new_catalyst_pts, 2)
    scored_ticker["components"]["catalyst_quality"]["catalysts_full"] = catalysts_full
    scored_ticker["components"]["catalyst_quality"]["details"] = [c["label"] for c in catalysts_full]
    scored_ticker["components"]["catalyst_quality"]["tier"] = catalysts_full[0]["tier"]
    scored_ticker["catalysts"] = catalysts_full
    scored_ticker["catalyst_tier"] = catalysts_full[0]["tier"]
    scored_ticker["score"] = round(scored_ticker.get("score", 0) - old_catalyst_pts + new_catalyst_pts, 2)
    scored_ticker["_signals_added"] = [e["key"] for e in added]
    return True
