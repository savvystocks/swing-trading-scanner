from datetime import datetime


def _f(d, *keys):
    if not d:
        return None
    for k in keys:
        v = d.get(k)
        if v is None or v == "":
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _s(d, *keys):
    if not d:
        return None
    for k in keys:
        v = d.get(k)
        if v:
            return str(v)
    return None


def _side(raw):
    s = (raw or "").lower()
    if s.startswith("c"):
        return "CALL"
    if s.startswith("p"):
        return "PUT"
    return (raw or "").upper() or None


def _dte(expiry):
    if not expiry:
        return None
    try:
        e = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
        return (e - datetime.utcnow().date()).days
    except (ValueError, TypeError):
        return None


def _iv_pct(raw):
    iv = None
    try:
        iv = float(raw)
    except (TypeError, ValueError):
        return None
    if iv is None:
        return None
    return round(iv * 100, 1) if iv < 5 else round(iv, 1)


def aggregate_ticker_flow(alerts):
    agg = {}
    for a in alerts:
        t = _s(a, "ticker", "underlying_symbol", "underlying", "symbol")
        if not t:
            continue
        prem = _f(a, "total_premium", "premium", "premium_value") or 0.0
        side = _side(_s(a, "type", "option_type"))
        d = agg.setdefault(t, {"call_premium": 0.0, "put_premium": 0.0})
        if side == "CALL":
            d["call_premium"] += prem
        elif side == "PUT":
            d["put_premium"] += prem
    return agg


def normalize_flow_alert(alert, ticker_flow=None, contract_stats=None, positioning=None, quote=None):
    side = _side(_s(alert, "type", "option_type"))
    stats = contract_stats or {}
    pos = positioning or {}
    q = quote or {}

    bid = _f(q, "bid", "nbbo_bid")
    ask = _f(q, "ask", "nbbo_ask")
    mid = _f(q, "mid")
    if mid is None:
        mid = _f(alert, "price", "option_price", "mid")
    if mid is None and bid is not None and ask is not None:
        mid = round((bid + ask) / 2, 2)

    vol = _f(alert, "volume")
    avg_vol_30d = _f(stats, "avg_vol_30d", "avg_volume", "avg_30_day_volume", "volume_30d_avg")
    rvol = _f(stats, "rvol", "contract_rvol")
    if avg_vol_30d is None and rvol and vol:
        avg_vol_30d = vol / rvol

    call_prem = _f(ticker_flow or {}, "call_premium", "bullish_premium")
    put_prem = _f(ticker_flow or {}, "put_premium", "bearish_premium")
    total_dir = (call_prem or 0.0) + (put_prem or 0.0)
    flow_dominance_pct = None
    if total_dir > 0 and side in ("CALL", "PUT"):
        directional = call_prem if side == "CALL" else put_prem
        flow_dominance_pct = round((directional or 0.0) / total_dir * 100, 1)

    spread_pct = _f(q, "spread_pct")
    if spread_pct is None and bid is not None and ask is not None and mid:
        spread_pct = round((ask - bid) / mid * 100, 1)

    return {
        "ticker": _s(alert, "ticker", "underlying_symbol", "underlying", "symbol"),
        "side": side,
        "spot": _f(alert, "underlying_price", "underlying", "live_spot", "spot"),
        "strike": _f(alert, "strike"),
        "mid": mid,
        "bid": bid,
        "ask": ask,
        "spread_pct": spread_pct,
        "oi": int(_f(alert, "open_interest", "oi")) if _f(alert, "open_interest", "oi") is not None else None,
        "vol": int(vol) if vol is not None else None,
        "avg_vol_30d": avg_vol_30d,
        "volume_oi_ratio": _f(alert, "volume_oi_ratio"),
        "premium": _f(alert, "total_premium", "premium", "premium_value"),
        "ask_side_premium": _f(alert, "total_ask_side_prem"),
        "bid_side_premium": _f(alert, "total_bid_side_prem"),
        "call_premium": call_prem,
        "put_premium": put_prem,
        "flow_dominance_pct": flow_dominance_pct,
        "iv_pct": _iv_pct(_s(alert, "iv_end", "implied_volatility", "iv")),
        "occ_symbol": _s(alert, "option_chain", "option_symbol", "occ_symbol"),
        "expiration": _s(alert, "expiry", "expiration"),
        "dte": _dte(_s(alert, "expiry", "expiration")),
        "delta": _f(stats, "delta"),
        "sector": _s(alert, "sector") or _s(stats, "sector"),
        "nope": pos.get("nope"),
        "gamma_flip_pin": pos.get("gamma_flip_pin"),
        "skew_inversion": pos.get("skew_inversion"),
        "alert_rule": _s(alert, "alert_rule"),
        "has_sweep": alert.get("has_sweep"),
        "source": "uw_flow_alert",
    }


def candidates_from_flow(payload, positioning_by_ticker=None, contract_stats_by_occ=None,
                         quotes_by_occ=None, universe=None):
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    dominance = aggregate_ticker_flow(rows)
    out = []
    for a in rows:
        if not isinstance(a, dict):
            continue
        ticker = _s(a, "ticker", "underlying_symbol", "underlying", "symbol")
        if universe is not None and (ticker or "").upper().split(".")[0] not in universe:
            continue
        occ = _s(a, "option_chain", "option_symbol", "occ_symbol")
        out.append(normalize_flow_alert(
            a,
            ticker_flow=dominance.get(ticker),
            contract_stats=(contract_stats_by_occ or {}).get(occ),
            positioning=(positioning_by_ticker or {}).get(ticker),
            quote=(quotes_by_occ or {}).get(occ),
        ))
    return out
