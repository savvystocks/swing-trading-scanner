import pandas as pd
import numpy as np


def to_dataframe(ohlcv):
    df = pd.DataFrame(ohlcv)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    for col in ("open", "high", "low", "close", "adjusted_close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def sma(series, period):
    return series.rolling(period, min_periods=period).mean()


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series, fast=12, slow=26, signal=9):
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    line = fast_ema - slow_ema
    sig = ema(line, signal)
    hist = line - sig
    return line, sig, hist


def atr(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def bollinger(series, period=20, std_mult=2.0):
    mid = sma(series, period)
    std = series.rolling(period, min_periods=period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    width = (upper - lower) / mid
    return mid, upper, lower, width


def bb_squeeze_percentile(series, period=20, lookback=120):
    _, _, _, width = bollinger(series, period)
    return width.rolling(lookback, min_periods=lookback).apply(
        lambda w: (w.rank(pct=True).iloc[-1]) * 100
    )


def compute_all(df):
    close = df["close"]
    out = df.copy()
    for p in (5, 10, 20, 50, 100, 150, 200):
        out[f"sma_{p}"] = sma(close, p)
    for p in (5, 10, 20, 50):
        out[f"ema_{p}"] = ema(close, p)
    out["rsi_14"] = rsi(close, 14)
    macd_line, macd_signal, macd_hist = macd(close)
    out["macd"] = macd_line
    out["macd_signal"] = macd_signal
    out["macd_hist"] = macd_hist
    out["atr_14"] = atr(df, 14)
    bb_mid, bb_up, bb_lo, bb_width = bollinger(close, 20, 2.0)
    out["bb_mid"] = bb_mid
    out["bb_upper"] = bb_up
    out["bb_lower"] = bb_lo
    out["bb_width"] = bb_width
    out["bb_squeeze_pct"] = bb_squeeze_percentile(close, 20, 120)
    out["avg_vol_20"] = df["volume"].rolling(20, min_periods=20).mean()
    out["avg_vol_50"] = df["volume"].rolling(50, min_periods=50).mean()
    return out
