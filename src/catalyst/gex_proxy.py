"""Cheap Dealer GEX Direction Proxy via IV Skew - Robust Version.

REWRITE HISTORY (2026-06-03):
- v1: Tried open_interest from Alpaca OptionsSnapshot. Field doesn't exist.
- v2: Wrapped src.alpaca_options.get_iv_skew_and_uoa - that function uses strict
      0.20-0.35 delta band which misses most chains where strikes are deep ITM
      or far OTM. Returned None for AAPL, NVDA, AMD.
- v3 (this): Custom skew computation with adaptive delta filtering. Take the
      closest-to-25-delta strike pair available rather than requiring exact band.

How IV skew maps to GEX regime:
  - Put IV >> Call IV by 5%+ = bearish skew = institutions paying for put hedges
                              = POSITIVE_PIN (dealers long puts)
  - Call IV > Put IV by 2%+ = bullish skew = retail bidding calls
                              = NEGATIVE_AMP (dealers short calls)
  - Otherwise = NEUTRAL

Cost: ~200-500ms per ticker × top 300 = ~60-150s extra scan time. Alpaca free.
"""

import os
import re
import logging
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


def _compute_gex_proxy(symbol, current_price):
    """Custom IV skew with adaptive delta selection. Returns regime dict or None."""
    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not secret or not current_price:
        return None

    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        return None

    try:
        client = OptionHistoricalDataClient(api_key, secret)
        today = datetime.now()
        min_exp = (today + timedelta(days=20)).strftime("%Y-%m-%d")
        max_exp = (today + timedelta(days=45)).strftime("%Y-%m-%d")
        chain_req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            # Wide band so we catch the 25-delta wing even on high-vol names
            strike_price_gte=str(round(current_price * 0.75, 2)),
            strike_price_lte=str(round(current_price * 1.25, 2)),
        )
        snaps = client.get_option_chain(chain_req)
    except Exception as e:
        logger.debug(f"gex_proxy chain fetch failed for {symbol}: {e}")
        return None

    if not snaps:
        return None

    # Bucket every contract with both delta and IV
    calls = []  # list of (delta, iv) for calls
    puts = []   # list of (abs_delta, iv) for puts
    for sym, s in snaps.items():
        try:
            m = re.match(r"[A-Z]+\d{6}([CP])\d+", sym if isinstance(sym, str) else str(sym))
            if not m:
                continue
            is_call = m.group(1) == "C"
            g = getattr(s, "greeks", None)
            if g is None:
                continue
            delta = getattr(g, "delta", None)
            if delta is None:
                continue
            iv = getattr(s, "implied_volatility", None)
            if iv is None or iv <= 0:
                continue
            d = float(delta)
            ivf = float(iv)
            if is_call:
                if 0 < d < 1:
                    calls.append((d, ivf))
            else:
                if -1 < d < 0:
                    puts.append((abs(d), ivf))
        except Exception:
            continue

    if not calls or not puts:
        return None

    # Find the closest-to-0.25 delta strike on each side
    target_delta = 0.25
    call_pick = min(calls, key=lambda x: abs(x[0] - target_delta))
    put_pick = min(puts, key=lambda x: abs(x[0] - target_delta))

    call_iv = call_pick[1]
    put_iv = put_pick[1]
    skew_pct = (put_iv - call_iv) * 100

    # Sanity check - if we couldn't get near the 25 delta wing, skip
    # (e.g. if closest available delta is 0.99 the skew is meaningless)
    if abs(call_pick[0] - target_delta) > 0.30 or abs(put_pick[0] - target_delta) > 0.30:
        return None

    # Map to GEX regime
    if skew_pct > 5:
        regime = "POSITIVE_PIN"
        label = (f"IV skew {skew_pct:+.1f}% (25d put IV {put_iv*100:.1f}% vs "
                 f"call IV {call_iv*100:.1f}%) - dealers long puts, pinning")
    elif skew_pct < -2:
        regime = "NEGATIVE_AMP"
        label = (f"IV skew {skew_pct:+.1f}% (25d call IV {call_iv*100:.1f}% vs "
                 f"put IV {put_iv*100:.1f}%) - dealers short calls, amplification")
    else:
        regime = "NEUTRAL"
        label = (f"IV skew {skew_pct:+.1f}% (25d call IV {call_iv*100:.1f}% vs "
                 f"put IV {put_iv*100:.1f}%) - neutral skew")

    return {
        "regime": regime,
        "skew_pct": round(skew_pct, 1),
        "call_iv_pct": round(call_iv * 100, 1),
        "put_iv_pct": round(put_iv * 100, 1),
        "call_delta": round(call_pick[0], 2),
        "put_delta": round(put_pick[0], 2),
        "label": label,
        "_source": "iv_skew_proxy_v3",
    }


def enrich_picks_with_gex_proxy(picks, max_picks=300, verbose=False):
    """Run cheap IV-skew GEX proxy on top N picks.

    Only fills _dealer_gex if NOT already populated (full Black-Scholes runs later
    on top 15 with more precision).
    """
    if not picks:
        return picks

    pool = picks[:max_picks]
    tagged = 0
    skipped_existing = 0
    skipped_no_data = 0
    for p in pool:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        if p.get("_dealer_gex"):
            skipped_existing += 1
            continue
        spot = p.get("price") or (p.get("live_spot"))
        if not spot:
            skipped_no_data += 1
            continue
        try:
            res = _compute_gex_proxy(ticker, spot)
        except Exception:
            res = None
        if res:
            p["_dealer_gex"] = res
            tagged += 1
        else:
            skipped_no_data += 1

    if verbose:
        print(f"  gex_proxy: {tagged} tagged on top {len(pool)} "
              f"({skipped_existing} skipped - had precision GEX, "
              f"{skipped_no_data} skipped - no options/no signal)")
    return picks
