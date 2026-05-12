SIGNAL_CATEGORIES = {
    "catalyst": ["catalyst_quality", "earnings_signal", "fda_signal", "ma_signal", "index_inclusion"],
    "insider": ["insider_depth", "form4_cluster"],
    "institutional": ["institutional_ownership", "13f_delta"],
    "options_flow": ["options_flow", "unusual_options"],
    "technical": ["trend_template", "above_50dma", "above_200dma", "breakout"],
    "fundamental": ["analyst_changes", "earnings_revisions", "valuation"],
    "post_earnings": ["post_earnings_drift"],
    "macro_sector": ["sector_momentum", "sympathy", "crypto_regime"],
    "news_quality": ["news", "freshness"],
    "theme": ["position_in_theme", "factor_match"],
}


def count_active_categories(candidate):
    components = candidate.get("components") or {}
    catalysts = candidate.get("catalysts") or []
    catalyst_keys = {c.get("key") for c in catalysts if isinstance(c, dict)}
    insider_depth = candidate.get("insider_depth") or {}
    options_flow = candidate.get("options_flow") or {}
    smart_money = candidate.get("_smart_money_signals") or []
    extension = candidate.get("_extension_check") or {}

    active = set()

    if any(components.get(k, {}).get("points", 0) >= 2 for k in ["catalyst_quality"]) or catalyst_keys:
        active.add("catalyst")

    if (insider_depth.get("buyer_count") or 0) >= 3 or "insider_cluster" in smart_money:
        active.add("insider")

    if "13f_accumulation" in smart_money:
        active.add("institutional")

    if "options_flow_bullish" in smart_money or options_flow.get("sentiment") == "BULLISH":
        active.add("options_flow")

    if components.get("trend_template", {}).get("points", 0) >= 2 or candidate.get("above_50dma"):
        active.add("technical")

    if components.get("analyst_changes", {}).get("points", 0) >= 3:
        active.add("fundamental")

    if components.get("post_earnings_drift", {}).get("points", 0) >= 3:
        active.add("post_earnings")

    if components.get("sympathy", {}).get("points", 0) >= 2 or components.get("crypto_regime", {}).get("points", 0) >= 3:
        active.add("macro_sector")

    if components.get("news", {}).get("points", 0) >= 3 or components.get("freshness", {}).get("points", 0) >= 2:
        active.add("news_quality")

    if components.get("position_in_theme", {}).get("points", 0) >= 3:
        active.add("theme")

    return active


def stacking_multiplier(category_count):
    if category_count >= 7:
        return 20.0
    if category_count == 6:
        return 8.0
    if category_count == 5:
        return 4.0
    if category_count == 4:
        return 2.0
    return 1.0


def apply_stacking(candidates, verbose=False):
    for s in candidates:
        active_cats = count_active_categories(s)
        mult = stacking_multiplier(len(active_cats))
        s["_active_categories"] = sorted(active_cats)
        s["_category_count"] = len(active_cats)
        s["_stacking_multiplier"] = mult
        base = s.get("score") or 0
        s["_pre_stack_score"] = base
        s["_stacked_score"] = round(base * mult, 2)
    if verbose:
        from collections import Counter
        dist = Counter(s["_category_count"] for s in candidates)
        print(f"  stacking distribution: " + " · ".join(f"{k}cat={v}" for k, v in sorted(dist.items())))
    return candidates
