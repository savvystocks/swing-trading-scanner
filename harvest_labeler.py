def _result(outcome, label, realized, touch_ts, signal_ts, n_polls, n_stale, mfe, mae, ambiguous):
    ttt = None
    if touch_ts is not None and signal_ts is not None:
        ttt = round((touch_ts - signal_ts) / 60000.0, 3)
    return {
        "outcome": outcome,
        "label": label,
        "realized_return": round(realized, 6) if realized is not None else None,
        "touch_ts_utc": touch_ts,
        "time_to_touch_min": ttt,
        "mfe": round(mfe, 6) if mfe is not None else None,
        "mae": round(mae, 6) if mae is not None else None,
        "n_polls": n_polls,
        "n_stale": n_stale,
        "ambiguous_touch": ambiguous,
    }


def label_path(entry_ref, up_pct, down_pct, vertical_ts, signal_ts, path):
    if not entry_ref or entry_ref <= 0:
        return _result("open", None, None, None, signal_ts, len(path or []), 0, None, None, False)
    up_level = entry_ref * (1.0 + up_pct)
    down_level = entry_ref * (1.0 + down_pct)
    ordered = sorted(path or [], key=lambda p: p["poll_ts"])
    n_polls = len(ordered)
    n_stale = 0
    mfe = None
    mae = None
    for p in ordered:
        bid = p.get("bid")
        if p.get("stale") or bid is None:
            n_stale += 1
            continue
        r = (bid - entry_ref) / entry_ref
        mfe = r if mfe is None or r > mfe else mfe
        mae = r if mae is None or r < mae else mae
        ts = p["poll_ts"]
        if ts >= vertical_ts:
            rr = (bid - entry_ref) / entry_ref
            return _result("vertical", 1 if rr > 0 else -1, rr, ts, signal_ts, n_polls, n_stale, mfe, mae, False)
        if bid == 0:
            return _result("down", -1, -1.0, ts, signal_ts, n_polls, n_stale, mfe, mae, False)
        hi = p.get("high") if p.get("high") is not None else bid
        lo = p.get("low") if p.get("low") is not None else bid
        up_touch = hi >= up_level
        down_touch = lo <= down_level
        if up_touch and down_touch:
            return _result("down", -1, down_pct, ts, signal_ts, n_polls, n_stale, mfe, mae, True)
        if down_touch:
            return _result("down", -1, (bid - entry_ref) / entry_ref, ts, signal_ts, n_polls, n_stale, mfe, mae, False)
        if up_touch:
            return _result("up", 1, (bid - entry_ref) / entry_ref, ts, signal_ts, n_polls, n_stale, mfe, mae, False)
    return _result("open", None, None, None, signal_ts, n_polls, n_stale, mfe, mae, False)
