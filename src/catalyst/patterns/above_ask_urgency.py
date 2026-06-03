"""Pattern 3: Above-Ask Urgency (Tier B).

Trade executed at or above ask price. The pro PM willing to pay UP for fill
= high time-sensitivity = real catalyst incoming.

Threshold: 50%+ of total premium executed at-ask-or-above = urgency confirmed.

Score contribution: 15 points (Tier B).
"""


def _to_float(v, default=0):
    try:
        return float(v) if v else default
    except (TypeError, ValueError):
        return default


def detect(uw_client, ticker, pick=None):
    alerts = uw_client.flow_alerts(ticker=ticker, limit=100)
    if not alerts:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    rows = alerts.get("data") if isinstance(alerts, dict) else alerts
    if not isinstance(rows, list) or not rows:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    side_premiums = {"CALL": {"total": 0, "above_ask": 0}, "PUT": {"total": 0, "above_ask": 0}}

    for r in rows:
        if not isinstance(r, dict):
            continue
        type_field = (r.get("type") or "").lower()
        side = "CALL" if "call" in type_field else ("PUT" if "put" in type_field else None)
        if not side:
            continue
        prem = _to_float(r.get("total_premium"))
        price = _to_float(r.get("price"))
        ask = _to_float(r.get("ask"))
        # If we don't have ask explicitly, use the side breakdown
        # UW provides ask_side_volume and bid_side_volume in some endpoints
        ask_side_prem = _to_float(r.get("ask_side_prem") or r.get("total_ask_side_prem"))
        bid_side_prem = _to_float(r.get("bid_side_prem") or r.get("total_bid_side_prem"))

        side_premiums[side]["total"] += prem
        if ask_side_prem > 0:
            side_premiums[side]["above_ask"] += ask_side_prem
        elif ask > 0 and price >= ask:
            side_premiums[side]["above_ask"] += prem

    # Threshold lowered: 40% above-ask ratio (was 50% - too strict for normal market days)
    triggers = []
    for side, p in side_premiums.items():
        if p["total"] >= 250_000:
            ratio = p["above_ask"] / p["total"] if p["total"] > 0 else 0
            if ratio >= 0.4:
                triggers.append({"side": side, "total": p["total"], "above_ask": p["above_ask"], "ratio": ratio})

    if not triggers:
        return {"fires": False, "side": None, "score": 0,
                "label": "no above-ask urgency detected (<50% ask-side premium)",
                "details": side_premiums}

    # Take highest ratio
    triggers.sort(key=lambda x: (x["ratio"], x["total"]), reverse=True)
    top = triggers[0]

    label = (f"ABOVE-ASK URGENCY: {top['side']} side has "
             f"${top['above_ask']/1e6:.1f}M / ${top['total']/1e6:.1f}M "
             f"({int(top['ratio']*100)}%) executed at ask or above = pro urgency")

    return {
        "fires": True,
        "side": top["side"],
        "score": 15,
        "label": label,
        "details": top,
    }
