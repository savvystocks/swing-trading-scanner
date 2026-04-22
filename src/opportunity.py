def _component_from_tier(tier):
    if tier is None or tier == 0:
        return 0
    return min(35, int((tier / 5.0) * 35))


def _component_from_conviction(conv_score):
    if conv_score is None:
        return 0
    return min(30, int((conv_score / 100.0) * 30))


def _component_from_lane_b(lane_b_signals):
    if not lane_b_signals:
        return 0
    hits = 0
    weights = {
        "pocket_pivot": 4,
        "base_quality": 5,
        "insider_cluster": 6,
        "revenue_acceleration": 5,
        "earnings_turn": 3,
        "peer_pack": 2,
    }
    total = 0
    for key, w in weights.items():
        sig = lane_b_signals.get(key) or {}
        if sig.get("fired"):
            total += w
            hits += 1
    return min(25, total)


def _component_from_stress(stress):
    if not stress:
        return 5
    overall = stress.get("overall")
    if overall == "PASS":
        return 10
    if overall == "WARN":
        return 5
    if overall == "FAIL":
        return 0
    return 5


def _sector_maturity_penalty(maturity):
    if maturity == "LATE":
        return -5
    if maturity == "EARLY":
        return 3
    return 0


def opportunity_score(ticket):
    tier = ticket.get("tier") or 0
    conv = (ticket.get("conviction") or {}).get("score")
    lane_b = ticket.get("lane_b") or {}
    stress = ticket.get("stress") or {}
    maturity = ticket.get("sector_maturity", "N/A")

    t = _component_from_tier(tier)
    c = _component_from_conviction(conv)
    lb = _component_from_lane_b(lane_b)
    s = _component_from_stress(stress)
    penalty = _sector_maturity_penalty(maturity)

    total = max(0, min(100, t + c + lb + s + penalty))
    return {
        "score": total,
        "components": {
            "tier_pts": t,
            "conviction_pts": c,
            "lane_b_pts": lb,
            "stress_pts": s,
            "sector_maturity_adj": penalty,
        },
    }


def classify_lane(ticket, opportunity_pts):
    tier = ticket.get("tier") or 0
    conv = (ticket.get("conviction") or {}).get("score") or 0
    lane_b_count = ticket.get("lane_b_signal_count", 0)
    maturity = ticket.get("sector_maturity", "N/A")
    post_earn = ((ticket.get("gates") or {}).get("g7") or {}).get("summary", "")
    is_post_earn_catalyst = "POST-EARN" in post_earn and ("MILD" in post_earn or "CATALYST" in post_earn)

    if tier >= 4 and conv >= 60:
        return "A"
    if is_post_earn_catalyst:
        return "C"
    if lane_b_count >= 2 and maturity != "LATE" and tier >= 2:
        return "B"
    if tier >= 4:
        return "A"
    if tier >= 3 and lane_b_count >= 1 and maturity != "LATE":
        return "B"
    return None
