import pandas as pd
import numpy as np


def realized_vol_annualized(df, lookback_days=30):
    if df is None or len(df) < lookback_days + 2:
        return None
    close = df["close"].iloc[-(lookback_days + 1):]
    log_returns = np.log(close / close.shift(1)).dropna()
    if len(log_returns) < 5:
        return None
    return float(log_returns.std() * np.sqrt(252))


def vol_rank(df, lookback_window_days=252, rv_lookback_days=30):
    if df is None or len(df) < lookback_window_days + rv_lookback_days + 2:
        return None
    close = df["close"]
    log_returns = np.log(close / close.shift(1)).dropna()
    rolling_vol = log_returns.rolling(rv_lookback_days, min_periods=rv_lookback_days).std() * np.sqrt(252)
    recent_window = rolling_vol.iloc[-lookback_window_days:].dropna()
    if len(recent_window) < 50:
        return None
    current = float(recent_window.iloc[-1])
    hi = float(recent_window.max())
    lo = float(recent_window.min())
    if hi - lo <= 0:
        return None
    rank = (current - lo) / (hi - lo) * 100
    return {
        "vol_rank_pct": round(rank, 0),
        "current_realized_vol": round(current * 100, 1),
        "52w_high_vol": round(hi * 100, 1),
        "52w_low_vol": round(lo * 100, 1),
    }


def options_interpretation(vr_pct):
    if vr_pct is None:
        return "unknown"
    if vr_pct <= 30:
        return "CHEAP"
    if vr_pct <= 60:
        return "FAIR"
    if vr_pct <= 80:
        return "EXPENSIVE"
    return "VERY_EXPENSIVE"
