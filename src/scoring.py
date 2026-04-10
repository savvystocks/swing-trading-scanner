def score_candidate(pillars, gates, is_us):
    pillar_results = {
        1: pillars["pillar_1"]["verdict"],
        2: pillars["pillar_2"]["verdict"],
        3: pillars["pillar_3"]["verdict"],
        4: pillars["pillar_4"]["verdict"],
        5: pillars["pillar_5"]["verdict"],
        6: pillars["pillar_6"]["verdict"],
        7: pillars["pillar_7"]["verdict"],
    }

    applicable_pillars = 7
    p7 = pillars["pillar_7"]
    if not is_us and p7.get("applicable") is False:
        applicable_pillars = 6
        pillar_results.pop(7)

    passes = sum(1 for v in pillar_results.values() if v in ("PASS", "PASS_BONUS"))
    partials = sum(1 for v in pillar_results.values() if v == "PARTIAL")
    fails = sum(1 for v in pillar_results.values() if v == "FAIL")

    if applicable_pillars == 7:
        if passes >= 6:
            tier = 5
        elif passes >= 5:
            tier = 4
        elif passes >= 4:
            tier = 3
        else:
            tier = 2
    else:
        if passes >= 6:
            tier = 5
        elif passes >= 4:
            tier = 4
        elif passes >= 3:
            tier = 3
        else:
            tier = 2

    hard_gate_fails = []
    if pillars["pillar_1"]["verdict"] == "FAIL":
        hard_gate_fails.append("pillar_1_trend_template")
    if gates["gate_4"]["verdict"] == "FAIL":
        hard_gate_fails.append("gate_4_catalyst")
    if gates["gate_6"]["verdict"] == "FAIL":
        hard_gate_fails.append("gate_6_liquidity")
    if gates["gate_7"]["verdict"] == "FAIL":
        hard_gate_fails.append("gate_7_earnings_blackout")

    if hard_gate_fails:
        tier = 0

    if gates.get("gate_5_modifier", {}).get("direction") == "bullish":
        tier = min(5, tier + 0.5)
    elif gates.get("gate_5_modifier", {}).get("direction") == "bearish":
        tier = max(0, tier - 0.5)

    if tier == 0:
        label = "NO TRADE"
    elif tier >= 5:
        label = "Tier 5 Full Conviction"
    elif tier >= 4:
        label = "Tier 4 High Conviction"
    elif tier >= 3:
        label = "Tier 3 Standard"
    else:
        label = "Tier 1-2 Watchlist"

    return {
        "tier": tier,
        "label": label,
        "pillars_passed": passes,
        "pillars_partial": partials,
        "pillars_failed": fails,
        "applicable_pillars": applicable_pillars,
        "hard_gate_fails": hard_gate_fails,
        "pillar_results": pillar_results,
    }


def build_trade_ticket(ticker, name, price, tier_info, pillars, gates, vix_regime):
    stop_widths = {"low_vol": 0.10, "normal": 0.12, "elevated": 0.15, "extreme": 0.20, "crisis": 0.20, "unknown": 0.12}
    stop_pct = stop_widths.get(vix_regime, 0.12)

    stop = round(price * (1 - stop_pct), 2)
    phase1_target = round(price * 1.50, 2)
    runner_target = round(price * 1.80, 2)
    risk = price - stop
    reward = phase1_target - price
    rr = round(reward / risk, 2) if risk > 0 else None

    return {
        "ticker": ticker,
        "name": name,
        "price": float(price),
        "tier": tier_info["tier"],
        "label": tier_info["label"],
        "stop_loss": stop,
        "stop_pct": stop_pct * 100,
        "phase1_target": phase1_target,
        "runner_target": runner_target,
        "risk_reward": rr,
        "pillars_passed": tier_info["pillars_passed"],
        "applicable_pillars": tier_info["applicable_pillars"],
        "hard_gate_fails": tier_info["hard_gate_fails"],
    }
