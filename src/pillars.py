import pandas as pd


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


def pick_benchmark(ticker):
    return "VUKE.LSE" if ticker.endswith(".LSE") else "SPY.US"
