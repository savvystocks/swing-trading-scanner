CATALYST_TIERS = {
    "earnings_bmo_with_beat_streak": {"tier": "S", "points": 5.0, "label": "Earnings BMO + beat streak", "direction": "bull", "event_timing": "scheduled_overnight"},
    "fda_pdufa_tomorrow": {"tier": "S", "points": 5.0, "label": "FDA PDUFA decision tomorrow", "direction": "bull", "event_timing": "scheduled_overnight"},
    "merger_cash_buyout": {"tier": "S", "points": 5.0, "label": "Cash buyout announced", "direction": "bull", "event_timing": "post_event"},
    "major_contract_win": {"tier": "S", "points": 5.0, "label": "Material contract win", "direction": "bull", "event_timing": "post_event"},
    "index_inclusion": {"tier": "S", "points": 5.0, "label": "Index inclusion announced", "direction": "bull", "event_timing": "scheduled_overnight"},
    "macro_event_high_impact": {"tier": "A", "points": 4.0, "label": "High-impact macro event within 3d (CPI/FOMC/jobs)", "direction": "neutral", "event_timing": "scheduled_overnight"},

    "earnings_bmo_tomorrow": {"tier": "A", "points": 4.0, "label": "Earnings tomorrow before open", "direction": "bull", "event_timing": "scheduled_overnight"},
    "earnings_amc_today": {"tier": "A", "points": 4.0, "label": "Earnings tonight after close", "direction": "bull", "event_timing": "scheduled_overnight"},
    "asset_sale": {"tier": "A", "points": 4.0, "label": "Asset purchase agreement", "direction": "bull", "event_timing": "post_event"},
    "merger": {"tier": "A", "points": 4.0, "label": "Merger agreement filed", "direction": "bull", "event_timing": "post_event"},
    "fda_event": {"tier": "B", "points": 3.5, "label": "FDA / PDUFA event filed", "direction": "bull", "event_timing": "fresh_breaking"},
    "clinical_milestone": {"tier": "B", "points": 3.5, "label": "Clinical milestone (Phase 1/2/3)", "direction": "bull", "event_timing": "fresh_breaking"},
    "definitive_agreement": {"tier": "A", "points": 3.5, "label": "Material definitive agreement", "direction": "bull", "event_timing": "post_event"},

    "strategic_investment": {"tier": "S", "points": 5.0, "label": "Strategic investment from hyperscaler/NVIDIA", "direction": "bull", "event_timing": "post_event"},
    "capex_echo": {"tier": "A", "points": 4.0, "label": "Hyperscaler capex echo (named customer)", "direction": "bull", "event_timing": "ongoing"},
    "revision_spike": {"tier": "A", "points": 4.0, "label": "EPS revision spike (estimates raised)", "direction": "bull", "event_timing": "ongoing"},
    "backlog_surge": {"tier": "A", "points": 3.5, "label": "Record backlog / RPO surge", "direction": "bull", "event_timing": "ongoing"},
    "spinoff_catalyst": {"tier": "B", "points": 3.0, "label": "Spinoff / separation catalyst", "direction": "bull", "event_timing": "scheduled_overnight"},

    "private_placement": {"tier": "B", "points": 3.0, "label": "Private placement filed", "direction": "bull", "event_timing": "post_event"},
    "covenant_relief": {"tier": "B", "points": 3.0, "label": "Forbearance / covenant relief", "direction": "bull", "event_timing": "post_event"},
    "strategic_partnership": {"tier": "A", "points": 4.0, "label": "Strategic partnership (esp. tech/AI deals)", "direction": "bull", "event_timing": "post_event"},
    "contract_win": {"tier": "A", "points": 4.0, "label": "Contract or tender award (defense/infra/enterprise)", "direction": "bull", "event_timing": "post_event"},
    "activist_stake": {"tier": "B", "points": 3.0, "label": "Activist 13D stake disclosed", "direction": "bull", "event_timing": "post_event"},

    "insider_cluster": {"tier": "C", "points": 2.0, "label": "Form 4 insider buying cluster", "direction": "bull", "event_timing": "ongoing"},
    "cohort_high_momentum_runners": {"tier": "A", "points": 4.0, "label": "High-momentum mid-cap (space/quantum/nuclear/AI/robotics)", "direction": "bull", "event_timing": "ongoing"},
    "cohort_recent_gappers_30d": {"tier": "B", "points": 3.0, "label": "Recent 30d gapper >=25% (in-motion name)", "direction": "bull", "event_timing": "ongoing"},
    "cohort_ai_infra_pureplay": {"tier": "A", "points": 4.5, "label": "AI infrastructure pure-play (hyperscaler-tied) - TECH PRIORITY", "direction": "bull", "event_timing": "ongoing"},
    "cohort_china_megacap_adrs": {"tier": "C", "points": 2.0, "label": "China mega-cap ADR (BABA/JD/PDD-style)", "direction": "bull", "event_timing": "ongoing"},
    "cohort_uk_dual_listed_adrs": {"tier": "C", "points": 2.0, "label": "UK dual-listed ADR (LSE + NYSE)", "direction": "bull", "event_timing": "ongoing"},
    "cohort_mega_cap_ai_tech": {"tier": "B", "points": 3.0, "label": "Mega-cap AI/tech (NVDA/AMD/QCOM/AMAT-style)", "direction": "bull", "event_timing": "ongoing"},
    "cohort_lazar_plays": {"tier": "C", "points": 2.0, "label": "Lazar Capital portfolio name", "direction": "bull", "event_timing": "ongoing"},
    "cohort_crypto_treasury": {"tier": "C", "points": 2.0, "label": "Crypto-treasury cohort", "direction": "bull", "event_timing": "ongoing"},
    "cohort_prediction_markets": {"tier": "C", "points": 2.0, "label": "Prediction market cohort", "direction": "bull", "event_timing": "ongoing"},
    "cohort_biotech_binary": {"tier": "C", "points": 2.0, "label": "Biotech binary catalyst cohort", "direction": "bull", "event_timing": "ongoing"},
    "earnings_spillover": {"tier": "B", "points": 3.0, "label": "Earnings spillover from cohort peer in <=3d", "direction": "bull", "event_timing": "pre_event"},
    "sympathy_continuation": {"tier": "B", "points": 3.0, "label": "Sympathy continuation from cohort peer move", "direction": "bull", "event_timing": "ongoing"},
    "insider_window": {"tier": "B", "points": 2.5, "label": "Insider buying in last 14d", "direction": "bull", "event_timing": "ongoing"},
    "earnings_lead_up_10_15d": {"tier": "B", "points": 3.5, "label": "Earnings in 10-15d (sweet spot for pre-event run-up)", "direction": "bull", "event_timing": "pre_event"},
    "earnings_imminent_5_9d": {"tier": "B", "points": 3.0, "label": "Earnings in 5-9d (IV expansion zone)", "direction": "bull", "event_timing": "pre_event"},
    "earnings_peak_iv_3_4d": {"tier": "C", "points": 2.0, "label": "Earnings in 3-4d (peak IV, late entry)", "direction": "bull", "event_timing": "pre_event"},
    "ai_deal_announcement": {"tier": "A", "points": 4.5, "label": "AI/cloud deal w/ hyperscaler (NVDA/MSFT/META/AMZN partner)", "direction": "bull", "event_timing": "post_event"},
    "semis_capex_signal": {"tier": "A", "points": 4.0, "label": "Semis capex cycle signal (TSM/AMAT/LRCX guide-up)", "direction": "bull", "event_timing": "ongoing"},
    "defense_contract_award": {"tier": "A", "points": 4.0, "label": "DOD/major defense contract awarded", "direction": "bull", "event_timing": "post_event"},
    "bank_post_earnings_drift": {"tier": "B", "points": 3.0, "label": "Bank beat by >2 sigma in last 5d (continuation)", "direction": "bull", "event_timing": "post_event"},
    "commodity_breakout": {"tier": "C", "points": 2.5, "label": "Oil/gas/copper breaks 50d high (energy/materials beta)", "direction": "bull", "event_timing": "ongoing"},
    "post_earnings_beat": {"tier": "A", "points": 4.0, "label": "Beat + raised guide in last 1-5d (sector-neutral drift)", "direction": "bull", "event_timing": "post_event"},
    "buyback": {"tier": "C", "points": 1.5, "label": "Buyback program announced", "direction": "bull", "event_timing": "post_event"},

    "rebrand": {"tier": "D", "points": 1.0, "label": "Rebrand / name change", "direction": "bull", "event_timing": "post_event"},
    "cohort_ai_rebrand": {"tier": "D", "points": 1.0, "label": "AI rebrand cohort", "direction": "bull", "event_timing": "ongoing"},
    "cohort_cannabis_basket": {"tier": "D", "points": 1.0, "label": "Cannabis sector cohort", "direction": "bull", "event_timing": "ongoing"},
    "cohort_small_cap_china_adr": {"tier": "D", "points": 0.5, "label": "Small-cap China ADR cohort", "direction": "bull", "event_timing": "ongoing"},

    "going_concern": {"tier": "S", "points": 5.0, "label": "Going concern language in 10-Q/K", "direction": "bear"},
    "earnings_miss_with_guide_down": {"tier": "S", "points": 5.0, "label": "Earnings miss + guidance lowered", "direction": "bear"},
    "fda_rejection": {"tier": "S", "points": 5.0, "label": "FDA CRL / drug rejection", "direction": "bear"},
    "merger_terminated": {"tier": "A", "points": 4.0, "label": "M&A deal terminated", "direction": "bear"},
    "dilutive_offering": {"tier": "A", "points": 4.0, "label": "Dilutive share offering at discount", "direction": "bear"},
    "reverse_stock_split": {"tier": "A", "points": 4.0, "label": "Reverse stock split announced", "direction": "bear"},
    "lawsuit_material": {"tier": "A", "points": 3.5, "label": "Material lawsuit / SEC inquiry", "direction": "bear"},
    "downgrade_cluster": {"tier": "B", "points": 3.0, "label": "Multiple analyst downgrades 30d", "direction": "bear"},
    "auditor_change": {"tier": "B", "points": 3.0, "label": "Auditor resignation", "direction": "bear"},
    "delisting_warning": {"tier": "B", "points": 3.0, "label": "Exchange delisting notice", "direction": "bear"},
    "restatement": {"tier": "B", "points": 3.0, "label": "Financial restatement", "direction": "bear"},
    "executive_departure": {"tier": "C", "points": 2.0, "label": "CEO/CFO departure", "direction": "bear"},
    "insider_selling_cluster": {"tier": "C", "points": 2.0, "label": "Heavy insider selling cluster", "direction": "bear"},
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
            "direction": meta.get("direction", "bull"),
            "event_timing": meta.get("event_timing", "ongoing"),
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


def cross_confirmation_score(catalysts_full):
    if not catalysts_full:
        return {"points": 0.0, "label": "no catalysts", "count": 0, "multiplier_label": "NONE"}
    n = len(catalysts_full)
    if n >= 4:
        return {"points": 15.0, "label": f"HIGH conviction ({n} catalysts cross-confirm)", "count": n, "multiplier_label": "HIGH"}
    if n >= 3:
        return {"points": 10.0, "label": f"STRONG ({n} catalysts cross-confirm)", "count": n, "multiplier_label": "STRONG"}
    if n == 2:
        return {"points": 5.0, "label": "MODERATE (2 catalysts)", "count": n, "multiplier_label": "MODERATE"}
    return {"points": 0.0, "label": "single catalyst", "count": n, "multiplier_label": "SINGLE"}


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
        "catalyst_quality": {
            "points": round(catalyst_pts, 2),
            "tier": catalysts[0]["tier"] if catalysts else "-",
            "details": [c["label"] for c in catalysts],
            "catalysts_full": catalysts,
        },
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

    direction = "bull"
    if primary_catalyst:
        direction = primary_catalyst.get("direction", "bull")

    return {
        "ticker": ticker,
        "score": round(final, 2),
        "confidence": confidence,
        "catalyst_tier": catalyst_tier,
        "direction": direction,
        "components": components,
        "catalysts": catalysts,
    }


TIER_RANK = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1, "-": 0}


def _has_tier_min(candidate, min_tier_letter):
    min_rank = TIER_RANK.get(min_tier_letter, 0)
    catalysts = candidate.get("catalysts") or []
    for cat in catalysts:
        tier = cat.get("tier", "-")
        if TIER_RANK.get(tier, 0) >= min_rank:
            return True
    primary = candidate.get("catalyst_tier", "-")
    return TIER_RANK.get(primary, 0) >= min_rank


def assign_buckets(scored_list, top_pct_strong=5, top_pct_watch=15,
                   strong_min_tier="B", watch_min_tier="C", emit_d_tier=False):
    if not scored_list:
        return scored_list
    sorted_list = sorted(scored_list, key=lambda x: x["score"], reverse=True)
    n = len(sorted_list)
    strong_n = max(1, int(n * top_pct_strong / 100))
    watch_n = max(1, int(n * top_pct_watch / 100))

    promoted_to_strong = 0
    blocked_strong = 0
    d_tier_filtered = 0

    for i, c in enumerate(sorted_list):
        if c["score"] <= 0:
            c["bucket"] = "BELOW_THRESHOLD"
            c["percentile"] = 0
            continue

        if not emit_d_tier and not _has_tier_min(c, "C"):
            c["bucket"] = "BELOW_THRESHOLD"
            c["percentile"] = round((1 - i / n) * 100, 1)
            c["filter_reason"] = "D-tier-only catalyst"
            d_tier_filtered += 1
            continue

        if i < strong_n:
            if _has_tier_min(c, strong_min_tier):
                c["bucket"] = "STRONG"
                promoted_to_strong += 1
            else:
                c["bucket"] = "WATCH"
                c["filter_reason"] = f"score top-{top_pct_strong}% but no {strong_min_tier}+ tier catalyst"
                blocked_strong += 1
            c["percentile"] = round((1 - i / n) * 100, 1)
        elif i < watch_n:
            if _has_tier_min(c, watch_min_tier):
                c["bucket"] = "WATCH"
            else:
                c["bucket"] = "SPECULATIVE"
                c["filter_reason"] = f"top-{top_pct_watch}% but no {watch_min_tier}+ tier catalyst"
            c["percentile"] = round((1 - i / n) * 100, 1)
        else:
            c["bucket"] = "SPECULATIVE"
            c["percentile"] = round((1 - i / n) * 100, 1)

    return sorted_list
