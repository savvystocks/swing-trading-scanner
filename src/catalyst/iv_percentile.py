import os
from datetime import datetime, timedelta


def fetch_iv_percentile(symbol, current_iv, lookback_days=252):
    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not api_secret or not current_iv or current_iv <= 0:
        return None
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
    except ImportError:
        return None

    try:
        client = StockHistoricalDataClient(api_key, api_secret)
        end = datetime.now()
        start = end - timedelta(days=lookback_days + 30)
        req = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        bars = client.get_stock_bars(req)
    except Exception:
        return None

    try:
        df = bars.df
        if df.empty or len(df) < 60:
            return None
        closes = df["close"].values
        returns = []
        for i in range(1, len(closes)):
            if closes[i-1] > 0:
                returns.append((closes[i] - closes[i-1]) / closes[i-1])
        if len(returns) < 30:
            return None
        import math
        rolling_vol = []
        window = 21
        for i in range(window, len(returns)):
            slice_ = returns[i-window:i]
            mean = sum(slice_) / len(slice_)
            var = sum((r - mean) ** 2 for r in slice_) / (len(slice_) - 1)
            rolling_vol.append(math.sqrt(var * 252) * 100)
        if not rolling_vol:
            return None
        sorted_vol = sorted(rolling_vol)
        below = sum(1 for v in sorted_vol if v <= current_iv)
        percentile = (below / len(sorted_vol)) * 100
        realized_30d = rolling_vol[-1] if rolling_vol else None
        return {
            "iv_percentile": round(percentile, 1),
            "realized_vol_30d": round(realized_30d, 1) if realized_30d else None,
            "iv_minus_realized": round(current_iv - realized_30d, 1) if realized_30d else None,
            "interpretation": _interpret(percentile, current_iv, realized_30d),
        }
    except Exception:
        return None


def _interpret(percentile, current_iv, realized):
    if percentile <= 30:
        regime = "COMPRESSED"
        comment = "IV in bottom 30% of 12-mo range — options cheap, asymmetric upside"
    elif percentile <= 60:
        regime = "FAIR"
        comment = "IV mid-range — fair pricing, no edge from vol alone"
    elif percentile <= 85:
        regime = "ELEVATED"
        comment = "IV in top 15-40% — options expensive, IV crush risk material"
    else:
        regime = "PEAK"
        comment = "IV in top 15% — buying here is paying peak premium, sell-vol territory"
    if realized and current_iv:
        diff = current_iv - realized
        if diff < -5:
            comment += f". IV {diff:.0f}pp BELOW realized = market UNDERPRICING vol (edge to buyers)"
        elif diff > 10:
            comment += f". IV {diff:.0f}pp above realized = market OVERPRICING vol (edge to sellers)"
    return {"regime": regime, "comment": comment}


def apply_iv_percentile(candidates, bracket=None, verbose=False):
    enriched = 0
    for s in candidates:
        ticker = s.get("ticker")
        eodhd_ticker = s.get("eodhd_ticker") or ""
        if not eodhd_ticker.endswith(".US") or not ticker:
            continue
        symbol = ticker.replace(".US", "").replace(".LSE", "")
        opts = s.get("options_check") or {}
        current_iv = opts.get("implied_volatility_pct") or opts.get("iv_pct") or opts.get("atm_iv_pct")
        if not current_iv:
            continue
        result = fetch_iv_percentile(symbol, current_iv)
        if result:
            s["iv_percentile_analysis"] = result
            enriched += 1
    if verbose:
        print(f"  iv_percentile: enriched {enriched}/{len(candidates)}")
    return candidates


def iv_passes_bracket_gate(candidate, bracket, tier):
    iv_data = candidate.get("iv_percentile_analysis")
    if not iv_data:
        return True
    percentile = iv_data.get("iv_percentile")
    if percentile is None:
        return True
    if tier == "A++":
        thresholds = {"micro": 50, "small": 55, "mid": 60}
    elif tier == "A+":
        thresholds = {"micro": 60, "small": 65, "mid": 70}
    else:
        thresholds = {"micro": 75, "small": 80, "mid": 85}
    return percentile <= thresholds.get(bracket, 70)
