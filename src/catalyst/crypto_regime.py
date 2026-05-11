def fetch_crypto_regime(client):
    out = {"regime": "unknown", "btc_7d_pct": None, "btc_30d_pct": None, "eth_7d_pct": None}
    for symbol, label in (("BTC-USD.CC", "btc"), ("ETH-USD.CC", "eth")):
        try:
            bars = client.ohlcv(symbol)
            if not bars or len(bars) < 31:
                continue
            last = float(bars[-1].get("close") or 0)
            d7 = float(bars[-8].get("close") or 0) if len(bars) >= 8 else 0
            d30 = float(bars[-31].get("close") or 0) if len(bars) >= 31 else 0
            if last and d7:
                out[f"{label}_7d_pct"] = round((last - d7) / d7 * 100, 2)
            if last and d30:
                out[f"{label}_30d_pct"] = round((last - d30) / d30 * 100, 2)
            out[f"{label}_price"] = last
        except Exception:
            continue
    btc7 = out.get("btc_7d_pct") or 0
    eth7 = out.get("eth_7d_pct") or 0
    if btc7 >= 8 or eth7 >= 10:
        out["regime"] = "HOT"
    elif btc7 >= 3 or eth7 >= 5:
        out["regime"] = "BULLISH"
    elif btc7 <= -8 or eth7 <= -10:
        out["regime"] = "COLD"
    elif btc7 <= -3 or eth7 <= -5:
        out["regime"] = "BEARISH"
    else:
        out["regime"] = "NEUTRAL"
    return out


def apply_crypto_regime_boost(scored_results, crypto_regime, crypto_cohort_tickers):
    if not crypto_regime or crypto_regime["regime"] in ("NEUTRAL", "unknown"):
        return scored_results
    regime = crypto_regime["regime"]
    score_delta = 0
    if regime == "HOT":
        score_delta = 6
        label_prefix = "crypto HOT"
    elif regime == "BULLISH":
        score_delta = 3
        label_prefix = "crypto bullish"
    elif regime == "BEARISH":
        score_delta = -3
        label_prefix = "crypto bearish"
    elif regime == "COLD":
        score_delta = -6
        label_prefix = "crypto COLD"
    else:
        return scored_results
    cohort_set = set(t.upper() for t in (crypto_cohort_tickers or []))
    for s in scored_results:
        ticker = (s.get("ticker") or "").upper()
        if ticker not in cohort_set:
            continue
        components = s.get("components") or {}
        components["crypto_regime"] = {
            "points": score_delta,
            "label": f"{label_prefix}: BTC {crypto_regime.get('btc_7d_pct', 'n/a')}%/7d, ETH {crypto_regime.get('eth_7d_pct', 'n/a')}%/7d",
        }
        s["components"] = components
        s["score"] = round((s.get("score") or 0) + score_delta, 2)
    return scored_results
