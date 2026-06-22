import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst import uw_adapter, alert_engine, scan_safeguards, alpaca_executor, earnings_routing


def _live_flow():
    from src.unusual_whales_api import UnusualWhalesClient
    c = UnusualWhalesClient()
    if not c.enabled:
        return {"data": []}
    return c.flow_alerts(limit=100, min_premium=1000000) or {"data": []}


def _live_ivr(ticker):
    try:
        from src.catalyst.ambush_generator import _iv_rank
        r = _iv_rank((ticker or "").split(".")[0])
        return r.get("iv_rank") if r else None
    except Exception:
        return None


def _build_vertical(candidate, bias):
    ticker = (candidate.get("ticker") or "").split(".")[0]
    spot = candidate.get("spot")
    if not ticker or not spot or bias not in ("LONG", "SHORT"):
        return None
    try:
        from src.options_suggest_bear_spread import _pull_chain, _closest
        from src.catalyst import defined_risk as dr
    except Exception:
        return None
    right = "call" if bias == "LONG" else "put"
    chain = _pull_chain(ticker, right, spot, 30, 45)
    if not chain or not chain.get("by_exp"):
        return None

    def mk(c, expiry):
        return {"strike": c["strike"], "mid": c["mid"], "delta": c["delta"],
                "expiration": expiry, "dte": c["dte"], "occ_symbol": c["symbol"]}

    for expiry, contracts in chain["by_exp"].items():
        longc = _closest(contracts, 0.60, 0.50, 0.75)
        if not longc:
            continue
        if right == "call":
            pool = [c for c in contracts if c["strike"] > longc["strike"]]
        else:
            pool = [c for c in contracts if c["strike"] < longc["strike"]]
        shortc = _closest(pool, 0.30, 0.18, 0.45)
        if not shortc:
            continue
        if right == "call":
            return dr.bull_call_debit_spread(ticker, mk(longc, expiry), mk(shortc, expiry))
        return dr.bear_put_debit_spread(ticker, mk(longc, expiry), mk(shortc, expiry))
    return None


def _build_backspread(candidate, bias):
    ticker = (candidate.get("ticker") or "").split(".")[0]
    spot = candidate.get("spot")
    if not ticker or not spot or bias not in ("LONG", "SHORT"):
        return None
    try:
        from src.options_suggest_bear_spread import _pull_chain, _closest
        from src.catalyst import defined_risk as dr
    except Exception:
        return None
    right = "call" if bias == "LONG" else "put"
    chain = _pull_chain(ticker, right, spot, 30, 60)
    if not chain or not chain.get("by_exp"):
        return None

    def mk(x, expiry):
        return {"strike": x["strike"], "mid": x["mid"], "delta": x["delta"],
                "expiration": expiry, "dte": x["dte"], "occ_symbol": x["symbol"]}

    for expiry, contracts in chain["by_exp"].items():
        nearc = _closest(contracts, 0.50, 0.40, 0.60)
        if not nearc:
            continue
        pool = [x for x in contracts if (x["strike"] > nearc["strike"]) == (right == "call")]
        farc = _closest(pool, 0.30, 0.18, 0.42)
        if not farc:
            continue
        if right == "call":
            return dr.call_ratio_backspread(ticker, mk(nearc, expiry), mk(farc, expiry), ratio=2)
        return dr.put_ratio_backspread(ticker, mk(nearc, expiry), mk(farc, expiry), ratio=2)
    return None


def _build_calendar(candidate):
    ticker = (candidate.get("ticker") or "").split(".")[0]
    spot = candidate.get("spot")
    if not ticker or not spot:
        return None
    try:
        from src.options_suggest_bear_spread import _pull_chain, _closest
        from src.catalyst import defined_risk as dr
    except Exception:
        return None
    front = _pull_chain(ticker, "call", spot, 21, 35)
    back = _pull_chain(ticker, "call", spot, 50, 80)
    if not front or not back or not front.get("by_exp") or not back.get("by_exp"):
        return None
    fexp, fcons = next(iter(front["by_exp"].items()))
    bexp, bcons = next(iter(back["by_exp"].items()))
    fatm = _closest(fcons, 0.50, 0.40, 0.60)
    if not fatm:
        return None
    batm = next((x for x in bcons if abs(x["strike"] - fatm["strike"]) < 1e-6), None)
    if not batm:
        return None

    def mk(x, expiry):
        return {"strike": x["strike"], "mid": x["mid"], "delta": x["delta"],
                "expiration": expiry, "dte": x["dte"], "occ_symbol": x["symbol"]}

    return dr.calendar_spread(ticker, "call", mk(fatm, fexp), mk(batm, bexp))


def _open_positions():
    try:
        from src.catalyst import paper_pipeline as pp
        if not pp.OPEN_PATH.exists():
            return []
        with open(pp.OPEN_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
        return [{"ticker": r.get("ticker"), "sector": scan_safeguards.sector_of(r.get("ticker"))}
                for r in rows if isinstance(r, dict)]
    except Exception:
        return []


def _select_combo(candidate, bias, backwardation, combo_fn=None):
    if combo_fn:
        return combo_fn(candidate, bias)
    setup = (candidate.get("earnings_setup") or {}).get("setup")
    if setup == "PRE_EARNINGS_HARVEST":
        return _build_calendar(candidate)
    if setup == "PEMD":
        return _build_vertical(candidate, "LONG")
    if backwardation and candidate.get("skew_inversion") and bias in ("LONG", "SHORT"):
        return _build_backspread(candidate, bias) or _build_vertical(candidate, bias)
    return _build_vertical(candidate, bias)


def _to_f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _retry(fn, attempts=2, base=0.6):
    import time
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            es = str(e).lower()
            if ("html" in es or "429" in es or "too many" in es or "rate limit" in es) and i < attempts - 1:
                print(f"  alpaca rate-limit, backoff {base * (2 ** i):.1f}s")
                time.sleep(base * (2 ** i))
                continue
            return None
    return None


def _max_gamma_strike(gex_by_strike):
    rows = (gex_by_strike or {}).get("data") if isinstance(gex_by_strike, dict) else gex_by_strike
    if not isinstance(rows, list):
        return None
    best, best_mag = None, -1.0
    for r in rows:
        if not isinstance(r, dict):
            continue
        strike = _to_f(r.get("strike") or r.get("price"))
        if strike is None:
            continue
        gamma = _to_f(r.get("gamma"))
        if gamma is None:
            gamma = (_to_f(r.get("call_gamma_exposure")) or 0.0) + (_to_f(r.get("put_gamma_exposure")) or 0.0)
        mag = abs(gamma)
        if mag > best_mag:
            best_mag, best = mag, strike
    return best


def _darkpool_node(uw, ticker, spot):
    if not ticker or not spot:
        return None
    try:
        rows = (uw.darkpool_ticker(ticker) or {}).get("data") or []
    except Exception:
        return None
    buckets = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        price = _to_f(r.get("price") or r.get("executed_price"))
        size = _to_f(r.get("size") or r.get("volume") or r.get("premium")) or 0.0
        if price is None:
            continue
        key = round(price, 0)
        buckets[key] = buckets.get(key, 0.0) + size
    if not buckets:
        return None
    node = max(buckets, key=buckets.get)
    return {"price": node, "size": round(buckets[node], 0), "near": bool(abs(spot - node) / spot <= 0.01)}


def _cheap_pass(c):
    oi = c.get("oi")
    spot = c.get("spot")
    strike = c.get("strike")
    dom = c.get("flow_dominance_pct")
    if not (oi and oi >= 500):
        return False
    if not (spot and strike and abs(strike - spot) / spot * 100 <= 5):
        return False
    if dom is None or dom <= 55:
        return False
    return True


def _enrich(candidate):
    occ = candidate.get("occ_symbol")
    ticker = (candidate.get("ticker") or "").split(".")[0]
    spot = candidate.get("spot")
    has_alpaca = bool(os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"))

    if occ and has_alpaca:
        try:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.requests import OptionLatestQuoteRequest
            client = OptionHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
            q = _retry(lambda: client.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=occ)).get(occ))
            if q and q.bid_price and q.ask_price:
                bid, ask = float(q.bid_price), float(q.ask_price)
                mid = (bid + ask) / 2
                candidate["bid"], candidate["ask"], candidate["mid"] = round(bid, 2), round(ask, 2), round(mid, 2)
                if mid > 0:
                    candidate["spread_pct"] = round((ask - bid) / mid * 100, 1)
        except Exception:
            pass

    try:
        from src.unusual_whales_api import UnusualWhalesClient
        uw = UnusualWhalesClient()
        if uw.enabled:
            if occ:
                rows = (uw.option_contract_historic(occ) or {}).get("data") or []
                vols = [v for v in (_to_f(r.get("volume")) for r in rows[-30:]) if v is not None]
                if vols:
                    candidate["avg_vol_30d"] = sum(vols) / len(vols)
            if ticker and spot:
                from src.catalyst.uw_enrichment import _summarize_gex
                gex_by_strike = uw.greek_exposure_by_strike(ticker)
                g = _summarize_gex(None, gex_by_strike, ticker, spot) or {}
                flip = _to_f(g.get("gamma_flip_strike"))
                if flip:
                    candidate["zero_gamma"] = round(flip, 2)
                    if abs(spot - flip) / spot <= 0.015:
                        candidate["gamma_flip_pin"] = True
                net_gex = _to_f(g.get("net_gex"))
                if net_gex is not None:
                    candidate["gex_net"] = net_gex
                    candidate["negative_gamma"] = net_gex < 0
                mg = _max_gamma_strike(gex_by_strike)
                if mg is not None:
                    candidate["max_gamma_strike"] = round(mg, 2)
                dp = _darkpool_node(uw, ticker, spot)
                if dp:
                    candidate["darkpool_node"] = dp.get("price")
                    candidate["near_darkpool_node"] = dp.get("near")
    except Exception:
        pass

    if ticker and spot:
        try:
            from src.catalyst.vol_microstructure import pull_skew_data
            sk = pull_skew_data(ticker, spot)
            bias = (sk or {}).get("skew_bias")
            side = candidate.get("side")
            if (side == "CALL" and bias == "bullish") or (side == "PUT" and bias == "bearish"):
                candidate["skew_inversion"] = True
        except Exception:
            pass

    if ticker and spot and has_alpaca:
        try:
            from datetime import datetime, timedelta
            from src.alpaca_ohlcv import get_daily_bars_eodhd_format
            from src.indicators import atr as _atr
            import pandas as pd
            bars = get_daily_bars_eodhd_format(ticker, from_date=(datetime.utcnow().date() - timedelta(days=40)).isoformat())
            if bars and len(bars) >= 15:
                bars.sort(key=lambda b: b["date"])
                closes = [b["close"] for b in bars]
                if len(closes) >= 4 and closes[-4]:
                    candidate["gap_up_pct"] = round((closes[-1] - closes[-4]) / closes[-4] * 100, 1)
                a = _atr(pd.DataFrame(bars), 14)
                atr_val = float(a.iloc[-1]) if a is not None and len(a) else None
                if atr_val and spot:
                    atr_pct = atr_val / spot * 100
                    candidate["atr_pct"] = round(atr_pct, 2)
                    candidate["atr_trail_pct"] = round(max(15.0, min(40.0, 12.0 + atr_pct * 3.0)), 1)
        except Exception:
            pass

    return candidate


def _format_alert(candidate, decision, exec_size_pct, account_gbp, alpaca_rec=None):
    t = candidate.get("ticker")
    head = f"<b>V8.5 {decision['decision']} {t} {decision['structure']}</b>"
    lines = [
        head,
        f"regime {decision['regime']} ({decision['bias']}) | paper size {exec_size_pct}% of £{account_gbp:.0f}",
        f"spot {candidate.get('spot')} | flow dominance {candidate.get('flow_dominance_pct')}% | "
        f"IVR {decision.get('ivr')} | confirmations {decision['screen']['positioning']['confirmations']}",
        decision["route_alert"],
    ]
    ctx = []
    if candidate.get("negative_gamma"):
        ctx.append("NEG-GAMMA squeeze risk")
    if candidate.get("near_darkpool_node"):
        ctx.append(f"at dark-pool node {candidate.get('darkpool_node')}")
    if candidate.get("vix"):
        ctx.append(f"VIX {candidate.get('vix')}")
    if ctx:
        lines.append(" | ".join(ctx))
    if alpaca_rec:
        status = alpaca_rec.get("status") or alpaca_rec.get("error")
        lines.append(f"Alpaca PAPER: {alpaca_rec.get('contracts')}x -> {status}")
    lines.append("Auto-executed on Alpaca PAPER (simulated). Real money is your call, manual.")
    return "\n".join(str(x) for x in lines)


def _send(text):
    from src.telegram import send_alert
    return send_alert(text)


def session_heartbeat(now_utc=None, send_fn=None, state_path=None):
    from datetime import datetime, timezone
    import pathlib
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    elif now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_et = now_utc
    try:
        from zoneinfo import ZoneInfo
        now_et = now_utc.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        pass
    if now_et.weekday() >= 5:
        return None

    path = state_path or (pathlib.Path(__file__).parent.parent / "data" / "ambush_logs" / "heartbeat_state.json")
    today = now_et.date().isoformat()
    state = {"date": today, "online_sent": False, "offline_sent": False}
    try:
        if path.exists():
            s = json.load(open(path, "r", encoding="utf-8"))
            if s.get("date") == today:
                state = s
    except Exception:
        pass

    mins = now_et.hour * 60 + now_et.minute
    msg = None
    sent = None
    if not state["online_sent"] and 9 * 60 + 30 <= mins < 16 * 60:
        msg, sent = "\U0001F7E2 V9 Scanner Online - Awaiting Institutional Flow", "online"
        state["online_sent"] = True
    elif not state["offline_sent"] and mins >= 15 * 60 + 58:
        msg, sent = "\U0001F534 V9 Scanner Offline - Session Concluded", "offline"
        state["offline_sent"] = True

    if msg:
        try:
            (send_fn or _send)(msg)
        except Exception:
            pass
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
        except Exception:
            pass
    return sent


def _env_float(key, default):
    raw = (os.environ.get(key, "") or "").strip()
    try:
        return float(raw) if raw else float(default)
    except ValueError:
        return float(default)


def run_scan(flow_payload=None, flow_fn=None, combo_fn=None, telegram_fn=None, events_fn=None,
             regime_state=None, ladder_state=None, ivr_fn=None, universe=None, enrich_fn=None,
             apply_cooldown=True, max_alerts=10, execute=True, executor_fn=None,
             account_gbp=None, exec_size_pct=None):
    if flow_payload is None:
        flow_payload = (flow_fn or _live_flow)()
    if universe is None:
        universe = scan_safeguards.load_universe()
    if regime_state is None:
        try:
            from src.catalyst import regime_compass
            regime_state = regime_compass.evaluate()
        except Exception:
            regime_state = {"regime": "C", "bias": "NEUTRAL"}
    if ladder_state is None:
        from src.catalyst import probe_ladder
        ladder_state = probe_ladder.evaluate()
    if account_gbp is None:
        account_gbp = _env_float("ACCOUNT_SIZE_GBP", 4000)
    if exec_size_pct is None:
        exec_size_pct = _env_float("EXEC_SIZE_PCT", 25)

    bias = regime_state.get("bias")
    backwardation = bool(regime_state.get("backspread_unlock"))
    candidates = uw_adapter.candidates_from_flow(flow_payload, universe=universe,
                                                 watchlist=scan_safeguards.MIDCAP_WATCHLIST)
    open_positions = _open_positions()

    survivors = [c for c in candidates if _cheap_pass(c)]
    survivors.sort(key=lambda x: ((x.get("flow_dominance_pct") or 0.0), (x.get("premium") or 0.0)), reverse=True)
    top_n = int(_env_float("ENRICH_TOP_N", 5))

    alerts = []
    for c in survivors[:top_n]:
        c = (enrich_fn or _enrich)(c)
        ev = (events_fn or scan_safeguards.earnings_exdiv_days)(c.get("ticker"))
        c["earnings_in_days"] = ev.get("earnings_in_days")
        c["exdiv_in_days"] = ev.get("exdiv_in_days")
        ivr = (ivr_fn or _live_ivr)(c.get("ticker"))
        c["ivr"] = ivr
        c["vix"] = (regime_state.get("vix_term") or {}).get("vix")
        if not c.get("sector"):
            c["sector"] = scan_safeguards.sector_of(c.get("ticker"))
        c["earnings_setup"] = earnings_routing.classify(c)

        combo = _select_combo(c, bias, backwardation, combo_fn)
        vault_state = {"ivr": ivr, "backwardation": backwardation,
                       "skew": 0.06 if c.get("skew_inversion") else None}
        decision = alert_engine.process(
            c, combo=combo, regime_state=regime_state, vault_state=vault_state,
            open_positions=open_positions, ladder_state=ladder_state, apply_cooldown=apply_cooldown)
        decision["ivr"] = ivr
        if not decision.get("alerted"):
            continue

        eff_size_pct = round(exec_size_pct * decision.get("size_multiplier", 1.0), 2)
        alpaca_rec = None
        if execute and combo is not None:
            contracts = alpaca_executor.size_spread(combo, account_gbp=account_gbp, size_pct=eff_size_pct)
            resp, err = (executor_fn or alpaca_executor.submit_spread)(combo, contracts)
            alpaca_rec = {"contracts": contracts, "order_id": (resp or {}).get("id"),
                          "status": (resp or {}).get("status"), "error": err}

        (telegram_fn or _send)(_format_alert(c, decision, eff_size_pct, account_gbp, alpaca_rec))
        alerts.append({"ticker": c.get("ticker"), "decision": decision["decision"],
                       "structure": decision["structure"], "size_pct": eff_size_pct, "alpaca": alpaca_rec})
        if len(alerts) >= max_alerts:
            break

    return {"candidates": len(candidates), "alerts": alerts, "regime": regime_state.get("regime")}


if __name__ == "__main__":
    try:
        hb = session_heartbeat()
        if hb:
            print(f"heartbeat: {hb}")
    except Exception:
        pass
    force = "--force" in sys.argv
    if not force:
        try:
            from src.catalyst.ambush_generator import _market_is_open
            if not _market_is_open():
                print("market closed - skipping live scan")
                sys.exit(0)
        except Exception:
            pass
    result = run_scan(apply_cooldown="--no-cooldown" not in sys.argv)
    print(f"live scan: {result['candidates']} candidates, {len(result['alerts'])} alerts, regime {result['regime']}")
    for a in result["alerts"]:
        print(f"  ALERT {a['ticker']} {a['decision']} {a['structure']}")
