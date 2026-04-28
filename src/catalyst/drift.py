def compute_drift(df, lookback_5d=5, lookback_10d=10):
    if df is None or len(df) < lookback_10d + 1:
        return None
    last_close = float(df["close"].iloc[-1])
    close_5d_ago = float(df["close"].iloc[-1 - lookback_5d]) if len(df) > lookback_5d else None
    close_10d_ago = float(df["close"].iloc[-1 - lookback_10d]) if len(df) > lookback_10d else None
    if close_5d_ago is None or close_5d_ago == 0:
        return None
    roc_5d = (last_close - close_5d_ago) / close_5d_ago * 100
    roc_10d = (last_close - close_10d_ago) / close_10d_ago * 100 if close_10d_ago else None
    return {
        "roc_5d": round(roc_5d, 2),
        "roc_10d": round(roc_10d, 2) if roc_10d is not None else None,
        "last_close": round(last_close, 2),
    }


def drift_score(drift, points_max=10.0):
    if not drift:
        return {"points": 0.0, "label": "no drift data"}
    roc_5d = drift.get("roc_5d") or 0
    if roc_5d >= 8:
        points = points_max
        label = f"strong drift +{roc_5d:.1f}% 5d"
    elif roc_5d >= 4:
        points = points_max * 0.7
        label = f"positive drift +{roc_5d:.1f}% 5d"
    elif roc_5d >= 1:
        points = points_max * 0.4
        label = f"mild drift +{roc_5d:.1f}% 5d"
    elif roc_5d >= -2:
        points = points_max * 0.2
        label = f"flat {roc_5d:+.1f}% 5d"
    elif roc_5d >= -5:
        points = 0.0
        label = f"weak {roc_5d:+.1f}% 5d"
    else:
        points = -points_max * 0.3
        label = f"negative drift {roc_5d:+.1f}% 5d"
    return {"points": round(points, 2), "label": label, "roc_5d": roc_5d}
