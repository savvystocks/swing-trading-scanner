import os
import re
from datetime import datetime, timedelta


LOTTERY_TARGET_ROI = 500
LOTTERY_HOLD_DAYS = 7


def lottery_score_swing(ticket, sector_perf=None):
    score = 0
    reasons = []
    breakdown = {}

    pillars = ticket.get("pillars") or {}
    p7 = pillars.get("p7") or {}
    p7_summary = p7.get("summary", "")

    si_pct = None
    m = re.search(r"SI ([\d.]+)%", p7_summary)
    if m:
        try:
            si_pct = float(m.group(1))
        except ValueError:
            pass

    if si_pct is not None:
        if si_pct >= 35:
            score += 25
            reasons.append(f"COILED SPRING: SI {si_pct:.0f}% (squeeze fuel)")
            breakdown["squeeze_fuel"] = 25
        elif si_pct >= 25:
            score += 18
            reasons.append(f"high SI {si_pct:.0f}% (moderate squeeze)")
            breakdown["squeeze_fuel"] = 18
        elif si_pct >= 15:
            score += 8
            reasons.append(f"SI {si_pct:.0f}%")
            breakdown["squeeze_fuel"] = 8

    gates = ticket.get("gates") or {}
    g7 = gates.get("g7") or {}
    g7_summary = g7.get("summary", "")
    earnings_days = None
    m = re.search(r"\((\d+) days?\)", g7_summary)
    if m:
        try:
            earnings_days = int(m.group(1))
        except ValueError:
            pass

    if earnings_days is not None:
        if 1 <= earnings_days <= 3:
            score += 30
            reasons.append(f"EARNINGS IMMINENT: {earnings_days}d (binary catalyst)")
            breakdown["binary_catalyst"] = 30
        elif 4 <= earnings_days <= 7:
            score += 22
            reasons.append(f"earnings in {earnings_days}d (catalyst window)")
            breakdown["binary_catalyst"] = 22
        elif 8 <= earnings_days <= 14:
            score += 12
            reasons.append(f"earnings in {earnings_days}d")
            breakdown["binary_catalyst"] = 12

    float_shares = ticket.get("shares_float") or ticket.get("float")
    if float_shares:
        try:
            float_m = float(float_shares) / 1e6
            if float_m < 30:
                score += 15
                reasons.append(f"micro float {float_m:.0f}M shares (move amplifier)")
                breakdown["float_tightness"] = 15
            elif float_m < 75:
                score += 8
                reasons.append(f"tight float {float_m:.0f}M shares")
                breakdown["float_tightness"] = 8
            elif float_m < 150:
                score += 3
                breakdown["float_tightness"] = 3
        except (ValueError, TypeError):
            pass

    industry = (ticket.get("industry") or "").lower()
    sector = (ticket.get("sector") or "").lower()
    HOT_COHORTS = {
        "biotech": 12, "biotechnology": 12, "pharmaceutical": 8,
        "semiconductor": 10, "ai": 10, "artificial intelligence": 10,
        "cryptocurrency": 8, "blockchain": 8, "fintech": 6,
        "renewable": 5, "solar": 5, "lithium": 6,
    }
    cohort_bonus = 0
    cohort_label = None
    for kw, pts in HOT_COHORTS.items():
        if kw in industry or kw in sector:
            if pts > cohort_bonus:
                cohort_bonus = pts
                cohort_label = kw
    if cohort_bonus:
        score += cohort_bonus
        reasons.append(f"hot cohort: {cohort_label} (+{cohort_bonus} amplifier)")
        breakdown["cohort_amplifier"] = cohort_bonus

    hunter = ticket.get("hunter") or {}
    if hunter.get("ret_5d") is not None:
        ret_5d = hunter["ret_5d"]
        if 5 <= ret_5d <= 15:
            score += 10
            reasons.append(f"momentum building: {ret_5d:+.1f}% in 5d")
            breakdown["momentum"] = 10
        elif ret_5d > 15:
            score += 4
            reasons.append(f"already extended: {ret_5d:+.1f}% in 5d (chase risk)")
            breakdown["momentum"] = 4

    pct_above_50d = hunter.get("pct_above_50d")
    if pct_above_50d is not None and -2 <= pct_above_50d <= 5:
        score += 8
        reasons.append(f"on 50d MA ({pct_above_50d:+.1f}%) - explosive launch zone")
        breakdown["entry_zone"] = 8

    if sector_perf:
        for sp in sector_perf:
            etf = sp.get("etf", "")
            stage = sp.get("stage")
            if stage == 2 and sp.get("outlook") in ("LEADING", "STRONG"):
                gics_match = (
                    "Tech" in (ticket.get("sector") or "") and "XLK" in etf
                ) or (
                    "Health" in (ticket.get("sector") or "") and "XLV" in etf
                ) or (
                    "Energy" in (ticket.get("sector") or "") and "XLE" in etf
                )
                if gics_match:
                    score += 6
                    reasons.append(f"sector tailwind: {etf} Stage 2 {sp.get('outlook')}")
                    breakdown["sector_wind"] = 6
                    break

    return {
        "score": min(100, score),
        "reasons": reasons,
        "breakdown": breakdown,
        "qualified": score >= 50,
        "tier": "PRIME" if score >= 70 else "STRONG" if score >= 55 else "STANDARD" if score >= 40 else "WEAK",
    }


def find_lottery_contract(chain_snapshots, current_price, direction="bull",
                          target_dte_range=(7, 14), max_premium=2.00,
                          target_delta_range=(0.15, 0.35)):
    if not chain_snapshots:
        return None

    today = datetime.now()
    candidates = []
    for sym, snap in chain_snapshots.items():
        try:
            m = re.match(r"[A-Z]+(\d{6})([CP])(\d+)", sym)
            if not m:
                continue
            cp = m.group(2)
            if direction == "bull" and cp != "C":
                continue
            if direction == "bear" and cp != "P":
                continue
            expiry = datetime.strptime("20" + m.group(1), "%Y%m%d")
            dte = (expiry - today).days
            if dte < target_dte_range[0] or dte > target_dte_range[1]:
                continue
            strike = int(m.group(3)) / 1000
            quote = snap.latest_quote
            greeks = snap.greeks if hasattr(snap, "greeks") else None
            if not quote or not greeks:
                continue
            bid = float(quote.bid_price) if quote.bid_price else 0
            ask = float(quote.ask_price) if quote.ask_price else 0
            if bid <= 0 or ask <= 0:
                continue
            mid = (bid + ask) / 2
            if mid > max_premium:
                continue
            spread_pct = (ask - bid) / mid * 100
            if spread_pct > 30:
                continue
            delta = float(greeks.delta) if greeks.delta else None
            if delta is None:
                continue
            abs_delta = abs(delta)
            if abs_delta < target_delta_range[0] or abs_delta > target_delta_range[1]:
                continue
            iv = float(snap.implied_volatility) * 100 if hasattr(snap, "implied_volatility") and snap.implied_volatility else None

            target_premium = mid * (1 + LOTTERY_TARGET_ROI / 100)
            if direction == "bull":
                required_stock_price = strike + target_premium
            else:
                required_stock_price = strike - target_premium
            required_move_pct = (required_stock_price - current_price) / current_price * 100

            score = abs_delta * 50 - spread_pct - dte * 0.5
            candidates.append({
                "symbol": sym,
                "strike": strike,
                "expiration": expiry.strftime("%Y-%m-%d"),
                "dte": dte,
                "delta": round(delta, 3),
                "iv_pct": round(iv, 1) if iv else None,
                "bid": bid,
                "ask": ask,
                "mid": round(mid, 2),
                "spread_pct": round(spread_pct, 1),
                "current_stock_price": current_price,
                "target_stock_price": round(required_stock_price, 2),
                "required_move_pct": round(required_move_pct, 1),
                "cost_per_contract": round(mid * 100, 0),
                "target_roi_pct": LOTTERY_TARGET_ROI,
                "_score": score,
            })
        except (ValueError, AttributeError):
            continue

    if not candidates:
        return None

    candidates.sort(key=lambda c: c["_score"], reverse=True)
    best = candidates[0]
    best.pop("_score", None)
    return best


def estimate_lottery_probability(lottery_score, contract):
    if not contract:
        return 0.0
    required_move = abs(contract.get("required_move_pct", 0))
    base_prob_by_move = 50.0 if required_move <= 5 else 25.0 if required_move <= 10 else 12.0 if required_move <= 15 else 5.0 if required_move <= 25 else 2.0
    score_multiplier = 0.5 + (lottery_score / 100)
    return round(min(60, base_prob_by_move * score_multiplier), 1)


def add_lottery_to_picks(picks, sector_perf=None, verbose=True):
    enhanced = 0
    for ticket in picks:
        if not ticket:
            continue
        ls = lottery_score_swing(ticket, sector_perf=sector_perf)
        ticket["lottery_score"] = ls
        if ls["qualified"]:
            enhanced += 1
    if verbose:
        print(f"  lottery_playbook: {enhanced}/{len(picks)} picks qualified for lottery scoring")
    return picks
