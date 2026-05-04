import pandas as pd


def resample_to_weekly(df_daily):
    if len(df_daily) < 60:
        return None
    if not isinstance(df_daily.index, pd.DatetimeIndex):
        df = df_daily.copy()
        df.index = pd.to_datetime(df.index)
    else:
        df = df_daily

    weekly = df.resample("W-FRI").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()

    if len(weekly) < 30:
        return None

    weekly["sma_10w"] = weekly["close"].rolling(10, min_periods=10).mean()
    weekly["sma_30w"] = weekly["close"].rolling(30, min_periods=30).mean()
    weekly["sma_40w"] = weekly["close"].rolling(40, min_periods=40).mean()
    return weekly


def weekly_stage(weekly_df):
    if weekly_df is None or len(weekly_df) < 30:
        return {"stage": None, "reason": "insufficient weekly history"}

    last = weekly_df.iloc[-1]
    close = last["close"]
    sma_10w = last.get("sma_10w")
    sma_30w = last.get("sma_30w")
    sma_40w = last.get("sma_40w")

    if pd.isna(sma_10w) or pd.isna(sma_30w):
        return {"stage": None, "reason": "MAs not computed"}

    sma_30w_8w_ago = weekly_df["sma_30w"].iloc[-9] if len(weekly_df) >= 9 else None
    rising_30w = bool(pd.notna(sma_30w_8w_ago) and sma_30w > sma_30w_8w_ago)
    falling_30w = bool(pd.notna(sma_30w_8w_ago) and sma_30w < sma_30w_8w_ago)

    above_30w = bool(close > sma_30w)
    above_10w = bool(close > sma_10w)
    sma_10w_above_30w = bool(sma_10w > sma_30w)

    if above_30w and rising_30w and sma_10w_above_30w:
        stage = 2
    elif above_30w and not rising_30w:
        stage = 3
    elif not above_30w and falling_30w:
        stage = 4
    elif not above_30w and not falling_30w:
        stage = 1
    else:
        stage = None

    pct_above_30w = (close / sma_30w - 1) * 100 if sma_30w > 0 else None

    return {
        "stage": stage,
        "weekly_close": float(close),
        "weekly_sma_10w": float(sma_10w),
        "weekly_sma_30w": float(sma_30w),
        "weekly_sma_40w": float(sma_40w) if pd.notna(sma_40w) else None,
        "above_30w": above_30w,
        "above_10w": above_10w,
        "sma_10w_above_30w": sma_10w_above_30w,
        "30w_rising": rising_30w,
        "30w_falling": falling_30w,
        "pct_above_30w": float(pct_above_30w) if pct_above_30w is not None else None,
    }


def apply_multi_timeframe_to_hunter(scored_results, verbose=True):
    boosted = 0
    penalized = 0
    disqualified = 0

    for r in scored_results:
        ticket = r.get("ticket") if isinstance(r, dict) and "ticket" in r else r
        if not ticket:
            continue
        ind = r.get("ind")
        if ind is None or len(ind) < 200:
            continue

        weekly = resample_to_weekly(ind)
        ws = weekly_stage(weekly)
        ticket["weekly_stage"] = ws

        h = ticket.get("hunter")
        if not h:
            continue

        score = h.get("score", 0)
        reasons = list(h.get("reasons", []))
        stage = ws.get("stage")
        pct_above = ws.get("pct_above_30w")

        adjustment = 0
        if stage == 2:
            adjustment = 8
            reasons.append(f"weekly Stage 2 confirmed ({pct_above:+.1f}% vs 30w SMA)")
            boosted += 1
        elif stage == 3:
            adjustment = -5
            reasons.append(f"weekly Stage 3 (top forming)")
            penalized += 1
        elif stage == 4:
            adjustment = -20
            reasons.append(f"WEEKLY STAGE 4 - daily breakout vs broken weekly trend")
            penalized += 1
        elif stage == 1:
            adjustment = -10
            reasons.append(f"weekly Stage 1 (basing)")

        new_score = max(0, min(100, score + adjustment))
        h["score"] = new_score
        h["reasons"] = reasons
        h["multi_timeframe"] = {
            "weekly_stage": stage,
            "adjustment": adjustment,
            "pct_above_30w": pct_above,
        }

        if new_score < 50 and h.get("qualified"):
            h["qualified"] = False
            h.setdefault("disqualified", []).append("multi_timeframe_filter")
            disqualified += 1

    if verbose:
        print(f"  multi_timeframe: weekly Stage 2 boosted={boosted} penalized={penalized} disqualified={disqualified}")
    return scored_results
