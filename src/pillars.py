import pandas as pd
import re


def trend_template(row, df):
    close = row["close"]
    sma_50 = row.get("sma_50")
    sma_150 = row.get("sma_150")
    sma_200 = row.get("sma_200")

    if any(pd.isna(x) for x in (sma_50, sma_150, sma_200)):
        return {"pass": False, "checks": {}, "reason": "insufficient history"}

    past_200 = df["sma_200"].iloc[-22:] if len(df) >= 22 else df["sma_200"]
    trending_up = past_200.iloc[-1] > past_200.iloc[0] if len(past_200) >= 2 else False

    high_52 = df["high"].iloc[-252:].max() if len(df) >= 252 else df["high"].max()
    low_52 = df["low"].iloc[-252:].min() if len(df) >= 252 else df["low"].min()

    checks = {
        "1_above_150_200": close > sma_150 and close > sma_200,
        "2_sma150_above_sma200": sma_150 > sma_200,
        "3_sma200_trending_up": trending_up,
        "4_sma50_above_sma150_sma200": sma_50 > sma_150 and sma_50 > sma_200,
        "5_30pct_above_52wk_low": close >= low_52 * 1.30,
        "6_within_25pct_of_52wk_high": close >= high_52 * 0.75,
        "7_rs_placeholder": True,
    }
    passed = all(checks.values())
    return {
        "pass": passed,
        "checks": checks,
        "high_52": float(high_52),
        "low_52": float(low_52),
        "pct_from_high": float((close - high_52) / high_52 * 100),
        "pct_above_low": float((close - low_52) / low_52 * 100),
    }


def weinstein_stage(df):
    if len(df) < 210:
        return None
    close = df["close"].iloc[-1]
    sma_30wk = df["close"].rolling(150, min_periods=150).mean().iloc[-1]
    sma_30wk_prev = df["close"].rolling(150, min_periods=150).mean().iloc[-21]
    rising = sma_30wk > sma_30wk_prev
    falling = sma_30wk < sma_30wk_prev

    if close > sma_30wk and rising:
        return 2
    if close > sma_30wk and not rising:
        return 3
    if close < sma_30wk and falling:
        return 4
    if close < sma_30wk and not falling:
        return 1
    return None


def pillar_1_trend_following(df_ind):
    last = df_ind.iloc[-1]
    tt = trend_template(last, df_ind)
    stage = weinstein_stage(df_ind)
    passes = sum(1 for v in tt["checks"].values() if v)
    if tt["pass"] and stage == 2:
        verdict = "PASS"
    elif passes >= 5 and stage == 2:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    return {
        "verdict": verdict,
        "trend_template_passed": passes,
        "trend_template_total": 7,
        "stage": stage,
        "details": tt,
    }


def pillar_2_volatility_breakout(df_ind):
    last = df_ind.iloc[-1]
    squeeze_pct = last.get("bb_squeeze_pct")
    bb_width = last.get("bb_width")
    close = last["close"]
    bb_upper = last.get("bb_upper")

    if pd.isna(squeeze_pct) or pd.isna(bb_width):
        return {"verdict": "FAIL", "reason": "insufficient history"}

    in_squeeze = squeeze_pct <= 20
    upper_break = bool(pd.notna(bb_upper) and close > bb_upper)
    recent_squeeze = df_ind["bb_squeeze_pct"].iloc[-10:].min() <= 20

    if recent_squeeze and upper_break:
        verdict = "PASS"
    elif in_squeeze:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "squeeze_percentile": float(squeeze_pct),
        "bb_width": float(bb_width),
        "in_squeeze": bool(in_squeeze),
        "upper_band_break": upper_break,
        "recent_squeeze_last_10d": bool(recent_squeeze),
    }


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pillar_3_can_slim(fundamentals):
    h = (fundamentals or {}).get("Highlights", {}) or {}
    eps_growth_yoy = _num(h.get("QuarterlyEarningsGrowthYOY"))
    rev_growth_yoy = _num(h.get("QuarterlyRevenueGrowthYOY"))
    profit_margin = _num(h.get("ProfitMargin"))
    roe = _num(h.get("ReturnOnEquityTTM"))
    peg = _num(h.get("PEGRatio"))

    checks = {
        "eps_growth_25pct": eps_growth_yoy is not None and eps_growth_yoy >= 0.25,
        "revenue_growth_20pct": rev_growth_yoy is not None and rev_growth_yoy >= 0.20,
        "profit_margin_positive": profit_margin is not None and profit_margin > 0,
        "roe_above_17pct": roe is not None and roe >= 0.17,
        "peg_reasonable": peg is None or (0 < peg <= 2.5),
    }
    passed = sum(1 for v in checks.values() if v)
    if passed >= 4:
        verdict = "PASS"
    elif passed >= 3:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "checks": checks,
        "eps_growth_yoy": eps_growth_yoy,
        "revenue_growth_yoy": rev_growth_yoy,
        "profit_margin": profit_margin,
        "roe_ttm": roe,
        "peg": peg,
    }


def rs_score(candidate_df, benchmark_df, lookback=20):
    if len(candidate_df) < lookback + 1 or len(benchmark_df) < lookback + 1:
        return None
    c_start = candidate_df["close"].iloc[-(lookback + 1)]
    c_end = candidate_df["close"].iloc[-1]
    b_start = benchmark_df["close"].iloc[-(lookback + 1)]
    b_end = benchmark_df["close"].iloc[-1]
    c_ret = (c_end - c_start) / c_start * 100
    b_ret = (b_end - b_start) / b_start * 100
    return {
        "candidate_return": float(c_ret),
        "benchmark_return": float(b_ret),
        "rs_score": float(c_ret - b_ret),
    }


def pillar_4_statarb(candidate_df, benchmark_df, lookback=20):
    rs = rs_score(candidate_df, benchmark_df, lookback)
    if rs is None:
        return {"verdict": "FAIL", "reason": "insufficient history"}
    score = rs["rs_score"]
    if score >= 3.0:
        verdict = "PASS"
    elif score >= 1.0:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    return {"verdict": verdict, **rs}


def pillar_5_global_macro(vix_df):
    if vix_df is None or len(vix_df) == 0:
        return {"verdict": "PARTIAL", "reason": "no vix data", "vix": None, "regime": "unknown"}
    vix = float(vix_df["close"].iloc[-1])
    if vix < 15:
        regime = "low_vol"
    elif vix <= 22:
        regime = "normal"
    elif vix <= 30:
        regime = "elevated"
    elif vix <= 35:
        regime = "extreme"
    else:
        regime = "crisis"

    if regime in ("low_vol", "normal"):
        verdict = "PASS"
    elif regime == "elevated":
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    return {"verdict": verdict, "vix": vix, "regime": regime}


def pillar_6_erm(fundamentals, is_us):
    earnings = (fundamentals or {}).get("Earnings", {}) or {}
    history = earnings.get("History", {}) or {}
    trend = earnings.get("Trend", {}) or {}
    ratings = (fundamentals or {}).get("AnalystRatings", {}) or {}

    recent = sorted(history.items(), reverse=True)[:4]
    beats = 0
    last_surprise = None
    for _, row in recent:
        sp = _num(row.get("surprisePercent"))
        if sp is not None:
            if last_surprise is None:
                last_surprise = sp
            if sp > 0:
                beats += 1

    up_7d = 0
    up_30d = 0
    down_30d = 0
    if trend:
        first_trend = list(trend.values())[0] if trend else {}
        up_7d = int(float(first_trend.get("epsRevisionsUpLast7days") or 0))
        up_30d = int(float(first_trend.get("epsRevisionsUpLast30days") or 0))
        down_30d = int(float(first_trend.get("epsRevisionsDownLast30days") or 0))

    analyst_upgrades = None
    if is_us:
        strong_buy = _num(ratings.get("StrongBuy")) or 0
        buy = _num(ratings.get("Buy")) or 0
        hold = _num(ratings.get("Hold")) or 0
        sell = _num(ratings.get("Sell")) or 0
        total = strong_buy + buy + hold + sell + (_num(ratings.get("StrongSell")) or 0)
        analyst_upgrades = (strong_buy + buy) / total if total > 0 else None

    beat_and_raise = beats >= 2 and last_surprise is not None and last_surprise > 0
    positive_revisions = up_30d > down_30d and up_30d >= 2
    downgrades = down_30d > up_30d * 2 and down_30d >= 3

    if downgrades:
        verdict = "FAIL"
    elif beat_and_raise and positive_revisions:
        verdict = "PASS_BONUS"
    elif beat_and_raise or positive_revisions:
        verdict = "PASS"
    elif up_30d >= 1 and down_30d == 0:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "consecutive_beats": beats,
        "last_surprise_pct": last_surprise,
        "eps_up_7d": up_7d,
        "eps_up_30d": up_30d,
        "eps_down_30d": down_30d,
        "analyst_bullish_ratio_us": analyst_upgrades,
        "beat_and_raise": beat_and_raise,
    }


def pillar_7_short_squeeze(fundamentals, df_ind, insider_txns, is_us):
    shares_stats = (fundamentals or {}).get("SharesStats", {}) or {}
    sp_float = _num(shares_stats.get("ShortPercentFloat"))
    shares_float = _num(shares_stats.get("SharesFloat"))

    if sp_float is None:
        if is_us:
            return {"verdict": "FAIL", "reason": "no SI data", "applicable": True}
        return {"verdict": "UNAVAILABLE", "applicable": False, "reason": "no LSE SI data"}

    days_to_cover = None
    if shares_float and len(df_ind) >= 20:
        avg_vol = df_ind["avg_vol_20"].iloc[-1]
        if avg_vol and avg_vol > 0:
            shares_short = shares_float * (sp_float / 100.0 if sp_float > 1 else sp_float)
            days_to_cover = float(shares_short / avg_vol)

    insider_buys_30d = 0
    if is_us and insider_txns:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
        for tx in insider_txns:
            try:
                d = pd.Timestamp(tx.get("transactionDate"))
                if d >= cutoff and str(tx.get("transactionAcquiredDisposed", "")).upper() == "A":
                    insider_buys_30d += 1
            except Exception:
                pass

    si_pct = sp_float if sp_float <= 1 else sp_float / 100.0

    if si_pct >= 0.20:
        si_level = "coiled_spring"
    elif si_pct >= 0.10:
        si_level = "moderate"
    elif si_pct >= 0.03:
        si_level = "low"
    else:
        si_level = "none"

    if si_level == "coiled_spring":
        verdict = "PASS_BONUS"
    elif si_level == "moderate":
        verdict = "PASS"
    elif si_level == "low" and insider_buys_30d >= 2 and is_us:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "applicable": True,
        "short_percent_float": si_pct * 100,
        "si_level": si_level,
        "days_to_cover": days_to_cover,
        "insider_buys_30d": insider_buys_30d if is_us else None,
    }


CATALYST_KEYWORDS = {
    "tier_a": [
        r"beat.{0,20}estimate", r"raises? guidance", r"raising guidance",
        r"fda approval", r"major contract", r"acquires?", r"acquisition",
        r"merger", r"takeover bid", r"buyout",
    ],
    "tier_b": [
        r"analyst upgrade", r"price target raised?", r"upgraded to buy",
        r"new product", r"launch", r"partnership", r"index addition",
    ],
}


def gate_4_catalyst(fundamentals, news_items):
    earnings = (fundamentals or {}).get("Earnings", {}) or {}
    history = earnings.get("History", {}) or {}
    recent_beat = False
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=90)
    for date, row in history.items():
        try:
            d = pd.Timestamp(date)
            sp = _num(row.get("surprisePercent"))
            if d >= cutoff and sp is not None and sp >= 5:
                recent_beat = True
                break
        except Exception:
            pass

    tier_a_hits = []
    tier_b_hits = []
    for n in (news_items or [])[:20]:
        title = (n.get("title") or "").lower()
        content = (n.get("content") or "")[:500].lower()
        text = f"{title} {content}"
        for kw in CATALYST_KEYWORDS["tier_a"]:
            if re.search(kw, text):
                tier_a_hits.append(title[:60])
                break
        else:
            for kw in CATALYST_KEYWORDS["tier_b"]:
                if re.search(kw, text):
                    tier_b_hits.append(title[:60])
                    break

    if recent_beat or tier_a_hits:
        tier = "A"
        verdict = "PASS"
    elif tier_b_hits:
        tier = "B"
        verdict = "PASS"
    else:
        tier = "C"
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "tier": tier,
        "recent_earnings_beat": recent_beat,
        "tier_a_headlines": tier_a_hits[:3],
        "tier_b_headlines": tier_b_hits[:3],
    }


def gate_3_rvol(df_ind):
    last = df_ind.iloc[-1]
    avg = last.get("avg_vol_20")
    vol = last.get("volume")
    if not avg or not vol or avg == 0:
        return {"verdict": "FAIL", "rvol": None}
    rvol = float(vol / avg)
    if rvol >= 1.5:
        verdict = "PASS"
    elif rvol >= 1.0:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    return {"verdict": verdict, "rvol": rvol}


def gate_6_liquidity(fundamentals, df_ind):
    h = (fundamentals or {}).get("Highlights", {}) or {}
    stats = (fundamentals or {}).get("SharesStats", {}) or {}
    mcap = _num(h.get("MarketCapitalization"))
    shares_float = _num(stats.get("SharesFloat"))
    shares_out = _num(stats.get("SharesOutstanding"))

    last = df_ind.iloc[-1]
    avg_vol = last.get("avg_vol_20") or 0
    close = last.get("close") or 0
    dollar_vol = avg_vol * close

    float_pct = None
    if shares_float and shares_out and shares_out > 0:
        float_pct = shares_float / shares_out * 100

    checks = {
        "mcap_above_500m": bool(mcap and mcap >= 500_000_000),
        "dollar_vol_above_2m": bool(dollar_vol >= 2_000_000),
        "float_above_30pct": bool(float_pct is None or float_pct >= 30),
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    return {
        "verdict": verdict,
        "market_cap": mcap,
        "dollar_volume_20d": float(dollar_vol),
        "float_pct_of_shares": float_pct,
        "checks": checks,
    }


def gate_7_earnings_blackout(fundamentals):
    earnings = (fundamentals or {}).get("Earnings", {}) or {}
    trend = earnings.get("Trend", {}) or {}
    future_dates = []
    today = pd.Timestamp.now().normalize()
    for date_str in trend.keys():
        try:
            d = pd.Timestamp(date_str)
            if d > today:
                future_dates.append(d)
        except Exception:
            pass
    if not future_dates:
        return {"verdict": "PASS", "next_earnings": None, "days_until": None, "reason": "no scheduled date"}
    next_date = min(future_dates)
    days = (next_date - today).days
    if days <= 10:
        verdict = "FAIL"
    else:
        verdict = "PASS"
    return {
        "verdict": verdict,
        "next_earnings": next_date.strftime("%Y-%m-%d"),
        "days_until": days,
    }


def pick_benchmark(ticker):
    return "VUKE.LSE" if ticker.endswith(".LSE") else "SPY.US"
