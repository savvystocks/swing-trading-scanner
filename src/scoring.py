BASE_PILLARS = (1, 3, 4, 5, 6)
BONUS_PILLARS = (2, 7)


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

    base_ids = list(BASE_PILLARS)
    applicable_pillars = len(base_ids)
    base_results = {i: pillar_results[i] for i in base_ids}

    passes = sum(1 for v in base_results.values() if v in ("PASS", "PASS_BONUS"))
    partials = sum(1 for v in base_results.values() if v == "PARTIAL")
    fails = sum(1 for v in base_results.values() if v == "FAIL")
    effective_score = passes + partials * 0.5

    if effective_score >= 5:
        tier = 5
    elif effective_score >= 4:
        tier = 4
    elif effective_score >= 3:
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

    bonus_applied = []
    p2_pass = pillar_results[2] in ("PASS", "PASS_BONUS")
    p7_pass = pillar_results[7] in ("PASS", "PASS_BONUS") and pillars["pillar_7"].get("applicable", True)
    if tier > 0 and (p2_pass or p7_pass):
        tier = min(5, tier + 0.5)
        if p2_pass:
            bonus_applied.append("p2_vol_squeeze")
        if p7_pass:
            bonus_applied.append("p7_short_squeeze")

    if gates.get("gate_5_modifier", {}).get("direction") == "bullish":
        tier = min(5, tier + 0.5)
    elif gates.get("gate_5_modifier", {}).get("direction") == "bearish":
        tier = max(0, tier - 0.5)

    post_earn = (gates.get("gate_7") or {}).get("post_earnings")
    if post_earn and post_earn.get("verdict") == "CATALYST" and tier > 0:
        tier = min(5, tier + 0.5)

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
        "bonus_applied": bonus_applied,
    }


def build_trade_ticket(ticker, name, price, tier_info, pillars, gates, vix_regime, sector="", industry="", description=""):
    stop_widths = {"low_vol": 0.10, "normal": 0.12, "elevated": 0.15, "extreme": 0.20, "crisis": 0.20, "unknown": 0.12}
    stop_pct = stop_widths.get(vix_regime, 0.12)

    stop = round(price * (1 - stop_pct), 2)
    phase1_target = round(price * 1.50, 2)
    runner_target = round(price * 1.80, 2)
    risk = price - stop
    reward = phase1_target - price
    rr = round(reward / risk, 2) if risk > 0 else None

    p1 = pillars["pillar_1"]
    p2 = pillars["pillar_2"]
    p3 = pillars["pillar_3"]
    p4 = pillars["pillar_4"]
    p5 = pillars["pillar_5"]
    p6 = pillars["pillar_6"]
    p7 = pillars["pillar_7"]

    pillar_detail = {
        "p1": {
            "verdict": p1["verdict"],
            "summary": f"{p1.get('trend_template_passed','?')}/7 template, stage {p1.get('stage','?')}",
        },
        "p2": {
            "verdict": p2["verdict"],
            "squeeze_pct": p2.get("squeeze_percentile"),
            "upper_break": p2.get("upper_band_break"),
            "summary": f"squeeze pct {p2.get('squeeze_percentile', 0):.0f}, break={p2.get('upper_band_break', False)}",
        },
        "p3": {
            "verdict": p3["verdict"],
            "summary": f"EPS YoY {(p3.get('eps_growth_yoy') or 0)*100:+.1f}%, Rev YoY {(p3.get('revenue_growth_yoy') or 0)*100:+.1f}%, ROE {(p3.get('roe_ttm') or 0)*100:.0f}%",
        },
        "p4": {
            "verdict": p4["verdict"],
            "summary": f"RS {p4.get('rs_score', 0):+.2f}% (stock {p4.get('candidate_return', 0):+.2f} vs bench {p4.get('benchmark_return', 0):+.2f})",
        },
        "p5": {
            "verdict": p5["verdict"],
            "summary": f"VIX {p5.get('vix', 0):.1f} ({p5.get('regime','?')})",
        },
        "p6": {
            "verdict": p6["verdict"],
            "summary": f"beats={p6.get('consecutive_beats',0)}, up30d={p6.get('eps_up_30d',0)}, down30d={p6.get('eps_down_30d',0)}",
        },
        "p7": {
            "verdict": p7["verdict"],
            "summary": (f"SI {p7.get('short_percent_float', 0):.1f}% ({p7.get('si_level','?')}), DTC {p7.get('days_to_cover') or 0:.1f}"
                        if p7.get("applicable", True) else "unavailable (LSE)"),
        },
    }

    g3 = gates["gate_3"]
    g4 = gates["gate_4"]
    g6 = gates["gate_6"]
    g7 = gates["gate_7"]

    gate_detail = {
        "g3": {"verdict": g3["verdict"], "summary": f"RVOL {g3.get('rvol') or 0:.2f}x"},
        "g4": {"verdict": g4["verdict"], "summary": f"Tier {g4.get('tier','?')} catalyst, beat={g4.get('recent_earnings_beat', False)}"},
        "g6": {"verdict": g6["verdict"], "summary": f"mcap ${(g6.get('market_cap') or 0)/1e9:.1f}B, $vol ${g6.get('dollar_volume_20d', 0)/1e6:.1f}M"},
        "g7": {"verdict": g7["verdict"], "summary": _g7_summary(g7)},
    }

    short_desc = (description or "").strip()
    if len(short_desc) > 220:
        cut = short_desc[:220]
        last_space = cut.rfind(" ")
        short_desc = cut[:last_space] + "..." if last_space > 0 else cut + "..."

    return {
        "ticker": ticker,
        "name": name,
        "sector": sector or "",
        "industry": industry or "",
        "description": short_desc,
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
        "pillars": pillar_detail,
        "gates": gate_detail,
    }


def _g7_summary(g7):
    post = g7.get("post_earnings")
    base = f"next earnings {g7.get('next_earnings', '?')} ({g7.get('days_until', '?')} days)"
    if not post:
        return base
    pe = post
    parts = [f"POST-EARN {pe['verdict']}"]
    if pe.get("surprise_pct") is not None:
        parts.append(f"surprise {pe['surprise_pct']:+.1f}%")
    if pe.get("gap_pct") is not None:
        parts.append(f"gap {pe['gap_pct']:+.1f}%")
    if pe.get("holding_gap") is not None:
        parts.append(f"holding={'yes' if pe['holding_gap'] else 'no'}")
    if pe.get("volume_spike") is not None:
        parts.append(f"vol {pe['volume_spike']:.1f}x")
    return ", ".join(parts)
