def analyze_options_market(candidate):
    opts = candidate.get("options_check") or {}
    flow = candidate.get("options_flow") or {}
    iv_analysis = candidate.get("iv_percentile_analysis") or {}

    implied_move = opts.get("implied_move_1d_pct") or opts.get("implied_move_pct")
    deep = candidate.get("deep_research") or {}
    expected_move = deep.get("expected_move") or {}
    analog = deep.get("analog_precedent") or {}
    analog_median = analog.get("median_next_day_pct")

    edge_label = None
    edge_direction = None
    if implied_move is not None and analog_median is not None:
        try:
            im = float(implied_move)
            am = abs(float(analog_median))
            if am > 0:
                ratio = im / am
                if ratio < 0.8:
                    edge_label = "MARKET_UNDERPRICING"
                    edge_direction = "bullish_for_premium_buyer"
                elif ratio > 1.3:
                    edge_label = "MARKET_OVERPRICING"
                    edge_direction = "bearish_for_premium_buyer"
                else:
                    edge_label = "FAIRLY_PRICED"
                    edge_direction = "neutral"
        except (TypeError, ValueError):
            pass

    skew_atm = flow.get("atm_iv_skew_pct")
    skew_signal = None
    if skew_atm is not None:
        try:
            s = float(skew_atm)
            if s < -3:
                skew_signal = "calls_expensive_vs_puts_BULLISH_positioning"
            elif s > 5:
                skew_signal = "puts_expensive_vs_calls_BEARISH_positioning"
        except (TypeError, ValueError):
            pass

    cp_ratio = flow.get("call_put_ratio")
    cp_signal = None
    if cp_ratio is not None:
        try:
            cp = float(cp_ratio)
            if cp >= 3:
                cp_signal = f"call/put {cp:.1f}x — heavy bullish positioning"
            elif cp >= 2:
                cp_signal = f"call/put {cp:.1f}x — bullish positioning"
            elif cp <= 0.5:
                cp_signal = f"call/put {cp:.2f}x — bearish positioning"
        except (TypeError, ValueError):
            pass

    blocks = flow.get("block_trades") or []
    call_blocks = [b for b in blocks if b.get("type") == "call"]
    put_blocks = [b for b in blocks if b.get("type") == "put"]
    block_summary = None
    if call_blocks or put_blocks:
        call_premium = sum(b.get("premium_value", 0) for b in call_blocks)
        put_premium = sum(b.get("premium_value", 0) for b in put_blocks)
        if call_premium > put_premium * 2 and call_premium >= 100_000:
            block_summary = f"{len(call_blocks)} call blocks worth ${call_premium/1000:.0f}k (smart money long)"
        elif put_premium > call_premium * 2 and put_premium >= 100_000:
            block_summary = f"{len(put_blocks)} put blocks worth ${put_premium/1000:.0f}k (smart money hedging/short)"

    out = {
        "implied_move_pct": implied_move,
        "analog_median_move_pct": analog_median,
        "edge_label": edge_label,
        "edge_direction": edge_direction,
        "skew_signal": skew_signal,
        "cp_signal": cp_signal,
        "block_summary": block_summary,
        "iv_percentile": iv_analysis.get("iv_percentile"),
        "iv_regime": (iv_analysis.get("interpretation") or {}).get("regime"),
    }
    candidate["_options_market_read"] = out
    return out


def apply_options_market_critic(candidates, verbose=False):
    edge_count = 0
    for s in candidates:
        result = analyze_options_market(s)
        if result.get("edge_label") == "MARKET_UNDERPRICING":
            edge_count += 1
    if verbose:
        print(f"  options market critic: {edge_count}/{len(candidates)} have market-underpricing edge")
    return candidates
