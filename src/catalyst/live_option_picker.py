import os
import re
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def find_best_call(symbol, spot, dte_min=25, dte_max=50):
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        return None
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        return None

    client = OptionHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    today = datetime.now()
    min_exp = (today + timedelta(days=dte_min)).strftime("%Y-%m-%d")
    max_exp = (today + timedelta(days=dte_max)).strftime("%Y-%m-%d")

    try:
        req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(spot * 0.85, 2)),
            strike_price_lte=str(round(spot * 1.35, 2)),
            type="call",
        )
        snaps = client.get_option_chain(req)
    except Exception as e:
        logger.warning(f"Alpaca option chain {symbol}: {e}")
        return None

    if not snaps:
        return None

    rows = []
    for sym, s in snaps.items():
        try:
            g = s.greeks
            q = s.latest_quote
            if not g or not q or not g.delta:
                continue
            bid = float(q.bid_price) if q.bid_price else 0
            ask = float(q.ask_price) if q.ask_price else 0
            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
            if mid <= 0.05:
                continue
            delta = abs(float(g.delta))
            if delta < 0.18 or delta > 0.65:
                continue
            spread_pct = ((ask - bid) / mid * 100) if mid > 0 else 100
            if spread_pct > 60:
                continue
            m = re.match(r"([A-Z]+)(\d{6})([CP])(\d+)", sym if isinstance(sym, str) else str(sym))
            if not m:
                continue
            exp_raw = m.group(2)
            strike = int(m.group(4)) / 1000
            exp = f"20{exp_raw[:2]}-{exp_raw[2:4]}-{exp_raw[4:6]}"
            iv = getattr(s, "implied_volatility", None) or getattr(g, "implied_volatility", 0) or 0
            rows.append({
                "strike": strike,
                "exp": exp,
                "delta": round(delta, 3),
                "iv_pct": round(float(iv) * 100, 1) if iv else None,
                "mid": round(mid, 2),
                "bid": round(bid, 2),
                "ask": round(ask, 2),
                "spread_pct": round(spread_pct, 1),
                "gamma": round(abs(float(g.gamma)), 4) if g.gamma else 0,
                "theta": round(float(g.theta), 4) if g.theta else 0,
                "vega": round(float(g.vega), 4) if g.vega else 0,
            })
        except Exception:
            continue

    if not rows:
        return None

    rows.sort(key=lambda r: abs(r["delta"] - 0.35))
    return rows[0]


def _estimate_iv_crush_points(current_iv_pct, has_earnings_imminent, has_earnings_lead_up, has_general_catalyst):
    if current_iv_pct is None or current_iv_pct <= 0:
        return 0.0
    if has_earnings_imminent:
        crush = min(current_iv_pct * 0.45, 45.0)
        return -crush
    if has_earnings_lead_up:
        crush = min(current_iv_pct * 0.15, 12.0)
        return -crush
    if has_general_catalyst:
        crush = min(current_iv_pct * 0.08, 6.0)
        return -crush
    return -min(current_iv_pct * 0.03, 2.0)


def project_outcomes(option, spot, scenarios=(5, 8, 12, 15, 20), has_earnings_imminent=False, has_earnings_lead_up=False, has_general_catalyst=False):
    mid = option["mid"]
    strike = option["strike"]
    delta = option["delta"]
    gamma = option.get("gamma", 0)
    vega = option.get("vega", 0)
    current_iv = option.get("iv_pct", 0) or 0

    iv_change_pts = _estimate_iv_crush_points(
        current_iv,
        has_earnings_imminent,
        has_earnings_lead_up,
        has_general_catalyst,
    )
    iv_crush_pnl = vega * iv_change_pts

    out = []
    for pct in scenarios:
        new_spot = spot * (1 + pct / 100)
        underlying_move = new_spot - spot
        delta_pnl = delta * underlying_move
        gamma_pnl = 0.5 * gamma * (underlying_move ** 2)
        new_option_value = mid + delta_pnl + gamma_pnl + iv_crush_pnl
        intrinsic = max(0, new_spot - strike)
        new_option_value = max(new_option_value, intrinsic * 0.92)
        new_option_value = max(0.01, new_option_value)
        return_pct = (new_option_value - mid) / mid * 100
        out.append({
            "underlying_pct": pct,
            "new_spot": round(new_spot, 2),
            "new_option": round(new_option_value, 2),
            "return_pct": round(return_pct, 0),
        })
    return out, {
        "iv_change_pts": round(iv_change_pts, 1),
        "iv_dollar_impact": round(iv_crush_pnl, 2),
        "scenario_label": (
            "earnings IV crush priced in (~45% IV reduction)" if has_earnings_imminent
            else "modest IV decay priced in (~15% reduction)" if has_earnings_lead_up
            else "light IV softening priced in (~8% reduction)" if has_general_catalyst
            else "minimal IV change (no event ahead)"
        ),
    }


def build_trade_line(ticker, spot, option):
    if not option:
        return None
    pct_to_strike = ((option["strike"] - spot) / spot * 100)
    return (
        f"Buy {ticker} ${option['strike']:.0f}C exp {option['exp']} @ ${option['mid']:.2f} mid "
        f"(bid ${option['bid']:.2f}/ask ${option['ask']:.2f}) "
        f"· d {option['delta']:.2f} · IV {option['iv_pct']}% "
        f"· strike {pct_to_strike:+.1f}% OTM"
    )


def build_outcome_table(option, spot):
    if not option:
        return []
    return project_outcomes(option, spot)
