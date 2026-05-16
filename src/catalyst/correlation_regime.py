import math
from datetime import datetime, timedelta


def compute_correlation_regime(eodhd_client, lookback_days=30):
    sample_tickers = [
        "SPY.US", "QQQ.US", "AAPL.US", "MSFT.US", "GOOG.US",
        "AMZN.US", "META.US", "NVDA.US", "XLF.US", "XLE.US",
        "XLK.US", "XLV.US", "IWM.US", "VTV.US", "VUG.US",
    ]

    end_dt = datetime.utcnow().date()
    start_dt = end_dt - timedelta(days=lookback_days + 10)

    returns_by_ticker = {}
    for t in sample_tickers:
        try:
            bars = eodhd_client.ohlcv(t, from_date=start_dt.strftime("%Y-%m-%d"), to_date=end_dt.strftime("%Y-%m-%d")) or []
            closes = []
            for b in bars[-lookback_days - 1:]:
                try:
                    closes.append(float(b.get("close")))
                except Exception:
                    continue
            if len(closes) < 10:
                continue
            rets = []
            for i in range(1, len(closes)):
                if closes[i - 1] > 0:
                    rets.append(math.log(closes[i] / closes[i - 1]))
            if len(rets) >= 10:
                returns_by_ticker[t] = rets
        except Exception:
            continue

    if len(returns_by_ticker) < 5:
        return None

    spy_rets = returns_by_ticker.get("SPY.US")
    if not spy_rets:
        return None

    correlations = []
    for ticker, rets in returns_by_ticker.items():
        if ticker == "SPY.US":
            continue
        n = min(len(spy_rets), len(rets))
        if n < 10:
            continue
        spy_slice = spy_rets[-n:]
        ticker_slice = rets[-n:]
        c = _correlation(spy_slice, ticker_slice)
        if c is not None:
            correlations.append(c)

    if not correlations:
        return None

    avg_corr = sum(correlations) / len(correlations)
    max_corr = max(correlations)

    if avg_corr >= 0.85:
        regime = "EXTREME"
        note = f"Avg corr to SPY {avg_corr:.2f} - everything moves together, macro dominates"
    elif avg_corr >= 0.70:
        regime = "HIGH"
        note = f"Avg corr {avg_corr:.2f} - elevated, single-name alpha muted"
    elif avg_corr >= 0.50:
        regime = "MEDIUM"
        note = f"Avg corr {avg_corr:.2f} - normal, stock-picking edge available"
    else:
        regime = "LOW"
        note = f"Avg corr {avg_corr:.2f} - dispersion regime, ideal for catalysts"

    return {
        "avg_correlation": round(avg_corr, 2),
        "max_correlation": round(max_corr, 2),
        "regime": regime,
        "note": note,
        "n_samples": len(correlations),
    }


def _correlation(xs, ys):
    if not xs or not ys or len(xs) != len(ys):
        return None
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    denom_x = math.sqrt(sum((xs[i] - mx) ** 2 for i in range(n)))
    denom_y = math.sqrt(sum((ys[i] - my) ** 2 for i in range(n)))
    if denom_x == 0 or denom_y == 0:
        return None
    return num / (denom_x * denom_y)
