"""SHARES PROBES - OVERNIGHT + TURN_OF_MONTH (owner order 2026-08-11 21:52: every feasible
tested strategy trades live in the probe section).

Sim evidence (SPY daily history, 12-strategy sweep 2026-08-11): the overnight close->open hold
earned ~+6.3%/yr with the day session flat; turn-of-month (last sessions of the month through
the 3rd) compounded +378% vs +99% buy-and-hold long-run. Both are shares strategies - simple,
liquid, penny-spread - so they run as $1k whole-share live probes: OVERNIGHT buys SPY on the
session's last cycles (>=19:40 UTC) and sells on the first cycle next morning; TURN_OF_MONTH
buys on/after the 25th and sells on/after the 4th. Records are self-contained (book=PROBE,
"shares" block, no legs dict -> the options exit engine ignores them; the reconciler knows
their symbol). Fail-open everywhere: this module can never block or crash the fade path.
"""
import json
import urllib.request
from datetime import datetime, timezone

import fade_book


def _cfg():
    return ((fade_book.spec().get("probe") or {}).get("shares") or {}) if fade_book.active() else {}


def _mins_to_close(creds):
    """Minutes until today's close from the Alpaca clock (DST- and half-day-proof). None on failure."""
    req = urllib.request.Request("https://paper-api.alpaca.markets/v2/clock",
                                 headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1]})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            c = json.loads(r.read())
            if not c.get("is_open"):
                return None
            nc = datetime.fromisoformat(c["next_close"])
            return (nc - datetime.now(timezone.utc)).total_seconds() / 60.0
    except Exception:
        return None


def _price(sym, creds):
    req = urllib.request.Request(
        f"https://data.alpaca.markets/v2/stocks/{sym}/trades/latest",
        headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1]})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return float((json.loads(r.read()).get("trade") or {}).get("p") or 0) or None
    except Exception:
        return None


def _order(sym, qty, side, creds):
    body = json.dumps({"symbol": sym, "qty": str(qty), "side": side, "type": "market",
                       "time_in_force": "day"}).encode()
    req = urllib.request.Request("https://paper-api.alpaca.markets/v2/orders", data=body,
                                 headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1],
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  shares probe: {side} failed {type(e).__name__}: {str(e)[:80]}")
        return None


def _close(r, creds, lab, now):
    sym = r["shares"]["symbol"]
    px = _price(sym, creds)
    resp = _order(sym, r["shares"]["qty"], "sell", creds)
    if resp and resp.get("id"):
        pnl = round((px - r["shares"]["entry_price"]) * r["shares"]["qty"], 2) if px else None
        r["status"] = "CLOSED"
        r["exit"] = {"ts": now.isoformat(), "price": px, "order_id": resp["id"], "pnl_usd": pnl}
        txt = f"${pnl:+.2f}" if pnl is not None else "pnl pending"
        print(f"  PROBE[{r['probe_strategy']}] closed {sym}: {txt}")
        try:
            lab._notify(f"<b>PROBE {r['probe_strategy']} closed</b> {sym} {txt}")
        except Exception:
            pass
        return True
    return False


def _held_qty(sym, creds):
    """Broker-side truth: current equity qty for sym (0 if none). The idempotency guard for
    entries - a record lost to a push race must never cause a second buy (2026-08-12: the
    first OVERNIGHT night bought twice exactly this way)."""
    req = urllib.request.Request(f"https://paper-api.alpaca.markets/v2/positions/{sym}",
                                 headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1]})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return abs(int(float(json.loads(r.read()).get("qty") or 0)))
    except Exception:
        return 0


def cycle(creds, allow_entries=True):
    """Called each engine cycle (market already confirmed open upstream). Fail-open.
    allow_entries=False (owner HALT / active brake) still runs exits - never entries."""
    cfg = _cfg()
    if not cfg.get("enabled") or not creds or not all(creds):
        return
    import sandbox_proactive_lab as lab
    sym = cfg.get("symbol", "SPY")
    size = float(cfg.get("size_usd", 1000))
    now = datetime.now(timezone.utc)
    today = now.date()
    log = lab._load_log_list()
    dirty = False
    open_ov = open_tom = None
    ov_entered_today = tom_this_month = False
    for r in log:
        if r.get("book") != "PROBE" or not r.get("shares"):
            continue
        ts = r.get("entry_ts_utc") or ""
        if r.get("probe_strategy") == "OVERNIGHT" and ts[:10] == now.isoformat()[:10]:
            ov_entered_today = True
        if r.get("probe_strategy") == "TURN_OF_MONTH" and ts[:7] == now.isoformat()[:7]:
            tom_this_month = True
        if r.get("status") != "OPEN":
            continue
        if r.get("probe_strategy") == "OVERNIGHT":
            open_ov = r
        elif r.get("probe_strategy") == "TURN_OF_MONTH":
            open_tom = r
    if open_ov is not None and (open_ov.get("entry_ts_utc") or "")[:10] < now.isoformat()[:10]:
        dirty = _close(open_ov, creds, lab, now) or dirty          # morning side of the overnight
    if open_tom is not None and 4 <= today.day <= 24:
        dirty = _close(open_tom, creds, lab, now) or dirty         # past the turn-of-month window

    def _enter(strategy):
        px = _price(sym, creds)
        if not px:
            return False
        qty = max(1, int(size // px))
        resp = _order(sym, qty, "buy", creds)
        if resp and resp.get("id"):
            log.append({"book": "PROBE", "probe_strategy": strategy,
                        "trade_set_id": "shp" + resp["id"][:9], "ticker": sym,
                        "shares": {"symbol": sym, "qty": qty, "entry_price": px},
                        "order_id": resp["id"], "status": "OPEN",
                        "entry_ts_utc": now.isoformat(),
                        "note": "shares probe (tested strategy, live experiment)"})
            print(f"  PROBE[{strategy}] bought {qty} {sym} @ ~{px}")
            try:
                lab._notify(f"<b>PROBE {strategy}</b> bought {qty} {sym} @ ~${px}")
            except Exception:
                pass
            return True
        return False

    open_qty = sum((r.get("shares") or {}).get("qty") or 0 for r in log
                   if r.get("status") == "OPEN" and (r.get("shares") or {}).get("symbol") == sym)
    if allow_entries and _held_qty(sym, creds) > open_qty:
        allow_entries = False
        print(f"  shares probe: broker holds more {sym} than OPEN records claim - entry guard on")
    if allow_entries and open_ov is None and not ov_entered_today:
        mtc = _mins_to_close(creds)
        if mtc is not None and mtc <= 25:          # the session's last ~2 cycles, whatever the close
            dirty = _enter("OVERNIGHT") or dirty   # (clock-derived: DST shifts and half-days included)
    if allow_entries and open_tom is None and today.day >= 25 and not tom_this_month:
        dirty = _enter("TURN_OF_MONTH") or dirty
    if dirty:
        lab._save_log_list(log)
