from src.catalyst.iv_percentile import iv_passes_bracket_gate
from src.catalyst.sector_rotation_gate import sector_gate_passes


def analog_passes_bracket_gate(candidate, bracket, tier):
    aset = candidate.get("analog_set") or {}
    if not aset:
        return True
    stats = aset.get("statistics") or {}
    n = stats.get("n_analogs") or 0
    win_rate = stats.get("win_rate_next_day_pct") or 0
    if tier == "A++":
        thresholds = {"micro": {"min_n": 6, "min_win": 65}, "small": {"min_n": 7, "min_win": 60}, "mid": {"min_n": 7, "min_win": 55}}
    elif tier == "A+":
        thresholds = {"micro": {"min_n": 4, "min_win": 55}, "small": {"min_n": 5, "min_win": 50}, "mid": {"min_n": 5, "min_win": 45}}
    else:
        thresholds = {"micro": {"min_n": 3, "min_win": 45}, "small": {"min_n": 3, "min_win": 40}, "mid": {"min_n": 3, "min_win": 35}}
    t = thresholds.get(bracket, {"min_n": 3, "min_win": 45})
    return n >= t["min_n"] and win_rate >= t["min_win"]


TIER_ORDER = {"REJECT": 0, "A": 1, "A+": 2, "A++": 3}
TIER_ABOVE = {"A++": "A+", "A+": "A", "A": "REJECT"}


def _min_tier(a, b):
    return a if TIER_ORDER.get(a, 0) <= TIER_ORDER.get(b, 0) else b


def _demote(tier):
    return TIER_ABOVE.get(tier, "REJECT")


def evaluate_tier(candidate, bracket, regime_info=None):
    cat_count = candidate.get("_category_count") or 0

    # Path 3 / Option C: positioning-first promotion path.
    # ELITE/STRONG positioning conviction promotes the pick into AA tiers
    # regardless of backward-looking _category_count. This kills the Minervini-pillar
    # gating that was filtering out crowded-short / crowded-long names before
    # their positioning thesis was ever evaluated.
    pf = candidate.get("_positioning_first") or {}
    pf_tier = pf.get("conviction_tier")
    pf_score = pf.get("score") or 0
    if pf_tier == "ELITE" and pf_score >= 70:
        proposed = "A++"
    elif pf_tier == "STRONG" and pf_score >= 55:
        proposed = "A+"
    elif pf_tier == "MODERATE" and pf_score >= 40:
        proposed = "A"
    elif bracket == "micro":
        if cat_count >= 5:
            proposed = "A++"
        elif cat_count >= 4:
            proposed = "A+"
        elif cat_count >= 3:
            proposed = "A"
        else:
            return {"tier": "REJECT", "reason": f"only {cat_count} stacked categories (micro needs 3+ for A) and no positioning edge"}
    elif bracket == "small":
        if cat_count >= 6:
            proposed = "A++"
        elif cat_count >= 4:
            proposed = "A+"
        elif cat_count >= 3:
            proposed = "A"
        else:
            return {"tier": "REJECT", "reason": f"only {cat_count} stacked categories (small needs 3+ for A) and no positioning edge"}
    else:
        if cat_count >= 7:
            proposed = "A++"
        elif cat_count >= 5:
            proposed = "A+"
        elif cat_count >= 4:
            proposed = "A"
        else:
            return {"tier": "REJECT", "reason": f"only {cat_count} stacked categories (mid needs 4+ for A) and no positioning edge"}

    demotions = []
    pf_side = pf.get("side")

    ext_cap = candidate.get("_extension_tier_cap") or "A++"
    # PUT-side positioning picks SKIP extension cap entirely - extension IS the put thesis.
    if pf_side == "PUT":
        demotions.append(f"PUT-side: skipped extension cap (extension is the thesis)")
    elif ext_cap == "REJECT":
        # Allow ELITE positioning to override extension reject for CALL side
        # (e.g., crowded short + breakout extension can still be valid)
        if pf_tier == "ELITE" and pf_score >= 75:
            demotions.append(f"ELITE positioning override of extension REJECT")
        else:
            return {"tier": "REJECT", "reason": "extension filter REJECT (2+ red flags on returns/MA distance)"}
    elif TIER_ORDER.get(ext_cap, 3) < TIER_ORDER.get(proposed, 0):
        # ELITE/STRONG positioning gets to ignore extension cap demotion
        if pf_tier in ("ELITE", "STRONG"):
            demotions.append(f"positioning {pf_tier} override of extension cap {ext_cap}")
        else:
            demotions.append(f"extension cap → {ext_cap}")
            proposed = ext_cap

    if candidate.get("_landmine_red", 0) > 0:
        flags = candidate.get("_landmine_flags") or []
        red_labels = [f["label"] for f in flags if f["severity"] == "RED"][:2]
        # PUT-side: some red landmines (dilution, going concern, CRL, exec turmoil) are
        # actually the SHORT thesis. Skip rejection.
        if pf_side == "PUT":
            demotions.append(f"PUT-side: landmine REDs are short thesis: {'; '.join(red_labels)}")
        else:
            return {"tier": "REJECT", "reason": f"RED landmine: {'; '.join(red_labels)}"}
    if candidate.get("_landmine_yellow", 0) >= 2:
        flags = candidate.get("_landmine_flags") or []
        yel_labels = [f["label"] for f in flags if f["severity"] == "YELLOW"][:2]
        if pf_side == "PUT":
            demotions.append(f"PUT-side: 2+ YELLOW landmines acceptable: {'; '.join(yel_labels)}")
        else:
            return {"tier": "REJECT", "reason": f"2+ YELLOW landmines: {'; '.join(yel_labels)}"}

    sm_signals = candidate.get("_smart_money_signals") or []
    # ELITE/STRONG positioning override smart-money requirements:
    # the positioning IS the alpha source; we don't need 13F confirmation.
    if pf_tier in ("ELITE", "STRONG"):
        demotions.append(f"positioning {pf_tier}: smart-money requirement waived")
    else:
        if proposed == "A++" and len(sm_signals) < 2:
            demotions.append(f"smart-money <2 (got {len(sm_signals)}) -> A+")
            proposed = "A+"
        if proposed == "A+" and len(sm_signals) < 1:
            demotions.append("no smart-money -> A")
            proposed = "A"

    # ELITE positioning bypasses IV/analog/sector gating entirely.
    # The positioning thesis is the primary edge, not historical analogs or sector flow.
    if pf_tier == "ELITE" and pf_score >= 70:
        demotions.append("ELITE positioning: IV/analog/sector gates bypassed")
    else:
        while proposed != "REJECT":
            if iv_passes_bracket_gate(candidate, bracket, proposed):
                break
            prev = proposed
            proposed = _demote(proposed)
            if proposed != "REJECT":
                demotions.append(f"IV too high for {prev} → demoted to {proposed}")
        if proposed == "REJECT":
            ivp = (candidate.get("iv_percentile_analysis") or {}).get("iv_percentile")
            return {"tier": "REJECT", "reason": f"IV percentile {ivp} too high for any tier in {bracket} bracket"}

        while proposed != "REJECT":
            if analog_passes_bracket_gate(candidate, bracket, proposed):
                break
            prev = proposed
            proposed = _demote(proposed)
            if proposed != "REJECT":
                demotions.append(f"weak analogs for {prev} → demoted to {proposed}")
        if proposed == "REJECT":
            aset = (candidate.get("analog_set") or {}).get("statistics") or {}
            return {"tier": "REJECT", "reason": f"analog hit-rate {aset.get('win_rate_next_day_pct', 'n/a')}% insufficient for any tier"}

        sector_rot = candidate.get("_sector_rotation") or {}
        while proposed != "REJECT":
            if sector_gate_passes(sector_rot.get("verdict"), proposed):
                break
            prev = proposed
            proposed = _demote(proposed)
            if proposed != "REJECT":
                demotions.append(f"sector {sector_rot.get('verdict')} → demoted from {prev} to {proposed}")
        if proposed == "REJECT":
            return {"tier": "REJECT", "reason": f"sector ETF in {sector_rot.get('verdict')} — headwind too strong for any tier"}

    if regime_info and pf_tier != "ELITE":
        from src.catalyst.vol_regime_tuner import cap_tier_by_regime
        capped = cap_tier_by_regime(proposed, regime_info)
        if TIER_ORDER.get(capped, 0) < TIER_ORDER.get(proposed, 0):
            demotions.append(f"vol regime '{regime_info.get('regime')}' capped {proposed} → {capped}")
            proposed = capped
    elif regime_info and pf_tier == "ELITE":
        demotions.append(f"ELITE positioning: vol regime cap bypassed")

    counter = candidate.get("counter_thesis") or {}
    # counter_thesis was built for backward-looking bull cases; PUT-side picks
    # are SHORT theses so the bull-case rejection doesn't apply.
    if counter.get("verdict_on_bull_thesis") == "REJECTED" and pf_side != "PUT":
        if pf_tier == "ELITE":
            demotions.append(f"ELITE positioning override of counter-thesis REJECT")
        else:
            return {"tier": "REJECT", "reason": f"counter-thesis: {counter.get('what_kills_this_trade', 'bear case strong')[:120]}"}

    composite = candidate.get("composite_quality") or {}
    if composite.get("composite_score", 50) < 30:
        # ELITE positioning waives composite quality (the positioning extreme IS the edge,
        # even if the underlying business quality scores low)
        if pf_tier == "ELITE":
            demotions.append(f"ELITE positioning: composite quality gate waived")
        else:
            flags = composite.get("flags") or []
            return {"tier": "REJECT", "reason": f"quality red flag: {'; '.join(flags[:2])}"}

    reason_parts = [f"passed all gates as {proposed}"]
    if demotions:
        reason_parts.append("demotions: " + " · ".join(demotions))
    return {"tier": proposed, "reason": "; ".join(reason_parts), "_demotions": demotions}


def assign_tiers(candidates_by_bracket, regime_info=None, verbose=False):
    results = {"A++": [], "A+": [], "A": [], "REJECT": []}
    rejection_log = []

    for bracket in ("micro", "small", "mid"):
        bucket = candidates_by_bracket.get(bracket, [])
        for s in bucket:
            verdict = evaluate_tier(s, bracket, regime_info=regime_info)
            tier = verdict["tier"]
            s["_aa_tier"] = tier
            s["_aa_reason"] = verdict["reason"]
            s["_aa_demotions"] = verdict.get("_demotions") or []
            if tier == "REJECT":
                rejection_log.append({
                    "ticker": s.get("ticker"),
                    "bracket": bracket,
                    "reason": verdict["reason"],
                    "stacked_score": s.get("_stacked_score") or s.get("score") or 0,
                })
                results["REJECT"].append(s)
            else:
                results[tier].append(s)

    rejection_log.sort(key=lambda r: r["stacked_score"], reverse=True)

    for tier_key in ("A++", "A+", "A"):
        results[tier_key].sort(key=lambda s: s.get("_stacked_score") or s.get("score") or 0, reverse=True)

    if verbose:
        print(f"  AA gates: A++ = {len(results['A++'])}, A+ = {len(results['A+'])}, A = {len(results['A'])}, REJECT = {len(results['REJECT'])}")
    return results, rejection_log


def pick_top_per_bracket(tier_results, per_bracket=2):
    by_bracket_tier = {}
    for tier in ("A++", "A+", "A"):
        for s in tier_results.get(tier, []):
            bracket = s.get("bracket")
            by_bracket_tier.setdefault(bracket, []).append(s)
    out = {}
    for bracket in ("micro", "small", "mid"):
        names = by_bracket_tier.get(bracket, [])
        out[bracket] = names[:per_bracket]
    return out
