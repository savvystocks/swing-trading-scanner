"""School 1c - the FILL LEDGER: microstructure truth for every executed trade, BOTH ends.

Observational and fail-open like the harvest logger: every hook is wrapped so a ledger crash can
never alter or block the trade path (asserted by the passivity suite). Events append to
data/harvest_inbox/fills_YYYYMMDD.jsonl (committed by the engine's normal inbox push); the VPS
poller ingests them into the `fills` table, idempotent on event_id.

Event kinds:
  entry_submit        order placed: signal-time quote (bid/ask/mid/spread), limit, qty, type, tif
  entry_fill          terminal entry-order state: fill price/qty/at, signal-to-fill delay,
                      fill-vs-mid and fill-vs-limit slippage; partial/expired/cancelled recorded
                      as events, never discarded
  exit_submit         a cron close order left the building (close/scale/flush), decision context
  exit_fill           terminal exit-order state (same fields as entry_fill)
  exit_fill_backstop  a broker stop filled: stop price vs actual fill = the gap-through measurement

HEADER NOTE (permanent): paper fills are optimistic. Every paper-era number in this ledger is a
FLOOR on real costs, not an estimate of them.
"""
import os
import json
import uuid
from datetime import datetime, timezone

INBOX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "harvest_inbox")

_PENDING_CLOSE_ORDERS = []          # stashed by sandbox_proactive_lab._close_position (response body)


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def log_event(kind, **fields):
    """Append one ledger event. Absolutely fail-open: any error is swallowed."""
    try:
        os.makedirs(INBOX_DIR, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = os.path.join(INBOX_DIR, f"fills_{stamp}.jsonl")
        evt = {"event_id": uuid.uuid4().hex, "kind": kind, "ts_utc": _now_ms(), **fields}
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(evt, default=str) + "\n")
        return True
    except Exception:
        return False


def stash_close_order(occ, resp):
    """Called by _close_position with the parsed DELETE /positions response (the close order)."""
    try:
        _PENDING_CLOSE_ORDERS.append({"occ": occ, "order_id": (resp or {}).get("id"),
                                      "qty": (resp or {}).get("qty"), "at": _now_iso()})
    except Exception:
        pass


def entry_submits(record):
    """Emit entry_submit per submitted leg of a freshly entered record (signal-time quote attached)."""
    try:
        if not record:
            return
        orders = record.get("orders") or {}
        legs = record.get("legs") or {}
        for name, o in orders.items():
            if not o.get("submitted") or not o.get("order_id"):
                continue
            leg = legs.get(name) or {}
            ec = leg.get("execution_cost") or {}
            log_event("entry_submit", ticker=record.get("ticker"), occ=leg.get("occ_symbol"),
                      order_id=o.get("order_id"), ordered_qty=leg.get("contracts"),
                      limit_price=leg.get("limit_price"), order_type="limit", tif="day",
                      quote_bid=ec.get("bid"), quote_ask=ec.get("ask"), quote_mid=ec.get("mid"),
                      quote_spread_pct=ec.get("bid_ask_spread_pct"),
                      submit_status=o.get("status"), entry_ts_utc=record.get("entry_ts_utc"))
    except Exception:
        pass


def sweep(log_list, order_state_fn, creds, save_fn):
    """Per-cycle passive sweep: (a) drain stashed close orders into exit_submit events and remember
    their ids on the record; (b) poll unresolved entry/exit order ids to terminal state and emit
    entry_fill / exit_fill with delay + slippage. Bookkeeping marks live on the record so each
    terminal state is emitted exactly once."""
    try:
        dirty = False
        while _PENDING_CLOSE_ORDERS:
            st = _PENDING_CLOSE_ORDERS.pop()
            occ = (st.get("occ") or "").upper()
            for rec in log_list:
                legs = rec.get("legs") or {}
                if any((l.get("occ_symbol") or "").upper() == occ for l in legs.values()):
                    rec.setdefault("exit_order_ids", [])
                    if st.get("order_id") and st["order_id"] not in [e.get("order_id") for e in rec["exit_order_ids"]]:
                        rec["exit_order_ids"].append({"order_id": st["order_id"], "at": st.get("at"),
                                                      "ledger_terminal": None})
                        log_event("exit_submit", ticker=rec.get("ticker"), occ=occ,
                                  order_id=st.get("order_id"), qty=st.get("qty"), order_type="market")
                        dirty = True
                    break
        horizon = _now_ms() - 3 * 24 * 3600 * 1000
        for rec in log_list:
            if not isinstance(rec.get("legs"), dict):
                continue
            ets = rec.get("entry_ts_utc") or ""
            for name, o in (rec.get("orders") or {}).items():
                if not o.get("order_id") or o.get("ledger_terminal"):
                    continue
                state = order_state_fn(o["order_id"], creds)
                if not state:
                    continue
                status = (state.get("status") or "").lower()
                if status in ("filled", "canceled", "cancelled", "expired", "rejected", "done_for_day"):
                    leg = (rec.get("legs") or {}).get(name) or {}
                    ec = leg.get("execution_cost") or {}
                    fq = _f(state.get("filled_qty"))
                    fp = _f(state.get("filled_avg_price"))
                    delay = _delay_ms(ets, state.get("filled_at"))
                    log_event("entry_fill", ticker=rec.get("ticker"), occ=leg.get("occ_symbol"),
                              order_id=o["order_id"], terminal_state=status,
                              ordered_qty=leg.get("contracts"), filled_qty=fq,
                              filled_avg_price=fp, filled_at=state.get("filled_at"),
                              signal_to_fill_ms=delay, limit_price=leg.get("limit_price"),
                              quote_mid_at_signal=ec.get("mid"),
                              slip_vs_mid=_slip(fp, ec.get("mid")), slip_vs_limit=_slip(fp, leg.get("limit_price")))
                    o["ledger_terminal"] = status
                    dirty = True
            for e in rec.get("exit_order_ids") or []:
                if e.get("ledger_terminal"):
                    continue
                state = order_state_fn(e["order_id"], creds)
                if not state:
                    continue
                status = (state.get("status") or "").lower()
                if status in ("filled", "canceled", "cancelled", "expired", "rejected", "done_for_day"):
                    fq = _f(state.get("filled_qty"))
                    fp = _f(state.get("filled_avg_price"))
                    log_event("exit_fill", ticker=rec.get("ticker"),
                              occ=next((l.get("occ_symbol") for l in (rec.get("legs") or {}).values()), None),
                              order_id=e["order_id"], terminal_state=status, filled_qty=fq,
                              filled_avg_price=fp, filled_at=state.get("filled_at"),
                              submit_to_fill_ms=_delay_ms(e.get("at"), state.get("filled_at")))
                    e["ledger_terminal"] = status
                    dirty = True
            if rec.get("status") in ("CLOSED", "FLUSHED") and _rec_ts_ms(ets) < horizon:
                continue
        if dirty and save_fn:
            save_fn(log_list)
        return dirty
    except Exception:
        return False


def backstop_fill_event(rec, occ, stop_price, fill_price, fill_qty, fill_at, entry_px):
    """Called from _capture_backstop_fill: the gap-through measurement on stop fills."""
    try:
        gap = None
        if stop_price and fill_price:
            gap = round((float(fill_price) - float(stop_price)) / float(stop_price) * 100.0, 2)
        log_event("exit_fill_backstop", ticker=rec.get("ticker"), occ=occ, stop_price=stop_price,
                  filled_avg_price=fill_price, filled_qty=fill_qty, filled_at=fill_at,
                  entry_px=entry_px, gap_through_pct=gap)
    except Exception:
        pass


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _rec_ts_ms(iso):
    try:
        return int(datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return 0


def _delay_ms(start_iso, end_iso):
    a, b = _rec_ts_ms(start_iso), _rec_ts_ms(end_iso)
    return (b - a) if (a and b) else None


def _slip(fill, ref):
    f, r = _f(fill), _f(ref)
    if f is None or r is None or r == 0:
        return None
    return round((f - r) / r * 100.0, 3)
