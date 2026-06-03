"""Pattern 7: Gamma Flip Magnet (Tier S).

When spot is within 0.5% of the zero-gamma flip strike, dealer hedging forces
price hard one way. In NEGATIVE_AMP regime, price gets pulled BELOW flip.
In POSITIVE_PIN regime, price gets pulled toward flip.

Score contribution: 25 points (Tier S).
"""


def _to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def detect(uw_client, ticker, pick=None):
    # Get the per-strike GEX to compute flip
    gex_strike = uw_client.greek_exposure_by_strike(ticker)
    spot = (pick or {}).get("live_spot") or (pick or {}).get("price")

    if not gex_strike or not spot:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    try:
        spot_val = float(spot)
    except (TypeError, ValueError):
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    strikes_payload = gex_strike.get("data") if isinstance(gex_strike, dict) else gex_strike
    if not isinstance(strikes_payload, list) or not strikes_payload:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    # Find flip strike: cumulative net GEX crosses zero
    pairs = []
    for s in strikes_payload:
        if not isinstance(s, dict):
            continue
        k = _to_float(s.get("strike"))
        cg = _to_float(s.get("call_gex")) or 0
        pg = _to_float(s.get("put_gex")) or 0
        if k is not None:
            pairs.append((k, cg + pg))
    pairs.sort(key=lambda x: x[0])

    # Only consider strikes within +/- 30% of spot (deep OTM artifacts produce junk flips)
    near_spot = [(k, g) for k, g in pairs if abs(k - spot_val) / spot_val <= 0.30]
    if not near_spot:
        near_spot = pairs

    cumulative = 0
    flip_strike = None
    prev_sign = None
    for strike, g in near_spot:
        cumulative += g
        cur_sign = 1 if cumulative > 0 else (-1 if cumulative < 0 else 0)
        if prev_sign is not None and prev_sign != cur_sign and prev_sign != 0:
            flip_strike = strike
            break
        prev_sign = cur_sign

    if flip_strike is None:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    # Distance from spot to flip as percentage
    distance_pct = abs(spot_val - flip_strike) / spot_val * 100

    # Net GEX above and below flip to determine direction
    net_gex_total = sum(g for _, g in pairs)
    regime = "NEGATIVE_AMP" if net_gex_total < 0 else ("POSITIVE_PIN" if net_gex_total > 0 else "NEUTRAL")

    # Widened from 0.5% to 1.5% - real strikes are rarely within 0.5% of spot
    if distance_pct > 1.5:
        return {"fires": False, "side": None, "score": 0,
                "label": f"flip strike ${flip_strike:.2f} ({distance_pct:.2f}% away from spot - not in magnet zone)",
                "details": {"flip_strike": flip_strike, "spot": spot_val, "distance_pct": distance_pct, "regime": regime}}

    # Within 1.5% - magnet zone fires. Closer = more score.
    if distance_pct <= 0.5:
        magnet_score = 25
    elif distance_pct <= 1.0:
        magnet_score = 18
    else:
        magnet_score = 12
    if regime == "NEGATIVE_AMP":
        # Negative gamma amplifies moves - price will accelerate away from current position
        if spot_val < flip_strike:
            # Below flip in negative gamma = downward acceleration
            side = "PUT"
        else:
            # Above flip in negative gamma = upward acceleration
            side = "CALL"
        label = f"WITHIN 0.5% OF FLIP STRIKE ${flip_strike:.2f} in NEGATIVE_AMP regime ({distance_pct:.2f}% away) - amplification {side}"
    else:
        # Positive gamma pins toward flip
        if spot_val > flip_strike:
            side = "PUT"  # pinning pulls down
        else:
            side = "CALL"  # pinning pulls up
        label = f"WITHIN 0.5% OF FLIP STRIKE ${flip_strike:.2f} in POSITIVE_PIN regime ({distance_pct:.2f}% away) - pinning toward flip"

    return {
        "fires": True,
        "side": side,
        "score": magnet_score,
        "label": label,
        "details": {
            "flip_strike": flip_strike,
            "spot": spot_val,
            "distance_pct": distance_pct,
            "regime": regime,
            "net_gex_total": net_gex_total,
        },
    }
