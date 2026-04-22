from src.alpaca_options import get_options_chain, get_live_price, get_iv_skew_and_uoa
from src.iv_metrics import vol_rank, options_interpretation


def _estimate_option_value_at_target(contract, stock_price_now, stock_price_at_target):
    strike = contract["strike"]
    mid = contract["mid"]
    dte = contract["dte"]

    intrinsic_now = max(0, stock_price_now - strike)
    extrinsic_now = max(0, mid - intrinsic_now)

    days_held_est = min(28, max(7, dte - 7))
    remaining_dte = max(1, dte - days_held_est)
    time_decay_factor = (remaining_dte / dte) ** 0.5
    extrinsic_at_target = extrinsic_now * time_decay_factor

    intrinsic_at_target = max(0, stock_price_at_target - strike)
    return intrinsic_at_target + extrinsic_at_target


def suggest_options_trade(ticker, phase1_target, current_price=None, df_ind=None):
    if not ticker.endswith(".US"):
        print(f"  [options {ticker}] SKIP: not a .US ticker")
        return None

    underlying = ticker.replace(".US", "")

    if current_price is None:
        live = get_live_price(underlying)
        current_price = live if live else current_price
    if current_price is None:
        print(f"  [options {underlying}] SKIP: no current_price available")
        return None

    contract = get_options_chain(underlying, "call", current_price)
    if not contract:
        return None

    vr = vol_rank(df_ind) if df_ind is not None else None
    interp = options_interpretation(vr["vol_rank_pct"]) if vr else "unknown"
    skew = get_iv_skew_and_uoa(underlying, current_price)

    mid = contract["mid"]
    strike = contract["strike"]
    breakeven = strike + mid
    breakeven_pct = (breakeven - current_price) / current_price * 100

    value_at_target = _estimate_option_value_at_target(contract, current_price, phase1_target)
    contracts_per_100_shares = 1
    cost_per_contract = mid * 100
    profit_per_contract = (value_at_target - mid) * 100
    roi_pct = (value_at_target - mid) / mid * 100 if mid > 0 else 0

    iv = contract.get("impliedVol", 0)
    iv_pct = iv * 100 if iv and iv < 5 else iv

    return {
        "underlying": underlying,
        "current_price": float(current_price),
        "strike": float(strike),
        "expiration": contract["expiration"],
        "dte": contract["dte"],
        "delta": contract["delta"],
        "theta": contract["theta"],
        "iv_pct": round(iv_pct, 1) if iv_pct else None,
        "premium_mid": float(mid),
        "bid": contract.get("bid"),
        "ask": contract.get("ask"),
        "spread_pct": contract.get("spread_pct"),
        "open_interest": contract.get("openInterest"),
        "cost_per_contract": round(cost_per_contract, 2),
        "breakeven": round(breakeven, 2),
        "breakeven_pct_move": round(breakeven_pct, 2),
        "projected_value_at_target": round(value_at_target, 2),
        "projected_roi_pct": round(roi_pct, 0),
        "profit_per_contract_at_target": round(profit_per_contract, 2),
        "vol_rank": vr,
        "vol_interpretation": interp,
        "iv_skew": skew,
    }
