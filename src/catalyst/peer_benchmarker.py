from collections import defaultdict


PEER_AXES = [
    "revenue_growth_yoy",
    "gross_margin",
    "operating_margin",
    "fcf_margin",
    "ret_30d",
    "ret_90d",
    "short_pct_float",
    "ev_to_ebitda",
    "ps_ratio",
    "market_cap",
]


def _coerce(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_peer_groups(candidates):
    groups = defaultdict(list)
    for s in candidates:
        industry = (s.get("industry") or "").strip().lower()
        bracket = s.get("bracket")
        if not industry or not bracket:
            continue
        key = (bracket, industry)
        groups[key].append(s)
    return groups


def compute_percentiles(value, peer_values):
    valid = [v for v in peer_values if v is not None]
    if not valid or value is None:
        return None
    below = sum(1 for v in valid if v < value)
    return round(below / len(valid) * 100, 0)


def benchmark_against_peers(candidate, peer_group):
    peer_set = [p for p in peer_group if p.get("ticker") != candidate.get("ticker")]
    if len(peer_set) < 3:
        return None
    out = {"peer_count": len(peer_set), "rankings": {}}
    for axis in PEER_AXES:
        self_val = _coerce(candidate.get(axis))
        peer_vals = [_coerce(p.get(axis)) for p in peer_set]
        pct = compute_percentiles(self_val, peer_vals)
        if pct is not None:
            out["rankings"][axis] = {
                "self": self_val,
                "percentile": pct,
                "peer_median": _median(peer_vals),
            }
    growth_axes = ["revenue_growth_yoy", "ret_30d", "ret_90d"]
    quality_axes = ["gross_margin", "operating_margin", "fcf_margin"]
    growth_ranks = [out["rankings"][a]["percentile"] for a in growth_axes if a in out["rankings"]]
    quality_ranks = [out["rankings"][a]["percentile"] for a in quality_axes if a in out["rankings"]]
    out["growth_percentile_avg"] = round(sum(growth_ranks) / len(growth_ranks), 0) if growth_ranks else None
    out["quality_percentile_avg"] = round(sum(quality_ranks) / len(quality_ranks), 0) if quality_ranks else None
    return out


def _median(vals):
    valid = sorted(v for v in vals if v is not None)
    if not valid:
        return None
    n = len(valid)
    if n % 2 == 1:
        return round(valid[n // 2], 2)
    return round((valid[n // 2 - 1] + valid[n // 2]) / 2, 2)


def apply_peer_benchmarking(candidates, verbose=False):
    groups = build_peer_groups(candidates)
    enriched = 0
    for s in candidates:
        industry = (s.get("industry") or "").strip().lower()
        bracket = s.get("bracket")
        if not industry or not bracket:
            continue
        key = (bracket, industry)
        peer_group = groups.get(key, [])
        if len(peer_group) < 4:
            continue
        bench = benchmark_against_peers(s, peer_group)
        if bench:
            s["peer_benchmark"] = bench
            enriched += 1
    if verbose:
        print(f"  peer_benchmarker: enriched {enriched}/{len(candidates)} with industry peer ranks")
    return candidates
