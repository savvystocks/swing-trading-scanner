import json
import pathlib
from datetime import datetime, timedelta

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
PAPER_PATH = PROJECT_ROOT / "data" / "catalyst" / "paper_trades.json"
PRED_DIR = PROJECT_ROOT / "data" / "catalyst" / "predictions"

POSITION_SIZE_USD = 100.0
TRADE_TIER_FILTER = ("BUY",)
FX_SPREAD_ROUND_TRIP_PCT = 0.5
COMMISSION_PER_TRADE = 0.0


def _load_trades():
    if PAPER_PATH.exists():
        with open(PAPER_PATH) as f:
            return json.load(f)
    return []


def _save_trades(trades):
    PAPER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PAPER_PATH, "w") as f:
        json.dump(trades, f, indent=2)


def simulate_outcomes(client):
    trades = _load_trades()
    existing_ids = {t["trade_id"] for t in trades}
    new_trades = 0

    if not PRED_DIR.exists():
        return 0, len(trades)

    for pred_file in sorted(PRED_DIR.glob("*.json")):
        scan_date = pred_file.stem
        with open(pred_file) as f:
            snap = json.load(f)
        for pred in snap.get("predictions", []):
            if pred["signal"] not in TRADE_TIER_FILTER:
                continue
            trade_id = f"{scan_date}|{pred['ticker']}"
            if trade_id in existing_ids:
                continue

            outcome = _simulate_one(client, pred, scan_date)
            if outcome:
                outcome["trade_id"] = trade_id
                outcome["scan_date"] = scan_date
                outcome["ticker"] = pred["ticker"]
                outcome["signal"] = pred["signal"]
                outcome["probability_pct"] = pred.get("probability_pct")
                outcome["entry_price"] = pred["entry_price"]
                outcome["stop_price"] = pred.get("stop_price")
                outcome["target_1_price"] = pred.get("target_1_price")
                outcome["target_2_price"] = pred.get("target_2_price")
                trades.append(outcome)
                new_trades += 1

    _save_trades(trades)
    return new_trades, len(trades)


def _simulate_one(client, pred, scan_date_str):
    eodhd_ticker = pred.get("eodhd_ticker") or f"{pred['ticker']}.US"
    scan_date = datetime.strptime(scan_date_str, "%Y-%m-%d").date()
    end_date = scan_date + timedelta(days=10)
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

    shares = POSITION_SIZE_USD / entry
    half_shares = shares / 2

    high = float(next_day["high"])
    low = float(next_day["low"])
    open_price = float(next_day["open"])
    close = float(next_day["close"])

    t1 = pred.get("target_1_price")
    t2 = pred.get("target_2_price")
    stop = pred.get("stop_price")

    exits = []
    remaining = shares
    proceeds = 0.0

    if stop and low <= stop:
        if open_price <= stop:
            exit_price = open_price
        else:
            exit_price = stop
        proceeds += remaining * exit_price
        exits.append({"reason": "stop", "price": round(exit_price, 4), "shares": round(remaining, 4)})
        remaining = 0
    else:
        if t1 and high >= t1:
            proceeds += half_shares * t1
            exits.append({"reason": "T1", "price": round(t1, 4), "shares": round(half_shares, 4)})
            remaining -= half_shares
        if t2 and high >= t2 and remaining > 0:
            proceeds += remaining * t2
            exits.append({"reason": "T2", "price": round(t2, 4), "shares": round(remaining, 4)})
            remaining = 0
        if remaining > 0:
            proceeds += remaining * close
            exits.append({"reason": "close", "price": round(close, 4), "shares": round(remaining, 4)})
            remaining = 0

    cost = shares * entry
    fees = COMMISSION_PER_TRADE * 2
    fx = (cost + proceeds) * (FX_SPREAD_ROUND_TRIP_PCT / 100) / 2
    pnl_usd = proceeds - cost - fees - fx
    pnl_pct = (pnl_usd / cost) * 100

    return {
        "outcome_date": next_day["date"],
        "shares": round(shares, 4),
        "entry_cost_usd": round(cost, 2),
        "proceeds_usd": round(proceeds, 2),
        "fees_usd": round(fees + fx, 2),
        "pnl_usd": round(pnl_usd, 2),
        "pnl_pct": round(pnl_pct, 2),
        "exits": exits,
        "next_high": round(high, 4),
        "next_low": round(low, 4),
        "next_close": round(close, 4),
    }


def get_paper_stats(days=30):
    trades = _load_trades()
    if not trades:
        return None
    cutoff = datetime.utcnow().date() - timedelta(days=days)
    recent = [
        t for t in trades
        if datetime.strptime(t["scan_date"], "%Y-%m-%d").date() >= cutoff
    ]
    if not recent:
        return None

    n = len(recent)
    wins = [t for t in recent if t["pnl_usd"] > 0]
    losses = [t for t in recent if t["pnl_usd"] <= 0]
    total_pnl = sum(t["pnl_usd"] for t in recent)
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
    biggest_win = max((t["pnl_usd"] for t in recent), default=0)
    biggest_loss = min((t["pnl_usd"] for t in recent), default=0)
    capital_deployed = sum(t["entry_cost_usd"] for t in recent)
    total_fees = sum(t["fees_usd"] for t in recent)

    return {
        "lookback_days": days,
        "n": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / n * 100, 1) if n else 0,
        "total_pnl_usd": round(total_pnl, 2),
        "capital_deployed_usd": round(capital_deployed, 2),
        "roi_pct": round(total_pnl / capital_deployed * 100, 2) if capital_deployed else 0,
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "biggest_win_usd": round(biggest_win, 2),
        "biggest_loss_usd": round(biggest_loss, 2),
        "total_fees_usd": round(total_fees, 2),
        "position_size_usd": POSITION_SIZE_USD,
    }
