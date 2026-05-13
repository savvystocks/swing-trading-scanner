def has_insider_cluster(candidate):
    depth = candidate.get("insider_depth") or {}
    cluster_size = depth.get("buyer_count") or 0
    total_value = depth.get("total_value_usd") or 0
    if cluster_size >= 3 and total_value >= 250_000:
        return True
    if depth.get("ceo_or_cfo_bought") and total_value >= 100_000:
        return True
    return False


def has_options_flow_bullish(candidate):
    flow = candidate.get("options_flow") or {}
    if flow.get("sentiment") == "BULLISH":
        return True
    cp = flow.get("call_put_ratio")
    if cp and cp >= 2.0:
        return True
    blocks = flow.get("block_trade_count") or 0
    if blocks >= 3 and len([b for b in (flow.get("block_trades") or []) if b.get("type") == "call"]) >= 2:
        return True
    return False


def has_activist_filing(candidate):
    cats = candidate.get("catalysts") or []
    keys = {c.get("key") for c in cats if isinstance(c, dict)}
    return any(k in keys for k in ("activist_stake", "13d", "13d_a"))


def has_13f_accumulation(candidate):
    inst = candidate.get("institutional_ownership") or {}
    delta_q = inst.get("delta_q_pct")
    if delta_q is not None:
        try:
            return float(delta_q) >= 5
        except (TypeError, ValueError):
            pass
    pct_inst = candidate.get("pct_inst_held")
    if pct_inst is not None:
        try:
            return float(pct_inst) >= 75
        except (TypeError, ValueError):
            pass
    return False


def has_index_inclusion(candidate):
    cats = candidate.get("catalysts") or []
    return any(c.get("key") == "index_inclusion" for c in cats)


def smart_money_signals(candidate):
    signals = []
    if has_insider_cluster(candidate):
        signals.append("insider_cluster")
    if has_options_flow_bullish(candidate):
        signals.append("options_flow_bullish")
    if has_activist_filing(candidate):
        signals.append("activist_filing")
    if has_13f_accumulation(candidate):
        signals.append("13f_accumulation")
    if has_index_inclusion(candidate):
        signals.append("index_inclusion")
    return signals


def passes_smart_money_filter(candidate, min_signals=1):
    sigs = smart_money_signals(candidate)
    candidate["_smart_money_signals"] = sigs
    return len(sigs) >= min_signals


def annotate_smart_money(candidates, verbose=False):
    if not candidates:
        return
    n_with_signal = 0
    n_two_plus = 0
    for s in candidates:
        sigs = smart_money_signals(s)
        s["_smart_money_signals"] = sigs
        if len(sigs) >= 1:
            n_with_signal += 1
        if len(sigs) >= 2:
            n_two_plus += 1
    if verbose:
        print(f"  smart-money annotated: {n_with_signal} have >=1 signal, {n_two_plus} have >=2 (used as scoring bonus, not gate)")


def filter_smart_money_required(candidates, bracket=None, verbose=False):
    annotate_smart_money(candidates, verbose=False)
    if verbose:
        n_signal = sum(1 for c in candidates if len(c.get("_smart_money_signals") or []) >= 1)
        print(f"  smart-money (annotation only, no filter): {n_signal}/{len(candidates)} have >=1 signal")
    return candidates, []
