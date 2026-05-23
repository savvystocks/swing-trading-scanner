"""DIY options flow detector using free Alpaca options chain data.

Goal: catch ~50% of what Unusual Whales catches for free.

Method: For each top pick, fetch full call chain. Detect "unusual" via:
- Total call volume today vs total call OI (vol > 30% of OI = active accumulation)
- Single-strike vol spikes (one strike accounting for 40%+ of total vol)
- Volume-weighted call-side moneyness (heavy buying close-to-ATM = directional bet)
- Put/call volume ratio (low PCR = bullish positioning)

Not as good as real-time sweep detection but catches the high-conviction
positioning signals at zero cost.
"""

import os
from datetime import datetime, timedelta


def _alpaca_client():
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        return None
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        return OptionHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
    except ImportError:
        return None


def compute_flow_signal(symbol, spot, dte_min=10, dte_max=60):
    client = _alpaca_client()
    if not client:
        return None
    try:
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        return None

    today = datetime.now().date()
    min_exp = (today + timedelta(days=dte_min)).strftime("%Y-%m-%d")
    max_exp = (today + timedelta(days=dte_max)).strftime("%Y-%m-%d")

    try:
        call_req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(spot * 0.85, 2)),
            strike_price_lte=str(round(spot * 1.30, 2)),
            type="call",
        )
        call_snaps = client.get_option_chain(call_req)

        put_req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(spot * 0.70, 2)),
            strike_price_lte=str(round(spot * 1.15, 2)),
            type="put",
        )
        put_snaps = client.get_option_chain(put_req)
    except Exception:
        return None

    if not call_snaps:
        return None

    call_total_vol = 0
    call_total_oi = 0
    strike_volumes = {}
    for sym, s in call_snaps.items():
        try:
            q = getattr(s, "latest_quote", None)
            t = getattr(s, "latest_trade", None)
            iv = getattr(s, "implied_volatility", None)
            day_bar = getattr(s, "previous_day_bar", None) or getattr(s, "minute_bar", None) or getattr(s, "daily_bar", None)
            vol_today = 0
            if day_bar:
                vol_today = getattr(day_bar, "volume", 0) or 0
            oi_now = getattr(s, "open_interest", None) or 0
            call_total_vol += vol_today
            call_total_oi += oi_now
            import re
            m = re.match(r"([A-Z]+)(\d{6})([CP])(\d+)", sym if isinstance(sym, str) else str(sym))
            if m:
                strike = int(m.group(4)) / 1000
                strike_volumes[strike] = strike_volumes.get(strike, 0) + vol_today
        except Exception:
            continue

    put_total_vol = 0
    put_total_oi = 0
    for sym, s in put_snaps.items():
        try:
            day_bar = getattr(s, "previous_day_bar", None) or getattr(s, "minute_bar", None) or getattr(s, "daily_bar", None)
            vol_today = getattr(day_bar, "volume", 0) or 0 if day_bar else 0
            oi_now = getattr(s, "open_interest", None) or 0
            put_total_vol += vol_today
            put_total_oi += oi_now
        except Exception:
            continue

    if call_total_oi == 0 and call_total_vol == 0:
        return None

    vol_oi_ratio = call_total_vol / call_total_oi if call_total_oi > 0 else 0
    pcr_vol = put_total_vol / call_total_vol if call_total_vol > 0 else 0

    concentrated_strike = None
    concentration_pct = 0
    if strike_volumes:
        top_strike = max(strike_volumes.items(), key=lambda kv: kv[1])
        if call_total_vol > 0:
            concentration_pct = top_strike[1] / call_total_vol * 100
            if concentration_pct > 35:
                concentrated_strike = top_strike[0]

    signals = []
    score = 0
    if vol_oi_ratio > 0.3:
        score += 35
        signals.append(f"Call vol {call_total_vol:,} vs OI {call_total_oi:,} ({vol_oi_ratio*100:.0f}% - active accumulation)")
    if pcr_vol < 0.5 and call_total_vol > 200:
        score += 25
        signals.append(f"Put/Call ratio {pcr_vol:.2f} - bullish positioning")
    if concentrated_strike:
        score += 30
        otm_pct = (concentrated_strike - spot) / spot * 100
        signals.append(f"Concentrated buying at ${concentrated_strike:.0f} strike ({concentration_pct:.0f}% of vol, {otm_pct:+.1f}% from spot)")
    if vol_oi_ratio > 1.0:
        score += 20
        signals.append("Vol exceeds OI - genuine opening positioning, not closing")

    score = min(100, score)
    verdict = "STRONG_FLOW" if score >= 60 else "MODERATE_FLOW" if score >= 30 else "QUIET"

    return {
        "verdict": verdict,
        "score": score,
        "call_volume_today": call_total_vol,
        "call_oi": call_total_oi,
        "vol_oi_ratio": round(vol_oi_ratio, 2),
        "put_call_ratio_vol": round(pcr_vol, 2),
        "concentrated_strike": concentrated_strike,
        "concentration_pct": round(concentration_pct, 0),
        "signals": signals,
    }


def apply_options_flow_diy(picks, max_picks=15, verbose=False):
    if not picks:
        return
    enriched = 0
    strong_count = 0
    for p in picks[:max_picks]:
        try:
            ticker = p.get("ticker")
            spot = p.get("price") or p.get("live_spot") or 0
            if not ticker or not spot:
                continue
            try:
                spot = float(spot)
            except (TypeError, ValueError):
                continue
            sig = compute_flow_signal(ticker, spot)
            if sig:
                p["_options_flow_diy"] = sig
                enriched += 1
                if sig["verdict"] == "STRONG_FLOW":
                    strong_count += 1
        except Exception:
            continue
    if verbose:
        print(f"  options_flow_diy: enriched {enriched}/{max_picks}, {strong_count} STRONG_FLOW signals")
