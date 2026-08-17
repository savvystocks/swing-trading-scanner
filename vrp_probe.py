"""VRP_DAILY probe (owner order 2026-08-14 22:53: spec the upstream-signal probe for Monday).

The volatility-risk-premium leg at daily cadence: sell 1 XSP put ~2.5% OTM expiring ~2
trading days out, hold to European cash settlement (no sell order ever exists -> can never
be a day trade). Signal origin is STRUCTURAL - implied vol persistently overprices realized
vol - so nobody has to act before us; this is the top row of the signal-origin table trading
daily. Discovery mode: no entry conditions beyond a usable bid; the harvest of daily fills
tells us later WHICH days deserve the trade (VIX level, term structure), and conditions get
added through the virgin-day machinery, never by hand. Records mirror PUTW (bare occ, no
legs dict -> options exit engine ignores them; reconciler knows bare-occ records). Caps:
1 entry/day, max 3 open (laddered expiries). Tail stated: a -10% crash day costs roughly
$4-5k per open contract on paper - accepted for data at this account size.
"""
import json
import urllib.request
from datetime import date, datetime, timedelta, timezone

import fade_book


def _cfg():
    return ((fade_book.spec().get("probe") or {}).get("vrp") or {}) if fade_book.active() else {}


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


def _sell(occ, limit, creds, qty=1):
    body = json.dumps({"symbol": occ, "qty": str(qty), "side": "sell", "type": "limit",
                       "limit_price": str(round(limit, 2)), "time_in_force": "day"}).encode()
    req = urllib.request.Request("https://paper-api.alpaca.markets/v2/orders", data=body,
                                 headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1],
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  vrp: order failed {type(e).__name__}: {str(e)[:80]}")
        return None


def cycle(creds, allow_entries=True):
    """Each engine cycle: settle expired VRP records; enter once daily after 15:00 UTC."""
    cfg = _cfg()
    if not cfg.get("enabled") or not creds or not all(creds):
        return
    import sandbox_proactive_lab as lab
    now = datetime.now(timezone.utc)
    today = now.date()
    log = lab._load_log_list()
    dirty = False
    n_open = 0
    entered_today = False
    for r in log:
        if r.get("probe_strategy") != "VRP_DAILY":
            continue
        if (r.get("entry_ts_utc") or "")[:10] == today.isoformat():
            entered_today = True
        if r.get("status") != "OPEN":
            continue
        exp = date.fromisoformat(r["expiry"])
        if today > exp:
            try:
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
                print(f"  PROBE[VRP_DAILY] settled {r['occ']}: ${pnl:+.0f}")
                try:
                    lab._notify(f"<b>PROBE VRP_DAILY settled</b> {r['occ']}: ${pnl:+.0f}")
                except Exception:
                    pass
            continue
        n_open += 1
    if dirty:
        lab._save_log_list(log)
    if not allow_entries or entered_today or n_open >= int(cfg.get("max_open", 3)) or now.hour < 15:
        return
    try:
        s = _xsp_close_series()
        spot = float(s.iloc[-1])
    except Exception:
        return
    strike = round(spot * (1 - cfg.get("otm_pct", 2.5) / 100))
    for dd in range(int(cfg.get("dte", 2)), int(cfg.get("dte", 2)) + 3):
        exp = today + timedelta(days=dd)
        if exp.weekday() >= 5:
            continue
        occ = f"XSP{exp.strftime('%y%m%d')}P{int(strike * 1000):08d}"
        bid, ask = _quote(occ, creds)
        if bid and bid >= 0.05:
            _q = int(cfg.get("contracts", 1))
            resp = _sell(occ, bid, creds, qty=_q)
            if resp and resp.get("id"):
                log.append({"book": "PROBE", "probe_strategy": "VRP_DAILY", "contracts": _q,
                            "trade_set_id": "vrp" + resp["id"][:9], "ticker": "XSP",
                            "occ": occ, "strike": strike, "expiry": exp.isoformat(),
                            "premium": bid, "order_id": resp["id"], "status": "OPEN",
                            "entry_ts_utc": now.isoformat(),
                            "note": "daily VRP short put (structural premium, discovery mode)"})
                lab._save_log_list(log)
                print(f"  PROBE[VRP_DAILY] sold {occ} @ {bid} (exp {exp})")
                try:
                    lab._notify(f"<b>PROBE VRP_DAILY</b> sold {occ} @ ${bid} exp {exp}")
                except Exception:
                    pass
            return
