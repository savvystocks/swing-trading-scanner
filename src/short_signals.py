import pandas as pd


def stage_4_check(df):
    if len(df) < 200:
        return {"pass": False, "passes": 0, "total": 6, "reason": "insufficient history"}
    last = df.iloc[-1]
    close = last["close"]
    sma_50 = last.get("sma_50")
    sma_150 = last.get("sma_150")
    sma_200 = last.get("sma_200")
    if any(pd.isna(x) for x in (sma_50, sma_150, sma_200)):
        return {"pass": False, "passes": 0, "total": 6, "reason": "MAs not computed"}

    past_200 = df["sma_200"].iloc[-22:] if len(df) >= 22 else df["sma_200"]
    trending_down = past_200.iloc[-1] < past_200.iloc[0] if len(past_200) >= 2 else False
    high_52 = df["high"].iloc[-252:].max() if len(df) >= 252 else df["high"].max()
    low_52 = df["low"].iloc[-252:].min() if len(df) >= 252 else df["low"].min()

    checks = {
        "below_150_200": bool(close < sma_150 and close < sma_200),
        "sma150_below_sma200": bool(sma_150 < sma_200),
        "sma200_trending_down": bool(trending_down),
        "sma50_below_sma150_sma200": bool(sma_50 < sma_150 and sma_50 < sma_200),
        "20pct_below_52wk_high": bool(close <= high_52 * 0.80),
        "within_15pct_of_52wk_low": bool(close <= low_52 * 1.15),
    }
    passes = sum(1 for v in checks.values() if v)
    return {
        "pass": all(checks.values()),
        "passes": passes,
        "total": 6,
        "checks": checks,
        "pct_from_high": float((close - high_52) / high_52 * 100),
        "pct_above_low": float((close - low_52) / low_52 * 100),
    }


def distribution_count(df, lookback=25, vol_lookback=40):
    if len(df) < vol_lookback + lookback:
        return 0, 0
    avg_vol = df["volume"].iloc[-(vol_lookback + lookback):-lookback].mean()
    if not avg_vol:
        return 0, 0
    dist = 0
    acc = 0
    for i in range(len(df) - lookback, len(df)):
        if i == 0:
            continue
        prev_close = df["close"].iloc[i - 1]
        if not prev_close:
            continue
        chg = (df["close"].iloc[i] / prev_close - 1) * 100
        vol_pct = df["volume"].iloc[i] / avg_vol * 100
        if chg < -0.2 and vol_pct > 110:
            dist += 1
        elif chg > 0.2 and vol_pct > 110:
            acc += 1
    return dist, acc


def inverse_rs(candidate_df, benchmark_df, lookback=20):
    if len(candidate_df) < lookback or len(benchmark_df) < lookback:
        return None
    cand_now = candidate_df["close"].iloc[-1]
    cand_then = candidate_df["close"].iloc[-lookback]
    bench_now = benchmark_df["close"].iloc[-1]
    bench_then = benchmark_df["close"].iloc[-lookback]
    if not all([cand_now, cand_then, bench_now, bench_then]):
        return None
    cand_ret = cand_now / cand_then - 1
    bench_ret = bench_now / bench_then - 1
    return (cand_ret - bench_ret) * 100


def breakdown_through_50d(df):
    if len(df) < 60:
        return False, 0.0
    if "sma_50" not in df.columns:
        return False, 0.0
    sma50 = df["sma_50"].iloc[-1]
    close = df["close"].iloc[-1]
    if pd.isna(sma50) or not sma50:
        return False, 0.0
    diff_pct = (close / sma50 - 1) * 100
    closes_10 = df["close"].iloc[-10:]
    sma50_10 = df["sma_50"].iloc[-10:]
    crossed_below = (closes_10.iloc[0] >= sma50_10.iloc[0]) and (closes_10.iloc[-1] < sma50_10.iloc[-1])
    return bool(crossed_below), float(diff_pct)


def short_score(df_ind, benchmark_df, fundamentals=None):
    if df_ind is None or len(df_ind) < 200:
        return None

    score = 0
    reasons = []

    stage = stage_4_check(df_ind)
    if stage["pass"]:
        score += 35
        reasons.append(f"Stage 4 confirmed ({stage['passes']}/6)")
    elif stage["passes"] >= 4:
        score += 22
        reasons.append(f"Stage 4 partial ({stage['passes']}/6)")
    elif stage["passes"] >= 3:
        score += 10
        reasons.append(f"breakdown forming ({stage['passes']}/6)")

    dist_25, acc_25 = distribution_count(df_ind, lookback=25)
    if dist_25 >= 5 and dist_25 > acc_25 + 1:
        score += 25
        reasons.append(f"{dist_25} distribution days last 25 (vs {acc_25} acc)")
    elif dist_25 >= 3 and dist_25 > acc_25:
        score += 15
        reasons.append(f"{dist_25} distribution days last 25 (vs {acc_25} acc)")

    irs_20 = inverse_rs(df_ind, benchmark_df, lookback=20)
    irs_60 = inverse_rs(df_ind, benchmark_df, lookback=60)
    if irs_20 is not None and irs_20 <= -10:
        score += 20
        reasons.append(f"underperforming benchmark by {-irs_20:.1f}% over 20d")
    elif irs_20 is not None and irs_20 <= -5:
        score += 12
        reasons.append(f"underperforming benchmark by {-irs_20:.1f}% over 20d")

    crossed, diff_pct = breakdown_through_50d(df_ind)
    if crossed:
        score += 15
        reasons.append(f"just broke down through 50d MA ({diff_pct:+.1f}%)")
    elif diff_pct < -8:
        score += 5
        reasons.append(f"below 50d MA by {diff_pct:.1f}% (post-breakdown)")

    if fundamentals:
        trend = (fundamentals.get("Earnings") or {}).get("Trend") or {}
        revs_down_total = 0.0
        revs_up_total = 0.0
        for k, v in list(trend.items())[:2]:
            try:
                rd = float(v.get("epsRevisionsDownLast30days") or 0)
                ru = float(v.get("epsRevisionsUpLast30days") or 0)
                revs_down_total += rd
                revs_up_total += ru
            except (ValueError, TypeError):
                pass
        if revs_down_total > revs_up_total + 1:
            score += 5
            reasons.append(f"analyst revisions {revs_down_total:.0f} down vs {revs_up_total:.0f} up")

    return {
        "score": min(100, int(score)),
        "qualified": score >= 50,
        "reasons": reasons,
        "stage_4_check": stage,
        "distribution_count_25d": dist_25,
        "accumulation_count_25d": acc_25,
        "inverse_rs_20d": float(irs_20) if irs_20 is not None else None,
        "inverse_rs_60d": float(irs_60) if irs_60 is not None else None,
        "below_50d_pct": float(diff_pct) if crossed or diff_pct < 0 else None,
    }
