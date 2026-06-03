"""Position monitor - polls UW REST every 10 min for active positions.

Reads data/positions.json, checks each position's underlying for:
  - Dealer regime flip (POSITIVE_PIN <-> NEGATIVE_AMP)
  - Spot crossing the zero-gamma flip strike

Fires Telegram alert on change. Saves state to data/position_monitor_state.json
so we only alert on transitions, not every poll.

REST-polled fallback for the WebSocket worker (which required UW Advanced
plan $375/mo).
"""

import os
import sys
import json
import pathlib
from datetime import datetime, timezone


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.positions import load_positions
from src.unusual_whales_api import get_client
from src.catalyst.uw_enrichment import _summarize_gex


STATE_PATH = pathlib.Path(__file__).parent.parent / "data" / "position_monitor_state.json"


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


def check_position(uw, pos, state):
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

    prev = state.get(ticker) or {}
    prev_regime = prev.get("dealer_regime")
    prev_spot = prev.get("spot")
    prev_flip = prev.get("flip_strike")

    if regime and prev_regime and regime != prev_regime:
        bad_for_calls = regime == "NEGATIVE_AMP"
        bad_for_puts = regime == "POSITIVE_PIN"
        warn = (side == "CALL" and bad_for_calls) or (side == "PUT" and bad_for_puts)
        severity = "WARN" if warn else "INFO"
        alerts.append(
            f"<b>POSITION ALERT [{severity}]: {ticker} {side} ${strike}</b>\n"
            f"Dealer regime: {prev_regime} -> {regime}\n"
            f"{'Watch for accelerated move against you' if warn else 'Move may decelerate'}"
        )

    if (spot and prev_spot and flip is not None and prev_flip is not None
            and (prev_spot >= prev_flip) != (spot >= flip)):
        alerts.append(
            f"<b>POSITION ALERT: {ticker} {side} ${strike}</b>\n"
            f"Spot ${spot:.2f} crossed gamma flip strike ${flip:.2f}\n"
            f"Hedging regime change - reassess"
        )

    new_state = {
        "dealer_regime": regime,
        "flip_strike": flip,
        "spot": spot,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }
    return alerts, new_state


def main():
    positions = load_positions()
    if not positions:
        print("No active positions")
        return

    print(f"Monitoring {len(positions)} positions: {', '.join(p['ticker'] for p in positions)}")

    uw = get_client()
    if not uw.enabled:
        print("UNUSUAL_WHALES_TOKEN missing")
        sys.exit(1)

    state = load_state()
    new_state = {}
    total_alerts = 0

    for pos in positions:
        try:
            alerts, ns = check_position(uw, pos, state)
            if ns:
                new_state[pos["ticker"]] = ns
            for alert in alerts:
                send_telegram(alert)
                total_alerts += 1
                print(f"  alerted: {alert.splitlines()[0]}")
        except Exception as e:
            print(f"  {pos['ticker']} failed: {type(e).__name__}: {e}")

    save_state(new_state)
    print(f"Done. {total_alerts} alerts. UW calls: {uw.calls_made}")


if __name__ == "__main__":
    main()
