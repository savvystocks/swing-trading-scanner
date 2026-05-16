def suggest_structure(pick):
    if not pick:
        return None

    iv_data = pick.get("iv_percentile_analysis") or {}
    iv_pctile = iv_data.get("iv_percentile")
    vol_micro = pick.get("_vol_microstructure") or {}
    riv = vol_micro.get("realized_vs_implied") or {}
    riv_verdict = riv.get("verdict")
    forensic = pick.get("unified_forensic") or pick.get("haiku_synthesis") or {}
    verdict = forensic.get("verdict")
    bear = pick.get("bear_verification") or {}
    is_trap = bear.get("is_this_trade_a_trap", False)
    survival = pick.get("_survival_score") or {}
    survival_score = survival.get("score", 70)

    cats = pick.get("catalysts") or []
    has_earnings_imminent = any(
        isinstance(c, dict) and c.get("key") in ("earnings_imminent_5_9d", "earnings_amc_today", "earnings_bmo_tomorrow", "earnings_peak_iv_3_4d")
        for c in cats
    )

    suggestions = []

    if is_trap:
        suggestions.append({
            "structure": "SKIP",
            "rationale": "Bear-case verification flagged TRAP. Do not put on directional or premium-selling positions.",
        })
        return suggestions

    if survival_score < 30:
        suggestions.append({
            "structure": "SKIP",
            "rationale": f"Trade Survival Score {survival_score:.0f}/100 - too many headwinds. Wait for better setup.",
        })
        return suggestions

    if verdict in ("BUY", "STRONG_BUY") and (riv_verdict in ("iv_underpriced", "fair") or not riv_verdict):
        suggestions.append({
            "structure": "long_call",
            "rationale": "Bullish LLM verdict + reasonable IV. Standard long call captures asymmetric upside.",
            "details": "Use 25-45 DTE, 0.30-0.40 delta strike, exit before last 3 DTE.",
        })

    if (iv_pctile is not None and iv_pctile > 75) or riv_verdict == "iv_overpriced_strong":
        if verdict in ("BUY", "STRONG_BUY"):
            suggestions.append({
                "structure": "bull_call_spread (debit)",
                "rationale": "IV high makes long calls expensive. Bull call spread caps gain but reduces cost.",
                "details": "Buy 0.45 delta call, sell 0.20 delta call same expiry. Net debit. Defined risk.",
            })
            suggestions.append({
                "structure": "put_credit_spread",
                "rationale": "If bullish + IV rich, sell put spread for premium. Win on flat-to-up move.",
                "details": "Sell 0.25 delta put, buy 0.10 delta put, 30-45 DTE. Collect 30-40% of width.",
            })

    if has_earnings_imminent and verdict not in ("SKIP", "STRONG_SELL"):
        suggestions.append({
            "structure": "calendar_spread",
            "rationale": "Earnings imminent - front-month IV is rich, back-month is cheap. Calendar harvests this.",
            "details": "Sell front-week strike, buy 30-45 DTE same strike. Max profit at expiry of front leg if stock pins at strike.",
        })
        suggestions.append({
            "structure": "long_straddle_or_strangle",
            "rationale": "Binary earnings event - if expecting BIG move either direction, straddle captures both sides.",
            "details": "Long ATM straddle (call + put same strike) OR long strangle (call + put different strikes). Expensive but uncapped both ways. Only if implied move < expected move.",
        })

    if verdict == "HOLD" and iv_pctile is not None and iv_pctile > 60:
        suggestions.append({
            "structure": "iron_condor",
            "rationale": "Neutral LLM verdict + elevated IV = sell premium on both sides. Range-bound bet.",
            "details": "Sell 0.20 delta call AND 0.20 delta put, buy 0.05 wings. 30-45 DTE. Theta positive.",
        })

    if survival_score >= 50 and survival_score < 65 and verdict in ("BUY", "STRONG_BUY"):
        suggestions.append({
            "structure": "long_ITM_call (defensive)",
            "rationale": "Reduced size + ITM = lower vega exposure, mostly delta. Survives mild stress.",
            "details": "0.65-0.75 delta call, 45+ DTE, smaller position. Acts more like leveraged stock than option.",
        })

    if not suggestions:
        suggestions.append({
            "structure": "wait",
            "rationale": "Signals mixed. Wait for cleaner setup or fresh catalyst.",
        })

    return suggestions


def apply_multi_leg_suggestions(candidates, verbose=False, max_picks=5):
    if not candidates:
        return
    enriched = 0
    for c in candidates[:max_picks]:
        try:
            sugg = suggest_structure(c)
            if sugg:
                c["_multi_leg_suggestions"] = sugg
                enriched += 1
        except Exception:
            continue
    if verbose:
        print(f"  multi_leg_suggester: produced suggestions for {enriched} picks")
