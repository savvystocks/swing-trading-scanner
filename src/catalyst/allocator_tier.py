TIER_1_ALLOCATORS = {
    "berkshire hathaway", "warren buffett",
    "appaloosa management", "david tepper",
    "pershing square", "bill ackman",
    "scion asset management", "michael burry",
    "duquesne family office", "stanley druckenmiller",
    "third point", "dan loeb",
    "elliott management", "paul singer",
    "starboard value",
    "tiger global", "chase coleman",
    "viking global", "andreas halvorsen",
    "lone pine capital", "stephen mandel",
    "soroban capital",
    "greenlight capital", "david einhorn",
    "icahn capital", "carl icahn",
    "trian fund management", "nelson peltz",
    "sequoia capital", "valeant",
    "altimeter capital", "brad gerstner",
    "coatue management", "philippe laffont",
    "marshall wace",
    "millennium management",
    "citadel advisors",
    "renaissance technologies",
    "two sigma",
    "point72",
}

TIER_2_ALLOCATORS = {
    "de shaw", "balyasny", "fortress", "blackrock advisors",
    "blue mountain", "harris associates", "fpr partners",
    "maverick capital", "egerton capital", "select equity",
    "fundsmith", "blue jay capital", "darsana capital", "marshall wace",
    "fpa funds", "polen capital", "ariel investments", "akre capital",
    "ako capital", "ruane cunniff", "tweedy browne",
    "harding loevner", "first eagle", "wedgewood partners",
}

TIER_4_PASSIVE = {
    "vanguard", "blackrock", "state street", "fidelity",
    "ishares", "spdr", "etf", "index fund",
}


def classify_allocator(institution_name):
    if not institution_name:
        return 4
    name = institution_name.lower()
    for t in TIER_1_ALLOCATORS:
        if t in name:
            return 1
    for t in TIER_2_ALLOCATORS:
        if t in name:
            return 2
    for t in TIER_4_PASSIVE:
        if t in name:
            return 4
    return 3


def score_13f_quality(institutional_data):
    if not institutional_data:
        return {"tier_1_count": 0, "tier_2_count": 0, "tier_3_count": 0, "tier_4_count": 0, "quality_score": 0}

    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    new_positions = institutional_data.get("new_positions") or []
    adds = institutional_data.get("increased_positions") or []
    reductions = institutional_data.get("reduced_positions") or []
    exits = institutional_data.get("sold_out") or []

    tier_1_new = []
    tier_1_adds = []
    tier_2_new = []

    for pos in new_positions:
        name = pos.get("institution_name") or pos.get("name") or ""
        tier = classify_allocator(name)
        counts[tier] = counts.get(tier, 0) + 1
        if tier == 1:
            tier_1_new.append(name)
        elif tier == 2:
            tier_2_new.append(name)

    for pos in adds:
        name = pos.get("institution_name") or pos.get("name") or ""
        tier = classify_allocator(name)
        if tier == 1:
            tier_1_adds.append(name)

    quality = 0
    if tier_1_new:
        quality += 40
    elif tier_2_new:
        quality += 20
    if tier_1_adds:
        quality += 25
    quality += min(counts.get(1, 0) * 10, 30)
    quality += min(counts.get(2, 0) * 5, 20)

    tier_1_exits = sum(1 for p in exits if classify_allocator(p.get("institution_name") or "") == 1)
    if tier_1_exits >= 2:
        quality -= 30
    elif tier_1_exits >= 1:
        quality -= 15

    quality = max(0, min(quality, 100))

    return {
        "tier_1_count": counts.get(1, 0),
        "tier_2_count": counts.get(2, 0),
        "tier_3_count": counts.get(3, 0),
        "tier_4_count": counts.get(4, 0),
        "tier_1_new_positions": tier_1_new[:5],
        "tier_1_adds": tier_1_adds[:5],
        "tier_1_exits": tier_1_exits,
        "quality_score": quality,
    }


def enrich_allocator_tier(candidates, verbose=False):
    enriched = 0
    for s in candidates:
        inst = s.get("institutional_ownership") or {}
        result = score_13f_quality(inst)
        s["allocator_quality"] = result
        if result["quality_score"] > 0:
            enriched += 1
    if verbose:
        high_q = sum(1 for s in candidates if (s.get("allocator_quality") or {}).get("quality_score", 0) >= 40)
        print(f"  allocator_tier: {high_q} candidates with tier-1/2 institutional buying")
    return candidates
