from src.catalyst.factor_screener import compute_factor_matches


def compute_theme_universe_returns(scored_results, days_back=180):
    theme_to_tickers = {}
    for s in scored_results:
        result = compute_factor_matches(s)
        for f in result.get("matched_factors", []):
            if f.get("type") != "theme":
                continue
            theme = f["factor_id"]
            ticker = s.get("ticker")
            if not ticker:
                continue
            ret_pct = _approx_return_pct(s, days_back)
            if ret_pct is None:
                continue
            theme_to_tickers.setdefault(theme, []).append({
                "ticker": ticker,
                "return_pct": ret_pct,
                "market_cap": s.get("market_cap") or 0,
            })
    return theme_to_tickers


def _approx_return_pct(s, days_back):
    drift = s.get("drift") or {}
    roc = drift.get("roc_10d")
    if roc is not None:
        return roc * (days_back / 10) * 0.5
    return None


def position_in_theme(ticker, theme_id, theme_to_tickers):
    members = theme_to_tickers.get(theme_id, [])
    if not members or len(members) < 3:
        return {"rank": "unknown", "asymmetry": "UNKNOWN", "comment": f"only {len(members)} members in theme"}
    sorted_members = sorted(members, key=lambda m: m["return_pct"], reverse=True)
    n = len(sorted_members)
    target = next((i for i, m in enumerate(sorted_members) if m["ticker"] == ticker), None)
    if target is None:
        return {"rank": "unknown", "asymmetry": "UNKNOWN"}

    percentile = (n - target) / n * 100
    median_return = sorted_members[n // 2]["return_pct"]
    target_return = sorted_members[target]["return_pct"]

    if percentile >= 75:
        rank = "leader"
        asymmetry = "LOW"
    elif percentile >= 50:
        rank = "mid"
        asymmetry = "MEDIUM"
    elif percentile >= 25:
        rank = "laggard"
        asymmetry = "HIGH"
    else:
        rank = "deep_laggard"
        asymmetry = "HIGH"

    relative_to_median = target_return - median_return
    return {
        "rank": rank,
        "asymmetry": asymmetry,
        "percentile": round(percentile, 0),
        "target_return_pct": round(target_return, 1),
        "median_return_pct": round(median_return, 1),
        "relative_to_median_pct": round(relative_to_median, 1),
        "theme_size": n,
        "comment": f"{rank} in {n}-member theme (target {target_return:+.0f}% vs median {median_return:+.0f}%)",
    }


def annotate_with_position_in_theme(scored_results):
    theme_universe = compute_theme_universe_returns(scored_results)
    for s in scored_results:
        result = compute_factor_matches(s)
        themes = [f["factor_id"] for f in result.get("matched_factors", []) if f.get("type") == "theme"]
        if not themes:
            continue
        positions = []
        for theme in themes:
            pos = position_in_theme(s.get("ticker"), theme, theme_universe)
            positions.append({"theme": theme, **pos})
        positions.sort(key=lambda p: 0 if p.get("rank") == "deep_laggard" else 1 if p.get("rank") == "laggard" else 2)
        s["position_in_theme"] = positions[0] if positions else None
        s["position_in_theme_all"] = positions
    return scored_results
