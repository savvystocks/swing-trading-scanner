import pandas as pd
import numpy as np


def _num(x):
    try:
        v = float(x)
        if pd.isna(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def _return_pct(close, days_back):
    if len(close) < days_back + 1:
        return None
    start = close.iloc[-(days_back + 1)]
    end = close.iloc[-1]
    if not start or start == 0:
        return None
    return (end - start) / start * 100


def composite_rs_raw(close):
    r1 = _return_pct(close, 21)
    r3 = _return_pct(close, 63)
    r6 = _return_pct(close, 126)
    r12 = _return_pct(close, 252)
    if any(v is None for v in (r1, r3, r6)):
        return None
    if r12 is None:
        return 0.4 * r3 + 0.3 * r1 + 0.3 * r6
    return 0.4 * r3 + 0.2 * r1 + 0.2 * r6 + 0.2 * r12


def up_down_volume_ratio(df, lookback=50):
    if len(df) < lookback + 1:
        return None
    recent = df.iloc[-lookback:]
    prior_close = recent["close"].shift(1)
    up_days = recent[recent["close"] > prior_close]
    down_days = recent[recent["close"] < prior_close]
    up_vol = up_days["volume"].sum()
    down_vol = down_days["volume"].sum()
    if down_vol == 0:
        return 3.0
    return float(up_vol / down_vol)


def earnings_acceleration(fundamentals):
    history = (fundamentals or {}).get("Earnings", {}).get("History", {}) or {}
    rows = []
    for date, row in history.items():
        actual = _num(row.get("epsActual"))
        if actual is None:
            continue
        try:
            d = pd.Timestamp(date)
            rows.append((d, actual))
        except Exception:
            continue
    rows.sort(key=lambda r: r[0], reverse=True)
    if len(rows) < 5:
        return None

    most_recent = rows[0][1]
    trailing_4 = [r[1] for r in rows[1:5]]
    avg_prior = sum(trailing_4) / len(trailing_4)

    if avg_prior <= 0:
        return 100.0 if most_recent > 0 else None
    return float((most_recent - avg_prior) / abs(avg_prior) * 100)


def distance_from_pivot(df_ind):
    last = df_ind.iloc[-1]
    close = last["close"]
    sma_50 = last.get("sma_50")
    if not sma_50 or sma_50 <= 0:
        return None
    pct_above_50d = (close - sma_50) / sma_50 * 100

    recent_20 = df_ind["high"].iloc[-20:].max()
    if not recent_20 or recent_20 <= 0:
        return None
    pct_from_20d_high = (close - recent_20) / recent_20 * 100

    return {
        "pct_above_50d": float(pct_above_50d),
        "pct_from_20d_high": float(pct_from_20d_high),
    }


def analyst_upside(fundamentals, current_price):
    h = (fundamentals or {}).get("Highlights", {}) or {}
    target = _num(h.get("WallStreetTargetPrice"))
    if target is None or current_price is None or current_price == 0:
        return None
    return float((target - current_price) / current_price * 100)


def multi_timeframe_trend(df):
    if len(df) < 60 * 5:
        return None
    weekly = df["close"].resample("W-FRI").last().dropna()
    if len(weekly) < 40:
        return None
    w_sma_10 = weekly.rolling(10).mean().iloc[-1]
    w_sma_40 = weekly.rolling(40).mean().iloc[-1]
    w_last = weekly.iloc[-1]
    if pd.isna(w_sma_10) or pd.isna(w_sma_40):
        return None
    weekly_uptrend = w_last > w_sma_10 and w_sma_10 > w_sma_40
    return bool(weekly_uptrend)


def fcf_quality(fundamentals):
    financials = (fundamentals or {}).get("Financials", {}) or {}
    cashflow = financials.get("Cash_Flow", {}) or {}
    income = financials.get("Income_Statement", {}) or {}

    annual_cf = (cashflow.get("yearly") or {}) if isinstance(cashflow.get("yearly"), dict) else {}
    annual_is = (income.get("yearly") or {}) if isinstance(income.get("yearly"), dict) else {}

    if not annual_cf or not annual_is:
        return None

    latest_cf_key = max(annual_cf.keys()) if annual_cf else None
    latest_is_key = max(annual_is.keys()) if annual_is else None
    if not latest_cf_key or not latest_is_key:
        return None

    cf_row = annual_cf.get(latest_cf_key, {})
    is_row = annual_is.get(latest_is_key, {})

    op_cf = _num(cf_row.get("totalCashFromOperatingActivities"))
    capex = _num(cf_row.get("capitalExpenditures")) or 0
    net_income = _num(is_row.get("netIncome"))

    if op_cf is None or net_income is None or net_income <= 0:
        return None

    fcf = op_cf - abs(capex)
    ratio = fcf / net_income
    return float(ratio)


def conviction_score(
    ticker,
    df_ind,
    fundamentals,
    sector,
    sector_performance,
    composite_rs_percentile,
):
    close = df_ind["close"]
    breakdown = {}
    total = 0.0

    if composite_rs_percentile is not None:
        rs_pts = min(25.0, composite_rs_percentile / 99.0 * 25.0)
        breakdown["composite_rs"] = {"value": composite_rs_percentile, "points": round(rs_pts, 1), "max": 25}
        total += rs_pts
    else:
        breakdown["composite_rs"] = {"value": None, "points": 0, "max": 25}

    udv = up_down_volume_ratio(df_ind, lookback=50)
    if udv is not None:
        if udv >= 2.0:
            udv_pts = 15.0
        elif udv >= 1.5:
            udv_pts = 12.0
        elif udv >= 1.2:
            udv_pts = 8.0
        elif udv >= 1.0:
            udv_pts = 4.0
        else:
            udv_pts = 0.0
        breakdown["up_down_vol"] = {"value": round(udv, 2), "points": udv_pts, "max": 15}
        total += udv_pts
    else:
        breakdown["up_down_vol"] = {"value": None, "points": 0, "max": 15}

    eacc = earnings_acceleration(fundamentals)
    if eacc is not None:
        if eacc >= 50:
            e_pts = 15.0
        elif eacc >= 25:
            e_pts = 12.0
        elif eacc >= 10:
            e_pts = 8.0
        elif eacc >= 0:
            e_pts = 4.0
        else:
            e_pts = 0.0
        breakdown["earnings_accel"] = {"value": round(eacc, 1), "points": e_pts, "max": 15}
        total += e_pts
    else:
        breakdown["earnings_accel"] = {"value": None, "points": 0, "max": 15}

    sector_bonus = 0.0
    sector_label = "NEUTRAL"
    if sector and sector_performance:
        match = None
        for s in sector_performance:
            if sector.lower() in s["sector"].lower() or s["sector"].lower() in sector.lower():
                match = s
                break
        if match:
            sector_label = match["outlook"]
            if match["outlook"] == "LEADING":
                sector_bonus = 10.0
            elif match["outlook"] == "STRONG":
                sector_bonus = 7.0
            elif match["outlook"] == "NEUTRAL":
                sector_bonus = 3.0
            elif match["outlook"] == "LAGGING":
                sector_bonus = 1.0
            else:
                sector_bonus = 0.0
    breakdown["sector_lead"] = {"value": sector_label, "points": sector_bonus, "max": 10}
    total += sector_bonus

    pivot = distance_from_pivot(df_ind)
    if pivot:
        pct_above = pivot["pct_above_50d"]
        if 2 <= pct_above <= 10:
            p_pts = 10.0
        elif 0 <= pct_above < 2:
            p_pts = 7.0
        elif 10 < pct_above <= 20:
            p_pts = 5.0
        elif -5 <= pct_above < 0:
            p_pts = 3.0
        else:
            p_pts = 0.0
        breakdown["pivot_proximity"] = {"value": f"{pct_above:+.1f}% vs 50d", "points": p_pts, "max": 10}
        total += p_pts
    else:
        breakdown["pivot_proximity"] = {"value": None, "points": 0, "max": 10}

    last_price = float(close.iloc[-1])
    upside = analyst_upside(fundamentals, last_price)
    if upside is not None:
        if upside >= 30:
            u_pts = 10.0
        elif upside >= 15:
            u_pts = 7.0
        elif upside >= 5:
            u_pts = 4.0
        elif upside >= 0:
            u_pts = 2.0
        else:
            u_pts = 0.0
        breakdown["analyst_upside"] = {"value": f"{upside:+.1f}%", "points": u_pts, "max": 10}
        total += u_pts
    else:
        breakdown["analyst_upside"] = {"value": None, "points": 0, "max": 10}

    mtf = multi_timeframe_trend(df_ind)
    if mtf is True:
        mtf_pts = 10.0
        mtf_val = "weekly uptrend"
    elif mtf is False:
        mtf_pts = 0.0
        mtf_val = "weekly weak"
    else:
        mtf_pts = 5.0
        mtf_val = "insufficient data"
    breakdown["multi_tf_trend"] = {"value": mtf_val, "points": mtf_pts, "max": 10}
    total += mtf_pts

    fcf = fcf_quality(fundamentals)
    if fcf is not None:
        if fcf >= 1.0:
            f_pts = 5.0
        elif fcf >= 0.7:
            f_pts = 3.0
        elif fcf >= 0.3:
            f_pts = 1.0
        else:
            f_pts = 0.0
        breakdown["fcf_quality"] = {"value": round(fcf, 2), "points": f_pts, "max": 5}
        total += f_pts
    else:
        breakdown["fcf_quality"] = {"value": None, "points": 0, "max": 5}

    return {
        "score": round(total, 1),
        "max": 100,
        "breakdown": breakdown,
    }


def compute_composite_rs_percentiles(ohlcv_by_ticker):
    raw_scores = {}
    for ticker, df in ohlcv_by_ticker.items():
        if df is None or len(df) < 64:
            continue
        raw = composite_rs_raw(df["close"])
        if raw is not None:
            raw_scores[ticker] = raw

    if not raw_scores:
        return {}

    sorted_tickers = sorted(raw_scores.items(), key=lambda x: x[1])
    total = len(sorted_tickers)
    percentiles = {}
    for rank, (ticker, _) in enumerate(sorted_tickers):
        percentiles[ticker] = round((rank + 1) / total * 99, 1)
    return percentiles
