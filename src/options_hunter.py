MIN_MCAP = 2_000_000_000

SECTOR_TILT_KEYWORDS = [
    "semiconductor", "semiconductors",
    "communications equipment", "networking",
    "aerospace", "defense",
    "oil & gas", "oil and gas", "energy equipment",
    "biotechnology", "biotech",
    "electronic equipment", "internet",
    "interactive media",
]


def _pass(verdict):
    return verdict in ("PASS", "PASS_BONUS")


def _detect_sector_tilt(sector, industry):
    s = (sector or "").lower()
    ind = (industry or "").lower()
    blob = f"{s} {ind}"
    for kw in SECTOR_TILT_KEYWORDS:
        if kw in blob:
            return kw.title()
    return None


def options_hunter_score(ticket, pillars_raw, gates_raw, ind, fundamentals):
    mcap = ticket.get("market_cap") or (gates_raw.get("gate_6", {}) or {}).get("market_cap") or 0
    if mcap < MIN_MCAP:
        return {
            "qualified": False,
            "score": 0,
            "eta_days": None,
            "eta_label": "n/a",
            "reasons": [],
            "disqualified_reason": f"mcap ${mcap/1e9:.1f}B < $2B",
        }

    p1 = pillars_raw.get("pillar_1", {})
    p2 = pillars_raw.get("pillar_2", {})
    p3 = pillars_raw.get("pillar_3", {})
    p4 = pillars_raw.get("pillar_4", {})
    p6 = pillars_raw.get("pillar_6", {})
    p7 = pillars_raw.get("pillar_7", {})

    if p1.get("verdict") == "FAIL":
        return {
            "qualified": False, "score": 0, "eta_days": None, "eta_label": "n/a",
            "reasons": [], "disqualified_reason": "p1 trend fail",
        }
    if (gates_raw.get("gate_6") or {}).get("verdict") == "FAIL":
        return {
            "qualified": False, "score": 0, "eta_days": None, "eta_label": "n/a",
            "reasons": [], "disqualified_reason": "g6 liquidity fail",
        }

    score = 0
    reasons = []

    if _pass(p1.get("verdict")):
        score += 10
    if _pass(p2.get("verdict")):
        score += 10
        reasons.append("P2 vol squeeze")
    if _pass(p3.get("verdict")):
        score += 5
    if _pass(p4.get("verdict")):
        score += 10

    if _pass(p6.get("verdict")):
        score += 20
        reasons.append("P6 earnings revisions (2x)")
    if p7.get("applicable", True) and _pass(p7.get("verdict")):
        score += 20
        reasons.append("P7 short squeeze (2x)")

    lane_b = ticket.get("lane_b") or {}
    lb_signals = 0
    for key in ("pocket_pivot", "base_quality", "insider_cluster",
                "revenue_acceleration", "earnings_turn", "peer_pack"):
        if (lane_b.get(key) or {}).get("fired"):
            lb_signals += 1
    score += min(20, lb_signals * 4)
    if lb_signals >= 2:
        reasons.append(f"{lb_signals} Lane B signals")

    g7 = gates_raw.get("gate_7") or {}
    days_until = g7.get("days_until")
    earnings_bucket = "none"
    if days_until is not None and 11 <= days_until <= 21:
        score += 15
        reasons.append(f"earnings in {days_until}d (sweet spot)")
        earnings_bucket = "sweet"
    elif days_until is not None and days_until <= 30:
        score += 5
        earnings_bucket = "near"

    tt = (p1.get("details") or {})
    pct_from_high = tt.get("pct_from_high")
    if pct_from_high is not None and pct_from_high >= -25:
        score += 10
        reasons.append("within 25% of 52w high")

    sector = ticket.get("sector")
    industry = ticket.get("industry")
    tilt = _detect_sector_tilt(sector, industry)
    if tilt:
        score += 5
        reasons.append(f"sector tilt: {tilt}")

    pct_above_50d = None
    ret_20d = None
    ret_5d = None
    sq_pct_local = None
    try:
        last = ind.iloc[-1]
        close = float(last["close"])
        sma_200 = last.get("sma_200")
        if sma_200 is not None and float(sma_200) > 0 and close < float(sma_200):
            score -= 15
            reasons.append("below 200d (broken — risky)")
        atr = last.get("atr_14")
        if atr is not None and close > 0:
            atr_pct = float(atr) / close * 100
            if atr_pct > 10:
                score -= 10
                reasons.append(f"ATR {atr_pct:.0f}% (too wild)")

        sma_50 = last.get("sma_50")
        if sma_50 is not None and float(sma_50) > 0:
            pct_above_50d = (close / float(sma_50) - 1) * 100

        sq_raw = last.get("bb_squeeze_pct")
        try:
            if sq_raw is not None:
                sq_pct_local = float(sq_raw)
        except (TypeError, ValueError):
            sq_pct_local = None

        try:
            if len(ind) >= 21:
                price_20d_ago = float(ind["close"].iloc[-21])
                if price_20d_ago > 0:
                    ret_20d = (close / price_20d_ago - 1) * 100
            if len(ind) >= 6:
                price_5d_ago = float(ind["close"].iloc[-6])
                if price_5d_ago > 0:
                    ret_5d = (close / price_5d_ago - 1) * 100
        except Exception:
            pass
    except Exception:
        pass

    ext_adj = _extension_adjustment(pct_above_50d, ret_20d, sq_pct_local, ret_5d)
    if ext_adj["delta"] != 0:
        score += ext_adj["delta"]
        reasons.append(ext_adj["label"])

    score = max(0, min(100, score))

    eta_days, eta_label = _compute_eta(p2, days_until, earnings_bucket, lb_signals)

    qualified = score >= 50

    return {
        "qualified": qualified,
        "score": int(round(score)),
        "eta_days": eta_days,
        "eta_label": eta_label,
        "reasons": reasons,
        "earnings_days": days_until,
        "pct_from_high": pct_from_high,
        "pct_above_50d": round(pct_above_50d, 1) if pct_above_50d is not None else None,
        "ret_20d": round(ret_20d, 1) if ret_20d is not None else None,
        "ret_5d": round(ret_5d, 1) if ret_5d is not None else None,
        "squeeze_pct": round(sq_pct_local, 1) if sq_pct_local is not None else None,
        "extension_state": ext_adj["state"],
        "sector_tilt": tilt,
        "lane_b_count": lb_signals,
    }


def _extension_adjustment(pct_above_50d, ret_20d, sq_pct=None, ret_5d=None):
    if pct_above_50d is None:
        return {"delta": 0, "label": "", "state": "unknown"}

    ext = pct_above_50d
    labels = []

    still_coiled = (
        ext <= 5
        and sq_pct is not None and sq_pct <= 30
        and ret_20d is not None and ret_20d <= 5
    )

    if still_coiled:
        ext_pts = 15
        ext_state = "STILL_COILED"
        labels.append(f"still coiled ({ext:+.0f}% 50d, {ret_20d:+.0f}% 20d, sq {sq_pct:.0f}p)")
    elif ext <= 10:
        ext_pts = 5
        ext_state = "MILD_PRIME"
        labels.append(f"mild entry ({ext:+.0f}% above 50d)")
    elif ext <= 18:
        ext_pts = 0
        ext_state = "MILD"
    elif ext <= 28:
        ext_pts = -8
        ext_state = "EXTENDED"
        labels.append(f"extended ({ext:+.0f}% above 50d)")
    elif ext <= 40:
        ext_pts = -18
        ext_state = "CHASING"
        labels.append(f"chasing ({ext:+.0f}% above 50d)")
    else:
        ext_pts = -28
        ext_state = "CHASING"
        labels.append(f"wildly extended ({ext:+.0f}% above 50d)")

    if ret_20d is not None:
        if ret_20d > 20:
            ext_pts -= 22
            labels.append(f"up {ret_20d:+.0f}% in 20d (running)")
            if ext_state in ("STILL_COILED", "MILD_PRIME", "MILD"):
                ext_state = "EXTENDED"
        elif ret_20d > 15:
            ext_pts -= 15
            labels.append(f"up {ret_20d:+.0f}% in 20d")
            if ext_state in ("STILL_COILED", "MILD_PRIME", "MILD"):
                ext_state = "EXTENDED"
        elif ret_20d > 10:
            ext_pts -= 8
            labels.append(f"up {ret_20d:+.0f}% in 20d")

    if ret_5d is not None and ret_5d > 8:
        ext_pts -= 8
        labels.append(f"up {ret_5d:+.0f}% in 5d (late)")

    return {"delta": ext_pts, "label": ", ".join(labels), "state": ext_state}


def _compute_eta(p2, earnings_days, earnings_bucket, lb_signals):
    if earnings_bucket == "sweet" and earnings_days:
        exit_in = max(3, earnings_days - 2)
        return exit_in, f"~{exit_in}d (day before earnings)"

    squeeze_pct = p2.get("squeeze_percentile")
    upper_break = p2.get("upper_band_break")
    recent_sq = p2.get("recent_squeeze_last_10d")

    if upper_break and recent_sq:
        return 7, "~1wk (breakout in progress)"
    if squeeze_pct is not None and squeeze_pct <= 20:
        return 10, "~1-2wk (squeeze coiled)"

    if earnings_days is not None and earnings_days <= 30:
        exit_in = max(3, earnings_days - 2)
        return exit_in, f"~{exit_in}d (before earnings)"

    if lb_signals >= 3:
        return 18, "~2-3wk (signals stacking)"

    return 25, "~3-4wk (momentum)"


def classify_hunters(scored_results, slot_plan=None, sector_perf=None):
    if slot_plan is None:
        slot_plan = [("MEGA", 1), ("LARGE", 3), ("MID", 4), ("EARLY", 1)]

    for r in scored_results:
        ticket = r["ticket"]
        hunter = options_hunter_score(
            ticket,
            r.get("pillars", {}),
            r.get("gates", {}),
            r.get("ind"),
            r.get("fundamentals"),
        )
        ticket["hunter"] = hunter

    if sector_perf:
        try:
            from src.sector_rotation import apply_sector_overlay_to_hunter
            apply_sector_overlay_to_hunter(scored_results, sector_perf, verbose=False)
        except Exception as e:
            print(f"  sector_rotation overlay failed: {type(e).__name__}: {e}")

    try:
        from src.multi_timeframe import apply_multi_timeframe_to_hunter
        apply_multi_timeframe_to_hunter(scored_results, verbose=False)
    except Exception as e:
        print(f"  multi_timeframe overlay failed: {type(e).__name__}: {e}")

    qualified = [r for r in scored_results if r["ticket"]["hunter"]["qualified"]]
    qualified.sort(key=lambda r: r["ticket"]["hunter"]["score"], reverse=True)

    buckets = {"MEGA": [], "LARGE": [], "MID": [], "EARLY": []}
    MEGA = 200_000_000_000
    LARGE = 10_000_000_000
    MID = 2_000_000_000
    for r in qualified:
        mcap = r["ticket"].get("market_cap") or 0
        if mcap >= MEGA:
            buckets["MEGA"].append(r)
        elif mcap >= LARGE:
            buckets["LARGE"].append(r)
        elif mcap >= MID:
            buckets["MID"].append(r)
        else:
            buckets["EARLY"].append(r)

    picks = []
    used = set()
    for bucket_name, slots in slot_plan:
        taken = 0
        for r in buckets[bucket_name]:
            if taken >= slots:
                break
            tkr = r["ticket"]["ticker"]
            if tkr in used:
                continue
            r["ticket"]["priority_bucket"] = bucket_name
            picks.append(r)
            used.add(tkr)
            taken += 1

    remaining = sum(s for _, s in slot_plan) - len(picks)
    if remaining > 0:
        leftover = [r for r in qualified if r["ticket"]["ticker"] not in used]
        for r in leftover[:remaining]:
            mcap = r["ticket"].get("market_cap") or 0
            if mcap >= MEGA:
                r["ticket"]["priority_bucket"] = "MEGA"
            elif mcap >= LARGE:
                r["ticket"]["priority_bucket"] = "LARGE"
            elif mcap >= MID:
                r["ticket"]["priority_bucket"] = "MID"
            else:
                r["ticket"]["priority_bucket"] = "EARLY"
            picks.append(r)
            used.add(r["ticket"]["ticker"])

    return picks
