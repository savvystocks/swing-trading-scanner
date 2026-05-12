EXTENSION_THRESHOLDS = {
    "ret_5d": {"yellow": 5, "red": 12},
    "ret_30d": {"yellow": 15, "red": 25},
    "ret_90d": {"yellow": 40, "red": 75},
    "pct_above_50dma": {"yellow": 12, "red": 20},
    "pct_above_200dma": {"yellow": 35, "red": 60},
}


def _coerce(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def measure_extension(candidate):
    red = 0
    yellow = 0
    details = []
    for key, thresh in EXTENSION_THRESHOLDS.items():
        val = _coerce(candidate.get(key))
        if val is None:
            continue
        if val >= thresh["red"]:
            red += 1
            details.append(f"{key}={val:.1f}% RED")
        elif val >= thresh["yellow"]:
            yellow += 1
            details.append(f"{key}={val:.1f}% yellow")
    return {"red_count": red, "yellow_count": yellow, "details": details}


def extension_tier_cap(candidate):
    m = measure_extension(candidate)
    candidate["_extension_check"] = m
    if m["red_count"] >= 2:
        return "REJECT"
    if m["red_count"] >= 1:
        return "A"
    if m["yellow_count"] >= 3:
        return "A"
    if m["yellow_count"] >= 2:
        return "A+"
    return "A++"


def is_prime_entry(candidate):
    m = candidate.get("_extension_check") or measure_extension(candidate)
    return m["red_count"] == 0 and m["yellow_count"] == 0


def filter_extension(candidates, verbose=False):
    passed = []
    rejected = []
    for s in candidates:
        cap = extension_tier_cap(s)
        s["_extension_tier_cap"] = cap
        if cap == "REJECT":
            rejected.append(s)
        else:
            passed.append(s)
    if verbose:
        prime_count = sum(1 for s in passed if is_prime_entry(s))
        print(f"  extension filter: {len(passed)} passed ({prime_count} prime-entry), {len(rejected)} rejected as extended")
    return passed, rejected
