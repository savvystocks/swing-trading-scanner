def days_to_cover(short_pct_float, shares_float, avg_daily_volume):
    if not short_pct_float or not shares_float or not avg_daily_volume or avg_daily_volume <= 0:
        return None
    si = short_pct_float / 100.0 if short_pct_float > 1 else short_pct_float
    shares_short = shares_float * si
    return round(shares_short / avg_daily_volume, 2)


def short_squeeze_setup_score(short_pct_float, days_to_cover_val, insider_buys_30d=0):
    if short_pct_float is None:
        return {"score": 0, "label": "no SI data"}
    si_pct = short_pct_float
    score = 0
    flags = []

    if si_pct >= 30:
        score += 4
        flags.append(f"SI {si_pct:.0f}% (extreme squeeze fuel)")
    elif si_pct >= 20:
        score += 3
        flags.append(f"SI {si_pct:.0f}% (high squeeze fuel)")
    elif si_pct >= 15:
        score += 2
        flags.append(f"SI {si_pct:.0f}% (moderate)")

    if days_to_cover_val is not None:
        if days_to_cover_val >= 7:
            score += 3
            flags.append(f"DTC {days_to_cover_val:.1f} days (severe)")
        elif days_to_cover_val >= 4:
            score += 2
            flags.append(f"DTC {days_to_cover_val:.1f} days")
        elif days_to_cover_val >= 2:
            score += 1

    if insider_buys_30d >= 3 and si_pct >= 15:
        score += 2
        flags.append(f"insider buys {insider_buys_30d} + high SI = explosive setup")

    if score >= 7:
        level = "EXPLOSIVE"
    elif score >= 5:
        level = "STRONG"
    elif score >= 3:
        level = "MODERATE"
    else:
        level = "LOW"

    return {
        "score": score,
        "level": level,
        "flags": flags,
        "short_pct_float": round(si_pct, 1),
        "days_to_cover": days_to_cover_val,
    }


def analyst_upgrade_cluster(analyst_ratings, lookback_days=30, min_upgrades=3):
    if not analyst_ratings:
        return {"cluster_detected": False, "upgrades_30d": 0}
    strong_buy = float(analyst_ratings.get("StrongBuy", 0) or 0)
    buy = float(analyst_ratings.get("Buy", 0) or 0)
    hold = float(analyst_ratings.get("Hold", 0) or 0)
    sell = float(analyst_ratings.get("Sell", 0) or 0)
    strong_sell = float(analyst_ratings.get("StrongSell", 0) or 0)
    total = strong_buy + buy + hold + sell + strong_sell
    bullish_pct = (strong_buy + buy) / total * 100 if total > 0 else 0
    return {
        "cluster_detected": False,
        "strong_buy": int(strong_buy),
        "buy": int(buy),
        "hold": int(hold),
        "sell": int(sell),
        "strong_sell": int(strong_sell),
        "bullish_pct": round(bullish_pct, 0),
        "total_analysts": int(total),
    }


def beneish_m_score(financials):
    if not financials:
        return None
    try:
        income = (financials.get("Income_Statement") or {}).get("yearly") or {}
        balance = (financials.get("Balance_Sheet") or {}).get("yearly") or {}
        cashflow = (financials.get("Cash_Flow") or {}).get("yearly") or {}

        years = sorted(income.keys(), reverse=True)
        if len(years) < 2:
            return None
        yt = years[0]
        ytm1 = years[1]

        def _num(d, key):
            try:
                v = d.get(key)
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        rev_t = _num(income.get(yt, {}), "totalRevenue")
        rev_tm1 = _num(income.get(ytm1, {}), "totalRevenue")
        cogs_t = _num(income.get(yt, {}), "costOfRevenue")
        cogs_tm1 = _num(income.get(ytm1, {}), "costOfRevenue")
        sga_t = _num(income.get(yt, {}), "sellingGeneralAdministrative")
        sga_tm1 = _num(income.get(ytm1, {}), "sellingGeneralAdministrative")
        ni_t = _num(income.get(yt, {}), "netIncome")
        cfo_t = _num(cashflow.get(yt, {}), "totalCashFromOperatingActivities")
        ar_t = _num(balance.get(yt, {}), "netReceivables")
        ar_tm1 = _num(balance.get(ytm1, {}), "netReceivables")
        ta_t = _num(balance.get(yt, {}), "totalAssets")
        ta_tm1 = _num(balance.get(ytm1, {}), "totalAssets")
        ppe_t = _num(balance.get(yt, {}), "propertyPlantEquipment")
        ppe_tm1 = _num(balance.get(ytm1, {}), "propertyPlantEquipment")
        ltd_t = _num(balance.get(yt, {}), "longTermDebt")
        ltd_tm1 = _num(balance.get(ytm1, {}), "longTermDebt")
        depr_t = _num(cashflow.get(yt, {}), "depreciation")
        depr_tm1 = _num(cashflow.get(ytm1, {}), "depreciation")

        if not all([rev_t, rev_tm1, ar_t, ar_tm1, ta_t, ta_tm1]):
            return None

        dsri = (ar_t / rev_t) / (ar_tm1 / rev_tm1) if rev_tm1 > 0 and ar_tm1 > 0 else 1
        gmi = ((rev_tm1 - (cogs_tm1 or 0)) / rev_tm1) / ((rev_t - (cogs_t or 0)) / rev_t) if rev_t > 0 else 1
        aqi_num = 1 - ((ar_t + (ppe_t or 0)) / ta_t) if ta_t > 0 else 0
        aqi_den = 1 - ((ar_tm1 + (ppe_tm1 or 0)) / ta_tm1) if ta_tm1 > 0 else 1
        aqi = aqi_num / aqi_den if aqi_den != 0 else 1
        sgi = rev_t / rev_tm1 if rev_tm1 > 0 else 1
        depi = ((depr_tm1 or 0) / ((ppe_tm1 or 1) + (depr_tm1 or 0))) / ((depr_t or 0) / ((ppe_t or 1) + (depr_t or 0))) if depr_t and ppe_t else 1
        sgai = ((sga_t or 0) / rev_t) / ((sga_tm1 or 0) / rev_tm1) if rev_tm1 > 0 and sga_tm1 else 1
        lvgi = ((ltd_t or 0) / ta_t) / ((ltd_tm1 or 0) / ta_tm1) if ta_tm1 > 0 and ltd_tm1 else 1
        tata = ((ni_t or 0) - (cfo_t or 0)) / ta_t if ta_t > 0 else 0

        m_score = (
            -4.84
            + 0.92 * dsri
            + 0.528 * gmi
            + 0.404 * aqi
            + 0.892 * sgi
            + 0.115 * depi
            - 0.172 * sgai
            + 4.679 * tata
            - 0.327 * lvgi
        )
        flag = "MANIPULATOR_LIKELY" if m_score > -1.78 else "CLEAN"
        return {
            "m_score": round(m_score, 3),
            "flag": flag,
            "components": {
                "dsri": round(dsri, 3), "gmi": round(gmi, 3), "aqi": round(aqi, 3),
                "sgi": round(sgi, 3), "depi": round(depi, 3), "sgai": round(sgai, 3),
                "tata": round(tata, 3), "lvgi": round(lvgi, 3),
            },
        }
    except Exception:
        return None
