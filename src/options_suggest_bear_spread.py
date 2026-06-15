import os
import re
from datetime import datetime, timedelta


def _pull_chain(underlying, right, spot, dte_min, dte_max):
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        return None
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        return None
    client = OptionHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    today = datetime.now()
    min_exp = (today + timedelta(days=dte_min)).strftime("%Y-%m-%d")
    max_exp = (today + timedelta(days=dte_max)).strftime("%Y-%m-%d")
    if right == "put":
        lo, hi = spot * 0.70, spot * 1.25
    else:
        lo, hi = spot * 0.95, spot * 1.35
    try:
        req = OptionChainRequest(
            underlying_symbol=underlying,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(lo, 2)),
            strike_price_lte=str(round(hi, 2)),
            type=right,
        )
        snaps = client.get_option_chain(req)
    except Exception as e:
        print(f"  [bear {underlying}] chain error: {type(e).__name__}: {str(e)[:100]}")
        return None
    if not snaps:
        return None
    by_exp = {}
    fetched_at = datetime.now().isoformat(timespec="seconds")
    for sym, snap in snaps.items():
        try:
            q = snap.latest_quote
            g = snap.greeks
            if not q or not g or not q.bid_price or not q.ask_price or g.delta is None:
                continue
            bid = float(q.bid_price)
            ask = float(q.ask_price)
            mid = (bid + ask) / 2
            if mid <= 0.05:
                continue
            delta = float(g.delta)
            spread_pct = (ask - bid) / mid * 100
            sym_str = sym if isinstance(sym, str) else str(sym)
            m = re.match(r"([A-Z]+)(\d{6})([CP])(\d+)", sym_str)
            if not m:
                continue
            strike = int(m.group(4)) / 1000
            exp_raw = m.group(2)
            expiry = f"20{exp_raw[:2]}-{exp_raw[2:4]}-{exp_raw[4:6]}"
            dte = (datetime.strptime(expiry, "%Y-%m-%d") - today).days
            iv = getattr(snap, "implied_volatility", None) or getattr(g, "implied_volatility", None)
            by_exp.setdefault(expiry, []).append({
                "strike": strike,
                "delta": delta,
                "abs_delta": abs(delta),
                "bid": round(bid, 2),
                "ask": round(ask, 2),
                "mid": round(mid, 2),
                "iv": float(iv) if iv else None,
                "theta": round(float(g.theta), 4) if g.theta else None,
                "dte": dte,
                "spread_pct": round(spread_pct, 1),
                "symbol": sym_str,
            })
        except (ValueError, AttributeError):
            continue
    return {"by_exp": by_exp, "fetched_at": fetched_at}


def _closest(contracts, target_abs_delta, lo, hi, max_spread_pct=30):
    pool = [c for c in contracts if lo <= c["abs_delta"] <= hi and c["spread_pct"] <= max_spread_pct]
    if not pool:
        return None
    pool.sort(key=lambda c: abs(c["abs_delta"] - target_abs_delta))
    return pool[0]


def _leg(c):
    return {
        "strike": c["strike"],
        "delta": round(c["delta"], 3),
        "mid": c["mid"],
        "bid": c["bid"],
        "ask": c["ask"],
        "iv_pct": round(c["iv"] * 100, 1) if c["iv"] else None,
        "spread_pct": c["spread_pct"],
        "occ_symbol": c["symbol"],
    }


def suggest_bear_put_debit_spread(ticker, current_price, dte_min=30, dte_max=45,
                                  long_delta=0.65, short_delta=0.35):
    chain = _pull_chain(ticker, "put", current_price, dte_min, dte_max)
    if not chain or not chain["by_exp"]:
        return None
    best = None
    best_rr = -1.0
    for expiry, contracts in chain["by_exp"].items():
        longp = _closest(contracts, long_delta, 0.55, 0.80)
        if not longp:
            continue
        shortp = _closest([c for c in contracts if c["strike"] < longp["strike"]], short_delta, 0.22, 0.45)
        if not shortp:
            continue
        net_debit = longp["mid"] - shortp["mid"]
        width = longp["strike"] - shortp["strike"]
        if net_debit <= 0 or width <= 0:
            continue
        max_loss = net_debit * 100
        max_profit = (width - net_debit) * 100
        if max_profit <= 0:
            continue
        breakeven = longp["strike"] - net_debit
        rr = max_profit / max_loss
        if rr > best_rr:
            best_rr = rr
            best = {
                "ticker": ticker,
                "structure": "bear_put_debit_spread",
                "direction": "BEARISH",
                "current_price": round(float(current_price), 2),
                "expiration": expiry,
                "dte": longp["dte"],
                "long_leg": _leg(longp),
                "short_leg": _leg(shortp),
                "net_debit": round(net_debit, 2),
                "limit_price": round(net_debit, 2),
                "order": "BUY_TO_OPEN net debit",
                "width": round(width, 2),
                "max_loss_per_spread": round(max_loss, 2),
                "max_profit_per_spread": round(max_profit, 2),
                "breakeven": round(breakeven, 2),
                "breakeven_pct_move": round((breakeven - current_price) / current_price * 100, 2),
                "risk_reward_ratio": round(rr, 2),
                "fetched_at": chain["fetched_at"],
            }
    return best


def suggest_bear_call_credit_spread(ticker, current_price, dte_min=30, dte_max=45,
                                    short_delta=0.35, long_delta=0.20):
    chain = _pull_chain(ticker, "call", current_price, dte_min, dte_max)
    if not chain or not chain["by_exp"]:
        return None
    best = None
    best_rr = -1.0
    for expiry, contracts in chain["by_exp"].items():
        shortc = _closest(contracts, short_delta, 0.28, 0.45)
        if not shortc:
            continue
        longc = _closest([c for c in contracts if c["strike"] > shortc["strike"]], long_delta, 0.10, 0.30)
        if not longc:
            continue
        net_credit = shortc["mid"] - longc["mid"]
        width = longc["strike"] - shortc["strike"]
        if net_credit <= 0 or width <= 0:
            continue
        max_profit = net_credit * 100
        max_loss = (width - net_credit) * 100
        if max_loss <= 0:
            continue
        breakeven = shortc["strike"] + net_credit
        rr = max_profit / max_loss
        if rr > best_rr:
            best_rr = rr
            best = {
                "ticker": ticker,
                "structure": "bear_call_credit_spread",
                "direction": "BEARISH",
                "current_price": round(float(current_price), 2),
                "expiration": expiry,
                "dte": shortc["dte"],
                "short_leg": _leg(shortc),
                "long_leg": _leg(longc),
                "net_credit": round(net_credit, 2),
                "limit_price": round(net_credit, 2),
                "order": "SELL_TO_OPEN net credit",
                "width": round(width, 2),
                "max_profit_per_spread": round(max_profit, 2),
                "max_loss_per_spread": round(max_loss, 2),
                "breakeven": round(breakeven, 2),
                "breakeven_pct_move": round((breakeven - current_price) / current_price * 100, 2),
                "risk_reward_ratio": round(rr, 2),
                "fetched_at": chain["fetched_at"],
            }
    return best
