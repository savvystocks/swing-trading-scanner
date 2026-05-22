"""Stage 2 prime-entry detection.

Minervini-style: identify stocks in confirmed uptrends that are NOT yet
extended. Sweet spot: above 50dMA + 200dMA, 50dMA above 200dMA, but
distance-from-50dMA is small (0-10%) so there's room to run before
mean reversion. Avoid stocks that are already 20%+ extended.
"""


def stage2_zone(pick):
    above_50 = pick.get("above_50dma")
    above_200 = pick.get("above_200dma")
    pct_above_50 = pick.get("pct_above_50dma")
    ret_30d = pick.get("ret_30d")

    try:
        pct = float(pct_above_50) if pct_above_50 is not None else None
    except (TypeError, ValueError):
        pct = None
    try:
        ret30 = float(ret_30d) if ret_30d is not None else None
    except (TypeError, ValueError):
        ret30 = None

    if not above_50 or not above_200:
        return {
            "zone": "NOT_IN_STAGE2",
            "score": 0,
            "note": "Below 50dMA or 200dMA - not in Stage 2 uptrend",
            "tradeable": False,
        }

    if pct is None or ret30 is None:
        return {
            "zone": "UNKNOWN",
            "score": 50,
            "note": "Insufficient data to classify Stage 2 zone",
            "tradeable": True,
        }

    if pct <= 7 and ret30 <= 15:
        return {
            "zone": "PRIME_ENTRY",
            "score": 95,
            "note": "Just above 50dMA, modest 30d run - room to extend",
            "tradeable": True,
        }
    if pct <= 12 and ret30 <= 22:
        return {
            "zone": "EARLY_CONTINUATION",
            "score": 80,
            "note": "Trend confirmed, early in the move",
            "tradeable": True,
        }
    if pct <= 18 and ret30 <= 32:
        return {
            "zone": "CONTINUATION",
            "score": 60,
            "note": "Mid-trend, some upside left but less optimal entry",
            "tradeable": True,
        }
    if pct <= 25 and ret30 <= 45:
        return {
            "zone": "EXTENDED",
            "score": 30,
            "note": f"+{pct:.0f}% above 50dMA / +{ret30:.0f}% 30d - mean reversion risk",
            "tradeable": False,
        }
    return {
        "zone": "CLIMAX",
        "score": 10,
        "note": f"Parabolic: +{pct:.0f}% above 50dMA / +{ret30:.0f}% 30d - distribution likely",
        "tradeable": False,
    }


def apply_stage2_zones(picks, verbose=False):
    if not picks:
        return
    counts = {"PRIME_ENTRY": 0, "EARLY_CONTINUATION": 0, "CONTINUATION": 0, "EXTENDED": 0, "CLIMAX": 0, "NOT_IN_STAGE2": 0, "UNKNOWN": 0}
    for p in picks:
        try:
            z = stage2_zone(p)
            p["_stage2_zone"] = z
            counts[z["zone"]] = counts.get(z["zone"], 0) + 1
        except Exception as e:
            if verbose:
                print(f"  stage2_zone fail {p.get('ticker')}: {type(e).__name__}: {e}")
    if verbose:
        prime = counts["PRIME_ENTRY"] + counts["EARLY_CONTINUATION"]
        bad = counts["EXTENDED"] + counts["CLIMAX"]
        print(f"  stage2_entry: PRIME/EARLY={prime}  CONTINUATION={counts['CONTINUATION']}  EXTENDED/CLIMAX={bad}  NOT_STAGE2={counts['NOT_IN_STAGE2']}")
