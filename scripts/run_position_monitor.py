"""Live position monitor - polls UW every 10 min during US market hours.

Reads data/paper_trades/live_positions.json (the file log_trade.py writes),
marks each OPEN option to its live mid, and fires a Telegram alert when:
  - the trailing-stop exit rules trip (hard stop / arm / trail) -> SELL or armed
  - dealer regime flips or spot crosses the gamma flip strike -> reassess

State in data/position_monitor_state.json so we only alert on transitions,
not on every poll.
"""

import os
import sys
import json
import pathlib
from datetime import datetime, timezone


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.unusual_whales_api import get_client
from src.catalyst.uw_enrichment import _summarize_gex
from src.catalyst.trade_ticket import _occ_symbol, _fetch_contract_data
from src.catalyst import live_exit


LIVE_POSITIONS_PATH = pathlib.Path(__file__).parent.parent / "data" / "paper_trades" / "live_positions.json"
STATE_PATH = pathlib.Path(__file__).parent.parent / "data" / "position_monitor_state.json"


def load_open_positions():
    if not LIVE_POSITIONS_PATH.exists():
        return []
    try:
        data = json.loads(LIVE_POSITIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [p for p in data if p.get("status") == "OPEN"]


def send_telegram(text):
    import urllib.request
    import urllib.parse
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not tok or not chat:
        print(f"[no-telegram] would alert: {text[:80]}")
        return
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status != 200:
                print(f"Telegram HTTP {r.status}")
    except Exception as e:
        print(f"Telegram failed: {type(e).__name__}: {e}")


def load_state():
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def live_mid(uw, pos):
    ticker = pos.get("ticker")
    strike = pos.get("strike")
    side = pos.get("side")
    expiry_s = pos.get("expiration") or pos.get("expiry")
    if not (ticker and strike and side and expiry_s):
        return None, None
    try:
        exp = datetime.strptime(str(expiry_s)[:10], "%Y-%m-%d").date()
    except Exception:
        return None, None
    occ = _occ_symbol(ticker, exp, side, float(strike))
    quote = _fetch_contract_data(uw, ticker, occ)
    if not quote:
        return occ, None
    bid, ask, last = quote.get("bid"), quote.get("ask"), quote.get("last")
    if bid and ask:
        return occ, (bid + ask) / 2
    if last:
        return occ, last
    return occ, None


def check_regime(uw, pos, prev):
    ticker = pos["ticker"]
    side = pos.get("side", "?")
    strike = pos.get("strike")
    alerts = []

    spot_data = uw.stock_state(ticker)
    spot = None
    if spot_data and isinstance(spot_data, dict):
        spot = (spot_data.get("data") or {}).get("close")
    try:
        spot = float(spot) if spot else None
    except (TypeError, ValueError):
        spot = None
    if not spot:
        return alerts, None

    gex_data = uw.greek_exposure_by_strike(ticker)
    gex_summary = _summarize_gex(None, gex_data, ticker, spot)
    if not gex_summary:
        return alerts, None

    regime = gex_summary.get("dealer_regime")
    flip = gex_summary.get("gamma_flip_strike")

    prev_regime = prev.get("dealer_regime")
    prev_spot = prev.get("spot")
    prev_flip = prev.get("flip_strike")

    if regime and prev_regime and regime != prev_regime:
        bad_for_calls = regime == "NEGATIVE_AMP"
        bad_for_puts = regime == "POSITIVE_PIN"
        warn = (side == "CALL" and bad_for_calls) or (side == "PUT" and bad_for_puts)
        severity = "WARN" if warn else "INFO"
        alerts.append(
            f"<b>REGIME [{severity}]: {ticker} {side} ${strike}</b>\n"
            f"Dealer regime: {prev_regime} -> {regime}\n"
            f"{'Watch for accelerated move against you' if warn else 'Move may decelerate'}"
        )

    if (spot and prev_spot and flip is not None and prev_flip is not None
            and (prev_spot >= prev_flip) != (spot >= flip)):
        alerts.append(
            f"<b>REGIME: {ticker} {side} ${strike}</b>\n"
            f"Spot ${spot:.2f} crossed gamma flip strike ${flip:.2f}\n"
            f"Hedging regime change - reassess"
        )

    return alerts, {
        "dealer_regime": regime,
        "flip_strike": flip,
        "spot": spot,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }


def main():
    positions = load_open_positions()
    if not positions:
        print("No open positions in live_positions.json")
        return

    print(f"Monitoring {len(positions)} positions: {', '.join(p['ticker'] for p in positions)}")

    uw = get_client()
    if not uw.enabled:
        print("UNUSUAL_WHALES_TOKEN missing")
        sys.exit(1)

    state = load_state()
    exits_state = state.get("exits") or {}
    regimes_state = state.get("regimes") or {}
    new_exits = {}
    new_regimes = {}
    total_alerts = 0

    for pos in positions:
        ticker = pos.get("ticker", "?")
        try:
            occ, mid = live_mid(uw, pos)
            if occ and mid:
                alert, ns = live_exit.evaluate(pos, mid, exits_state.get(occ))
                new_exits[occ] = ns
                pct = ns.get("last_pct")
                print(f"  {ticker} {pos.get('side')} ${pos.get('strike')}: mid ${mid:.2f} ({pct:+.0f}%) "
                      f"armed {ns.get('armed')}")
                if alert:
                    send_telegram(alert)
                    total_alerts += 1
                    print(f"    -> EXIT ALERT: {alert.splitlines()[0]}")
            elif occ:
                new_exits[occ] = exits_state.get(occ) or {}
                print(f"  {ticker}: no live mid (market closed or contract not found)")

            r_alerts, r_state = check_regime(uw, pos, regimes_state.get(ticker) or {})
            if r_state:
                new_regimes[ticker] = r_state
            for a in r_alerts:
                send_telegram(a)
                total_alerts += 1
                print(f"    -> REGIME ALERT: {a.splitlines()[0]}")
        except Exception as e:
            print(f"  {ticker} failed: {type(e).__name__}: {e}")

    save_state({
        "exits": new_exits,
        "regimes": new_regimes,
        "last_run": datetime.now(timezone.utc).isoformat(),
    })
    print(f"Done. {total_alerts} alerts. UW calls: {uw.calls_made}")


if __name__ == "__main__":
    main()
