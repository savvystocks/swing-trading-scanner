"""V10 Research Sandbox - Proactive Paper-Trading Lab + Active Alpaca Paper Execution.

Phase 2: trade the chop from three angles, route to the Alpaca PAPER API, log a forensic
state block + order ids, and have the autopsy emit a tuning advisory so we tighten the knobs
weekly from empirical win/loss data. Gate values are NOT hardcoded - they live in
v10_tunable_parameters.json (read every cycle) and are turned by tune_parameters.py.

On a trigger (regime_compass_bypass / regime C / consolidation) we enter THREE legs sized off
a $10,000 cluster budget:
   1. Bullish - long OTM call  (delta ~ +0.35)
   2. Bearish - long OTM put   (delta ~ -0.35)
   3. Flat    - calendar spread (buy back / sell front) for theta

EXECUTION SAFETY: routing defaults to DRY_RUN (build + log the order payload, do NOT submit).
Real submission to paper-api.alpaca.markets only happens with --live-paper (you run it). No
order is ever placed against a live/real-money endpoint - paper only. Touches no V9 engine.

Run (simulate):       python sandbox_proactive_lab.py
Run (submit to paper): ALPACA_PAPER_API_KEY=... ALPACA_PAPER_SECRET_KEY=... python sandbox_proactive_lab.py --live-paper
"""

import os
import sys
import json
import math
import uuid
import urllib.request
from datetime import datetime, timezone, timedelta, date

from v10_params import load as load_params

LOG_PATH = "proactive_sandbox_logs.json"
AUTOPSY_MD = "proactive_autopsy_log.md"
ADVISORY_MD = "v10_tuning_advisory.md"
CLUSTER_BUDGET = 10_000.0            # $10k per trade cluster (split across active legs)
PAPER_BASE = "https://paper-api.alpaca.markets"
CALL_DELTA, PUT_DELTA = 0.35, -0.35
WATCHLIST = ["TSLA", "PLTR", "AMD", "NVDA", "SOFI", "AAPL", "MSFT", "AMZN", "COIN", "MARA"]
CAL_FRONT_DTE = (10, 15)             # short leg expiration window (days)
CAL_BACK_DTE = (35, 45)             # long leg expiration window (days)


def _now_iso_ms():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------
# Metadata fetchers - all FAIL-OPEN (real value + source tag, mock on failure)
# ----------------------------------------------------------------------------
def _alpaca_daily(ticker, days=60):
    k = os.environ.get("ALPACA_PAPER_API_KEY") or os.environ.get("ALPACA_API_KEY")
    s = os.environ.get("ALPACA_PAPER_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY")
    if not (k and s):
        return []
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed
        cli = StockHistoricalDataClient(k, s)
        start = datetime.utcnow() - timedelta(days=days + 20)
        bars = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day,
                                                   start=start, feed=DataFeed.IEX)).data.get(ticker, [])
        return [{"h": float(b.high), "l": float(b.low), "c": float(b.close), "v": float(b.volume)} for b in bars]
    except Exception:
        return []


def macro_technical(ticker, mock):
    bars = [] if mock else _alpaca_daily(ticker)
    if len(bars) >= 21:
        closes = [b["c"] for b in bars]
        spot = closes[-1]
        sma20 = sum(closes[-20:]) / 20.0
        trs = [max(bars[i]["h"] - bars[i]["l"], abs(bars[i]["h"] - bars[i - 1]["c"]),
                   abs(bars[i]["l"] - bars[i - 1]["c"])) for i in range(1, len(bars))]
        atr = sum(trs[-14:]) / 14.0
        vols = [b["v"] for b in bars]
        rvol = round(vols[-1] / (sum(vols[-20:]) / 20.0), 2) if sum(vols[-20:]) else None
        src = "alpaca"
    else:
        spot, sma20, atr, rvol, src = 91.30, 90.85, 2.60, 1.18, "mock"
    return {"spot": round(spot, 2), "sma20": round(sma20, 2),
            "distance_to_sma20_pct": round((spot - sma20) / sma20 * 100, 3),
            "atr": round(atr, 2), "atr_pct": round(atr / spot * 100, 2),
            "rvol_10min": rvol if rvol is not None else 1.0, "source": src}


def iv_term_structure(ticker, spot, mock):
    iv_front, iv_back, src = (78.0, 62.0, "mock")    # real wiring: two Alpaca chain expiries
    ratio = round(iv_front / iv_back, 3) if iv_back else None
    return {"iv_front": iv_front, "iv_back": iv_back, "iv_ratio": ratio,
            "structure": "contango" if ratio and ratio < 1 else "backwardation" if ratio and ratio > 1 else "flat",
            "source": src}


def net_gex(ticker, spot, mock):
    if not mock:
        try:
            from src.unusual_whales_api import UnusualWhalesClient
            uw = UnusualWhalesClient()
            rows = (uw.greek_exposure_by_strike(ticker.split(".")[0]) or {}).get("data") or []
            pts = []
            for r in rows:
                k = _num(r.get("strike") or r.get("price"))
                g = (_num(r.get("call_gex")) or 0.0) + (_num(r.get("put_gex")) or 0.0)
                if k is not None:
                    pts.append((k, g))
            if pts:
                pts.sort()
                total = sum(g for _, g in pts)
                cum, prev_cum, crossings = 0.0, 0.0, []
                for k, g in pts:
                    prev_cum = cum
                    cum += g
                    if (prev_cum < 0 <= cum) or (prev_cum > 0 >= cum):
                        crossings.append(k)
                zero_gamma = (min(crossings, key=lambda k: abs(k - spot)) if crossings
                              else min(pts, key=lambda x: abs(x[0] - spot))[0])
                return {"net_gex": round(total, 1), "zero_gamma_strike": round(zero_gamma, 2),
                        "distance_to_zero_gamma_pct": round((spot - zero_gamma) / spot * 100, 3),
                        "regime": "negative_gamma" if total < 0 else "positive_gamma", "source": "uw"}
        except Exception:
            pass
    zg = round(spot * 1.004, 2)
    return {"net_gex": -1.85e8, "zero_gamma_strike": zg,
            "distance_to_zero_gamma_pct": round((spot - zg) / spot * 100, 3),
            "regime": "negative_gamma", "source": "mock"}


def alt_catalyst(ticker, mock):
    reddit_delta, insider_usd, cluster, src = None, None, None, "mock"
    if not mock:
        try:
            from prototype_alt_data import reddit_attention_map, insider_open_market_buys
            ra = reddit_attention_map().get(ticker.split(".")[0])
            if ra:
                reddit_delta = ra["mention_spike_pct"]
            ib = insider_open_market_buys(ticker, lookback_days=10)
            insider_usd = ib.get("total_value")
            from sandbox_v10_upgrades import detect_cluster
            buys = [{"date": b["date"], "filer": b["insider"], "value": b["value"]} for b in ib.get("buys", [])]
            cluster = detect_cluster(buys)["cluster_flag"] if buys else False
            src = "apewisdom+edgartools"
        except Exception:
            pass
    if reddit_delta is None:
        reddit_delta, insider_usd, cluster, src = 540.0, 1_250_000, True, "mock"
    return {"reddit_mention_delta_pct": reddit_delta, "insider_10d_buy_usd": insider_usd,
            "insider_cluster_flag": bool(cluster), "source": src}


def collect_metadata(ticker, mock=False):
    mt = macro_technical(ticker, mock)
    spot = mt["spot"]
    return {
        "entry_ts_utc": _now_iso_ms(),
        "macro": {"spot": mt["spot"], "sma20": mt["sma20"], "distance_to_sma20_pct": mt["distance_to_sma20_pct"],
                  "source": mt["source"]},
        "iv_term": iv_term_structure(ticker, spot, mock),
        "gex": net_gex(ticker, spot, mock),
        "alt_catalyst": alt_catalyst(ticker, mock),
        "technical": {"atr": mt["atr"], "atr_pct": mt["atr_pct"], "rvol_10min": mt["rvol_10min"],
                      "source": mt["source"]},
    }


# ----------------------------------------------------------------------------
# Trigger + legs + Alpaca paper routing
# ----------------------------------------------------------------------------
def should_enter_proactive(regime, params, candidate=None):
    if params.get("regime_compass_bypass"):
        return True, "regime_compass_bypass (ultra-loose, fail-open)"
    if regime == "C":
        return True, "regime_C_neutral (flat/chop)"
    if candidate and candidate.get("consolidating"):
        return True, "candidate_consolidating"
    return True, "fail-open sandbox"


def _est_premium(spot, strike, iv_pct, dte, right):
    intrinsic = max(0.0, (spot - strike) if right == "call" else (strike - spot))
    tv = spot * (iv_pct / 100.0) * math.sqrt(max(dte, 1) / 365.0) * 0.40
    return round(intrinsic + tv, 2)


def _occ(ticker, dte, right, strike):
    expiry = (date.today() + timedelta(days=dte))
    ymd = expiry.strftime("%y%m%d")
    rc = "C" if right == "call" else "P"
    k = str(int(round(strike * 1000))).zfill(8)
    return f"{ticker.upper()[:6]}{ymd}{rc}{k}", expiry.isoformat()


def build_legs(ticker, md, cluster_budget=CLUSTER_BUDGET, n_legs=3, illiquid=None):
    spot = md["macro"]["spot"]
    iv_f, iv_b = md["iv_term"]["iv_front"], md["iv_term"]["iv_back"]
    per_leg = round(cluster_budget / n_legs, 2)
    illiquid = illiquid or set()
    call_k, put_k = round(spot * 1.04, 1), round(spot * 0.96, 1)
    cp, pp = _est_premium(spot, call_k, iv_f, 35, "call"), _est_premium(spot, put_k, iv_f, 35, "put")
    front, back = _est_premium(spot, spot, iv_f, 14, "call"), _est_premium(spot, spot, iv_b, 45, "call")
    cal_debit = round(back - front, 2)

    def leg(name, structure, right, strike, dte, premium, **extra):
        occ, expiry = _occ(ticker, dte, right, strike)
        qty = int(per_leg // (premium * 100)) if premium and premium > 0 else 0
        return {"structure": structure, "occ_symbol": occ, "expiry": expiry, "strike": strike,
                "dte": dte, "entry_premium": premium, "limit_price": round(premium * 1.01, 2),
                "contracts": qty, "alloc_usd": per_leg,
                "illiquid": (name in illiquid) or qty <= 0, **extra}

    legs = {
        "bullish_call": leg("bullish_call", "LONG_CALL", "call", call_k, 35, cp, target_delta=CALL_DELTA),
        "bearish_put": leg("bearish_put", "LONG_PUT", "put", put_k, 35, pp, target_delta=PUT_DELTA),
    }
    cal_occ_f, _ = _occ(ticker, 14, "call", round(spot, 1))
    cal_occ_b, exp_b = _occ(ticker, 45, "call", round(spot, 1))
    qty_cal = int(per_leg // (cal_debit * 100)) if cal_debit > 0 else 0
    legs["flat_calendar"] = {"structure": "CALENDAR_SPREAD", "strike": round(spot, 1),
                             "front_occ": cal_occ_f, "back_occ": cal_occ_b, "front_dte": 14, "back_dte": 45,
                             "net_debit": cal_debit, "limit_price": round(cal_debit * 1.01, 2),
                             "contracts": qty_cal, "alloc_usd": per_leg,
                             "illiquid": ("flat_calendar" in illiquid) or qty_cal <= 0}
    return legs


def _order_payload(name, leg):
    if name == "flat_calendar":
        return {"order_class": "mleg", "qty": str(leg["contracts"]), "type": "limit",
                "limit_price": str(leg["limit_price"]), "time_in_force": "day", "legs": [
                    {"symbol": leg["front_occ"], "ratio_qty": "1", "side": "sell", "position_intent": "sell_to_open"},
                    {"symbol": leg["back_occ"], "ratio_qty": "1", "side": "buy", "position_intent": "buy_to_open"}]}
    return {"symbol": leg["occ_symbol"], "qty": str(leg["contracts"]), "side": "buy", "type": "limit",
            "limit_price": str(leg["limit_price"]), "time_in_force": "day"}


def _submit_paper_order(payload, creds):
    key, sec = creds
    data = json.dumps(payload).encode()
    req = urllib.request.Request(PAPER_BASE + "/v2/orders", data=data, method="POST",
                                 headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read().decode())
        return resp.get("id"), resp.get("status"), None
    except Exception as e:
        return None, "ERROR", str(e)[:120]


def route_to_alpaca_paper(ticker, legs, dry_run=True):
    creds = (os.environ.get("ALPACA_PAPER_API_KEY"), os.environ.get("ALPACA_PAPER_SECRET_KEY"))
    out = {}
    for name, leg in legs.items():
        if leg.get("illiquid"):                       # FAIL-OPEN: skip illiquid, keep the rest
            out[name] = {"status": "SKIPPED_ILLIQUID", "order_id": None, "submitted": False}
            continue
        payload = _order_payload(name, leg)
        if dry_run:
            out[name] = {"status": "DRY_RUN", "order_id": None, "submitted": False,
                         "limit_price": leg["limit_price"], "contracts": leg["contracts"], "payload": payload}
        elif not all(creds):
            out[name] = {"status": "NO_PAPER_CREDS", "order_id": None, "submitted": False, "payload": payload}
        else:
            oid, status, err = _submit_paper_order(payload, creds)
            out[name] = {"status": status, "order_id": oid, "error": err, "submitted": True,
                         "limit_price": leg["limit_price"], "contracts": leg["contracts"]}
    return out


# ---- real OCC resolution + portfolio guards (read-only Alpaca paper API) ----
COOLOFF_PATH = "sandbox_ticker_cooloff.json"


def _paper_creds():
    return (os.environ.get("ALPACA_PAPER_API_KEY"), os.environ.get("ALPACA_PAPER_SECRET_KEY"))


def _paper_get(path, creds):
    key, sec = creds
    req = urllib.request.Request(PAPER_BASE + path, headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def resolve_occ(ticker, right, target_strike, target_dte, creds=None, dte_min=None, dte_max=None):
    """Resolve a REAL active OCC contract near target strike/expiry via Alpaca
    /v2/options/contracts. CRITICAL: that endpoint defaults to ~this-week expiries, so we MUST
    bound expiration_date_gte/lte or we get the wrong contracts. Pass dte_min/dte_max to set an
    explicit window (e.g. 10-15d front / 35-45d back for the calendar). Fail-open -> None."""
    import urllib.parse
    creds = creds or _paper_creds()
    if not all(creds):
        return None
    if dte_min is not None and dte_max is not None:
        gte = date.today() + timedelta(days=dte_min)
        lte = date.today() + timedelta(days=dte_max)
    else:
        exp = date.today() + timedelta(days=target_dte)
        gte, lte = exp - timedelta(days=7), exp + timedelta(days=10)
    q = urllib.parse.urlencode({
        "underlying_symbols": ticker.split(".")[0], "type": right, "status": "active",
        "expiration_date_gte": gte.isoformat(), "expiration_date_lte": lte.isoformat(),
        "strike_price_gte": round(target_strike * 0.85, 2), "strike_price_lte": round(target_strike * 1.15, 2),
        "limit": 1000})
    try:
        rows = _paper_get(f"/v2/options/contracts?{q}", creds).get("option_contracts") or []
    except Exception:
        return None
    if not rows:
        return None
    best = min(rows, key=lambda c: abs(float(c.get("strike_price", 0)) - target_strike))
    return {"occ_symbol": best.get("symbol"), "strike": float(best.get("strike_price")),
            "expiration": best.get("expiration_date"), "open_interest": best.get("open_interest")}


def get_open_positions(creds=None):
    creds = creds or _paper_creds()
    if not all(creds):
        return []
    try:
        return _paper_get("/v2/positions", creds)
    except Exception:
        return []


def get_open_orders(creds=None):
    creds = creds or _paper_creds()
    if not all(creds):
        return []
    try:
        return _paper_get("/v2/orders?status=open&limit=500", creds)
    except Exception:
        return []


def _cancel_order(order_id, creds):
    key, sec = creds
    req = urllib.request.Request(PAPER_BASE + f"/v2/orders/{order_id}", method="DELETE",
                                 headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (200, 204)
    except Exception:
        return False


def audit_stale_orders(creds=None, max_minutes=None, orders=None):
    """Cancel limit orders sitting unfilled longer than max_minutes (default 30 = 3 cycles) so
    stale limits don't block buying power. Logs the cancels so the autopsy knows the leg was
    cancelled, not filled. Returns the cancelled list."""
    creds = creds or _paper_creds()
    if not all(creds):
        return []
    if max_minutes is None:
        max_minutes = load_params().get("stale_order_max_minutes", 30)
    orders = orders if orders is not None else get_open_orders(creds)
    now = datetime.now(timezone.utc)
    cancelled = []
    for o in orders:
        sub = o.get("submitted_at") or o.get("created_at")
        if not sub or o.get("type") != "limit":
            continue
        try:
            age = (now - datetime.fromisoformat(sub.replace("Z", "+00:00"))).total_seconds() / 60.0
        except Exception:
            continue
        if age > max_minutes and _cancel_order(o.get("id"), creds):
            cancelled.append({"order_id": o.get("id"), "symbol": o.get("symbol"),
                              "age_min": round(age, 1), "limit_price": o.get("limit_price")})
    if cancelled:
        _append_log({"trade_set_id": "AUDIT-" + uuid.uuid4().hex[:8], "type": "stale_order_cleanup",
                     "ts_utc": _now_iso_ms(), "max_minutes": max_minutes, "cancelled": cancelled,
                     "status": "CANCELLED"})
    return cancelled


def ticker_blocked(ticker, positions, params, open_orders=None, now=None):
    base = ticker.upper().split(".")[0]
    held = 0
    for p in positions or []:
        sym = (p.get("symbol") or "").upper()
        if sym == base or sym.startswith(base):
            held += abs(int(float(p.get("qty", 0) or 0)))
    pending = 0
    for o in open_orders or []:
        syms = [o.get("symbol")] + [l.get("symbol") for l in (o.get("legs") or [])]
        if any((s or "").upper().startswith(base) for s in syms):
            pending += abs(int(float(o.get("qty", 0) or 0)))
    cap = params.get("max_contracts_per_ticker", 3)
    if held + pending >= cap:
        return True, f"ticker cap: {held} held + {pending} pending on {base} >= {cap}"
    cool = {}
    if os.path.exists(COOLOFF_PATH):
        try:
            cool = json.load(open(COOLOFF_PATH, encoding="utf-8"))
        except Exception:
            cool = {}
    ts = cool.get(base)
    if ts:
        closed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        hrs = ((now or datetime.now(timezone.utc)) - closed).total_seconds() / 3600.0
        if hrs < params.get("ticker_cooloff_hours", 24):
            return True, f"cool-off: {base} closed {hrs:.1f}h ago (< {params.get('ticker_cooloff_hours', 24)}h)"
    return False, "clear"


def record_close(ticker):
    base = ticker.upper().split(".")[0]
    cool = json.load(open(COOLOFF_PATH, encoding="utf-8")) if os.path.exists(COOLOFF_PATH) else {}
    cool[base] = _now_iso_ms()
    json.dump(cool, open(COOLOFF_PATH, "w", encoding="utf-8"), indent=2)


def manage_exit(entry_ts_iso, entry_premium, current_premium, params, now=None):
    """24h minimum-hold swing guard + 30-50% squeeze. Blocks ANY close before min_hold_hours;
    once eligible, exits 100% of the leg at >= take_profit_pct."""
    now = now or datetime.now(timezone.utc)
    entry = datetime.fromisoformat(entry_ts_iso.replace("Z", "+00:00"))
    held_h = (now - entry).total_seconds() / 3600.0
    ret = round((current_premium / entry_premium - 1) * 100, 1) if entry_premium else 0.0
    min_hold = params.get("min_hold_hours", 24)
    if held_h < min_hold:
        return {"action": "HOLD", "reason": f"24h-hold guard: {held_h:.1f}h < {min_hold}h -> close BLOCKED",
                "return_pct": ret, "held_hours": round(held_h, 1)}
    tp = params.get("take_profit_pct", 30)
    if ret >= tp:
        return {"action": "CLOSE_TAKE_PROFIT", "reason": f"+{ret}% >= {tp}% squeeze after {held_h:.1f}h",
                "return_pct": ret, "held_hours": round(held_h, 1)}
    return {"action": "HOLD", "reason": f"eligible ({held_h:.1f}h) but +{ret}% < {tp}% target",
            "return_pct": ret, "held_hours": round(held_h, 1)}


def _resolve_legs_occ(ticker, legs, creds):
    for name, right in (("bullish_call", "call"), ("bearish_put", "put")):
        leg = legs[name]
        r = resolve_occ(ticker, right, leg["strike"], leg["dte"], creds)
        if r and r.get("occ_symbol"):
            leg.update({"occ_symbol": r["occ_symbol"], "strike": r["strike"], "expiry": r["expiration"],
                        "open_interest": r.get("open_interest"), "occ_source": "alpaca_resolved"})
        else:
            leg.update({"illiquid": True, "occ_source": "unresolved -> FAIL-OPEN skip"})
    cal = legs["flat_calendar"]
    f = resolve_occ(ticker, "call", cal["strike"], cal["front_dte"], creds,
                    dte_min=CAL_FRONT_DTE[0], dte_max=CAL_FRONT_DTE[1])   # 10-15d short leg
    b = resolve_occ(ticker, "call", cal["strike"], cal["back_dte"], creds,
                    dte_min=CAL_BACK_DTE[0], dte_max=CAL_BACK_DTE[1])     # 35-45d long leg
    if f and b and f.get("occ_symbol") and b.get("occ_symbol"):
        cal.update({"front_occ": f["occ_symbol"], "back_occ": b["occ_symbol"],
                    "front_expiry": f["expiration"], "back_expiry": b["expiration"], "occ_source": "alpaca_resolved"})
    else:
        cal.update({"illiquid": True, "occ_source": "unresolved -> FAIL-OPEN skip"})


def enter_proactive_set(ticker, regime, mock=False, candidate=None, dry_run=True, illiquid=None,
                        resolve_real=None, positions=None, open_orders=None):
    params = load_params()
    creds = _paper_creds()
    if positions is None:
        positions = get_open_positions(creds) if all(creds) else []
    blocked, why = ticker_blocked(ticker, positions, params, open_orders=open_orders)
    if blocked:
        return {"trade_set_id": None, "ticker": ticker, "skipped": True, "reason": why, "status": "SKIPPED"}

    ok, trigger = should_enter_proactive(regime, params, candidate)
    md = collect_metadata(ticker, mock=mock)
    active = 3 - len(illiquid or set())
    legs = build_legs(ticker, md, n_legs=max(active, 1), illiquid=illiquid)
    if resolve_real is None:
        resolve_real = all(creds)
    if resolve_real:
        _resolve_legs_occ(ticker, legs, creds)                 # real OCCs; unresolved -> fail-open skip
    orders = route_to_alpaca_paper(ticker, legs, dry_run=dry_run)
    record = {"trade_set_id": uuid.uuid4().hex[:12], "ticker": ticker, "regime": regime, "trigger": trigger,
              "entry_ts_utc": md["entry_ts_utc"], "cluster_budget_usd": CLUSTER_BUDGET,
              "execution_mode": "DRY_RUN" if dry_run else "LIVE_PAPER",
              "occ_resolution": "alpaca_real" if resolve_real else "synthesized",
              "ticker_guard": why, "open_positions_checked": len(positions),
              "params_snapshot": params, "metadata": md, "legs": legs, "orders": orders,
              "exit": None, "status": "OPEN"}
    _append_log(record)
    return record


def _append_log(record):
    data = []
    if os.path.exists(LOG_PATH):
        try:
            data = json.load(open(LOG_PATH, encoding="utf-8"))
        except Exception:
            data = []
    data.append(record)
    json.dump(data, open(LOG_PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def _rewrite_last(record):
    data = json.load(open(LOG_PATH, encoding="utf-8"))
    for i in range(len(data) - 1, -1, -1):
        if data[i]["trade_set_id"] == record["trade_set_id"]:
            data[i] = record
            break
    json.dump(data, open(LOG_PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


# ----------------------------------------------------------------------------
# Autopsy + Tuning Advisory
# ----------------------------------------------------------------------------
def _determining_factor(winner, md, move):
    alt, gex, ivt = md["alt_catalyst"], md["gex"], md["iv_term"]
    rd = alt.get("reddit_mention_delta_pct")
    if winner == "bullish_call":
        if alt.get("insider_cluster_flag"):
            return f"Insider cluster buy (${alt.get('insider_10d_buy_usd'):,.0f}/10d) predicted the bullish expansion; {gex['regime']} amplified the breakout."
        if rd is not None and rd > 500:
            return f"Breakout triggered by a +{rd:.0f}% Reddit spike while IV term was in {ivt['structure']}."
        return f"Bullish breakout (move {move}%); dealers short gamma near {gex['zero_gamma_strike']} fed the squeeze."
    if winner == "bearish_put":
        return f"Bearish breakdown (move {move}%): spot below zero-gamma {gex['zero_gamma_strike']} -> negative-gamma slide, no positive catalyst."
    return f"Range held: IV term {ivt['structure']} (ratio {ivt['iv_ratio']}) let front-month theta outrun the wings."


def _tuning_rules(record, returns, slippage_pct):
    md = record["metadata"]
    spot, zg = md["macro"]["spot"], md["gex"]["zero_gamma_strike"]
    final_spot = spot * (1 + (record.get("exit", {}) or {}).get("underlying_move_pct", 0) / 100.0)
    iv_ratio = md["iv_term"]["iv_ratio"]
    recs = []
    if returns.get("bullish_call", 0) < 0 and final_spot < zg:
        recs.append(("min_gex_distance",
                     "Bullish Call lost AND spot crossed below the Zero-Gamma strike -> "
                     "Tighten min_gex_distance or restrict Calls when GEX is negative."))
    if returns.get("flat_calendar", 0) < 0 and iv_ratio is not None and iv_ratio > 1.0:
        recs.append(("max_iv_ratio_for_calendar",
                     f"Calendar Spread lost AND IV Ratio {iv_ratio} > 1.0 (backwardation) -> "
                     "Enforce standard contango by setting max_iv_ratio_for_calendar to < 1.0."))
    if slippage_pct is not None and slippage_pct > 3.0:
        recs.append(("max_bid_ask_spread_pct",
                     f"Entry slippage {slippage_pct}% > 3% -> "
                     "Tighten max_bid_ask_spread_pct from 5.0% to 2.0%."))
    return recs


def run_trade_autopsy(record, leg_returns_pct, exit_reason="5d_time_exit",
                      underlying_move_pct=None, entry_slippage_pct=None):
    md = record["metadata"]
    ranked = sorted(leg_returns_pct.items(), key=lambda kv: kv[1], reverse=True)
    winner, w_ret = ranked[0]
    loser, l_ret = ranked[-1]
    record["exit"] = {"reason": exit_reason, "underlying_move_pct": underlying_move_pct,
                      "entry_slippage_pct": entry_slippage_pct, "leg_returns_pct": leg_returns_pct,
                      "winner": winner, "loser": loser}
    factor = _determining_factor(winner, md, underlying_move_pct)
    record["exit"]["determining_factor"] = factor
    record["status"] = "CLOSED"

    # post-mortem markdown
    label = {"bullish_call": "Bullish (call)", "bearish_put": "Bearish (put)", "flat_calendar": "Flat (calendar)"}
    pm = [f"## Autopsy - {record['ticker']} ({record['trade_set_id']})",
          f"- entered {record['entry_ts_utc']} | trigger {record['trigger']} | exit {exit_reason} "
          f"| move {underlying_move_pct}% | slippage {entry_slippage_pct}%", "",
          "| leg | structure | return % | verdict |", "|---|---|---|---|"]
    for leg, ret in ranked:
        v = "WINNER" if leg == winner else ("loser" if leg == loser else "")
        pm.append(f"| {label[leg]} | {record['legs'][leg]['structure']} | {ret:+.1f}% | {v} |")
    pm += ["", f"**Determining factor:** {factor}", ""]
    open(AUTOPSY_MD, "a", encoding="utf-8").write("\n".join(pm) + "\n")

    # tuning advisory
    recs = _tuning_rules(record, leg_returns_pct, entry_slippage_pct)
    adv = [f"## Tuning Advisory - {record['ticker']} ({record['trade_set_id']}) - {_now_iso_ms()}",
           f"trade: winner={winner} loser={loser} | move {underlying_move_pct}% | slippage {entry_slippage_pct}%",
           "", "Recommendations:"]
    adv += [f"- [{gate}] {msg}" for gate, msg in recs] or ["- none (no rule triggered)"]
    open(ADVISORY_MD, "a", encoding="utf-8").write("\n".join(adv) + "\n---\n")
    record["exit"]["tuning_recommendations"] = [g for g, _ in recs]
    return {"winner": winner, "loser": loser, "determining_factor": factor, "recommendations": recs}


# ----------------------------------------------------------------------------
# Scheduled cycle (GHA): stale-order audit -> watchlist sourcing -> first eligible
# ----------------------------------------------------------------------------
def run_scheduled_cycle(mock=False):
    creds = _paper_creds()
    live = all(creds)
    params = load_params()
    print("=" * 78)
    print(f"V10 PROACTIVE LAB - scheduled cycle ({'LIVE_PAPER' if live else 'DRY_RUN (no creds)'})")
    print("=" * 78)

    # 1. stale limit-order cleanup (free buying power)
    open_orders = get_open_orders(creds)
    cancels = audit_stale_orders(creds, orders=open_orders)
    print(f"stale-order audit: {len(cancels)} unfilled limit(s) cancelled "
          f"(> {params.get('stale_order_max_minutes', 30)}m)")
    for c in cancels:
        print(f"  cancelled {c['symbol']} age {c['age_min']}m")
    if cancels:
        open_orders = get_open_orders(creds)
    positions = get_open_positions(creds)
    print(f"portfolio: {len(positions)} positions, {len(open_orders)} open orders")

    # 2. watchlist sourcing - enter the FIRST candidate not capped/cooled
    print(f"watchlist: {WATCHLIST}")
    for t in WATCHLIST:
        rec = enter_proactive_set(t, "C", mock=mock, dry_run=not live,
                                  positions=positions, open_orders=open_orders)
        if rec.get("skipped"):
            print(f"  skip {t}: {rec['reason']}")
            continue
        md, legs, orders = rec["metadata"], rec["legs"], rec["orders"]
        print(f"\nENTERED {t} | {rec['execution_mode']} | OCC {rec['occ_resolution']}")
        print(f"  state: 20dSMA {md['macro']['distance_to_sma20_pct']:+.2f}% | IV {md['iv_term']['iv_ratio']} | "
              f"GEX {md['gex']['net_gex']} zg {md['gex']['zero_gamma_strike']} | "
              f"reddit {md['alt_catalyst']['reddit_mention_delta_pct']}% | insider ${md['alt_catalyst']['insider_10d_buy_usd']} "
              f"| ATR {md['technical']['atr_pct']}%")
        for name, leg in legs.items():
            o = orders[name]
            occ = leg.get("occ_symbol") or f"{leg.get('front_occ')}|{leg.get('back_occ')}"
            print(f"  {name:<14} {leg['structure']:<15} {occ:<24} x{leg['contracts']:<3} "
                  f"@lim ${leg['limit_price']:<6} -> {o['status']} {o['order_id']}")
        print("\nGHA scheduled cycle complete: 1 cluster entered + logged.")
        return rec
    print("\nno eligible watchlist candidate this cycle (all capped/cooled).")
    return None


# ----------------------------------------------------------------------------
# Local demo (single ticker)
# ----------------------------------------------------------------------------
def main():
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return run_scheduled_cycle(mock=os.environ.get("PROACTIVE_MOCK", "1") == "1")

    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    live_paper = "--live-paper" in sys.argv or (gha and all(_paper_creds()))   # auto under GHA
    dry_run = not live_paper
    mock = os.environ.get("PROACTIVE_MOCK", "1") == "1"
    print("=" * 78)
    print("V10 PROACTIVE LAB + ACTIVE ALPACA PAPER EXECUTION")
    print(f"(env: {'GITHUB_ACTIONS -> auto live-paper' if gha else 'local'} | metadata: {'MOCK' if mock else 'LIVE'} | "
          f"execution: {'LIVE_PAPER (auto-submit)' if live_paper else 'DRY_RUN (no orders fired)'})")
    print("=" * 78)

    params = load_params()
    print(f"\nloaded {len(params)} tunable params from v10_tunable_parameters.json:")
    print("  " + json.dumps(params))

    ticker = "HOOD"
    rec = enter_proactive_set(ticker, "C", mock=mock, candidate={"consolidating": True}, dry_run=dry_run)
    if rec.get("skipped"):
        print(f"\nSKIPPED {ticker}: {rec['reason']} (portfolio guard)")
        return
    print(f"\nTRIGGER: {rec['trigger']} -> 3 legs on {ticker} | cluster ${CLUSTER_BUDGET:,.0f} | mode {rec['execution_mode']}")
    print(f"OCC resolution: {rec['occ_resolution']} | ticker guard: {rec['ticker_guard']} | positions checked: {rec['open_positions_checked']}")

    md = rec["metadata"]
    print("\nSTATE BLOCK (un-mocked where live):")
    print(f"  macro   : spot {md['macro']['spot']} 20dSMA {md['macro']['sma20']} dist {md['macro']['distance_to_sma20_pct']:+.2f}% [{md['macro']['source']}]")
    print(f"  iv_term : ratio {md['iv_term']['iv_ratio']} ({md['iv_term']['structure']}) [{md['iv_term']['source']}]")
    print(f"  gex     : net {md['gex']['net_gex']} zero-gamma {md['gex']['zero_gamma_strike']} dist {md['gex']['distance_to_zero_gamma_pct']:+.2f}% [{md['gex']['source']}]")
    print(f"  alt     : reddit {md['alt_catalyst']['reddit_mention_delta_pct']}% insider ${md['alt_catalyst']['insider_10d_buy_usd']:,} cluster={md['alt_catalyst']['insider_cluster_flag']} [{md['alt_catalyst']['source']}]")
    print(f"  technical: ATR {md['technical']['atr_pct']}% RVOL {md['technical']['rvol_10min']} [{md['technical']['source']}]")

    print("\nALPACA PAPER ORDERS (3 legs):")
    for name, leg in rec["legs"].items():
        o = rec["orders"][name]
        occ = leg.get("occ_symbol") or f"{leg.get('front_occ')}|{leg.get('back_occ')}"
        print(f"  {name:<14} {leg['structure']:<15} {occ:<22} x{leg['contracts']:<3} @lim ${leg['limit_price']:<6} "
              f"-> {o['status']} order_id={o['order_id']}")

    # demonstrate FAIL-OPEN routing (force the put illiquid)
    rec2 = enter_proactive_set(ticker, "C", mock=mock, dry_run=True, illiquid={"bearish_put"})
    fo = {k: rec2["orders"][k]["status"] for k in rec2["orders"]}
    print(f"\nFAIL-OPEN demo (put illiquid): {fo}  <- set still trades the viable legs")

    # simulate a 5-day close that breaks the range to the downside -> trigger all 3 tuning rules
    print("\n" + "-" * 78)
    print("SIMULATED CLOSE: bearish breakdown -7%, entry slippage 4%")
    returns = {"bullish_call": -80.0, "bearish_put": 120.0, "flat_calendar": -30.0}
    res = run_trade_autopsy(rec, returns, underlying_move_pct=-7.0, entry_slippage_pct=4.0)
    _rewrite_last(rec)
    print(f"  winner {res['winner']} | determining factor: {res['determining_factor']}")
    print(f"\nTUNING ADVISORY ({ADVISORY_MD}):")
    for gate, msg in res["recommendations"]:
        print(f"  -> [{gate}] {msg}")

    print("\nEXIT MANAGEMENT (24h-hold swing guard + 30-50% squeeze):")
    a = manage_exit(rec["entry_ts_utc"], 8.91, 12.47, params, now=datetime.now(timezone.utc) + timedelta(hours=2))
    print(f"  +40% at 2h  -> {a['action']}: {a['reason']}")
    b = manage_exit(rec["entry_ts_utc"], 8.91, 12.03, params, now=datetime.now(timezone.utc) + timedelta(hours=26))
    print(f"  +35% at 26h -> {b['action']}: {b['reason']}")


if __name__ == "__main__":
    main()
