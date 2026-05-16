import os
from datetime import datetime, timedelta


def _calendar_event_proximity_score(macro, days_window=14):
    score = 80
    notes = []
    if not macro:
        return score, notes

    try:
        next_fomc_days = (macro or {}).get("days_to_next_fomc")
        if next_fomc_days is not None and 0 <= next_fomc_days <= 5:
            score -= 25
            notes.append(f"FOMC in {next_fomc_days}d")
        elif next_fomc_days is not None and 6 <= next_fomc_days <= 10:
            score -= 10
            notes.append(f"FOMC in {next_fomc_days}d (heads-up)")

        next_cpi_days = (macro or {}).get("days_to_next_cpi")
        if next_cpi_days is not None and 0 <= next_cpi_days <= 3:
            score -= 15
            notes.append(f"CPI in {next_cpi_days}d")

        next_nfp_days = (macro or {}).get("days_to_next_nfp")
        if next_nfp_days is not None and 0 <= next_nfp_days <= 2:
            score -= 15
            notes.append(f"NFP in {next_nfp_days}d")

        next_opex_days = (macro or {}).get("days_to_next_opex")
        if next_opex_days is not None and 0 <= next_opex_days <= 3:
            score -= 8
            notes.append(f"OPEX in {next_opex_days}d (dealer hedging volatility)")
    except Exception:
        pass

    return max(0, min(100, score)), notes


def _vol_regime_score(macro):
    score = 70
    notes = []
    if not macro:
        return score, notes

    vix = (macro or {}).get("vix")
    try:
        if vix is not None:
            vix = float(vix)
            if vix < 14:
                score = 90
                notes.append(f"VIX {vix:.1f} (very calm)")
            elif vix < 18:
                score = 80
                notes.append(f"VIX {vix:.1f} (calm)")
            elif vix < 22:
                score = 65
                notes.append(f"VIX {vix:.1f} (normal)")
            elif vix < 28:
                score = 40
                notes.append(f"VIX {vix:.1f} (elevated stress)")
            elif vix < 35:
                score = 20
                notes.append(f"VIX {vix:.1f} (high stress)")
            else:
                score = 5
                notes.append(f"VIX {vix:.1f} (crisis)")
    except Exception:
        pass

    vix_5d = (macro or {}).get("vix_5d_change_pct")
    try:
        if vix_5d is not None and float(vix_5d) > 15:
            score -= 10
            notes.append(f"VIX rising +{vix_5d:.0f}% in 5d")
    except Exception:
        pass

    return max(0, min(100, score)), notes


def _sector_context_score(candidate, macro):
    score = 70
    notes = []
    sector_rot = candidate.get("_sector_rotation") or {}
    verdict = sector_rot.get("verdict")
    if verdict == "STRONG_TAILWIND":
        score = 90
        notes.append("Sector strong tailwind")
    elif verdict == "TAILWIND":
        score = 80
        notes.append("Sector tailwind")
    elif verdict == "NEUTRAL":
        score = 60
        notes.append("Sector neutral")
    elif verdict == "HEADWIND":
        score = 35
        notes.append("Sector headwind")
    elif verdict == "STRONG_HEADWIND":
        score = 15
        notes.append("Sector strong headwind")

    ret_30d = candidate.get("ret_30d")
    try:
        if ret_30d is not None and float(ret_30d) > 25:
            score -= 15
            notes.append(f"Sector 30d +{float(ret_30d):.0f}% (extension risk)")
    except Exception:
        pass

    return max(0, min(100, score)), notes


def _credit_rates_score(macro):
    score = 75
    notes = []
    if not macro:
        return score, notes

    yield_10y_5d = (macro or {}).get("yield_10y_5d_change_bps")
    try:
        if yield_10y_5d is not None:
            if float(yield_10y_5d) > 25:
                score -= 20
                notes.append(f"10Y yield +{yield_10y_5d:.0f}bps 5d (risk-off)")
            elif float(yield_10y_5d) > 10:
                score -= 10
                notes.append(f"10Y yield +{yield_10y_5d:.0f}bps 5d")
            elif float(yield_10y_5d) < -15:
                score += 5
                notes.append(f"10Y yield {yield_10y_5d:.0f}bps 5d (risk-on signal)")
    except Exception:
        pass

    dxy_5d = (macro or {}).get("dxy_5d_change_pct")
    try:
        if dxy_5d is not None and float(dxy_5d) > 1.5:
            score -= 10
            notes.append(f"DXY +{dxy_5d:.1f}% 5d (multinational headwind)")
    except Exception:
        pass

    return max(0, min(100, score)), notes


def _news_sentiment_score(candidate):
    score = 70
    notes = []
    news_quality = candidate.get("_news_quality") or {}
    avg = news_quality.get("avg_sentiment")
    try:
        if avg is not None:
            avg = float(avg)
            if avg >= 0.5:
                score = 85
                notes.append("News sentiment strongly positive")
            elif avg >= 0.2:
                score = 75
            elif avg >= -0.2:
                score = 60
            elif avg >= -0.5:
                score = 40
                notes.append("News sentiment negative")
            else:
                score = 20
                notes.append("News sentiment strongly negative")
    except Exception:
        pass

    return max(0, min(100, score)), notes


def _company_external_score(candidate):
    score = 80
    notes = []

    landmines = candidate.get("_landmine_flags") or []
    red = [f for f in landmines if isinstance(f, dict) and f.get("severity") == "RED"]
    yellow = [f for f in landmines if isinstance(f, dict) and f.get("severity") == "YELLOW"]
    if red:
        score -= 50
        notes.append(f"RED landmine: {red[0].get('label', '')[:50]}")
    elif len(yellow) >= 2:
        score -= 20
        notes.append(f"{len(yellow)} YELLOW landmines")
    elif yellow:
        score -= 8

    if candidate.get("going_concern"):
        score -= 60
        notes.append("Going concern language present")

    if candidate.get("recent_shelf"):
        score -= 15
        notes.append("Recent S-3/424B5 shelf (dilution risk)")

    return max(0, min(100, score)), notes


def _pre_exhaustion_score(candidate):
    score = 85
    notes = []

    ret_5d = candidate.get("ret_5d")
    try:
        if ret_5d is not None:
            ret_5d = float(ret_5d)
            if ret_5d > 12:
                score -= 35
                notes.append(f"+{ret_5d:.0f}% 5d (extreme exhaustion)")
            elif ret_5d > 7:
                score -= 20
                notes.append(f"+{ret_5d:.0f}% 5d (exhausted)")
            elif ret_5d > 4:
                score -= 8
                notes.append(f"+{ret_5d:.0f}% 5d (mild run)")
    except Exception:
        pass

    ret_30d = candidate.get("ret_30d")
    try:
        if ret_30d is not None and float(ret_30d) > 30:
            score -= 15
            notes.append(f"+{ret_30d:.0f}% 30d (extended)")
    except Exception:
        pass

    pct_above_50dma = candidate.get("pct_above_50dma")
    try:
        if pct_above_50dma is not None and float(pct_above_50dma) > 20:
            score -= 10
            notes.append(f"+{pct_above_50dma:.0f}% above 50dMA")
    except Exception:
        pass

    return max(0, min(100, score)), notes


def _positioning_score(candidate, macro):
    score = 70
    notes = []

    iv_data = candidate.get("iv_percentile_analysis") or {}
    iv_pct = iv_data.get("iv_percentile")
    try:
        if iv_pct is not None:
            iv_pct = float(iv_pct)
            if iv_pct > 85:
                score -= 20
                notes.append(f"IV percentile {iv_pct:.0f} (option premium expensive)")
            elif iv_pct > 70:
                score -= 8
                notes.append(f"IV pctile {iv_pct:.0f}")
            elif iv_pct < 30:
                score += 5
                notes.append(f"IV pctile {iv_pct:.0f} (option cheap)")
    except Exception:
        pass

    return max(0, min(100, score)), notes


CATEGORY_WEIGHTS = {
    "calendar_event": 0.20,
    "vol_regime": 0.20,
    "sector_context": 0.10,
    "credit_rates": 0.10,
    "news_sentiment": 0.10,
    "company_external": 0.10,
    "pre_exhaustion": 0.10,
    "positioning": 0.10,
}


def compute_trade_survival_score(candidate, macro=None):
    cal_score, cal_notes = _calendar_event_proximity_score(macro)
    vol_score, vol_notes = _vol_regime_score(macro)
    sector_score, sector_notes = _sector_context_score(candidate, macro)
    credit_score, credit_notes = _credit_rates_score(macro)
    news_score, news_notes = _news_sentiment_score(candidate)
    company_score, company_notes = _company_external_score(candidate)
    exhaust_score, exhaust_notes = _pre_exhaustion_score(candidate)
    pos_score, pos_notes = _positioning_score(candidate, macro)

    weighted = (
        cal_score * CATEGORY_WEIGHTS["calendar_event"]
        + vol_score * CATEGORY_WEIGHTS["vol_regime"]
        + sector_score * CATEGORY_WEIGHTS["sector_context"]
        + credit_score * CATEGORY_WEIGHTS["credit_rates"]
        + news_score * CATEGORY_WEIGHTS["news_sentiment"]
        + company_score * CATEGORY_WEIGHTS["company_external"]
        + exhaust_score * CATEGORY_WEIGHTS["pre_exhaustion"]
        + pos_score * CATEGORY_WEIGHTS["positioning"]
    )
    total = round(weighted, 1)

    if total >= 80:
        verdict = "GO"
        verdict_class = "survival-go"
        action = "Full size allowed (no significant headwinds)"
        size_multiplier = 1.0
    elif total >= 65:
        verdict = "GO_NORMAL"
        verdict_class = "survival-go"
        action = "Normal sizing"
        size_multiplier = 1.0
    elif total >= 50:
        verdict = "REDUCE"
        verdict_class = "survival-reduce"
        action = "Reduce size 50% (mild headwinds detected)"
        size_multiplier = 0.5
    elif total >= 35:
        verdict = "ITM_ONLY"
        verdict_class = "survival-reduce"
        action = "Use ITM/longer DTE only (multiple headwinds)"
        size_multiplier = 0.33
    elif total >= 25:
        verdict = "AVOID"
        verdict_class = "survival-avoid"
        action = "Avoid - too many headwinds"
        size_multiplier = 0.0
    else:
        verdict = "SKIP"
        verdict_class = "survival-skip"
        action = "SKIP - high probability of being crushed"
        size_multiplier = 0.0

    risk_notes_combined = []
    risk_notes_combined.extend([("Calendar", n) for n in cal_notes])
    risk_notes_combined.extend([("Vol regime", n) for n in vol_notes])
    risk_notes_combined.extend([("Sector", n) for n in sector_notes])
    risk_notes_combined.extend([("Credit/rates", n) for n in credit_notes])
    risk_notes_combined.extend([("News", n) for n in news_notes])
    risk_notes_combined.extend([("Company", n) for n in company_notes])
    risk_notes_combined.extend([("Exhaustion", n) for n in exhaust_notes])
    risk_notes_combined.extend([("Positioning", n) for n in pos_notes])

    top_risks = sorted(
        [
            ("Calendar", cal_score, cal_notes),
            ("Vol regime", vol_score, vol_notes),
            ("Sector", sector_score, sector_notes),
            ("Credit/rates", credit_score, credit_notes),
            ("News", news_score, news_notes),
            ("Company", company_score, company_notes),
            ("Exhaustion", exhaust_score, exhaust_notes),
            ("Positioning", pos_score, pos_notes),
        ],
        key=lambda x: x[1],
    )[:3]
    kill_risks = [
        f"{cat}: {' / '.join(notes)[:80]}"
        for cat, sc, notes in top_risks
        if sc < 60 and notes
    ]

    return {
        "score": total,
        "verdict": verdict,
        "verdict_class": verdict_class,
        "action": action,
        "size_multiplier": size_multiplier,
        "category_scores": {
            "calendar_event": cal_score,
            "vol_regime": vol_score,
            "sector_context": sector_score,
            "credit_rates": credit_score,
            "news_sentiment": news_score,
            "company_external": company_score,
            "pre_exhaustion": exhaust_score,
            "positioning": pos_score,
        },
        "risk_notes": risk_notes_combined,
        "kill_risks": kill_risks,
    }


def apply_survival_scores(candidates, macro=None, verbose=False):
    if not candidates:
        return
    counts = {"GO": 0, "REDUCE": 0, "ITM_ONLY": 0, "AVOID": 0, "SKIP": 0}
    for c in candidates:
        try:
            sscore = compute_trade_survival_score(c, macro=macro)
            c["_survival_score"] = sscore
            v = sscore.get("verdict")
            if v == "GO_NORMAL":
                v = "GO"
            counts[v] = counts.get(v, 0) + 1
        except Exception as e:
            if verbose:
                print(f"  survival_score fail {c.get('ticker')}: {type(e).__name__}: {e}")
    if verbose:
        print(f"  survival_score: GO={counts.get('GO', 0)} REDUCE={counts.get('REDUCE', 0)} ITM_ONLY={counts.get('ITM_ONLY', 0)} AVOID={counts.get('AVOID', 0)} SKIP={counts.get('SKIP', 0)}")
