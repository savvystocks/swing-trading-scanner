SECTOR_ETF_MAP = {
    "semiconductors": "SOXX.US",
    "semiconductor": "SOXX.US",
    "biotech": "XBI.US",
    "biotechnology": "XBI.US",
    "banks": "KRE.US",
    "banks - regional": "KRE.US",
    "regional banks": "KRE.US",
    "energy": "XLE.US",
    "oil & gas": "XLE.US",
    "technology": "XLK.US",
    "tech": "XLK.US",
    "industrials": "XLI.US",
    "industrial": "XLI.US",
    "consumer discretionary": "XLY.US",
    "consumer cyclical": "XLY.US",
    "consumer staples": "XLP.US",
    "consumer defensive": "XLP.US",
    "healthcare": "XLV.US",
    "communication services": "XLC.US",
    "financials": "XLF.US",
    "financial services": "XLF.US",
    "utilities": "XLU.US",
    "real estate": "XLRE.US",
    "materials": "XLB.US",
    "basic materials": "XLB.US",
}


def map_sector_to_etf(sector_or_industry):
    if not sector_or_industry:
        return None
    key = sector_or_industry.strip().lower()
    if key in SECTOR_ETF_MAP:
        return SECTOR_ETF_MAP[key]
    for k, v in SECTOR_ETF_MAP.items():
        if k in key or key in k:
            return v
    return None


def evaluate_sector_rotation(snapshot, candidate):
    sector = candidate.get("sector") or ""
    industry = candidate.get("industry") or ""
    etf_symbol = map_sector_to_etf(industry) or map_sector_to_etf(sector)
    if not etf_symbol:
        return {"verdict": "NEUTRAL", "reason": "no sector ETF mapping (treating as neutral)"}
    etf_data = None
    for k, d in (snapshot or {}).items():
        if d and isinstance(d, dict) and d.get("ticker") == etf_symbol:
            etf_data = d
            break
    if not etf_data:
        return {"verdict": "NEUTRAL", "reason": f"{etf_symbol} not in macro snapshot (treating as neutral)"}
    roc_5d = etf_data.get("roc_5d_pct") or 0
    roc_30d = etf_data.get("roc_30d_pct") or 0
    if roc_5d > 3 and roc_30d > 5:
        verdict = "STRONG_TAILWIND"
    elif roc_5d > 0 and roc_30d > 0:
        verdict = "MILD_TAILWIND"
    elif roc_5d < -3 or roc_30d < -5:
        verdict = "HEADWIND"
    elif roc_30d < 0:
        verdict = "WEAK"
    else:
        verdict = "NEUTRAL"
    return {
        "verdict": verdict,
        "etf": etf_symbol,
        "roc_5d_pct": roc_5d,
        "roc_30d_pct": roc_30d,
        "reason": f"{etf_symbol} {roc_5d:+.1f}%/5d, {roc_30d:+.1f}%/30d",
    }


def sector_gate_passes(verdict, tier):
    if tier == "A++":
        return verdict in ("STRONG_TAILWIND", "MILD_TAILWIND", "NEUTRAL", "UNKNOWN")
    if tier == "A+":
        return verdict in ("STRONG_TAILWIND", "MILD_TAILWIND", "NEUTRAL", "WEAK", "UNKNOWN")
    return verdict != "HEADWIND"


def apply_sector_rotation_gate(candidates, macro_snapshot, verbose=False):
    snap = (macro_snapshot or {}).get("snapshot") or {}
    counts = {"STRONG_TAILWIND": 0, "MILD_TAILWIND": 0, "NEUTRAL": 0, "WEAK": 0, "HEADWIND": 0, "UNKNOWN": 0}
    for s in candidates:
        result = evaluate_sector_rotation(snap, s)
        s["_sector_rotation"] = result
        counts[result["verdict"]] = counts.get(result["verdict"], 0) + 1
    if verbose:
        print(f"  sector_rotation: " + " · ".join(f"{k}={v}" for k, v in counts.items() if v))
    return candidates
