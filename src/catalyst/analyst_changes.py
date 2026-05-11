def detect_analyst_changes(scored_results):
    out = {}
    for s in scored_results:
        ticker = s.get("ticker")
        if not ticker:
            continue
        eodhd_ticker = s.get("eodhd_ticker") or ""
        if not eodhd_ticker.endswith(".US"):
            continue
        ratings = s.get("analyst_ratings") or {}
        if not ratings:
            continue
        try:
            target = float(ratings.get("TargetPrice") or 0)
            rating_score = float(ratings.get("Rating") or 0)
            strong_buy = int(ratings.get("StrongBuy") or 0)
            buy = int(ratings.get("Buy") or 0)
            hold = int(ratings.get("Hold") or 0)
            sell = int(ratings.get("Sell") or 0)
            strong_sell = int(ratings.get("StrongSell") or 0)
        except (TypeError, ValueError):
            continue
        total = strong_buy + buy + hold + sell + strong_sell
        if total < 3:
            continue
        bullish_pct = (strong_buy + buy) / total * 100 if total else 0
        price = s.get("price") or 0
        upside_pct = ((target - price) / price * 100) if price and target else 0
        signal = None
        details = None
        score_delta = 0
        if bullish_pct >= 80 and upside_pct >= 15:
            signal = "analyst_strong_consensus"
            details = f"{strong_buy}SB+{buy}B of {total} ({bullish_pct:.0f}%), PT ${target:.0f} ({upside_pct:+.0f}%)"
            score_delta = 5
        elif bullish_pct >= 65 and upside_pct >= 10:
            signal = "analyst_bullish_consensus"
            details = f"{strong_buy + buy}/{total} buys, PT ${target:.0f} ({upside_pct:+.0f}% upside)"
            score_delta = 3
        elif strong_sell >= 2 or (sell + strong_sell) > buy:
            signal = "analyst_bearish_consensus"
            details = f"{sell + strong_sell} sells vs {strong_buy + buy} buys"
            score_delta = -5
        if signal:
            out[ticker] = {
                "key": signal,
                "details": details,
                "score_delta": score_delta,
                "rating_score": rating_score,
                "upside_pct": round(upside_pct, 1),
                "direction": "bull" if score_delta > 0 else "bear",
            }
    return out


def apply_analyst_scoring(scored_results, analyst_signals):
    for s in scored_results:
        ticker = s.get("ticker")
        if ticker not in analyst_signals:
            continue
        sig = analyst_signals[ticker]
        components = s.get("components") or {}
        components["analyst_changes"] = {
            "points": sig["score_delta"],
            "label": f"{sig['key'].replace('_', ' ')}: {sig['details']}",
        }
        s["components"] = components
        s["score"] = round((s.get("score") or 0) + sig["score_delta"], 2)
    return scored_results
