import numpy as np


def _safe_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def volatility_contraction(df, window=20, lookback=120):
    if df is None or len(df) < lookback + window:
        return {"score": 0, "fired": False, "reason": "insufficient history"}
    closes = df["close"].astype(float)
    rolling_std = closes.rolling(window).std()
    rolling_mean = closes.rolling(window).mean()
    bb_width_pct = (rolling_std * 4 / rolling_mean * 100).dropna()
    if len(bb_width_pct) < lookback:
        return {"score": 0, "fired": False, "reason": "insufficient bb history"}
    recent_window = bb_width_pct.iloc[-lookback:]
    current = float(bb_width_pct.iloc[-1])
    percentile = float((recent_window <= current).sum() / len(recent_window) * 100)
    score = 0
    if percentile <= 10:
        score = 3
    elif percentile <= 20:
        score = 2
    elif percentile <= 30:
        score = 1
    return {
        "score": score,
        "fired": score >= 1,
        "bb_width_pct": round(current, 2),
        "percentile": round(percentile, 1),
    }


def base_length(df, max_lookback=180, breakout_threshold_pct=10):
    if df is None or len(df) < 30:
        return {"score": 0, "fired": False, "reason": "insufficient history"}
    closes = df["close"].astype(float).values
    last_close = closes[-1]
    if last_close <= 0:
        return {"score": 0, "fired": False, "reason": "zero price"}
    upper_bound = last_close * (1 + breakout_threshold_pct / 100)
    lower_bound = last_close * (1 - breakout_threshold_pct / 100)
    days_in_base = 0
    n = min(len(closes), max_lookback)
    for i in range(1, n + 1):
        c = closes[-i]
        if c < lower_bound or c > upper_bound:
            break
        days_in_base += 1
    weeks_in_base = days_in_base // 5
    score = 0
    if weeks_in_base >= 16:
        score = 3
    elif weeks_in_base >= 10:
        score = 2
    elif weeks_in_base >= 6:
        score = 1
    return {
        "score": score,
        "fired": score >= 1,
        "days_in_base": days_in_base,
        "weeks_in_base": weeks_in_base,
        "breakout_threshold_pct": breakout_threshold_pct,
    }


def higher_low_after_correction(df, correction_lookback=120, recent_window=30):
    if df is None or len(df) < correction_lookback:
        return {"score": 0, "fired": False, "reason": "insufficient history"}
    closes = df["close"].astype(float)
    lows = df["low"].astype(float)
    recent_lows = lows.iloc[-recent_window:].values
    older_lows = lows.iloc[-correction_lookback:-recent_window].values
    if len(older_lows) < 10 or len(recent_lows) < 10:
        return {"score": 0, "fired": False, "reason": "insufficient window"}

    older_min = float(older_lows.min())
    recent_min = float(recent_lows.min())
    older_min_idx = int(np.argmin(older_lows))
    recent_min_idx = int(np.argmin(recent_lows))

    last_close = float(closes.iloc[-1])
    pct_above_recent_low = (last_close - recent_min) / recent_min * 100 if recent_min > 0 else 0

    higher_low_present = recent_min > older_min and recent_min_idx > older_min_idx
    score = 0
    if higher_low_present and pct_above_recent_low >= 5 and pct_above_recent_low <= 25:
        score = 3
    elif higher_low_present and pct_above_recent_low >= 3:
        score = 2
    elif higher_low_present:
        score = 1
    return {
        "score": score,
        "fired": score >= 1,
        "older_low": round(older_min, 2),
        "recent_low": round(recent_min, 2),
        "pct_above_recent_low": round(pct_above_recent_low, 1),
        "higher_low_present": bool(higher_low_present),
    }


def stage_4_turnaround(df, lookback_long=200, recent_window=20):
    if df is None or len(df) < lookback_long:
        return {"score": 0, "fired": False, "reason": "insufficient history"}
    closes = df["close"].astype(float)
    volumes = df["volume"].astype(float)

    long_high = float(closes.iloc[-lookback_long:].max())
    long_low = float(closes.iloc[-lookback_long:].min())
    last_close = float(closes.iloc[-1])
    if long_high <= 0 or long_low <= 0:
        return {"score": 0, "fired": False, "reason": "zero prices"}

    drawdown_pct = (long_high - last_close) / long_high * 100
    pct_off_low = (last_close - long_low) / long_low * 100

    sma_50 = float(closes.iloc[-50:].mean()) if len(closes) >= 50 else None
    sma_200 = float(closes.iloc[-200:].mean())

    sma_50_slope = None
    if len(closes) >= 60:
        sma_50_now = float(closes.iloc[-50:].mean())
        sma_50_then = float(closes.iloc[-60:-10].mean())
        sma_50_slope = (sma_50_now - sma_50_then) / sma_50_then * 100 if sma_50_then > 0 else None

    recent_vol = float(volumes.iloc[-recent_window:].mean())
    older_vol = float(volumes.iloc[-recent_window * 4:-recent_window].mean()) if len(volumes) >= recent_window * 5 else recent_vol
    vol_increase_pct = (recent_vol - older_vol) / older_vol * 100 if older_vol > 0 else 0

    is_post_correction = drawdown_pct >= 35
    is_off_lows = pct_off_low >= 8 and pct_off_low <= 35
    sma_50_turning = sma_50_slope is not None and sma_50_slope >= 1
    above_50 = sma_50 is not None and last_close > sma_50
    vol_picking_up = vol_increase_pct >= 15

    score = 0
    if is_post_correction and is_off_lows and sma_50_turning and above_50:
        score = 3
        if vol_picking_up:
            score = 3
    elif is_post_correction and is_off_lows and (sma_50_turning or above_50):
        score = 2
    elif is_post_correction and is_off_lows:
        score = 1

    return {
        "score": score,
        "fired": score >= 1,
        "drawdown_pct": round(drawdown_pct, 1),
        "pct_off_low": round(pct_off_low, 1),
        "sma_50_slope_pct": round(sma_50_slope, 2) if sma_50_slope is not None else None,
        "above_50d": bool(above_50),
        "vol_increase_pct": round(vol_increase_pct, 1),
        "post_correction": bool(is_post_correction),
        "off_lows": bool(is_off_lows),
    }


def volume_dry_up(df, recent_window=20, base_window=60):
    if df is None or len(df) < base_window + recent_window:
        return {"score": 0, "fired": False, "reason": "insufficient history"}
    volumes = df["volume"].astype(float)
    recent = float(volumes.iloc[-recent_window:].mean())
    older = float(volumes.iloc[-(base_window + recent_window):-recent_window].mean())
    if older <= 0:
        return {"score": 0, "fired": False, "reason": "no older volume"}
    decay_pct = (older - recent) / older * 100
    score = 0
    if decay_pct >= 35:
        score = 2
    elif decay_pct >= 20:
        score = 1
    return {
        "score": score,
        "fired": score >= 1,
        "recent_avg_vol": round(recent, 0),
        "older_avg_vol": round(older, 0),
        "vol_decay_pct": round(decay_pct, 1),
    }


def inflection_readiness_score(df):
    vc = volatility_contraction(df)
    bl = base_length(df)
    hl = higher_low_after_correction(df)
    s4 = stage_4_turnaround(df)
    vd = volume_dry_up(df)

    components = {
        "volatility_contraction": vc,
        "base_length": bl,
        "higher_low": hl,
        "stage_4_turnaround": s4,
        "volume_dry_up": vd,
    }
    fired = sum(1 for c in components.values() if c.get("fired"))
    raw_total = sum(c.get("score", 0) for c in components.values())

    if s4.get("fired") and s4.get("score", 0) >= 2:
        label = "STAGE_4_TURNAROUND"
    elif vc.get("score", 0) >= 2 and bl.get("score", 0) >= 2:
        label = "COILED_BASE"
    elif hl.get("score", 0) >= 2 and bl.get("score", 0) >= 1:
        label = "TURNING_UP"
    elif fired >= 2:
        label = "FORMING"
    elif fired >= 1:
        label = "EARLY"
    else:
        label = "NONE"

    points = min(15, raw_total * 1.5)

    return {
        "label": label,
        "points": round(points, 1),
        "raw_total": raw_total,
        "max_possible": 15,
        "components_fired": fired,
        "components": components,
    }
