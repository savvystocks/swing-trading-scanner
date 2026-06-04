"""Pattern 2: Volume > Open Interest (Tier A).

At the most-traded strike today, check volume > existing open_interest.
Volume > OI means NEW positioning (not just contract rolling). Real fresh conviction.

Score contribution: 20 points (Tier A).
"""


def _to_float(v, default=0):
    try:
        return float(v) if v else default
    except (TypeError, ValueError):
        return default


def _to_int(v, default=0):
    try:
        return int(float(v)) if v else default
    except (TypeError, ValueError):
        return default


def detect(uw_client, ticker, pick=None):
    # Get hot contracts for this ticker (sorted by volume)
    alerts = uw_client.flow_alerts(ticker=ticker, limit=50)
    if not alerts:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    rows = alerts.get("data") if isinstance(alerts, dict) else alerts
    if not isinstance(rows, list) or not rows:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    # Aggregate volume + OI per strike + side
    by_contract = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        type_field = (r.get("type") or "").lower()
        side = "CALL" if "call" in type_field else ("PUT" if "put" in type_field else None)
        if not side:
            continue
        strike = _to_float(r.get("strike"))
        if strike <= 0:
            continue
        vol = _to_int(r.get("volume"))
        oi = _to_int(r.get("open_interest"))
        key = (strike, side)
        slot = by_contract.setdefault(key, {"strike": strike, "side": side, "volume": 0, "open_interest": oi})
        slot["volume"] += vol
        slot["open_interest"] = max(slot["open_interest"], oi)  # take max OI seen

    if not by_contract:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    # Find the highest volume contract where vol > OI
    # OI_FLOOR stops a zero/near-zero-OI strike from exploding the ratio to a
    # meaningless 1000x+ and grabbing the max score off a single illiquid print.
    OI_FLOOR = 100
    triggers = []
    for key, c in by_contract.items():
        if c["volume"] > c["open_interest"] and c["volume"] >= 1000:
            ratio = c["volume"] / max(c["open_interest"], OI_FLOOR)
            triggers.append({**c, "vol_oi_ratio": ratio})

    if not triggers:
        return {"fires": False, "side": None, "score": 0,
                "label": f"no strike with volume > OI (NEW positioning not detected)",
                "details": {"contracts_checked": len(by_contract)}}

    # Take the highest ratio trigger
    triggers.sort(key=lambda x: x["vol_oi_ratio"], reverse=True)
    top = triggers[0]

    # Continuous score by ratio + absolute volume
    # 1x=10, 3x=17, 10x=24, 30x=29, 100x+=32
    import math
    ratio = top["vol_oi_ratio"]
    score = round(min(32, 10 + math.log10(ratio) * 8))
    # Volume size boost
    if top["volume"] >= 10000:
        score = round(min(32, score * 1.1))

    label = (f"VOL > OI fired on ${top['strike']:.2f} {top['side']}: "
             f"vol {top['volume']} vs OI {top['open_interest']} "
             f"(ratio {ratio:.1f}x) = NEW positioning")

    return {
        "fires": True,
        "side": top["side"],
        "score": score,
        "label": label,
        "details": top,
    }
