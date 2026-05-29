import os
import requests
from datetime import datetime, timedelta


SAM_API_BASE = "https://api.sam.gov/opportunities/v2/search"


HIGH_VALUE_KEYWORDS = (
    "ai", "artificial intelligence", "machine learning", "data center",
    "cloud computing", "satellite", "rocket launch", "missile defense",
    "nuclear", "small modular reactor", "smr", "battery", "lithium",
    "semiconductor", "fab", "foundry", "drone", "quantum",
    "cybersecurity", "5g", "spectrum", "biodefense",
)


def fetch_recent_contract_awards(api_key=None, days_back=2, limit=200, keywords=None):
    api_key = api_key or os.environ.get("SAM_GOV_API_KEY")
    if not api_key:
        return None, "no SAM_GOV_API_KEY"

    posted_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%m/%d/%Y")
    posted_to = datetime.utcnow().strftime("%m/%d/%Y")

    params = {
        "api_key": api_key,
        "limit": limit,
        "postedFrom": posted_from,
        "postedTo": posted_to,
        "ptype": "a",
    }

    try:
        r = requests.get(SAM_API_BASE, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:200]}"

    awards = data.get("opportunitiesData") or data.get("results") or []
    if keywords is None:
        keywords = HIGH_VALUE_KEYWORDS
    keywords_lower = [k.lower() for k in keywords]

    relevant = []
    for a in awards:
        title = (a.get("title") or "").lower()
        desc = (a.get("description") or "").lower()
        agency = (a.get("department") or a.get("agency") or "").lower()
        award_amount = a.get("award", {}).get("amount") if isinstance(a.get("award"), dict) else None
        awardee = a.get("award", {}).get("awardee", {}) if isinstance(a.get("award"), dict) else {}
        awardee_name = awardee.get("name", "") if isinstance(awardee, dict) else ""

        blob = f"{title} {desc} {agency} {awardee_name}".lower()
        matched_keywords = [kw for kw in keywords_lower if kw in blob]
        if not matched_keywords:
            continue

        relevant.append({
            "title": a.get("title", "")[:200],
            "agency": a.get("department") or a.get("agency", ""),
            "awardee_name": awardee_name,
            "award_amount": award_amount,
            "posted_date": a.get("postedDate", ""),
            "matched_keywords": matched_keywords[:3],
            "naics_code": a.get("naicsCode", ""),
            "url": a.get("uiLink", ""),
        })

    return relevant, None


def map_awardees_to_tickers(awards, ticker_companies):
    if not awards or not ticker_companies:
        return {}
    name_to_ticker = {}
    for ticker, name in ticker_companies.items():
        if not name:
            continue
        clean_name = name.lower().replace(",", "").replace(".", "")
        for token in clean_name.split():
            if len(token) < 4:
                continue
            name_to_ticker.setdefault(token, []).append(ticker)

    matched = {}
    for award in awards:
        awardee = (award.get("awardee_name") or "").lower()
        if not awardee:
            continue
        for token in awardee.split():
            if len(token) < 4:
                continue
            for ticker in name_to_ticker.get(token, []):
                matched.setdefault(ticker, []).append(award)
    return matched
