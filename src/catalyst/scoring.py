CATALYST_TIERS = {
    "earnings_bmo_with_beat_streak": {"tier": "S", "points": 5.0, "label": "Earnings BMO + beat streak"},
    "fda_pdufa_tomorrow": {"tier": "S", "points": 5.0, "label": "FDA PDUFA decision tomorrow"},
    "merger_cash_buyout": {"tier": "S", "points": 5.0, "label": "Cash buyout announced"},
    "major_contract_win": {"tier": "S", "points": 5.0, "label": "Material contract win"},

    "earnings_bmo_tomorrow": {"tier": "A", "points": 4.0, "label": "Earnings tomorrow before open"},
    "earnings_amc_today": {"tier": "A", "points": 4.0, "label": "Earnings tonight after close"},
    "asset_sale": {"tier": "A", "points": 4.0, "label": "Asset purchase agreement"},
    "merger": {"tier": "A", "points": 4.0, "label": "Merger agreement filed"},
    "fda_event": {"tier": "A", "points": 4.0, "label": "FDA / PDUFA event filed"},
    "clinical_milestone": {"tier": "A", "points": 4.0, "label": "Clinical milestone (Phase 1/2/3)"},
    "definitive_agreement": {"tier": "A", "points": 3.5, "label": "Material definitive agreement"},

    "private_placement": {"tier": "B", "points": 3.0, "label": "Private placement filed"},
    "covenant_relief": {"tier": "B", "points": 3.0, "label": "Forbearance / covenant relief"},
    "strategic_partnership": {"tier": "B", "points": 3.0, "label": "Strategic partnership"},
    "contract_win": {"tier": "B", "points": 3.0, "label": "Contract or tender award"},
    "activist_stake": {"tier": "B", "points": 3.0, "label": "Activist 13D stake disclosed"},

    "insider_cluster": {"tier": "C", "points": 2.0, "label": "Form 4 insider buying cluster"},
    "cohort_lazar_plays": {"tier": "C", "points": 2.0, "label": "Lazar Capital portfolio name"},
    "cohort_crypto_treasury": {"tier": "C", "points": 2.0, "label": "Crypto-treasury cohort"},
    "cohort_prediction_markets": {"tier": "C", "points": 2.0, "label": "Prediction market cohort"},
    "cohort_biotech_binary": {"tier": "C", "points": 2.0, "label": "Biotech binary catalyst cohort"},
    "buyback": {"tier": "C", "points": 1.5, "label": "Buyback program announced"},

    "rebrand": {"tier": "D", "points": 1.0, "label": "Rebrand / name change"},
    "cohort_ai_rebrand": {"tier": "D", "points": 1.0, "label": "AI rebrand cohort"},
    "cohort_cannabis_basket": {"tier": "D", "points": 1.0, "label": "Cannabis sector cohort"},
    "cohort_small_cap_china_adr": {"tier": "D", "points": 0.5, "label": "Small-cap China ADR cohort"},
}


def max_possible_score(signals, max_modifier=3.0):
    if not signals:
        return 0.0
    points = []
    seen = set()
    for s in signals:
        key = s.get("key")
        if not key or key in seen:
            continue
        seen.add(key)
        meta = CATALYST_TIERS.get(key)
        if meta:
            points.append(meta["points"])
    if not points:
        return 0.0
    points.sort(reverse=True)
    primary = points[0]
    secondary = sum(p * 0.25 for p in points[1:])
    base = min(primary + secondary, 5.0)
    return base * 1.5 + max_modifier


def base_catalyst_score(signals):
    if not signals:
        return 0.0, []
    chosen = []
    seen_keys = set()
    for s in signals:
        key = s.get("key")
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        meta = CATALYST_TIERS.get(key)
        if not meta:
            continue
        chosen.append({
            "key": key,
            "tier": meta["tier"],
            "points": meta["points"],
            "label": meta["label"],
            "details": s.get("details", ""),
        })
    if not chosen:
        return 0.0, []
    chosen.sort(key=lambda x: x["points"], reverse=True)
    primary = chosen[0]["points"]
    secondary_bonus = sum(c["points"] for c in chosen[1:]) * 0.25
    base = min(primary + secondary_bonus, 5.0)
    return base, chosen


def quality_factors(ticker_data):
    factors = []

    dvol = ticker_data.get("dollar_volume_20d")
    if dvol is not None:
        if dvol > 20_000_000:
            factors.append({"key": "liquidity", "points": 2.0, "label": f"liquid (${dvol/1e6:.1f}M avg $vol)"})
        elif dvol > 5_000_000:
            factors.append({"key": "liquidity", "points": 1.0, "label": f"adequate liquidity (${dvol/1e6:.1f}M)"})
        elif dvol < 1_000_000:
            factors.append({"key": "liquidity", "points": -2.0, "label": f"illiquid (${dvol/1e6:.2f}M)"})

    mcap = ticker_data.get("market_cap")
    if mcap is not None:
        if 200_000_000 <= mcap <= 5_000_000_000:
            factors.append({"key": "mcap", "points": 1.0, "label": f"sweet-spot mcap (${mcap/1e9:.2f}B)"})
        elif mcap < 50_000_000:
            factors.append({"key": "mcap", "points": -1.0, "label": f"micro-cap (${mcap/1e6:.0f}M)"})
        elif mcap > 10_000_000_000:
            factors.append({"key": "mcap", "points": -0.5, "label": f"large-cap, smaller % move ({mcap/1e9:.0f}B)"})

    above_200 = ticker_data.get("above_200dma")
    if above_200 is True:
        factors.append({"key": "trend", "points": 1.0, "label": "above 200dMA"})
    elif above_200 is False:
        factors.append({"key": "trend", "points": -1.0, "label": "below 200dMA"})

    pct_held = ticker_data.get("pct_inst_held")
    if pct_held is not None:
        if pct_held > 40:
            factors.append({"key": "institutional", "points": 0.5, "label": f"inst held {pct_held:.0f}%"})
        elif pct_held < 10:
            factors.append({"key": "institutional", "points": -0.5, "label": f"low inst {pct_held:.0f}%"})

    si = ticker_data.get("short_pct_float")
    if si is not None:
        if 15 <= si <= 30:
            factors.append({"key": "short_interest", "points": 1.0, "label": f"squeeze fuel SI {si:.0f}%"})
        elif si > 40:
            factors.append({"key": "short_interest", "points": -0.5, "label": f"crowded short SI {si:.0f}%"})

    if ticker_data.get("going_concern"):
        factors.append({"key": "going_concern", "points": -2.0, "label": "going-concern flag"})

    if ticker_data.get("recent_shelf"):
        factors.append({"key": "dilution", "points": -1.0, "label": "recent shelf / ATM offering"})

    if ticker_data.get("sector_tailwind"):
        factors.append({"key": "sector", "points": 0.5, "label": "sector tailwind 5d"})

    if ticker_data.get("cohort_stack"):
        factors.append({"key": "cohort_stack", "points": 1.0, "label": "multi-cohort overlap"})

    if ticker_data.get("beat_streak"):
        factors.append({"key": "beat_streak", "points": 1.5, "label": "3+ consecutive earnings beats"})

    total_mod = sum(f["points"] for f in factors)
    total_mod = max(-3.0, min(3.0, total_mod))
    return total_mod, factors


def score_ticker(ticker, signals, ticker_data):
    base, catalysts = base_catalyst_score(signals)
    mod, factors = quality_factors(ticker_data)
    if base == 0:
        final = 0.0
    else:
        final = round(min(10.0, max(0.0, base * 1.5 + mod)), 1)

    if final >= 8.0:
        bucket = "STRONG"
    elif final >= 6.0:
        bucket = "WATCH"
    elif final >= 4.0:
        bucket = "SPECULATIVE"
    else:
        bucket = "BELOW_THRESHOLD"

    primary_catalyst = catalysts[0] if catalysts else None
    catalyst_tier = primary_catalyst["tier"] if primary_catalyst else "-"

    return {
        "ticker": ticker,
        "score": final,
        "bucket": bucket,
        "catalyst_tier": catalyst_tier,
        "base_points": round(base, 2),
        "modifier_points": round(mod, 2),
        "catalysts": catalysts,
        "factors": factors,
    }
