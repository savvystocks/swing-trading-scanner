import json
import pathlib
from datetime import datetime, timedelta

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
PRED_DIR = PROJECT_ROOT / "data" / "catalyst" / "predictions"
HISTORY_PATH = PROJECT_ROOT / "data" / "catalyst" / "history.json"
PRED_DIR.mkdir(parents=True, exist_ok=True)


def snapshot_predictions(scan_date, all_scored):
    actionable = [
        c for c in all_scored
        if c.get("buy_signal") and c["buy_signal"].get("signal") in ("BUY", "WATCH")
        and c.get("buy_signal", {}).get("entry_price")
    ]
    snapshot = []
    for c in actionable:
        bs = c["buy_signal"]
        snapshot.append({
            "ticker": c["ticker"],
            "eodhd_ticker": c.get("eodhd_ticker"),
            "name": c.get("name"),
            "sector": c.get("sector"),
            "signal": bs["signal"],
            "probability_pct": bs.get("probability_pct"),
            "score": c["score"],
            "confidence": c.get("confidence"),
            "catalyst_tier": c.get("catalyst_tier"),
            "entry_price": bs["entry_price"],
            "stop_price": bs.get("stop_price"),
            "target_1_price": bs.get("target_1_price"),
            "target_2_price": bs.get("target_2_price"),
            "expected_move_low_pct": bs.get("expected_move_low_pct"),
            "expected_move_high_pct": bs.get("expected_move_high_pct"),
            "atr_pct": bs.get("atr_pct"),
            "primary_catalyst": (c.get("catalysts") or [{}])[0].get("label", ""),
        })
    out_path = PRED_DIR / f"{scan_date}.json"
    with open(out_path, "w") as f:
        json.dump({"scan_date": scan_date, "predictions": snapshot}, f, indent=2)
    return len(snapshot), out_path


def measure_outcomes(client, scan_date_str, max_lookback_days=3):
    pred_path = PRED_DIR / f"{scan_date_str}.json"
    if not pred_path.exists():
        return 0, 0
    with open(pred_path) as f:
        snap = json.load(f)
    predictions = snap.get("predictions", [])
    if not predictions:
        return 0, 0

    history = _load_history()
    already_measured_ids = {h["prediction_id"] for h in history}

    measured = 0
    skipped = 0
    for p in predictions:
        pred_id = f"{scan_date_str}|{p['ticker']}"
        if pred_id in already_measured_ids:
            skipped += 1
            continue
        outcome = _measure_one(client, p, scan_date_str, max_lookback_days)
        if outcome:
            history.append({
                "prediction_id": pred_id,
                "scan_date": scan_date_str,
                "outcome_date": outcome["outcome_date"],
                "ticker": p["ticker"],
                "signal": p["signal"],
                "probability_pct": p["probability_pct"],
                "confidence": p["confidence"],
                "catalyst_tier": p["catalyst_tier"],
                "entry_price": p["entry_price"],
                "stop_price": p.get("stop_price"),
                "target_1_price": p.get("target_1_price"),
                "target_2_price": p.get("target_2_price"),
                "primary_catalyst": p.get("primary_catalyst"),
                "next_open_pct": outcome["next_open_pct"],
                "next_high_pct": outcome["next_high_pct"],
                "next_close_pct": outcome["next_close_pct"],
                "next_low_pct": outcome["next_low_pct"],
                "hit_t1": outcome["hit_t1"],
                "hit_t2": outcome["hit_t2"],
                "hit_stop": outcome["hit_stop"],
            })
            measured += 1
    _save_history(history)
    return measured, skipped


def _measure_one(client, pred, scan_date_str, max_lookback_days):
    eodhd_ticker = pred.get("eodhd_ticker") or f"{pred['ticker']}.US"
    scan_date = datetime.strptime(scan_date_str, "%Y-%m-%d").date()
    end_date = scan_date + timedelta(days=max_lookback_days + 3)
    try:
        ohlcv = client.ohlcv(eodhd_ticker, from_date=scan_date_str, to_date=end_date.strftime("%Y-%m-%d"))
    except Exception:
        return None
    if not ohlcv:
        return None
    next_day = None
    for row in ohlcv:
        rd = datetime.strptime(row["date"], "%Y-%m-%d").date()
        if rd > scan_date:
            next_day = row
            break
    if not next_day:
        return None

    entry = float(pred["entry_price"])
    if entry <= 0:
        return None
    open_pct = (float(next_day["open"]) - entry) / entry * 100
    high_pct = (float(next_day["high"]) - entry) / entry * 100
    low_pct = (float(next_day["low"]) - entry) / entry * 100
    close_pct = (float(next_day["close"]) - entry) / entry * 100

    t1 = pred.get("target_1_price")
    t2 = pred.get("target_2_price")
    stop = pred.get("stop_price")
    hit_t1 = bool(t1 and float(next_day["high"]) >= t1)
    hit_t2 = bool(t2 and float(next_day["high"]) >= t2)
    hit_stop = bool(stop and float(next_day["low"]) <= stop)

    return {
        "outcome_date": next_day["date"],
        "next_open_pct": round(open_pct, 2),
        "next_high_pct": round(high_pct, 2),
        "next_low_pct": round(low_pct, 2),
        "next_close_pct": round(close_pct, 2),
        "hit_t1": hit_t1,
        "hit_t2": hit_t2,
        "hit_stop": hit_stop,
    }


def _load_history():
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH) as f:
            return json.load(f)
    return []


def _save_history(history):
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)


def get_recent_stats(days=30):
    history = _load_history()
    if not history:
        return None
    cutoff = datetime.utcnow().date() - timedelta(days=days)
    recent = [
        h for h in history
        if datetime.strptime(h["scan_date"], "%Y-%m-%d").date() >= cutoff
    ]
    if not recent:
        return None

    def stats_for(rows):
        if not rows:
            return None
        n = len(rows)
        hit_t1 = sum(1 for r in rows if r["hit_t1"])
        hit_t2 = sum(1 for r in rows if r["hit_t2"])
        hit_stop = sum(1 for r in rows if r["hit_stop"])
        avg_high = sum(r["next_high_pct"] for r in rows) / n
        avg_close = sum(r["next_close_pct"] for r in rows) / n
        gap_up = sum(1 for r in rows if r["next_open_pct"] > 0)
        return {
            "n": n,
            "hit_t1_pct": round(hit_t1 / n * 100, 1),
            "hit_t2_pct": round(hit_t2 / n * 100, 1),
            "hit_stop_pct": round(hit_stop / n * 100, 1),
            "gap_up_pct": round(gap_up / n * 100, 1),
            "avg_next_high_pct": round(avg_high, 2),
            "avg_next_close_pct": round(avg_close, 2),
        }

    buy = [r for r in recent if r["signal"] == "BUY"]
    watch = [r for r in recent if r["signal"] == "WATCH"]

    return {
        "lookback_days": days,
        "total_measured": len(recent),
        "BUY": stats_for(buy),
        "WATCH": stats_for(watch),
    }
