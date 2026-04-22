import json
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.telegram import send_alert

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "data" / "results"
STATE_DIR = PROJECT_ROOT / "data" / "intraday_state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

RVOL_TRIGGER = 2.0
MIN_PRICE_MOVE_PCT = 0.5


def load_latest_scan():
    today = datetime.now().strftime("%Y-%m-%d")
    path = RESULTS_DIR / f"scan_{today}.json"
    if not path.exists():
        candidates = sorted(RESULTS_DIR.glob("scan_*.json"), reverse=True)
        if not candidates:
            return None, None
        path = candidates[0]
    with open(path) as f:
        return json.load(f), path.stem


def already_alerted(ticker, scan_id):
    flag = STATE_DIR / f"{scan_id}_{ticker}.flag"
    return flag.exists()


def mark_alerted(ticker, scan_id):
    flag = STATE_DIR / f"{scan_id}_{ticker}.flag"
    flag.write_text(datetime.now(timezone.utc).isoformat())


def get_intraday_snapshot(underlying):
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not secret_key:
        return None

    client = StockHistoricalDataClient(api_key, secret_key)

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=25)
    bars_req = StockBarsRequest(
        symbol_or_symbols=underlying,
        timeframe=TimeFrame.Day,
        start=start.strftime("%Y-%m-%d"),
    )
    bars = client.get_stock_bars(bars_req)
    bar_list = bars.data.get(underlying) if hasattr(bars, "data") else None
    if not bar_list:
        return None

    volumes = [b.volume for b in bar_list[-21:-1] if b.volume]
    if len(volumes) < 5:
        return None
    avg_vol_20d = sum(volumes) / len(volumes)

    today_bar = bar_list[-1]
    today_date = today_bar.timestamp.date() if hasattr(today_bar, "timestamp") else None
    today_volume = today_bar.volume
    today_close = today_bar.close
    today_open = today_bar.open

    if now.date() != today_date:
        return {
            "underlying": underlying,
            "is_today": False,
            "rvol": today_volume / avg_vol_20d if avg_vol_20d else 0,
        }

    hours_into_session = max(0.5, (now.hour + now.minute / 60) - 13.5)
    session_elapsed_fraction = min(1.0, hours_into_session / 6.5)
    projected_full_day_volume = today_volume / session_elapsed_fraction if session_elapsed_fraction > 0.2 else today_volume
    rvol = projected_full_day_volume / avg_vol_20d if avg_vol_20d else 0
    price_move_pct = (today_close - today_open) / today_open * 100 if today_open else 0

    return {
        "underlying": underlying,
        "is_today": True,
        "avg_vol_20d": avg_vol_20d,
        "today_volume_so_far": today_volume,
        "projected_day_volume": projected_full_day_volume,
        "rvol": rvol,
        "session_elapsed": session_elapsed_fraction,
        "today_close": today_close,
        "today_open": today_open,
        "price_move_pct": price_move_pct,
    }


def check_and_alert(ticker, ticket, scan_id):
    if not ticker.endswith(".US"):
        return False, "not .US"
    underlying = ticker.replace(".US", "")

    if already_alerted(ticker, scan_id):
        return False, "already alerted today"

    snap = get_intraday_snapshot(underlying)
    if not snap:
        return False, "no snapshot available"

    rvol = snap.get("rvol", 0)
    move = snap.get("price_move_pct", 0)
    if rvol < RVOL_TRIGGER:
        return False, f"rvol {rvol:.2f}x below trigger {RVOL_TRIGGER}"
    if move < MIN_PRICE_MOVE_PCT:
        return False, f"price move {move:+.2f}% below {MIN_PRICE_MOVE_PCT}%"

    tier = ticket.get("tier")
    conv_score = (ticket.get("conviction") or {}).get("score")
    conv_str = f" · CONV {conv_score}/100" if conv_score is not None else ""
    today_price = snap.get("today_close") or ticket.get("price")

    text = (
        f"<b>VOLUME CONFIRMATION</b> · TIER {tier}{conv_str}\n"
        f"<b>{ticker}</b> · {ticket.get('name', '')[:32]}\n\n"
        f"RVOL {rvol:.1f}x today (vs 20d avg), price {move:+.1f}%\n"
        f"Current ${today_price:.2f} · Morning entry ${ticket['price']:.2f} · "
        f"Stop ${ticket['stop_loss']:.2f}\n\n"
        f"<i>Minervini-style pullback-reversal signal: the Tier {tier} setup from this morning is now "
        f"getting institutional confirmation on volume. This is the window buyers wait for.</i>"
    )
    sent = send_alert(text)
    if sent:
        mark_alerted(ticker, scan_id)
    return sent, f"rvol={rvol:.2f}x move={move:+.2f}%"


def main():
    scan, scan_id = load_latest_scan()
    if not scan:
        print("No scan file found, exiting")
        return
    tickets = scan.get("tickets", [])
    candidates = [t for t in tickets if t.get("tier") and t["tier"] >= 4 and t.get("ticker", "").endswith(".US")]
    print(f"Intraday check on {len(candidates)} Tier 4+ US candidates from scan {scan_id}")

    for t in candidates:
        ticker = t["ticker"]
        try:
            sent, reason = check_and_alert(ticker, t, scan_id)
            status = "SENT" if sent else "skip"
            print(f"  {ticker:12s} [{status}] {reason}")
        except Exception as e:
            print(f"  {ticker:12s} [error] {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
