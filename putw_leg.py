"""PUT-WRITE LEG (green-day premium leg, owner-ordered build 2026-08-10).

Validated on 2.1y of real XSP quotes: weekly 2%-OTM put-write, green-conditional,
+$2,103/67wk at 88% win (ALL-weeks +$2,710). Mechanics: once per week (first green trading
day), SELL 1 XSP put ~2% OTM expiring Friday; hold to expiry (European, cash-settled - no
assignment, no management); a settlement sweep books the P&L after expiry. Gated by
fade_book_spec.json "putw" block AND fade_book.active() (so FORCE_OFF test harnesses and the
OFF-state keep the engine byte-identical). Fail-open everywhere: this leg can never block or
crash the fade path.
"""
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone

import fade_book

_REPO = os.path.dirname(os.path.abspath(__file__))


def _cfg():
    return (fade_book.spec().get("putw") or {}) if fade_book.active() else {}


def _log_load():
    import sandbox_proactive_lab as lab
    return lab._load_log_list()


def _next_friday(today):
    d = today + timedelta(days=(4 - today.weekday()) % 7)
    return d if d > today else d + timedelta(days=7)


def _xsp_close_series():
    import yfinance as yf
    s = yf.download("^XSP", period="10d", progress=False, auto_adjust=True)["Close"].dropna()
    return s.iloc[:, 0] if hasattr(s, "columns") else s


def _quote(occ, creds):
    req = urllib.request.Request(
        f"https://data.alpaca.markets/v1beta1/options/quotes/latest?symbols={occ}&feed=indicative",
        headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1]})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            q = json.loads(r.read()).get("quotes", {}).get(occ) or {}
            return q.get("bp"), q.get("ap")
    except Exception:
        return None, None


def _sell_put(occ, limit, creds, qty=1):
    body = json.dumps({"symbol": occ, "qty": str(qty), "side": "sell", "type": "limit",
                       "limit_price": str(round(limit, 2)), "time_in_force": "day"}).encode()
    req = urllib.request.Request("https://paper-api.alpaca.markets/v2/orders", data=body,
                                 headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1],
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  putw: order failed {type(e).__name__}: {str(e)[:80]}")
        return None


def weekly_cycle(creds):
    """Called once per engine cycle, fail-open. Settles expired PUTW records; enters weekly."""
    cfg = _cfg()
    if not cfg.get("enabled") or not creds or not all(creds):
        return
    import sandbox_proactive_lab as lab
    log = lab._load_log_list()
    now = datetime.now(timezone.utc)
    today = now.date()
    dirty = False
    open_putw = None
    for r in log:
        if r.get("book") != "PUTW":
            continue
        if r.get("status") == "OPEN":
            exp = date.fromisoformat(r["expiry"])
            if today > exp:
                try:                                   # SETTLE: intrinsic vs XSP close on expiry
                    s = _xsp_close_series()
                    sd = [d for d in s.index.date if d <= exp]
                    settle = float(s[s.index.date == sd[-1]].iloc[-1]) if sd else None
                except Exception:
                    settle = None
                if settle is not None:
                    intrinsic = max(r["strike"] - settle, 0.0)
                    pnl = (r["premium"] - intrinsic) * 100 * (r.get("contracts") or 1)
                    r["status"] = "CLOSED"
                    r["settle"] = {"xsp": settle, "intrinsic": round(intrinsic, 2),
                                   "pnl_usd": round(pnl, 2), "at": now.isoformat()}
                    dirty = True
                    print(f"  putw SETTLED {r['occ']}: ${pnl:+.0f}")
                    try:
                        lab._notify(f"<b>PUTW settled</b> {r['occ']}: ${pnl:+.0f}")
                    except Exception:
                        pass
            else:
                open_putw = r
    if dirty:
        lab._save_log_list(log)
    if open_putw is not None:
        return                                          # one position at a time, hold to expiry
    # ENTRY: once weekly, first cycle at/after 15:00 UTC, green gate (prior week up)
    if now.hour < 15:
        return
    already = any(r.get("book") == "PUTW" and (r.get("entry_ts_utc") or "") >=
                  (today - timedelta(days=today.weekday())).isoformat() for r in log)
    if already:
        return                                          # one entry per calendar week
    try:
        s = _xsp_close_series()
        if cfg.get("green_gate", True) and not (len(s) >= 5 and float(s.iloc[-1]) > float(s.iloc[-5])):
            return                                      # prior week not green -> stand down
        spot = float(s.iloc[-1])
    except Exception:
        return
    strike = round(spot * (1 - cfg.get("otm_pct", 2.0) / 100))
    expiry = _next_friday(today)
    occ = f"XSP{expiry.strftime('%y%m%d')}P{int(strike * 1000):08d}"
    bid, ask = _quote(occ, creds)
    if not bid or bid <= 0.05:
        print(f"  putw: no usable bid for {occ} - skip this cycle")
        return
    _q = int(cfg.get("contracts", 1))
    resp = _sell_put(occ, bid, creds, qty=_q)
    if resp and resp.get("id"):
        log.append({"book": "PUTW", "contracts": _q,
                    "trade_set_id": "putw" + resp["id"][:8], "ticker": "XSP",
                    "occ": occ, "strike": strike, "expiry": expiry.isoformat(),
                    "premium": bid, "order_id": resp["id"], "status": "OPEN",
                    "entry_ts_utc": now.isoformat(), "note": "green-day put-write leg v1"})
        lab._save_log_list(log)
        print(f"  putw ENTERED: sold {occ} @ {bid} (green gate passed)")
        try:
            lab._notify(f"<b>PUTW ENTERED</b> sold {occ} @ ${bid} exp {expiry} (green-day leg)")
        except Exception:
            pass
