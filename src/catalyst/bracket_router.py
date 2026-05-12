MICRO_MIN = 250_000_000
MICRO_MAX = 1_000_000_000
SMALL_MAX = 5_000_000_000
MID_MAX = 50_000_000_000


def route_bracket(mcap):
    if not mcap or mcap < MICRO_MIN:
        return None
    if mcap < MICRO_MAX:
        return "micro"
    if mcap < SMALL_MAX:
        return "small"
    if mcap < MID_MAX:
        return "mid"
    return None


def route_candidates(scored):
    out = {"micro": [], "small": [], "mid": [], "filtered_out": []}
    for s in scored:
        mcap = s.get("market_cap") or 0
        bucket = route_bracket(mcap)
        if bucket is None:
            out["filtered_out"].append(s)
            continue
        s["bracket"] = bucket
        out[bucket].append(s)
    return out


def bracket_label(bracket):
    return {
        "micro": "MICRO ($250M-$1B)",
        "small": "SMALL ($1B-$5B)",
        "mid": "MID ($5B-$50B)",
    }.get(bracket, bracket)
