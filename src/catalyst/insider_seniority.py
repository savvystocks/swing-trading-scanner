ROLE_WEIGHTS = {
    "ceo": 3.0,
    "chief executive officer": 3.0,
    "cfo": 3.5,
    "chief financial officer": 3.5,
    "coo": 2.0,
    "chief operating officer": 2.0,
    "president": 2.5,
    "director": 1.5,
    "10% owner": 2.0,
    "evp": 1.5,
    "executive vice president": 1.5,
    "svp": 1.0,
    "senior vice president": 1.0,
    "vp": 0.75,
    "vice president": 0.75,
}


def _role_weight(role):
    if not role:
        return 0.5
    r = role.lower()
    for key, w in ROLE_WEIGHTS.items():
        if key in r:
            return w
    return 0.5


def score_insider_quality(transactions):
    if not transactions:
        return {"quality_score": 0, "ceo_or_cfo_bought": False, "total_value_usd": 0, "buyer_count": 0, "weighted_value": 0}

    seen_buyers = set()
    total_value = 0
    weighted_value = 0
    ceo_cfo = False
    organic_buys = 0
    excluded_count = 0

    for t in transactions:
        if not isinstance(t, dict):
            continue
        ttype = (t.get("transaction_type") or t.get("type") or "").upper()
        is_10b5_1 = bool(t.get("is_10b5_1") or t.get("plan"))
        is_option_exercise = "M" in ttype or "OPTION EXERCISE" in ttype
        is_buy = "P" in ttype or "PURCHASE" in ttype or "OPEN MARKET" in ttype
        if not is_buy:
            continue
        if is_10b5_1 or is_option_exercise:
            excluded_count += 1
            continue
        organic_buys += 1
        person = t.get("name") or t.get("filer") or ""
        role = t.get("role") or t.get("title") or ""
        amount = float(t.get("value") or 0)
        w = _role_weight(role)
        if person:
            seen_buyers.add(person)
        total_value += amount
        weighted_value += amount * w
        if any(k in role.lower() for k in ("ceo", "cfo", "chief executive", "chief financial")):
            ceo_cfo = True

    quality = 0
    if organic_buys >= 5:
        quality += 30
    elif organic_buys >= 3:
        quality += 20
    elif organic_buys >= 1:
        quality += 10
    if ceo_cfo:
        quality += 25
    if total_value >= 1_000_000:
        quality += 25
    elif total_value >= 250_000:
        quality += 15
    elif total_value >= 50_000:
        quality += 5
    quality = min(quality, 100)

    return {
        "quality_score": quality,
        "ceo_or_cfo_bought": ceo_cfo,
        "total_value_usd": round(total_value, 0),
        "weighted_value_usd": round(weighted_value, 0),
        "buyer_count": len(seen_buyers),
        "organic_buy_count": organic_buys,
        "excluded_10b5_1_or_option_exercise": excluded_count,
    }


def enrich_insider_quality(candidates, verbose=False):
    for s in candidates:
        depth = s.get("insider_depth") or {}
        transactions = depth.get("transactions") or depth.get("recent") or []
        quality = score_insider_quality(transactions)
        depth.update(quality)
        s["insider_depth"] = depth
    if verbose:
        high_q = sum(1 for s in candidates if (s.get("insider_depth") or {}).get("quality_score", 0) >= 50)
        print(f"  insider_seniority: {high_q} candidates with quality score >=50")
    return candidates
