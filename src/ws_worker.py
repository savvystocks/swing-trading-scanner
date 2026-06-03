"""UW WebSocket worker - real-time flow alerts -> Telegram.

Long-running daemon that:
  1. Connects to wss://api.unusualwhales.com/socket
  2. Subscribes to flow-alerts + news + trading_halts channels
  3. Filters incoming events by configurable thresholds
  4. Fires Telegram alerts for whale-tier events (>= $1M premium)
  5. Auto-reconnects on disconnect

Deploy on Vultr via systemd. See deploy/README.md.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone
from collections import deque

try:
    import websocket
except ImportError:
    print("Install: pip install websocket-client")
    sys.exit(1)


# Configuration (override via env vars on Vultr)
TOKEN = os.environ.get("UNUSUAL_WHALES_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

WS_URL = "wss://api.unusualwhales.com/socket"

# Thresholds - tune these to control alert volume
WHALE_PREMIUM_MIN = float(os.environ.get("WHALE_PREMIUM_MIN", "1000000"))   # $1M
ALERT_DEDUPE_SECONDS = int(os.environ.get("ALERT_DEDUPE_SECONDS", "300"))  # 5 min

# ETF blacklist - same as scanner
ETF_BLACKLIST = {
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "IVV", "SPLG", "VEA", "VWO",
    "XLE", "XLF", "XLK", "XLV", "XLP", "XLB", "XLY", "XLI", "XLU", "XLRE", "XLC",
    "TQQQ", "SQQQ", "SOXL", "SOXS", "SPXL", "SPXS", "UPRO", "SPXU",
    "FAS", "FAZ", "TNA", "TZA", "LABU", "LABD", "NUGT", "JNUG", "DUST", "JDST",
    "UVXY", "VXX", "SVXY", "VIXY", "URTY", "SRTY", "TECL", "TECS", "FNGU", "FNGD",
    "TLT", "IEF", "SHY", "LQD", "HYG", "AGG", "BND", "TBT", "TMF",
    "GLD", "SLV", "USO", "UNG", "GDX", "GDXJ", "GLDM", "IAU",
    "EWZ", "FXI", "INDA", "MCHI", "EWJ", "GBTC", "ETHE", "BITO", "BITX", "IBIT",
    "ARKK", "ARKG", "ARKW", "ARKQ", "ARKF",
    "SCHD", "DGRO", "VYM", "VIG", "JEPI", "JEPQ",
    "TSLL", "TSDD", "NVDL", "NVDS", "MSFU", "AAPU", "AAPD",
}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("ws_worker")


# Recent alerts cache (avoid spamming on same ticker repeatedly)
recent_alerts = deque(maxlen=500)


def _is_recently_alerted(key):
    now = time.time()
    for ts, k in list(recent_alerts):
        if now - ts > ALERT_DEDUPE_SECONDS:
            continue
        if k == key:
            return True
    recent_alerts.append((now, key))
    return False


def send_telegram(text):
    """Fire a Telegram message via Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured - skipping alert")
        return
    try:
        import urllib.request
        import urllib.parse
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status != 200:
                log.warning(f"Telegram HTTP {r.status}")
    except Exception as e:
        log.error(f"Telegram failed: {type(e).__name__}: {e}")


def handle_flow_alert(payload):
    """Filter and format a flow-alert event."""
    if not isinstance(payload, dict):
        return

    ticker = payload.get("ticker") or payload.get("underlying_symbol")
    if not ticker or ticker in ETF_BLACKLIST:
        return

    premium = 0
    for k in ("total_premium", "premium"):
        v = payload.get(k)
        if v is None:
            continue
        try:
            premium = max(premium, float(v))
            break
        except (TypeError, ValueError):
            pass

    if premium < WHALE_PREMIUM_MIN:
        return

    side = (payload.get("type") or payload.get("option_type") or "").upper()
    if "CALL" in side:
        side = "CALL"
    elif "PUT" in side:
        side = "PUT"
    else:
        side = "?"

    strike = payload.get("strike", "?")
    expiry = payload.get("expiry", "?")
    volume = payload.get("volume", "?")
    oi = payload.get("open_interest", "?")
    has_sweep = payload.get("has_sweep")
    has_floor = payload.get("has_floor")

    flags = []
    if has_sweep:
        flags.append("SWEEP")
    if has_floor:
        flags.append("FLOOR")

    # Dedupe key
    key = f"{ticker}|{side}|{strike}|{expiry}"
    if _is_recently_alerted(key):
        return

    flag_str = " " + "+".join(flags) if flags else ""
    msg = (
        f"<b>WHALE FLOW: {ticker} {side}</b>{flag_str}\n"
        f"${premium/1e6:.1f}M premium · ${strike} strike · exp {expiry}\n"
        f"vol {volume} / OI {oi}"
    )
    send_telegram(msg)
    log.info(f"alerted: {ticker} {side} ${premium/1e6:.1f}M")


def handle_news(payload):
    """News items - only fire on high-impact catalysts."""
    if not isinstance(payload, dict):
        return
    headline = payload.get("headline") or payload.get("title") or ""
    tickers = payload.get("tickers") or payload.get("symbols") or []
    if isinstance(tickers, str):
        tickers = [tickers]
    # Only stocks not ETFs
    tickers = [t for t in tickers if t and t not in ETF_BLACKLIST]
    if not tickers:
        return
    # Catalyst keywords
    high_impact = any(kw in headline.lower() for kw in (
        "earnings", "guidance", "fda", "approval", "downgrade", "upgrade",
        "acquisition", "merger", "lawsuit", "investigation", "halt", "delisted",
        "ceo", "resign", "fired", "fraud", "beat", "miss",
    ))
    if not high_impact:
        return
    key = f"news|{tickers[0]}|{headline[:50]}"
    if _is_recently_alerted(key):
        return
    msg = f"<b>NEWS: {','.join(tickers[:3])}</b>\n{headline[:200]}"
    send_telegram(msg)
    log.info(f"news alert: {tickers[0]}: {headline[:60]}")


def handle_trading_halt(payload):
    """Trading halts/resumes - always fire (risk event)."""
    if not isinstance(payload, dict):
        return
    ticker = payload.get("ticker") or payload.get("symbol")
    status = payload.get("status") or payload.get("event_type") or "?"
    reason = payload.get("reason", "")
    if not ticker:
        return
    msg = f"<b>TRADING HALT: {ticker}</b>\n{status} {reason}"
    send_telegram(msg)
    log.warning(f"halt: {ticker} {status} {reason}")


# Channel router
CHANNEL_HANDLERS = {
    "flow-alerts": handle_flow_alert,
    "news": handle_news,
    "trading_halts": handle_trading_halt,
}


def on_message(ws, raw):
    try:
        msg = json.loads(raw)
    except Exception as e:
        log.warning(f"non-JSON: {raw[:100]}")
        return
    if not isinstance(msg, list) or len(msg) < 2:
        return
    channel, payload = msg[0], msg[1]
    # Skip subscribe ack messages
    if isinstance(payload, dict) and payload.get("status") == "ok":
        log.info(f"joined channel: {channel}")
        return
    handler = CHANNEL_HANDLERS.get(channel)
    if handler:
        try:
            handler(payload)
        except Exception as e:
            log.error(f"handler {channel} failed: {type(e).__name__}: {e}")


def on_error(ws, error):
    log.error(f"WS error: {error}")


def on_close(ws, code, reason):
    log.warning(f"WS closed: code={code} reason={reason}")


def on_open(ws):
    log.info("WS open - subscribing to channels")
    for ch in ("flow-alerts", "news", "trading_halts"):
        ws.send(json.dumps({"channel": ch, "msg_type": "join"}))


def run_forever():
    """Run with auto-reconnect."""
    if not TOKEN:
        log.error("UNUSUAL_WHALES_TOKEN not set - exiting")
        sys.exit(1)
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured - alerts will be logged only")

    send_telegram(f"<b>WS worker started</b>  whale threshold: ${WHALE_PREMIUM_MIN/1e6:.1f}M")

    backoff = 1
    while True:
        try:
            url = f"{WS_URL}?token={TOKEN}"
            ws = websocket.WebSocketApp(
                url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            ws.run_forever(ping_interval=30, ping_timeout=10)
            backoff = 1  # reset after successful connection
        except Exception as e:
            log.error(f"connection failed: {type(e).__name__}: {e}")

        # Reconnect with backoff (max 60s)
        sleep_for = min(backoff, 60)
        log.info(f"reconnecting in {sleep_for}s")
        time.sleep(sleep_for)
        backoff = min(backoff * 2, 60)


if __name__ == "__main__":
    run_forever()
