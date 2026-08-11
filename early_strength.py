"""EARLY-STRENGTH CONFIRMED ENTRY (owner-ordered build 2026-08-11 21:31).

Sim evidence (real cohort paths, day-clustered): entering fade candidates only after their
option shows +5..15% from signal within the first hour produced +7.0%/day-mean with halves
+22.9/+21.8 - the most stable configuration ever measured here. Mechanic: the fade path
WATCHLISTS qualifying candidates instead of buying; each cycle re-quotes them; confirmed
strength -> enter at the confirmed ask; too old or overshot -> drop. Spec-gated by
entry.confirm_strength; absent = original immediate-entry behavior (OFF-state identical).
"""
import json
import os
import urllib.request
import uuid
from datetime import datetime, timezone

import fade_book

_WL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox_watchlist.json")


def _cfg():
    return (fade_book.spec().get("entry") or {}).get("confirm_strength") or {}


def enabled():
    return bool(_cfg()) and fade_book.active()


def _load():
    try:
        return json.load(open(_WL, encoding="utf-8"))
    except Exception:
        return {}


def _save(d):
    json.dump(d, open(_WL, "w", encoding="utf-8"), indent=1)


def stash(ticker, occ, ref_ask, regime, contracts, alloc):
    d = _load()
    d[occ] = {"ticker": ticker, "occ": occ, "ref": ref_ask, "regime": regime,
              "contracts": contracts, "alloc": alloc,
              "ts": datetime.now(timezone.utc).isoformat()}
    _save(d)
    print(f"  early-strength WATCHLISTED {ticker} {occ} ref ${ref_ask} (awaiting +5..15%)")


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


def _buy(occ, qty, limit, creds):
    body = json.dumps({"symbol": occ, "qty": str(qty), "side": "buy", "type": "limit",
                       "limit_price": str(round(limit, 2)), "time_in_force": "day"}).encode()
    req = urllib.request.Request("https://paper-api.alpaca.markets/v2/orders", data=body,
                                 headers={"APCA-API-KEY-ID": creds[0], "APCA-API-SECRET-KEY": creds[1],
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  early-strength order failed: {type(e).__name__}: {str(e)[:80]}")
        return None


def process(creds, lab):
    """Called each cycle: re-quote watchlist, enter confirmed, expire stale. Fail-open."""
    if not enabled() or not creds or not all(creds):
        return
    cfg = _cfg()
    lo, hi = cfg.get("min_pct", 5) / 100.0, cfg.get("max_pct", 15) / 100.0
    min_age, max_age = cfg.get("min_age_min", 20), cfg.get("max_age_min", 150)
    d = _load()
    if not d:
        return
    now = datetime.now(timezone.utc)
    changed = False
    for occ, w in list(d.items()):
        age = (now - datetime.fromisoformat(w["ts"])).total_seconds() / 60.0
        if age > max_age:
            del d[occ]; changed = True
            print(f"  early-strength expired {occ} (no confirmation in {max_age}m)")
            continue
        if age < min_age:
            continue
        bid, ask = _quote(occ, creds)
        if not bid or not ask or not w["ref"]:
            continue
        rise = bid / w["ref"] - 1
        if rise > hi:
            del d[occ]; changed = True
            print(f"  early-strength missed {occ} (+{rise*100:.0f}% > cap)")
            continue
        if rise >= lo:
            resp = _buy(occ, w["contracts"], ask, creds)
            del d[occ]; changed = True
            if resp and resp.get("id"):
                right = "call" if occ[-9] == "C" else "put"
                name = "bullish_call" if right == "call" else "bearish_put"
                rec = {"trade_set_id": uuid.uuid4().hex[:12], "ticker": w["ticker"],
                       "regime": w["regime"], "trigger": "early_strength_confirmed",
                       "book": "FADE", "entry_mode": "early_strength",
                       "entry_ts_utc": now.isoformat(), "leg_budget_usd": w["alloc"],
                       "execution_mode": "LIVE_PAPER", "occ_resolution": "alpaca_real",
                       "params_snapshot": {}, "metadata": {"entry_ts_utc": now.isoformat()},
                       "legs": {name: {"structure": f"LONG_{right.upper()}", "occ_symbol": occ,
                                       "strike": None, "dte": None, "entry_premium": ask,
                                       "limit_price": ask, "contracts": w["contracts"],
                                       "alloc_usd": w["alloc"],
                                       "execution_cost": {"bid": bid, "ask": ask,
                                                          "bid_ask_spread_pct": round((ask - bid) / ask * 100, 2),
                                                          "source": "alpaca_quote"}}},
                       "orders": {name: {"status": resp.get("status"), "order_id": resp["id"],
                                         "submitted": True, "limit_price": ask,
                                         "contracts": w["contracts"]}},
                       "exit": None, "status": "OPEN"}
                log = lab._load_log_list()
                log.append(rec)
                lab._save_log_list(log)
                print(f"  EARLY-STRENGTH ENTERED {w['ticker']} {occ} @ {ask} (+{rise*100:.0f}% confirmed)")
                try:
                    lab._notify(f"<b>FADE entry (early-strength)</b> {w['ticker']} {occ} @ ${ask} "
                                f"(confirmed +{rise*100:.0f}% from signal)")
                except Exception:
                    pass
    if changed:
        _save(d)
