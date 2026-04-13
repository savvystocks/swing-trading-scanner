from src.indicators import to_dataframe, sma
from datetime import datetime, timedelta

SECTOR_ETFS = {
    "XLK": "Technology",
    "XLV": "Healthcare",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLE": "Energy",
    "XLY": "Consumer Cyclical",
    "XLP": "Consumer Defensive",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLB": "Materials",
    "XLC": "Communication",
}

BREADTH_LOOKBACK = 420


def compute_market_breadth(client):
    from_date = (datetime.now() - timedelta(days=BREADTH_LOOKBACK)).strftime("%Y-%m-%d")
    above_200 = 0
    above_50 = 0
    advancing_5d = 0
    total = 0

    sectors_detail = []
    for etf, sector_name in SECTOR_ETFS.items():
        try:
            ohlcv = client.ohlcv(f"{etf}.US", from_date=from_date)
            if not ohlcv or len(ohlcv) < 200:
                continue
            df = to_dataframe(ohlcv)
            close = df["close"]
            current = float(close.iloc[-1])
            ma200 = float(sma(close, 200).iloc[-1])
            ma50 = float(sma(close, 50).iloc[-1])
            close_5d_ago = float(close.iloc[-6]) if len(close) >= 6 else current

            total += 1
            if current > ma200:
                above_200 += 1
            if current > ma50:
                above_50 += 1
            if current > close_5d_ago:
                advancing_5d += 1

            sectors_detail.append({
                "etf": etf,
                "sector": sector_name,
                "above_200": current > ma200,
                "above_50": current > ma50,
                "advancing_5d": current > close_5d_ago,
                "ret_5d": round((current - close_5d_ago) / close_5d_ago * 100, 2),
            })
        except Exception:
            continue

    if total == 0:
        return {"regime": "unknown", "score": 0, "sectors": []}

    pct_above_200 = above_200 / total
    pct_above_50 = above_50 / total
    pct_advancing = advancing_5d / total

    if pct_above_200 >= 0.73 and pct_above_50 >= 0.64:
        regime = "strong"
        score = 2
    elif pct_above_200 >= 0.55 and pct_above_50 >= 0.45:
        regime = "healthy"
        score = 1
    elif pct_above_200 >= 0.36:
        regime = "mixed"
        score = 0
    elif pct_above_200 >= 0.18:
        regime = "weak"
        score = -1
    else:
        regime = "bear"
        score = -2

    return {
        "regime": regime,
        "score": score,
        "pct_above_200": round(pct_above_200 * 100, 1),
        "pct_above_50": round(pct_above_50 * 100, 1),
        "pct_advancing_5d": round(pct_advancing * 100, 1),
        "above_200_count": f"{above_200}/{total}",
        "sectors": sectors_detail,
    }
