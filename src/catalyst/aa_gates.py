from src.catalyst.iv_percentile import iv_passes_bracket_gate
from src.catalyst.analog_statistician import analog_passes_bracket_gate
from src.catalyst.sector_rotation_gate import sector_gate_passes


def evaluate_tier(candidate, bracket, regime_info=None):
    proposed = "A"

    cat_count = candidate.get("_category_count") or 0
    if cat_count >= 7:
        proposed = "A++"
    elif cat_count >= 5:
        proposed = "A+"
    elif cat_count >= 4:
        proposed = "A"
    else:
        return {"tier": "REJECT", "reason": f"only {cat_count} stacked categories, need 4+"}

    ext_cap = candidate.get("_extension_tier_cap") or "A++"
    tier_order = {"REJECT": 0, "A": 1, "A+": 2, "A++": 3}
    if tier_order.get(ext_cap, 0) < tier_order.get(proposed, 0):
        proposed = ext_cap

    if candidate.get("_landmine_red", 0) > 0:
        return {"tier": "REJECT", "reason": f"{candidate['_landmine_red']} RED landmine flag(s)"}
    if candidate.get("_landmine_yellow", 0) >= 2:
        return {"tier": "REJECT", "reason": "2+ YELLOW landmine flags"}

    sm_signals = candidate.get("_smart_money_signals") or []
    if proposed == "A++" and len(sm_signals) < 2:
        proposed = "A+"
    if proposed == "A+" and len(sm_signals) < 1:
        proposed = "A"
    if proposed == "A" and not sm_signals:
        return {"tier": "REJECT", "reason": "no smart money signal — required for A grade"}

    if not iv_passes_bracket_gate(candidate, bracket, proposed):
        ivp = (candidate.get("iv_percentile_analysis") or {}).get("iv_percentile")
        return {"tier": "REJECT", "reason": f"IV percentile {ivp} too high for {bracket} {proposed}"}

    if not analog_passes_bracket_gate(candidate, bracket, proposed):
        aset = (candidate.get("analog_set") or {}).get("statistics") or {}
        return {"tier": "REJECT", "reason": f"analog hit-rate {aset.get('win_rate_next_day_pct', '?')}% insufficient for {bracket} {proposed}"}

    sector_rot = candidate.get("_sector_rotation") or {}
    if not sector_gate_passes(sector_rot.get("verdict"), proposed):
        return {"tier": "REJECT", "reason": f"sector rotation {sector_rot.get('verdict')} not OK for {proposed}"}

    if regime_info:
        from src.catalyst.vol_regime_tuner import cap_tier_by_regime
        capped = cap_tier_by_regime(proposed, regime_info)
        if capped != proposed:
            return {"tier": capped, "reason": f"vol regime capped from {proposed} to {capped} ({regime_info.get('regime')})"}

    counter = candidate.get("counter_thesis") or {}
    if counter.get("verdict_on_bull_thesis") == "REJECTED":
        return {"tier": "REJECT", "reason": "counter-thesis rejected bull case"}

    composite = candidate.get("composite_quality") or {}
    if composite.get("composite_score", 50) < 30:
        return {"tier": "REJECT", "reason": "composite quality score < 30 (Altman/Piotroski/Beneish flags)"}

    return {"tier": proposed, "reason": "passed all gates"}


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
            if tier == "REJECT":
                rejection_log.append({"ticker": s.get("ticker"), "bracket": bracket, "reason": verdict["reason"]})
                results["REJECT"].append(s)
            else:
                results[tier].append(s)

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
