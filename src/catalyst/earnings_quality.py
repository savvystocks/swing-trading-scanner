def _safe_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_earnings_quality(fundamentals):
    if not fundamentals:
        return None

    highlights = fundamentals.get("Highlights") or {}
    financials = fundamentals.get("Financials") or {}
    cash_flow_q = ((financials.get("Cash_Flow") or {}).get("quarterly") or {})
    income_q = ((financials.get("Income_Statement") or {}).get("quarterly") or {})
    balance_q = ((financials.get("Balance_Sheet") or {}).get("quarterly") or {})

    flags = []
    score = 70

    operating_cf = _safe_float(highlights.get("OperatingCashflow"))
    net_income = _safe_float(highlights.get("NetIncome")) or _safe_float(highlights.get("DilutedEpsTTM"))
    if operating_cf is not None and net_income and net_income > 0:
        cf_to_ni = operating_cf / net_income
        if cf_to_ni < 0.5:
            score -= 25
            flags.append(f"OpCF/NI ratio {cf_to_ni:.2f} (low - aggressive accounting risk)")
        elif cf_to_ni < 0.8:
            score -= 10
            flags.append(f"OpCF/NI ratio {cf_to_ni:.2f} (mildly soft)")
        elif cf_to_ni > 1.5:
            score += 10
            flags.append(f"OpCF/NI ratio {cf_to_ni:.2f} (strong - real cash flow)")

    fcf_yield = _safe_float(highlights.get("FreeCashFlowYield"))
    if fcf_yield is not None:
        if fcf_yield > 0.08:
            score += 8
            flags.append(f"FCF yield {fcf_yield*100:.1f}% (attractive)")
        elif fcf_yield < 0:
            score -= 12
            flags.append(f"FCF yield {fcf_yield*100:.1f}% (cash-burning)")

    roe = _safe_float(highlights.get("ReturnOnEquityTTM"))
    if roe is not None:
        if roe > 0.20:
            score += 8
            flags.append(f"ROE {roe*100:.0f}% (high quality)")
        elif roe < -0.10:
            score -= 10
            flags.append(f"ROE {roe*100:.0f}% (destroying equity)")

    valuation = fundamentals.get("Valuation") or {}
    peg = _safe_float(valuation.get("PEGRatio")) or _safe_float(highlights.get("PEGRatio"))
    if peg is not None and peg > 0:
        if peg < 1.0:
            score += 10
            flags.append(f"PEG {peg:.2f} (undervalued vs growth)")
        elif peg > 2.5:
            score -= 8
            flags.append(f"PEG {peg:.2f} (rich vs growth)")

    short_pct = _safe_float((fundamentals.get("SharesStats") or {}).get("ShortPercentFloat"))
    if short_pct is not None:
        if short_pct > 20:
            score -= 15
            flags.append(f"Short float {short_pct:.1f}% (heavy bearish positioning)")
        elif short_pct > 10:
            score -= 5
            flags.append(f"Short float {short_pct:.1f}% (notable short interest)")
        elif short_pct < 3:
            score += 3

    description = (fundamentals.get("General") or {}).get("Description") or ""
    desc_lower = description.lower()
    if "going concern" in desc_lower or "substantial doubt" in desc_lower:
        score -= 40
        flags.append("'Going concern' language in description")

    score = max(0, min(100, score))

    if score >= 80:
        rating = "HIGH"
    elif score >= 60:
        rating = "MED"
    elif score >= 40:
        rating = "LOW"
    else:
        rating = "RED_FLAG"

    return {
        "earnings_quality_score": score,
        "rating": rating,
        "flags": flags,
    }


def apply_earnings_quality(candidates, verbose=False):
    if not candidates:
        return
    enriched = 0
    for c in candidates:
        fund = c.get("fundamentals") or c.get("_raw_fundamentals")
        if not fund:
            continue
        try:
            eq = compute_earnings_quality(fund)
            if eq:
                c["_earnings_quality"] = eq
                enriched += 1
        except Exception:
            continue
    if verbose:
        print(f"  earnings_quality: enriched {enriched} picks with quality scoring")
