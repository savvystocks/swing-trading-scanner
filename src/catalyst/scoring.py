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

WEIGHT_CATALYST = 8.0
WEIGHT_LIQUIDITY = 5.0
WEIGHT_NEWS = 15.0
WEIGHT_DRIFT = 10.0
WEIGHT_HISTORICAL = 10.0
WEIGHT_FRESHNESS = 5.0
WEIGHT_PEER = 5.0
WEIGHT_LLM = 30.0


def max_possible_base(signals):
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
    return min(primary + secondary, 5.0)


def max_possible_score(signals):
    base = max_possible_base(signals)
    return base * WEIGHT_CATALYST + 25 + WEIGHT_NEWS + WEIGHT_DRIFT + WEIGHT_HISTORICAL + WEIGHT_FRESHNESS + WEIGHT_PEER + WEIGHT_LLM


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


def liquidity_setup_score(ticker_data, points_max=25.0):
    points = 0.0
    factors = []

    dvol = ticker_data.get("dollar_volume_20d")
    if dvol is not None:
        if dvol > 50_000_000:
            points += 8
            factors.append(f"+8 deep liquidity (${dvol/1e6:.0f}M)")
        elif dvol > 10_000_000:
            points += 6
            factors.append(f"+6 strong liquidity (${dvol/1e6:.0f}M)")
        elif dvol > 3_000_000:
            points += 3
            factors.append(f"+3 ok liquidity (${dvol/1e6:.0f}M)")
        elif dvol < 500_000:
            points -= 5
            factors.append(f"-5 illiquid (${dvol/1e6:.2f}M)")

    mcap = ticker_data.get("market_cap")
    if mcap is not None:
        if 200_000_000 <= mcap <= 5_000_000_000:
            points += 6
            factors.append(f"+6 sweet-spot mcap (${mcap/1e9:.1f}B)")
        elif 50_000_000 <= mcap < 200_000_000 or 5_000_000_000 < mcap <= 20_000_000_000:
            points += 3
            factors.append(f"+3 viable mcap (${mcap/1e9:.1f}B)")
        elif mcap < 20_000_000:
            points -= 4
            factors.append(f"-4 micro-float (${mcap/1e6:.0f}M)")
        elif mcap > 100_000_000_000:
            points -= 2
            factors.append(f"-2 mega-cap (${mcap/1e9:.0f}B)")

    above_200 = ticker_data.get("above_200dma")
    if above_200 is True:
        points += 4
        factors.append("+4 above 200dMA")
    elif above_200 is False:
        points -= 3
        factors.append("-3 below 200dMA")

    pct_held = ticker_data.get("pct_inst_held")
    if pct_held is not None:
        if pct_held > 60:
            points += 3
            factors.append(f"+3 strong inst {pct_held:.0f}%")
        elif pct_held > 30:
            points += 1
            factors.append(f"+1 inst {pct_held:.0f}%")
        elif pct_held < 5:
            points -= 3
            factors.append(f"-3 shell-pattern inst {pct_held:.0f}%")

    si = ticker_data.get("short_pct_float")
    if si is not None:
        if 15 <= si <= 30:
            points += 4
            factors.append(f"+4 squeeze fuel SI {si:.0f}%")
        elif 30 < si <= 45:
            points += 2
            factors.append(f"+2 high SI {si:.0f}%")
        elif si > 50:
            points -= 2
            factors.append(f"-2 crowded short SI {si:.0f}%")

    return {"points": round(min(points, points_max), 2), "factors": factors}


def red_flags_score(ticker_data):
    points = 0.0
    flags = []
    if ticker_data.get("going_concern"):
        points -= 8
        flags.append("-8 going-concern flag")
    if ticker_data.get("recent_shelf"):
        points -= 4
        flags.append("-4 recent shelf / dilution")
    return {"points": round(points, 2), "flags": flags}


def confidence_label(components):
    positive = 0
    if components.get("catalyst_quality", {}).get("points", 0) >= 16:
        positive += 1
    if components.get("liquidity_setup", {}).get("points", 0) >= 10:
        positive += 1
    if components.get("news", {}).get("points", 0) >= 8:
        positive += 1
    if components.get("drift", {}).get("points", 0) >= 5:
        positive += 1
    if components.get("historical", {}).get("points", 0) >= 5:
        positive += 1
    if components.get("freshness", {}).get("points", 0) >= 3:
        positive += 1
    if components.get("peer", {}).get("points", 0) >= 3:
        positive += 1
    if components.get("llm", {}).get("points", 0) >= 18:
        positive += 1

    if positive >= 5:
        return "HIGH"
    if positive >= 3:
        return "MEDIUM"
    return "LOW"


def score_ticker(ticker, signals, ticker_data, news_data=None, drift_data=None,
                 historical_data=None, peer_data=None, freshness_data=None, llm_data=None):
    base, catalysts = base_catalyst_score(signals)
    catalyst_pts = base * WEIGHT_CATALYST

    liq = liquidity_setup_score(ticker_data)
    red = red_flags_score(ticker_data)

    components = {
        "catalyst_quality": {"points": round(catalyst_pts, 2), "tier": catalysts[0]["tier"] if catalysts else "-", "details": [c["label"] for c in catalysts]},
        "liquidity_setup": liq,
        "news": news_data or {"points": 0.0, "label": "no news data"},
        "drift": drift_data or {"points": 0.0, "label": "no drift data"},
        "historical": historical_data or {"points": 0.0, "label": "no historical data"},
        "freshness": freshness_data or {"points": 0.0, "label": "no freshness data"},
        "peer": peer_data or {"points": 0.0, "label": "no peer data"},
        "llm": llm_data or {"points": 0.0, "label": "no LLM grade"},
        "red_flags": red,
    }

    if catalyst_pts <= 0:
        final = 0.0
    else:
        final = (
            catalyst_pts
            + liq["points"]
            + components["news"]["points"]
            + components["drift"]["points"]
            + components["historical"]["points"]
            + components["freshness"]["points"]
            + components["peer"]["points"]
            + components["llm"]["points"]
            + red["points"]
        )

    confidence = confidence_label(components)
    primary_catalyst = catalysts[0] if catalysts else None
    catalyst_tier = primary_catalyst["tier"] if primary_catalyst else "-"

    return {
        "ticker": ticker,
        "score": round(final, 2),
        "confidence": confidence,
        "catalyst_tier": catalyst_tier,
        "components": components,
        "catalysts": catalysts,
    }


def assign_buckets(scored_list, top_pct_strong=5, top_pct_watch=15):
    if not scored_list:
        return scored_list
    sorted_list = sorted(scored_list, key=lambda x: x["score"], reverse=True)
    n = len(sorted_list)
    strong_n = max(1, int(n * top_pct_strong / 100))
    watch_n = max(1, int(n * top_pct_watch / 100))

    threshold_strong = sorted_list[strong_n - 1]["score"] if n >= strong_n else float("inf")
    threshold_watch = sorted_list[min(watch_n - 1, n - 1)]["score"] if n >= watch_n else 0

    for i, c in enumerate(sorted_list):
        if i < strong_n and c["score"] > 0:
            c["bucket"] = "STRONG"
            c["percentile"] = round((1 - i / n) * 100, 1)
        elif i < watch_n and c["score"] > 0:
            c["bucket"] = "WATCH"
            c["percentile"] = round((1 - i / n) * 100, 1)
        elif c["score"] > 0:
            c["bucket"] = "SPECULATIVE"
            c["percentile"] = round((1 - i / n) * 100, 1)
        else:
            c["bucket"] = "BELOW_THRESHOLD"
            c["percentile"] = 0
    return sorted_list
