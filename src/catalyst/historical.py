from datetime import datetime, timedelta


def historical_earnings_reaction(fundamentals, df, lookback_quarters=4):
    if not fundamentals or df is None or len(df) < 30:
        return None
    history = (fundamentals.get("Earnings") or {}).get("History") or {}
    if not history:
        return None

    df = df.copy()
    df.index = df.index.normalize() if hasattr(df.index, "normalize") else df.index
    reactions = []
    for date_str, row in sorted(history.items(), reverse=True):
        report_date = row.get("reportDate")
        if not report_date:
            continue
        try:
            rd = datetime.strptime(report_date, "%Y-%m-%d").date()
        except Exception:
            continue
        try:
            day_before_idx = df.index.get_indexer([str(rd)], method="ffill")[0]
            if day_before_idx <= 0 or day_before_idx >= len(df):
                continue
            day_before_close = float(df["close"].iloc[day_before_idx])
            day_after_close = float(df["close"].iloc[day_before_idx + 1])
            move_pct = (day_after_close - day_before_close) / day_before_close * 100
            reactions.append({
                "report_date": report_date,
                "move_pct": round(move_pct, 2),
                "surprise_pct": row.get("surprisePercent"),
            })
            if len(reactions) >= lookback_quarters:
                break
        except Exception:
            continue
    if not reactions:
        return None
    moves = [r["move_pct"] for r in reactions]
    median_move = sorted(moves)[len(moves) // 2]
    pct_positive = sum(1 for m in moves if m > 0) / len(moves) * 100
    return {
        "median_move_pct": round(median_move, 2),
        "pct_positive": round(pct_positive, 1),
        "sample_size": len(reactions),
        "moves": reactions,
    }


def historical_score(reaction, points_max=10.0):
    if not reaction or reaction.get("sample_size", 0) < 2:
        return {"points": 0.0, "label": "insufficient history"}
    median = reaction["median_move_pct"]
    pct_pos = reaction["pct_positive"]
    if median >= 5 and pct_pos >= 75:
        points = points_max
        label = f"strong history median +{median:.1f}% / {pct_pos:.0f}% pos"
    elif median >= 3 and pct_pos >= 60:
        points = points_max * 0.75
        label = f"good history median +{median:.1f}% / {pct_pos:.0f}% pos"
    elif median >= 0 and pct_pos >= 50:
        points = points_max * 0.4
        label = f"mixed history median {median:+.1f}% / {pct_pos:.0f}% pos"
    elif median < -3:
        points = -points_max * 0.3
        label = f"poor history median {median:+.1f}% / {pct_pos:.0f}% pos"
    else:
        points = 0
        label = f"flat history median {median:+.1f}%"
    return {
        "points": round(points, 2),
        "label": label,
        "median_move": median,
        "pct_positive": pct_pos,
        "sample_size": reaction["sample_size"],
    }
