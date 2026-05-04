from src.alpaca_options import get_options_chain, get_live_price, get_iv_skew_and_uoa
from src.iv_metrics import vol_rank, options_interpretation


SHORT_DISQUALIFIERS_SI_PCT = 25.0
SHORT_DISQUALIFIERS_EARNINGS_DAYS = 14
SHORT_DISQUALIFIERS_MCAP_USD = 200_000_000_000
SHORT_DISQUALIFIERS_RSI = 25


def check_short_disqualifiers(short_candidate, fundamentals=None, ind=None):
    fails = []
    if fundamentals:
        si = fundamentals.get("short_pct_float") or fundamentals.get("ShortPercentFloat")
        if si is not None:
            try:
                si_f = float(si)
                if si_f >= SHORT_DISQUALIFIERS_SI_PCT:
                    fails.append(f"high SI {si_f:.0f}% (squeeze risk - skip)")
            except (ValueError, TypeError):
                pass
        mcap = fundamentals.get("market_cap") or fundamentals.get("MarketCapitalization")
        if mcap is not None:
            try:
                mcap_f = float(mcap)
                if mcap_f >= SHORT_DISQUALIFIERS_MCAP_USD:
                    fails.append(f"mega cap ${mcap_f/1e9:.0f}B (avoid shorting)")
            except (ValueError, TypeError):
                pass
        earn = (fundamentals.get("Earnings") or {}).get("History") or {}
        from datetime import datetime
        today = datetime.now().date()
        upcoming_days = None
        for k, v in earn.items():
            rd = v.get("reportDate")
            if rd:
                try:
                    rd_d = datetime.strptime(rd, "%Y-%m-%d").date()
                    if rd_d > today:
                        days = (rd_d - today).days
                        if upcoming_days is None or days < upcoming_days:
                            upcoming_days = days
                except (ValueError, TypeError):
                    pass
        if upcoming_days is not None and upcoming_days <= SHORT_DISQUALIFIERS_EARNINGS_DAYS:
            fails.append(f"earnings in {upcoming_days}d (IV crush risk on puts)")

    if ind is not None and len(ind) >= 14:
        rsi = ind["rsi_14"].iloc[-1] if "rsi_14" in ind.columns else None
        try:
            if rsi is not None and float(rsi) < SHORT_DISQUALIFIERS_RSI:
                fails.append(f"RSI {float(rsi):.0f} (oversold, bounce risk)")
        except (TypeError, ValueError):
            pass

    return fails


def estimate_put_value_at_target(strike, current_premium, current_price, target_price, dte):
    intrinsic_now = max(0, strike - current_price)
    extrinsic_now = max(0, current_premium - intrinsic_now)
    days_held_est = min(28, max(7, dte - 7))
    remaining_dte = max(1, dte - days_held_est)
    time_decay_factor = (remaining_dte / dte) ** 0.5
    extrinsic_at_target = extrinsic_now * time_decay_factor
    intrinsic_at_target = max(0, strike - target_price)
    return intrinsic_at_target + extrinsic_at_target


def suggest_put_trade(ticker, downside_target, current_price=None, df_ind=None, fundamentals=None):
    if not ticker.endswith(".US"):
        print(f"  [puts {ticker}] SKIP: not a .US ticker")
        return None, ["non-US"]

    underlying = ticker.replace(".US", "")

    disq = check_short_disqualifiers({"ticker": ticker}, fundamentals, df_ind)
    if disq:
        print(f"  [puts {underlying}] DISQUALIFIED: {'; '.join(disq)}")
        return None, disq

    if current_price is None:
        live = get_live_price(underlying)
        current_price = live if live else current_price
    if current_price is None:
        print(f"  [puts {underlying}] SKIP: no current_price available")
        return None, ["no current_price"]

    if not downside_target or downside_target >= current_price:
        downside_target = current_price * 0.85
        print(f"  [puts {underlying}] no downside_target supplied, using -15%: ${downside_target:.2f}")

    contract = get_options_chain(underlying, "put", current_price)
    if not contract:
        return None, ["no qualifying contract"]

    vr = vol_rank(df_ind) if df_ind is not None else None
    interp = options_interpretation(vr["vol_rank_pct"]) if vr else "unknown"
    skew = get_iv_skew_and_uoa(underlying, current_price)

    mid = contract["mid"]
    strike = contract["strike"]
    breakeven = strike - mid
    breakeven_pct = (breakeven - current_price) / current_price * 100

    value_at_target = estimate_put_value_at_target(strike, mid, current_price, downside_target, contract["dte"])
    cost_per_contract = mid * 100
    profit_per_contract = (value_at_target - mid) * 100
    roi_pct = (value_at_target - mid) / mid * 100 if mid > 0 else 0

    iv = contract.get("impliedVol", 0)
    iv_pct = iv * 100 if iv and iv < 5 else iv

    return {
        "underlying": underlying,
        "direction": "put",
        "current_price": float(current_price),
        "downside_target": float(downside_target),
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
    }, []
