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


def filter_smart_money_required(candidates, bracket=None, verbose=False):
    min_signals = 2 if bracket == "mid" else 1
    passed = []
    rejected = []
    for s in candidates:
        if passes_smart_money_filter(s, min_signals=min_signals):
            passed.append(s)
        else:
            rejected.append(s)
    if verbose:
        print(f"  smart-money required ({bracket}, min {min_signals}): {len(passed)} passed, {len(rejected)} rejected")
    return passed, rejected
