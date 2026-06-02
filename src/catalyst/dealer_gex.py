"""DIY Dealer Gamma Exposure (GEX) Calculator.

Options dealers take the other side of every retail and institutional
options trade. Their hedging behavior determines whether moves get
amplified or suppressed.

Standard model:
  - Dealers SHORT CALLS (retail buys calls) -> dealer is short gamma on calls
  - Dealers LONG PUTS (institutions buy puts as hedges) -> dealer is long gamma on puts
  - Net dealer gamma per strike = puts_gamma_OI - calls_gamma_OI (scaled)

When NET GAMMA is NEGATIVE: dealers must BUY into rallies + SELL into dips
to delta-hedge -> AMPLIFICATION regime (big moves)

When NET GAMMA is POSITIVE: dealers SELL into rallies + BUY into dips
-> PINNING regime (price gets pulled toward zero-gamma strike)

The zero-gamma flip strike is where net dealer gamma = 0. Spot above flip
= positive gamma regime. Spot below = negative gamma. The flip strike
acts as actual support/resistance.

Free data: Alpaca options chain (we already pull these).
"""

import math
from datetime import datetime, timedelta


def _norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def black_scholes_gamma(spot, strike, days_to_expiry, iv_pct, risk_free=0.045):
    """Compute Black-Scholes gamma per share."""
    try:
        S = float(spot)
        K = float(strike)
        T = max(float(days_to_expiry) / 365.0, 1.0 / 365.0)
        sigma = max(float(iv_pct) / 100.0, 0.01)
        r = float(risk_free)
        if S <= 0 or K <= 0 or sigma <= 0:
            return 0
        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
        gamma = _norm_pdf(d1) / (S * sigma * math.sqrt(T))
        return gamma
    except Exception:
        return 0


def _fetch_full_chain(ticker, spot):
    """Pull both call and put chains via Alpaca."""
    chains = {"call": [], "put": []}
    try:
        from src.alpaca_options import get_options_chain_full
        for side in ("call", "put"):
            chain = get_options_chain_full(ticker, side=side, spot=spot)
            if isinstance(chain, list):
                chains[side] = chain
            elif isinstance(chain, dict) and chain.get("contracts"):
                chains[side] = chain["contracts"]
    except Exception:
        pass
    return chains


def compute_dealer_gex(ticker, spot=None, verbose=False):
    """Compute net dealer gamma exposure per strike + identify regime + flip strike."""
    if spot is None:
        try:
            from src.alpaca_options import get_live_price
            spot = get_live_price(ticker)
        except Exception:
            spot = None
    if not spot:
        return None

    chains = _fetch_full_chain(ticker, spot)
    call_chain = chains.get("call") or []
    put_chain = chains.get("put") or []
    if not call_chain and not put_chain:
        return None

    today = datetime.utcnow().date()
    gex_by_strike = {}

    for side, contracts in (("call", call_chain), ("put", put_chain)):
        for c in contracts:
            try:
                strike = float(c.get("strike") or 0)
                oi = float(c.get("open_interest") or c.get("oi") or 0)
                iv = float(c.get("iv") or c.get("iv_pct") or c.get("implied_volatility") or 0)
                expiry_str = c.get("expiration") or c.get("expiry") or ""
                if iv > 5:
                    iv = iv * 100 if iv < 5 else iv
            except Exception:
                continue
            if strike <= 0 or oi <= 0 or iv <= 0:
                continue
            try:
                exp = datetime.strptime(expiry_str, "%Y-%m-%d").date()
                dte = max((exp - today).days, 0)
            except Exception:
                continue
            if dte <= 0 or dte > 365:
                continue

            gamma_per_share = black_scholes_gamma(spot, strike, dte, iv)
            gamma_exposure = gamma_per_share * oi * 100 * spot
            if side == "call":
                contribution = -gamma_exposure
            else:
                contribution = +gamma_exposure
            gex_by_strike.setdefault(strike, 0.0)
            gex_by_strike[strike] += contribution

    if not gex_by_strike:
        return None

    sorted_strikes = sorted(gex_by_strike.keys())
    cumulative = []
    running = 0.0
    for k in sorted_strikes:
        running += gex_by_strike[k]
        cumulative.append((k, running))

    net_total = cumulative[-1][1]
    flip_strike = None
    for i in range(1, len(cumulative)):
        prev_k, prev_c = cumulative[i - 1]
        curr_k, curr_c = cumulative[i]
        if (prev_c < 0 < curr_c) or (prev_c > 0 > curr_c):
            if (curr_c - prev_c) != 0:
                flip_strike = prev_k + (curr_k - prev_k) * (-prev_c) / (curr_c - prev_c)
            else:
                flip_strike = curr_k
            break
    if flip_strike is None:
        flip_strike = cumulative[len(cumulative) // 2][0]

    if spot < flip_strike:
        regime = "NEGATIVE_AMP"
        label = f"spot ${spot:.2f} BELOW flip ${flip_strike:.2f} = negative gamma, amplification regime"
    else:
        regime = "POSITIVE_PIN"
        label = f"spot ${spot:.2f} ABOVE flip ${flip_strike:.2f} = positive gamma, pinning regime"

    top_calls = sorted([(k, v) for k, v in gex_by_strike.items() if v < 0], key=lambda x: x[1])[:3]
    top_puts = sorted([(k, v) for k, v in gex_by_strike.items() if v > 0], key=lambda x: -x[1])[:3]

    result = {
        "ticker": ticker,
        "spot": round(spot, 2),
        "flip_strike": round(flip_strike, 2),
        "net_gex": round(net_total, 0),
        "regime": regime,
        "label": label,
        "top_call_walls": [{"strike": k, "gex": round(v, 0)} for k, v in top_calls],
        "top_put_walls": [{"strike": k, "gex": round(v, 0)} for k, v in top_puts],
        "strikes_analyzed": len(gex_by_strike),
    }

    if verbose:
        print(f"  dealer_gex {ticker}: {regime} flip=${flip_strike:.2f} net={net_total:.0f} ({len(gex_by_strike)} strikes)")
    return result


def enrich_picks_with_gex(picks, max_picks=15, verbose=False):
    if not picks:
        return picks
    amp_count = 0
    pin_count = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        spot = p.get("live_spot") or p.get("price")
        if not spot:
            continue
        try:
            res = compute_dealer_gex(ticker, spot=float(spot), verbose=False)
        except Exception:
            continue
        if res:
            p["_dealer_gex"] = res
            if res["regime"] == "NEGATIVE_AMP":
                amp_count += 1
            else:
                pin_count += 1
    if verbose:
        print(f"  dealer_gex: {amp_count} amplification, {pin_count} pinning")
    return picks


def get_index_gex_snapshot(verbose=False):
    """Compute GEX for SPY/QQQ/IWM for market-regime context."""
    snapshot = {}
    for ticker in ("SPY", "QQQ", "IWM"):
        try:
            res = compute_dealer_gex(ticker, verbose=verbose)
            if res:
                snapshot[ticker] = res
        except Exception:
            continue
    return snapshot
