import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst import uw_adapter, alert_engine, scan_safeguards, alpaca_executor


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


def _to_f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


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
            q = client.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=occ)).get(occ)
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
                g = _summarize_gex(None, uw.greek_exposure_by_strike(ticker), ticker, spot)
                flip = _to_f((g or {}).get("gamma_flip_strike"))
                if flip and abs(spot - flip) / spot <= 0.015:
                    candidate["gamma_flip_pin"] = True
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
    if alpaca_rec:
        status = alpaca_rec.get("status") or alpaca_rec.get("error")
        lines.append(f"Alpaca PAPER: {alpaca_rec.get('contracts')}x -> {status}")
    lines.append("Auto-executed on Alpaca PAPER (simulated). Real money is your call, manual.")
    return "\n".join(str(x) for x in lines)


def _send(text):
    from src.telegram import send_alert
    return send_alert(text)


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
    candidates = uw_adapter.candidates_from_flow(flow_payload, universe=universe)

    alerts = []
    for c in candidates:
        if not _cheap_pass(c):
            continue
        c = (enrich_fn or _enrich)(c)
        ev = (events_fn or scan_safeguards.earnings_exdiv_days)(c.get("ticker"))
        c["earnings_in_days"] = ev.get("earnings_in_days")
        c["exdiv_in_days"] = ev.get("exdiv_in_days")
        ivr = (ivr_fn or _live_ivr)(c.get("ticker"))
        combo = (combo_fn or _build_vertical)(c, bias)
        decision = alert_engine.process(
            c, combo=combo, regime_state=regime_state, vault_state={"ivr": ivr},
            ladder_state=ladder_state, apply_cooldown=apply_cooldown)
        decision["ivr"] = ivr
        if not decision.get("alerted"):
            continue

        alpaca_rec = None
        if execute and combo is not None:
            contracts = alpaca_executor.size_spread(combo, account_gbp=account_gbp, size_pct=exec_size_pct)
            resp, err = (executor_fn or alpaca_executor.submit_spread)(combo, contracts)
            alpaca_rec = {"contracts": contracts, "order_id": (resp or {}).get("id"),
                          "status": (resp or {}).get("status"), "error": err}

        (telegram_fn or _send)(_format_alert(c, decision, exec_size_pct, account_gbp, alpaca_rec))
        alerts.append({"ticker": c.get("ticker"), "decision": decision["decision"],
                       "structure": decision["structure"], "alpaca": alpaca_rec})
        if len(alerts) >= max_alerts:
            break

    return {"candidates": len(candidates), "alerts": alerts, "regime": regime_state.get("regime")}


if __name__ == "__main__":
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
