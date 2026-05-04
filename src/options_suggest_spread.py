from datetime import datetime, timedelta


def suggest_bull_call_spread(ticker, phase1_target, current_price, df_ind=None, max_cost_usd=1500):
    if not ticker.endswith(".US"):
        return None

    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
    except ImportError:
        return None

    import os
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        return None

    underlying = ticker.replace(".US", "")
    client = OptionHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])

    today = datetime.now()
    min_exp = (today + timedelta(days=21)).strftime("%Y-%m-%d")
    max_exp = (today + timedelta(days=50)).strftime("%Y-%m-%d")

    try:
        req = OptionChainRequest(
            underlying_symbol=underlying,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(current_price * 0.92, 2)),
            strike_price_lte=str(round(current_price * 1.30, 2)),
            type="call",
        )
        snapshots = client.get_option_chain(req)
    except Exception as e:
        print(f"  [spread {underlying}] FAIL: chain error: {type(e).__name__}: {str(e)[:100]}")
        return None

    if not snapshots:
        return None

    contracts_by_exp = {}
    for sym, snap in snapshots.items():
        try:
            q = snap.latest_quote
            g = snap.greeks
            if not q or not g or not q.bid_price or not q.ask_price:
                continue
            bid = float(q.bid_price)
            ask = float(q.ask_price)
            mid = (bid + ask) / 2
            if mid <= 0:
                continue
            delta = float(g.delta) if g.delta is not None else None
            if delta is None:
                continue
            spread_pct = (ask - bid) / mid * 100
            if spread_pct > 25:
                continue
            import re
            m = re.match(rf"{underlying}(\d{{6}})C(\d+)", sym)
            if not m:
                continue
            strike = int(m.group(2)) / 1000
            expiry = datetime.strptime("20" + m.group(1), "%Y%m%d").date()
            dte = (expiry - today.date()).days
            iv = float(snap.implied_volatility) if snap.implied_volatility else None
            theta = float(g.theta) if g.theta else None
            contracts_by_exp.setdefault(str(expiry), []).append({
                "strike": strike,
                "bid": bid,
                "ask": ask,
                "mid": mid,
                "delta": delta,
                "theta": theta,
                "iv": iv,
                "dte": dte,
                "spread_pct": spread_pct,
            })
        except (ValueError, AttributeError):
            continue

    best_spread = None
    best_score = -float("inf")

    for expiry_str, contracts in contracts_by_exp.items():
        contracts.sort(key=lambda c: c["strike"])
        for i, long_leg in enumerate(contracts):
            if long_leg["delta"] < 0.40 or long_leg["delta"] > 0.65:
                continue
            for short_leg in contracts[i+1:]:
                if short_leg["strike"] - long_leg["strike"] < 5:
                    continue
                if short_leg["strike"] - long_leg["strike"] > 30:
                    continue
                if short_leg["delta"] < 0.20 or short_leg["delta"] > 0.40:
                    continue
                net_debit = long_leg["mid"] - short_leg["mid"]
                if net_debit <= 0:
                    continue
                cost = net_debit * 100
                if cost > max_cost_usd:
                    continue
                width = short_leg["strike"] - long_leg["strike"]
                max_profit = (width - net_debit) * 100
                breakeven = long_leg["strike"] + net_debit
                target_price = phase1_target if phase1_target else current_price * 1.20
                if target_price > short_leg["strike"]:
                    profit_at_target = max_profit
                elif target_price > breakeven:
                    profit_at_target = (target_price - breakeven) * 100
                else:
                    profit_at_target = -cost
                roi_at_target = profit_at_target / cost * 100 if cost > 0 else 0
                risk_reward = max_profit / cost if cost > 0 else 0
                score = roi_at_target - (long_leg["spread_pct"] + short_leg["spread_pct"]) * 2
                if score > best_score:
                    best_score = score
                    best_spread = {
                        "underlying": underlying,
                        "structure": "bull_call_spread",
                        "current_price": float(current_price),
                        "expiration": expiry_str,
                        "dte": long_leg["dte"],
                        "long_leg": {
                            "strike": long_leg["strike"],
                            "delta": round(long_leg["delta"], 3),
                            "theta": round(long_leg["theta"], 4) if long_leg["theta"] else None,
                            "mid": round(long_leg["mid"], 2),
                            "bid": round(long_leg["bid"], 2),
                            "ask": round(long_leg["ask"], 2),
                            "spread_pct": round(long_leg["spread_pct"], 1),
                        },
                        "short_leg": {
                            "strike": short_leg["strike"],
                            "delta": round(short_leg["delta"], 3),
                            "theta": round(short_leg["theta"], 4) if short_leg["theta"] else None,
                            "mid": round(short_leg["mid"], 2),
                            "bid": round(short_leg["bid"], 2),
                            "ask": round(short_leg["ask"], 2),
                            "spread_pct": round(short_leg["spread_pct"], 1),
                        },
                        "net_debit": round(net_debit, 2),
                        "cost_per_spread": round(cost, 2),
                        "width": width,
                        "max_profit_per_spread": round(max_profit, 2),
                        "max_loss_per_spread": round(cost, 2),
                        "breakeven": round(breakeven, 2),
                        "breakeven_pct_move": round((breakeven - current_price) / current_price * 100, 2),
                        "risk_reward_ratio": round(risk_reward, 2),
                        "profit_at_target": round(profit_at_target, 2),
                        "roi_at_target_pct": round(roi_at_target, 0),
                        "iv_pct": round(long_leg["iv"] * 100, 1) if long_leg["iv"] else None,
                    }

    return best_spread
