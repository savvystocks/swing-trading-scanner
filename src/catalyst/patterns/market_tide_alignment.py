"""Pattern: Market tide + Sector tide alignment.

Confirms trade direction matches the overall market flow direction.

UW /market/market-tide returns 5-min snapshots of net_call_premium and net_put_premium.
If market net flow is bearish and we're considering a CALL, that's fighting the tide.
If market net flow is bullish and we're considering a PUT, that's fighting the tide.

Score contribution: +10 if aligned, -10 if fighting (we expose this in confluence math).
"""


def _to_float(v, default=0):
    try:
        return float(v) if v else default
    except (TypeError, ValueError):
        return default


def classify_market_tide(uw_client):
    """Return CALL_BIAS / PUT_BIAS / NEUTRAL based on today's net flow."""
    data = uw_client.market_tide()
    if not data:
        return {"regime": "UNKNOWN", "score": 0, "label": "market tide data unavailable"}

    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        return {"regime": "UNKNOWN", "score": 0, "label": "market tide returned no rows"}

    # Sum across all today's 5-min buckets
    total_call_prem = 0
    total_put_prem = 0
    total_vol = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        total_call_prem += _to_float(r.get("net_call_premium"))
        total_put_prem += _to_float(r.get("net_put_premium"))
        total_vol += _to_float(r.get("net_volume"))

    net_diff = total_call_prem - total_put_prem
    ratio = total_call_prem / max(abs(total_put_prem), 1) if total_put_prem > 0 else 0

    if net_diff >= 50_000_000 and total_vol > 0:
        regime = "CALL_BIAS"
        label = f"market tide BULLISH: net call premium +${net_diff/1e6:.0f}M today"
    elif net_diff <= -50_000_000 and total_vol < 0:
        regime = "PUT_BIAS"
        label = f"market tide BEARISH: net put premium ${abs(net_diff)/1e6:.0f}M today"
    else:
        regime = "NEUTRAL"
        label = f"market tide NEUTRAL: net diff ${net_diff/1e6:+.0f}M"

    return {
        "regime": regime,
        "net_call_premium": total_call_prem,
        "net_put_premium": total_put_prem,
        "net_volume": total_vol,
        "label": label,
    }


def detect(uw_client, ticker, pick=None, intended_side=None):
    """Compute alignment score given intended trade direction."""
    tide = classify_market_tide(uw_client)
    regime = tide["regime"]

    if intended_side is None:
        return {"fires": False, "side": None, "score": 0, "label": tide["label"], "details": tide}

    aligned = (
        (intended_side == "CALL" and regime == "CALL_BIAS") or
        (intended_side == "PUT" and regime == "PUT_BIAS")
    )
    fighting = (
        (intended_side == "CALL" and regime == "PUT_BIAS") or
        (intended_side == "PUT" and regime == "CALL_BIAS")
    )

    if aligned:
        return {
            "fires": True, "side": intended_side, "score": 10,
            "label": f"MARKET TIDE ALIGNED with {intended_side}: {tide['label']}",
            "details": tide,
        }
    if fighting:
        return {
            "fires": True, "side": intended_side, "score": -10,
            "label": f"MARKET TIDE FIGHTING {intended_side}: {tide['label']}",
            "details": tide,
        }
    return {
        "fires": False, "side": intended_side, "score": 0,
        "label": tide["label"],
        "details": tide,
    }
