def classify_vol_regime(macro):
    if not macro:
        return {"regime": "unknown", "vix": None, "tier_cap": None, "position_multiplier": 1.0, "stop_multiplier": 1.0}
    vix = macro.get("vix")
    vix_term = macro.get("vix_term") or ""
    if vix is None:
        return {"regime": "unknown", "vix": None, "tier_cap": None, "position_multiplier": 1.0, "stop_multiplier": 1.0}

    if vix < 15:
        regime = "LOW_VOL"
        tier_cap = "A++"
        pos_mult = 1.1
        stop_mult = 1.0
        comment = "Low vol — options cheap, full size acceptable"
    elif vix <= 20:
        regime = "NORMAL"
        tier_cap = "A++"
        pos_mult = 1.0
        stop_mult = 1.0
        comment = "Standard regime, normal parameters"
    elif vix <= 28:
        regime = "ELEVATED"
        tier_cap = "A+"
        pos_mult = 0.75
        stop_mult = 0.75
        comment = "Elevated VIX — reduce size 25%, tighten stops to -30%"
    else:
        regime = "STRESSED"
        tier_cap = "A"
        pos_mult = 0.5
        stop_mult = 0.625
        comment = "Stressed VIX — half size, only A trades, prefer spreads not lottery"
        if "BACKWARDATION" in vix_term:
            comment += " (BUT VIX backwardation = panic spike, mean-reversion buyable)"
            tier_cap = "A+"
            pos_mult = 0.75

    return {
        "regime": regime,
        "vix": vix,
        "vix_term": vix_term,
        "tier_cap": tier_cap,
        "position_multiplier": pos_mult,
        "stop_multiplier": stop_mult,
        "comment": comment,
    }


def cap_tier_by_regime(proposed_tier, regime_info):
    cap = regime_info.get("tier_cap")
    if not cap:
        return proposed_tier
    tier_order = {"A": 1, "A+": 2, "A++": 3, "REJECT": 0}
    return cap if tier_order.get(proposed_tier, 0) > tier_order.get(cap, 0) else proposed_tier
