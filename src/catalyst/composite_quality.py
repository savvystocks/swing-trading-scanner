def _coerce(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def beneish_m_score(candidate):
    raw = candidate.get("_raw_fundamentals") or {}
    if not raw:
        return None
    existing = candidate.get("beneish_m_score")
    if existing is not None:
        return existing
    return None


def altman_z_score(candidate):
    raw = candidate.get("_raw_fundamentals") or {}
    if not raw:
        return None
    balance = raw.get("Balance_Sheet", {}) or {}
    highlights = raw.get("Highlights", {}) or {}
    try:
        working_capital = _coerce(highlights.get("WorkingCapital"))
        total_assets = _coerce(highlights.get("TotalAssets"))
        retained_earnings = _coerce(highlights.get("RetainedEarnings"))
        ebit = _coerce(highlights.get("EBIT"))
        market_cap = _coerce(candidate.get("market_cap"))
        total_liab = _coerce(highlights.get("TotalLiabilities"))
        revenue = _coerce(highlights.get("RevenueTTM"))
        if not all(v is not None and v > 0 for v in [total_assets, total_liab, revenue]):
            return None
        z = 0
        if working_capital is not None:
            z += 1.2 * (working_capital / total_assets)
        if retained_earnings is not None:
            z += 1.4 * (retained_earnings / total_assets)
        if ebit is not None:
            z += 3.3 * (ebit / total_assets)
        if market_cap and total_liab:
            z += 0.6 * (market_cap / total_liab)
        z += 1.0 * (revenue / total_assets)
        return round(z, 2)
    except Exception:
        return None


def piotroski_f_score(candidate):
    highlights = (candidate.get("_raw_fundamentals") or {}).get("Highlights", {}) or {}
    score = 0
    try:
        net_income = _coerce(highlights.get("NetIncome"))
        roa = _coerce(highlights.get("ReturnOnAssetsTTM"))
        operating_cf = _coerce(highlights.get("OperatingCashflowTTM"))
        if net_income and net_income > 0:
            score += 1
        if roa and roa > 0:
            score += 1
        if operating_cf and operating_cf > 0:
            score += 1
        if operating_cf and net_income and operating_cf > net_income:
            score += 1
    except Exception:
        pass
    return score


def compute_composite_quality(candidate):
    altman = altman_z_score(candidate)
    piotroski = piotroski_f_score(candidate)
    beneish = beneish_m_score(candidate)

    flags = []
    score = 50
    if altman is not None:
        if altman < 1.8:
            flags.append(f"Altman Z {altman} — distress zone")
            score -= 20
        elif altman > 3.0:
            score += 10
    if piotroski is not None:
        if piotroski >= 7:
            score += 15
        elif piotroski <= 2:
            flags.append(f"Piotroski F {piotroski} — quality concerns")
            score -= 15
    if beneish is not None and beneish > -1.78:
        flags.append(f"Beneish M {beneish} — earnings manipulation risk")
        score -= 25

    return {
        "altman_z": altman,
        "piotroski_f": piotroski,
        "beneish_m": beneish,
        "composite_score": max(0, min(score, 100)),
        "flags": flags,
    }


def enrich_composite_quality(candidates, verbose=False):
    for s in candidates:
        s["composite_quality"] = compute_composite_quality(s)
    if verbose:
        red_flags = sum(1 for s in candidates if (s.get("composite_quality") or {}).get("flags"))
        print(f"  composite_quality: {red_flags} candidates with quality flags")
    return candidates
