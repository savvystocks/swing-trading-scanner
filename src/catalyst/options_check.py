import os
import math
from datetime import datetime, timedelta

ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")


def implied_move(symbol, current_price, days_forward=1):
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        return None
    if not symbol or not current_price or current_price <= 0:
        return None
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        return None
    try:
        client = OptionHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
        today = datetime.now()
        min_exp = (today + timedelta(days=5)).strftime("%Y-%m-%d")
        max_exp = (today + timedelta(days=30)).strftime("%Y-%m-%d")
        chain_req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(current_price * 0.95, 2)),
            strike_price_lte=str(round(current_price * 1.05, 2)),
        )
        snaps = client.get_option_chain(chain_req)
    except Exception:
        return None
    if not snaps:
        return None

    atm_ivs = []
    for sym, s in snaps.items():
        try:
            g = s.greeks
            if not g or g.delta is None:
                continue
            delta_abs = abs(float(g.delta))
            if delta_abs < 0.40 or delta_abs > 0.60:
                continue
            iv_val = getattr(s, "implied_volatility", None) or getattr(g, "implied_volatility", None)
            if iv_val:
                atm_ivs.append(float(iv_val))
        except Exception:
            continue
    if not atm_ivs:
        return None

    atm_iv = sum(atm_ivs) / len(atm_ivs)
    move_pct = atm_iv * math.sqrt(days_forward / 365.0) * 100
    return {
        "atm_iv_pct": round(atm_iv * 100, 1),
        "implied_move_1d_pct": round(move_pct, 2),
        "iv_sample_n": len(atm_ivs),
    }


def options_check_score(buy_signal_data, options_data):
    if not options_data or not buy_signal_data:
        return {"points": 0.0, "label": "no options data", "implied_move_1d_pct": None}

    expected_high = buy_signal_data.get("expected_move_high_pct")
    implied_1d = options_data.get("implied_move_1d_pct")
    if expected_high is None or implied_1d is None or implied_1d <= 0:
        return {"points": 0.0, "label": "options data incomplete", "implied_move_1d_pct": implied_1d}

    ratio = expected_high / implied_1d if implied_1d > 0 else 0
    if ratio > 2.0:
        points = -4.0
        label = f"OVER-OPTIMISTIC: model {expected_high:.1f}% vs options {implied_1d:.1f}% ({ratio:.1f}x)"
        verdict = "over_optimistic"
    elif ratio > 1.5:
        points = -1.5
        label = f"slightly optimistic vs options ({ratio:.1f}x implied)"
        verdict = "slightly_optimistic"
    elif ratio < 0.5:
        points = 2.0
        label = f"conservative vs options ({ratio:.1f}x implied) — room for upside"
        verdict = "conservative"
    else:
        points = 1.0
        label = f"aligned with options ({ratio:.1f}x implied)"
        verdict = "aligned"
    return {
        "points": round(points, 2),
        "label": label,
        "verdict": verdict,
        "implied_move_1d_pct": implied_1d,
        "model_expected_high_pct": expected_high,
        "ratio": round(ratio, 2),
        "atm_iv_pct": options_data.get("atm_iv_pct"),
    }
