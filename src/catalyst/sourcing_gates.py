import os


THEME_CLUSTERS = [
    {"MSTR", "COIN", "MARA", "RIOT", "CLSK", "BTDR", "BITF", "HUT", "WULF", "CIFR"},
    {"NVDA", "AMD", "AVGO", "SMCI", "ARM", "MU", "TSM", "MRVL"},
    {"GME", "AMC", "KOSS", "BBBY"},
]


def _env_float(key, default):
    raw = os.environ.get(key, "")
    if isinstance(raw, str):
        raw = raw.strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def get_config():
    return {
        "oi_floor": _env_float("GATE_OI_FLOOR", 500),
        "strike_coherence_pct": _env_float("GATE_STRIKE_COHERENCE_PCT", 5.0),
        "flow_dominance_pct": _env_float("GATE_FLOW_DOMINANCE_PCT", 55.0),
        "tight_spread_pct": _env_float("GATE_TIGHT_SPREAD_PCT", 1.5),
        "contract_rvol_mult": _env_float("GATE_CONTRACT_RVOL_MULT", 5.0),
        "nope_extreme": _env_float("GATE_NOPE_EXTREME", 1.0),
        "min_positioning_signals": _env_float("GATE_MIN_POSITIONING_SIGNALS", 2),
        "correlation_block": _env_float("GATE_CORRELATION_BLOCK", 0.50),
    }


def _side_premium_share(candidate):
    side = (candidate.get("side") or "").upper()
    call_prem = candidate.get("call_premium")
    put_prem = candidate.get("put_premium")
    if call_prem is None or put_prem is None:
        return None
    total = call_prem + put_prem
    if total <= 0:
        return None
    directional = call_prem if side in ("CALL", "LONG", "BULLISH") else put_prem
    return directional / total * 100.0


def five_gates(candidate, config=None):
    if config is None:
        config = get_config()
    spot = candidate.get("spot")
    strike = candidate.get("strike")
    bid = candidate.get("bid")
    ask = candidate.get("ask")
    mid = candidate.get("mid")
    oi = candidate.get("oi")
    vol = candidate.get("vol")
    avg_vol = candidate.get("avg_vol_30d")

    gates = {}
    reasons = []

    gates["oi_floor"] = oi is not None and oi >= config["oi_floor"]
    if not gates["oi_floor"]:
        reasons.append(f"OI {oi} < floor {config['oi_floor']:.0f}")

    if spot and strike:
        coh = abs(strike - spot) / spot * 100.0
        gates["strike_coherence"] = coh <= config["strike_coherence_pct"]
        if not gates["strike_coherence"]:
            reasons.append(f"strike {strike} is {coh:.1f}% off spot {spot} (max {config['strike_coherence_pct']}%)")
    else:
        gates["strike_coherence"] = False
        reasons.append("missing spot/strike for coherence")

    share = _side_premium_share(candidate)
    gates["flow_dominance"] = share is not None and share > config["flow_dominance_pct"]
    if not gates["flow_dominance"]:
        reasons.append(f"directional premium share {('%.0f%%' % share) if share is not None else 'n/a'} "
                       f"<= {config['flow_dominance_pct']:.0f}%")

    if bid is not None and ask is not None and mid and mid > 0:
        spread_pct = (ask - bid) / mid * 100.0
        gates["tight_liquidity"] = spread_pct <= config["tight_spread_pct"]
        if not gates["tight_liquidity"]:
            reasons.append(f"bid-ask {spread_pct:.1f}% of mid > {config['tight_spread_pct']}%")
    else:
        spread_pct = candidate.get("spread_pct")
        gates["tight_liquidity"] = spread_pct is not None and spread_pct <= config["tight_spread_pct"]
        if not gates["tight_liquidity"]:
            reasons.append("missing/insufficient quote for spread check")

    if vol is not None and avg_vol and avg_vol > 0:
        rvol = vol / avg_vol
        gates["contract_rvol"] = rvol >= config["contract_rvol_mult"]
        if not gates["contract_rvol"]:
            reasons.append(f"contract RVOL {rvol*100:.0f}% < {config['contract_rvol_mult']*100:.0f}%")
    else:
        gates["contract_rvol"] = False
        reasons.append("missing contract volume / 30d avg for RVOL")

    return {"passed": all(gates.values()), "gates": gates, "reasons": reasons}


def positioning_triggers(candidate, regime_bias, config=None):
    if config is None:
        config = get_config()
    side = (candidate.get("side") or "").upper()
    bias = (regime_bias or "").upper()
    direction_matches = (
        (bias == "SHORT" and side in ("PUT", "SHORT", "BEARISH")) or
        (bias == "LONG" and side in ("CALL", "LONG", "BULLISH"))
    )

    confirmations = []
    if candidate.get("gamma_flip_pin"):
        confirmations.append("gamma_flip_pin")
    if candidate.get("skew_inversion"):
        confirmations.append("skew_inversion")
    nope = candidate.get("nope")
    if nope is not None and abs(nope) >= config["nope_extreme"]:
        confirmations.append(f"nope_extreme({nope:+.2f})")

    enough = len(confirmations) >= config["min_positioning_signals"]
    passed = bool(direction_matches and enough)
    reasons = []
    if not direction_matches:
        reasons.append(f"{side or 'flow'} does not match regime bias {bias or 'n/a'}")
    if not enough:
        reasons.append(f"only {len(confirmations)} positioning signals (need {int(config['min_positioning_signals'])})")
    return {
        "passed": passed,
        "direction_matches_regime": direction_matches,
        "confirmations": confirmations,
        "count": len(confirmations),
        "reasons": reasons,
    }


def _same_theme(ticker, other):
    t = (ticker or "").upper().split(".")[0]
    o = (other or "").upper().split(".")[0]
    for cluster in THEME_CLUSTERS:
        if t in cluster and o in cluster:
            return True
    return False


def sector_correlation_guard(candidate, open_positions, returns_lookup=None, sector_map=None, config=None):
    if config is None:
        config = get_config()
    ticker = (candidate.get("ticker") or "").upper()
    cand_sector = (sector_map or {}).get(ticker) or candidate.get("sector")
    blocked_by = []
    reasons = []

    for pos in open_positions or []:
        pt = (pos.get("ticker") or "").upper()
        if not pt or pt == ticker:
            continue
        if _same_theme(ticker, pt):
            blocked_by.append(pt)
            reasons.append(f"same theme cluster as open {pt}")
            continue
        pos_sector = (sector_map or {}).get(pt) or pos.get("sector")
        if cand_sector and pos_sector and cand_sector == pos_sector:
            blocked_by.append(pt)
            reasons.append(f"same sector ({cand_sector}) as open {pt}")
            continue
        if returns_lookup and ticker in returns_lookup and pt in returns_lookup:
            corr = _pearson(returns_lookup[ticker], returns_lookup[pt])
            if corr is not None and corr > config["correlation_block"]:
                blocked_by.append(pt)
                reasons.append(f"correlation {corr:.2f} with open {pt} > {config['correlation_block']}")

    return {"passed": len(blocked_by) == 0, "blocked_by": blocked_by, "reasons": reasons, "sector": cand_sector}


def _pearson(xs, ys):
    n = min(len(xs), len(ys))
    if n < 5:
        return None
    xs, ys = xs[-n:], ys[-n:]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def evaluate_candidate(candidate, regime_bias, open_positions=None, returns_lookup=None, sector_map=None, config=None):
    if config is None:
        config = get_config()
    g = five_gates(candidate, config)
    p = positioning_triggers(candidate, regime_bias, config)
    s = sector_correlation_guard(candidate, open_positions or [], returns_lookup, sector_map, config)
    passed = g["passed"] and p["passed"] and s["passed"]
    return {
        "ticker": candidate.get("ticker"),
        "side": candidate.get("side"),
        "passed": passed,
        "five_gates": g,
        "positioning": p,
        "sector_guard": s,
        "reject_reasons": (g["reasons"] if not g["passed"] else [])
        + (p["reasons"] if not p["passed"] else [])
        + (s["reasons"] if not s["passed"] else []),
    }
