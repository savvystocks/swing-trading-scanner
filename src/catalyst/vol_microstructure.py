import os
import re
import math
from datetime import datetime, timedelta


def compute_realized_vol_30d(eodhd_ticker, eodhd_client):
    try:
        end_dt = datetime.utcnow().date()
        start_dt = end_dt - timedelta(days=70)
        bars = eodhd_client.ohlcv(eodhd_ticker, from_date=start_dt.strftime("%Y-%m-%d"), to_date=end_dt.strftime("%Y-%m-%d")) or []
        if len(bars) < 22:
            return None
        closes = []
        for b in bars[-31:]:
            try:
                closes.append(float(b.get("close")))
            except (TypeError, ValueError):
                continue
        if len(closes) < 22:
            return None
        returns = []
        for i in range(1, len(closes)):
            if closes[i - 1] > 0:
                returns.append(math.log(closes[i] / closes[i - 1]))
        if len(returns) < 21:
            return None
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        annual_vol_pct = math.sqrt(var * 252) * 100
        return round(annual_vol_pct, 1)
    except Exception:
        return None


def pull_skew_data(symbol, spot):
    from src.alpaca_creds import working_creds
    creds = working_creds()
    if not creds:
        return None
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        return None

    today = datetime.now()
    min_exp = (today + timedelta(days=20)).strftime("%Y-%m-%d")
    max_exp = (today + timedelta(days=45)).strftime("%Y-%m-%d")

    try:
        client = OptionHistoricalDataClient(creds[0], creds[1])
        call_req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(spot * 0.85, 2)),
            strike_price_lte=str(round(spot * 1.15, 2)),
            type="call",
        )
        call_snaps = client.get_option_chain(call_req)

        put_req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(spot * 0.85, 2)),
            strike_price_lte=str(round(spot * 1.15, 2)),
            type="put",
        )
        put_snaps = client.get_option_chain(put_req)
    except Exception:
        return None

    call_25d_iv = _find_iv_at_delta(call_snaps, target_delta=0.25, side="call")
    put_25d_iv = _find_iv_at_delta(put_snaps, target_delta=0.25, side="put")
    call_50d_iv = _find_iv_at_delta(call_snaps, target_delta=0.50, side="call")

    if call_25d_iv is None or put_25d_iv is None or call_50d_iv is None:
        return None

    put_call_skew = put_25d_iv - call_25d_iv

    if put_call_skew > 8:
        skew_bias = "bearish"
        bias_note = f"Puts richer by {put_call_skew:.1f} vol pts (institutions hedging downside)"
    elif put_call_skew < -3:
        skew_bias = "bullish"
        bias_note = f"Calls richer by {abs(put_call_skew):.1f} vol pts (institutions positioned long)"
    else:
        skew_bias = "neutral"
        bias_note = f"Skew flat ({put_call_skew:+.1f} vol pts)"

    return {
        "call_25d_iv": round(call_25d_iv, 1),
        "put_25d_iv": round(put_25d_iv, 1),
        "atm_iv": round(call_50d_iv, 1),
        "put_call_skew_pts": round(put_call_skew, 1),
        "skew_bias": skew_bias,
        "bias_note": bias_note,
    }


def _find_iv_at_delta(snaps, target_delta, side="call"):
    if not snaps:
        return None
    candidates = []
    for sym, s in snaps.items():
        try:
            g = s.greeks
            if not g or not g.delta:
                continue
            delta = abs(float(g.delta))
            if not (0.10 < delta < 0.60):
                continue
            iv = getattr(s, "implied_volatility", None) or getattr(g, "implied_volatility", 0) or 0
            if not iv:
                continue
            candidates.append((delta, float(iv) * 100))
        except Exception:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda x: abs(x[0] - target_delta))
    return candidates[0][1]


def realized_vs_implied_signal(realized_vol_pct, iv_atm_pct):
    if realized_vol_pct is None or iv_atm_pct is None:
        return None
    gap = iv_atm_pct - realized_vol_pct
    gap_ratio = iv_atm_pct / realized_vol_pct if realized_vol_pct > 0 else None
    if gap > 25 and gap_ratio and gap_ratio > 1.7:
        verdict = "iv_overpriced_strong"
        note = f"IV {iv_atm_pct:.0f}% >> realized {realized_vol_pct:.0f}% (+{gap:.0f} pts) - options EXPENSIVE, consider selling premium"
    elif gap > 12:
        verdict = "iv_overpriced"
        note = f"IV {iv_atm_pct:.0f}% > realized {realized_vol_pct:.0f}% (+{gap:.0f} pts) - mild premium"
    elif gap < -8:
        verdict = "iv_underpriced"
        note = f"IV {iv_atm_pct:.0f}% < realized {realized_vol_pct:.0f}% ({gap:+.0f} pts) - options CHEAP relative to realized vol"
    else:
        verdict = "fair"
        note = f"IV {iv_atm_pct:.0f}% vs realized {realized_vol_pct:.0f}% ({gap:+.0f} pts) - fairly priced"
    return {
        "realized_vol_pct": realized_vol_pct,
        "iv_atm_pct": iv_atm_pct,
        "gap_pts": round(gap, 1),
        "gap_ratio": round(gap_ratio, 2) if gap_ratio else None,
        "verdict": verdict,
        "note": note,
    }


def apply_vol_microstructure(candidates, eodhd_client=None, verbose=False, max_picks=10):
    if not candidates:
        return
    enriched = 0
    for c in candidates[:max_picks]:
        ticker = c.get("ticker")
        eodhd_ticker = c.get("eodhd_ticker")
        spot = c.get("live_spot") or c.get("price")
        if not ticker or not spot:
            continue
        try:
            spot = float(spot)
        except (TypeError, ValueError):
            continue

        realized = None
        if eodhd_client and eodhd_ticker:
            try:
                realized = compute_realized_vol_30d(eodhd_ticker, eodhd_client)
            except Exception:
                pass

        skew = None
        if ticker:
            try:
                skew = pull_skew_data(ticker, spot)
            except Exception:
                pass

        if skew or realized:
            iv_atm = (skew or {}).get("atm_iv")
            riv = realized_vs_implied_signal(realized, iv_atm) if iv_atm else None
            c["_vol_microstructure"] = {
                "skew": skew,
                "realized_vs_implied": riv,
            }
            enriched += 1

    if verbose:
        print(f"  vol_microstructure: enriched {enriched}/{min(max_picks, len(candidates))} picks with skew + realized/IV")
