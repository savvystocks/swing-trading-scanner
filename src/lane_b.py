import pandas as pd
import numpy as np


def pocket_pivot(df_ind, lookback=10):
    if df_ind is None or len(df_ind) < lookback + 2:
        return {"fired": False, "reason": "insufficient history"}
    last = df_ind.iloc[-1]
    prev = df_ind.iloc[-2]
    close = float(last["close"])
    prev_close = float(prev["close"])
    if close <= prev_close:
        return {"fired": False, "reason": "not an up day"}
    today_vol = float(last["volume"])
    avg_vol = float(last.get("avg_vol_20") or 0)
    if avg_vol <= 0:
        return {"fired": False, "reason": "no avg volume"}
    window = df_ind.iloc[-(lookback + 1):-1]
    down_days = window[window["close"] < window["close"].shift(1)]
    largest_down_vol = float(down_days["volume"].max()) if len(down_days) else 0
    pocket_fired = today_vol > largest_down_vol and today_vol >= avg_vol * 1.25
    return {
        "fired": bool(pocket_fired),
        "today_volume": today_vol,
        "largest_down_vol_last_10": largest_down_vol,
        "avg_vol_20": avg_vol,
        "up_day_return_pct": (close - prev_close) / prev_close * 100 if prev_close else 0,
    }


def base_quality(df_ind, lookback_weeks=12):
    if df_ind is None or len(df_ind) < lookback_weeks * 5 + 10:
        return {"score": 0, "fired": False, "reason": "insufficient history"}
    window = df_ind.iloc[-(lookback_weeks * 5):]
    high = float(window["high"].max())
    low = float(window["low"].min())
    close = float(window["close"].iloc[-1])
    if high <= 0:
        return {"score": 0, "fired": False}

    depth_pct = (high - low) / high * 100
    base_range_pct = (high - low) / close * 100
    avg_close = float(window["close"].mean())
    std_close = float(window["close"].std())
    tightness = std_close / avg_close if avg_close else 1.0

    first_third_vol = float(window["volume"].iloc[:len(window) // 3].mean())
    last_third_vol = float(window["volume"].iloc[-len(window) // 3:].mean())
    vol_dry_up = (first_third_vol > 0 and last_third_vol < first_third_vol * 0.90)

    near_high = close >= high * 0.95

    score = 0
    if 5 < depth_pct <= 25:
        score += 3
    elif 25 < depth_pct <= 33:
        score += 2
    elif depth_pct <= 35:
        score += 1
    if tightness < 0.04:
        score += 3
    elif tightness < 0.06:
        score += 2
    elif tightness < 0.08:
        score += 1
    if vol_dry_up:
        score += 2
    if near_high:
        score += 2

    fired = score >= 6
    return {
        "score": score,
        "max": 10,
        "fired": bool(fired),
        "depth_pct": round(depth_pct, 1),
        "tightness": round(tightness, 3),
        "volume_dry_up": bool(vol_dry_up),
        "near_high": bool(near_high),
    }


def insider_cluster(insider_txns, lookback_days=30, min_buyers=2):
    if not insider_txns:
        return {"fired": False, "buyer_count": 0, "total_value_usd": 0}
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
    unique_buyers = set()
    total_value = 0.0
    recent_txns = 0
    for tx in insider_txns:
        try:
            d = pd.Timestamp(tx.get("transactionDate"))
            if d < cutoff:
                continue
            if str(tx.get("transactionAcquiredDisposed", "")).upper() != "A":
                continue
            name = (tx.get("ownerName") or "").strip()
            if name:
                unique_buyers.add(name)
            recent_txns += 1
            shares = float(tx.get("transactionAmount") or 0)
            price = float(tx.get("transactionPrice") or 0)
            total_value += shares * price
        except Exception:
            pass
    fired = len(unique_buyers) >= min_buyers
    return {
        "fired": bool(fired),
        "buyer_count": len(unique_buyers),
        "total_value_usd": round(total_value, 0),
        "transactions": recent_txns,
    }


def revenue_acceleration(fundamentals):
    if not fundamentals:
        return {"fired": False, "reason": "no fundamentals"}
    fin = fundamentals.get("Financials", {}) or {}
    income = fin.get("Income_Statement", {}) or {}
    quarterly = income.get("quarterly", {}) or {}
    if not quarterly:
        return {"fired": False, "reason": "no quarterly revenue data"}
    rows = []
    for k, v in sorted(quarterly.items(), reverse=True)[:8]:
        rev = v.get("totalRevenue")
        if rev:
            try:
                rows.append(float(rev))
            except Exception:
                pass
    if len(rows) < 5:
        return {"fired": False, "reason": "insufficient quarters"}

    latest = rows[0]
    trailing = rows[1:5]
    yoy = None
    if len(rows) >= 5:
        yoy_prev = rows[4]
        if yoy_prev > 0:
            yoy = (latest - yoy_prev) / yoy_prev * 100
    qoq = (latest - trailing[0]) / trailing[0] * 100 if trailing[0] > 0 else 0

    avg_yoy_trailing = None
    yoy_deltas = []
    for i in range(1, 4):
        if i + 4 < len(rows) and rows[i + 4] > 0:
            yoy_deltas.append((rows[i] - rows[i + 4]) / rows[i + 4] * 100)
    if yoy_deltas:
        avg_yoy_trailing = sum(yoy_deltas) / len(yoy_deltas)

    acceleration_ratio = None
    if avg_yoy_trailing is not None and avg_yoy_trailing > 0:
        acceleration_ratio = yoy / avg_yoy_trailing if yoy else None

    fired = (
        yoy is not None and yoy >= 15
        and qoq >= 8
        and (acceleration_ratio is None or acceleration_ratio >= 1.5)
    )

    return {
        "fired": bool(fired),
        "latest_qoq_pct": round(qoq, 1),
        "latest_yoy_pct": round(yoy, 1) if yoy is not None else None,
        "avg_yoy_prior_3q": round(avg_yoy_trailing, 1) if avg_yoy_trailing is not None else None,
        "acceleration_ratio": round(acceleration_ratio, 2) if acceleration_ratio is not None else None,
    }


def earnings_turn(fundamentals):
    if not fundamentals:
        return {"fired": False}
    earn = (fundamentals.get("Earnings") or {}).get("History") or {}
    if not earn:
        return {"fired": False}
    rows = []
    for k, v in sorted(earn.items(), reverse=True):
        sp = v.get("surprisePercent")
        try:
            sp_val = float(sp) if sp is not None else None
        except Exception:
            sp_val = None
        if sp_val is not None:
            rows.append(sp_val)
        if len(rows) >= 4:
            break
    if len(rows) < 3:
        return {"fired": False, "reason": "insufficient earnings history"}

    most_recent = rows[0]
    q_ago = rows[1]
    two_q_ago = rows[2] if len(rows) > 2 else None

    turn_pattern = (
        most_recent > 0
        and q_ago < -5
        and (two_q_ago is None or two_q_ago < 2)
    )

    return {
        "fired": bool(turn_pattern),
        "recent_surprise_pct": round(most_recent, 1),
        "prior_surprise_pct": round(q_ago, 1),
        "two_q_ago_surprise_pct": round(two_q_ago, 1) if two_q_ago is not None else None,
    }


def compute_peer_pack_rotation(scored_results, lookback_days=63):
    industry_map = {}
    for r in scored_results:
        ticker = r["ticket"]["ticker"]
        sector = r["ticket"].get("sector") or "Unknown"
        industry = r["ticket"].get("industry") or sector or "Unknown"
        key = f"{sector} / {industry}"
        ind = r.get("ind")
        if ind is None or len(ind) < lookback_days + 1:
            continue
        try:
            today_price = float(ind["close"].iloc[-1])
            past_price = float(ind["close"].iloc[-lookback_days - 1])
            perf = (today_price - past_price) / past_price * 100 if past_price > 0 else 0
        except Exception:
            continue
        industry_map.setdefault(key, []).append((ticker, perf))

    peer_pack_signals = {}
    for industry, members in industry_map.items():
        if len(members) < 3:
            continue
        perfs = [p for _, p in members]
        leaders = [p for p in perfs if p >= 30]
        if len(leaders) < 3:
            continue
        median_perf = float(np.median(perfs))
        for ticker, perf in members:
            if perf < median_perf * 0.5 and perf < 20:
                peer_pack_signals[ticker] = {
                    "fired": True,
                    "industry": industry,
                    "your_perf_pct": round(perf, 1),
                    "industry_median_pct": round(median_perf, 1),
                    "leaders_in_industry": len(leaders),
                    "total_in_industry": len(members),
                }
    return peer_pack_signals


def run_all_lane_b(df_ind, fundamentals, insider_txns):
    return {
        "pocket_pivot": pocket_pivot(df_ind),
        "base_quality": base_quality(df_ind),
        "insider_cluster": insider_cluster(insider_txns),
        "revenue_acceleration": revenue_acceleration(fundamentals),
        "earnings_turn": earnings_turn(fundamentals),
    }


def lane_b_signal_count(signals):
    count = 0
    if signals.get("pocket_pivot", {}).get("fired"):
        count += 1
    if signals.get("base_quality", {}).get("fired"):
        count += 1
    if signals.get("insider_cluster", {}).get("fired"):
        count += 1
    if signals.get("revenue_acceleration", {}).get("fired"):
        count += 1
    if signals.get("earnings_turn", {}).get("fired"):
        count += 1
    if signals.get("peer_pack", {}).get("fired"):
        count += 1
    return count
