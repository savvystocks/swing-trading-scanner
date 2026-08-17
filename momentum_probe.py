"""MOMENTUM_ROT probe (owner order 2026-08-17 22:39: momentum rotation, fast-tracked).

Cross-sectional momentum - the most-documented equity anomaly in the academic record.
Honest corpus test (98-name objective mega-cap universe, no hot-hand picking, 23 months):
top-5 by 3-month return, monthly rebalance = +49.5% vs SPY +40.6%; with a 200d trend gate
+55.3%. Live variant: TOP-5, TREND-GATED, $1k/name shares lots, rebalanced monthly (first
cycle of a new month at/after 15:00 UTC; the FIRST run rebalances immediately - fast track).
Gate fails (SPY < 200d SMA) -> exit all, sit cash. Records are shares-style (book=PROBE,
no legs dict); month-long holds can never day-trade. Fail-open everywhere.
"""
import json
import urllib.request
from datetime import datetime, timezone

import fade_book

UNIVERSE = ("AAPL MSFT GOOGL AMZN NVDA META TSLA JPM V UNH XOM JNJ WMT MA PG HD CVX ABBV MRK "
            "LLY PEP KO AVGO COST TMO MCD CSCO ACN ABT CRM DHR ADBE TXN NEE VZ CMCSA INTC WFC "
            "PM NKE RTX ORCL UPS HON QCOM LOW AMGN IBM BA CAT GE SBUX PFE T MS AXP DE BLK GS "
            "SPGI ISRG MDT GILD LMT BKNG ADI SYK TJX MMC VRTX AMD PLD C SCHW CB MO ZTS SO CI "
            "DUK BDX ETN USB EOG NOC ITW HUM WM FDX AON PNC EMR APD CL GM F COP KMB").split()


def _cfg():
    return ((fade_book.spec().get("probe") or {}).get("momentum") or {}) if fade_book.active() else {}


def _bars(syms, creds, start):
    out = {}
    for i in range(0, len(syms), 20):
        url = ("https://data.alpaca.markets/v2/stocks/bars?symbols=" + ",".join(syms[i:i + 20]) +
               f"&timeframe=1Day&start={start}&limit=10000&adjustment=split&feed=iex")
        page = None
        try:
            while True:
                u = url + ("&page_token=" + page if page else "")
                req = urllib.request.Request(u, headers={"APCA-API-KEY-ID": creds[0],
                                                         "APCA-API-SECRET-KEY": creds[1]})
                with urllib.request.urlopen(req, timeout=30) as r:
                    j = json.loads(r.read())
                for t, bl in (j.get("bars") or {}).items():
                    out.setdefault(t, []).extend(b["c"] for b in bl)
                page = j.get("next_page_token")
                if not page:
                    break
        except Exception:
            continue
    return out


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
        print(f"  momentum: {side} {sym} failed {type(e).__name__}: {str(e)[:60]}")
        return None


def cycle(creds, allow_entries=True):
    cfg = _cfg()
    if not cfg.get("enabled") or not creds or not all(creds):
        return
    import sandbox_proactive_lab as lab
    now = datetime.now(timezone.utc)
    if now.hour < 15:
        return
    log = lab._load_log_list()
    holds = [r for r in log if r.get("probe_strategy") == "MOMENTUM_ROT" and r.get("status") == "OPEN"]
    last_reb = max((r.get("entry_ts_utc") or "")[:7] for r in holds) if holds else ""
    if holds and last_reb == now.isoformat()[:7]:
        return                                          # this month's rebalance is done
    if not allow_entries:
        return
    size = float(cfg.get("size_usd", 1000))
    topn = int(cfg.get("top_n", 5))
    look = int(cfg.get("lookback_days", 63))
    bars = _bars(UNIVERSE + ["SPY"], creds, "2025-08-01")
    spy = bars.get("SPY") or []
    if len(spy) < 200:
        return
    gate_ok = spy[-1] >= sum(spy[-200:]) / 200
    rets = {t: b[-1] / b[-look] - 1 for t, b in bars.items()
            if t != "SPY" and len(b) > look and b[-look] > 0}
    top = sorted(rets, key=rets.get, reverse=True)[:topn] if (gate_ok and len(rets) >= 50) else []
    dirty = False
    for r in holds:                                     # exit anything not in the new top set
        sym = r["shares"]["symbol"]
        if sym in top:
            top.remove(sym)                             # keep the winner riding
            continue
        px = (bars.get(sym) or [None])[-1]
        resp = _order(sym, r["shares"]["qty"], "sell", creds)
        if resp and resp.get("id"):
            pnl = round((px - r["shares"]["entry_price"]) * r["shares"]["qty"], 2) if px else None
            r["status"] = "CLOSED"
            r["exit"] = {"ts": now.isoformat(), "price": px, "order_id": resp["id"], "pnl_usd": pnl}
            dirty = True
            print(f"  PROBE[MOMENTUM_ROT] rotated OUT {sym}: {'$%+.2f' % pnl if pnl is not None else ''}")
    for sym in top:                                     # enter the new names
        px = (bars.get(sym) or [None])[-1]
        if not px:
            continue
        qty = max(1, int(size // px))
        resp = _order(sym, qty, "buy", creds)
        if resp and resp.get("id"):
            log.append({"book": "PROBE", "probe_strategy": "MOMENTUM_ROT",
                        "trade_set_id": "mom" + resp["id"][:9], "ticker": sym,
                        "shares": {"symbol": sym, "qty": qty, "entry_price": px},
                        "order_id": resp["id"], "status": "OPEN",
                        "entry_ts_utc": now.isoformat(),
                        "note": "top-5 3mo momentum, 200d trend gate, monthly rebalance"})
            dirty = True
            print(f"  PROBE[MOMENTUM_ROT] rotated IN {qty} {sym} @ ~{px}")
    if dirty:
        lab._save_log_list(log)
        try:
            lab._notify(f"<b>PROBE MOMENTUM_ROT</b> monthly rebalance done ({'gate OPEN' if gate_ok else 'gate CLOSED - cash'})")
        except Exception:
            pass
