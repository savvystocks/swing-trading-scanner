import pandas as pd
from src.indicators import to_dataframe

GICS_TO_ETF = {
    "Technology": ("XLK.US", "Technology"),
    "Financial Services": ("XLF.US", "Financials"),
    "Financials": ("XLF.US", "Financials"),
    "Healthcare": ("XLV.US", "Healthcare"),
    "Health Care": ("XLV.US", "Healthcare"),
    "Industrials": ("XLI.US", "Industrials"),
    "Energy": ("XLE.US", "Energy"),
    "Consumer Cyclical": ("XLY.US", "Consumer Cyclical"),
    "Consumer Discretionary": ("XLY.US", "Consumer Cyclical"),
    "Consumer Defensive": ("XLP.US", "Consumer Staples"),
    "Consumer Staples": ("XLP.US", "Consumer Staples"),
    "Utilities": ("XLU.US", "Utilities"),
    "Real Estate": ("XLRE.US", "Real Estate"),
    "Basic Materials": ("XLB.US", "Materials"),
    "Materials": ("XLB.US", "Materials"),
    "Communication Services": ("XLC.US", "Communication Services"),
}


def _pct_return(series, days_back):
    if len(series) < days_back + 1:
        return None
    start = series.iloc[-(days_back + 1)]
    end = series.iloc[-1]
    if not start:
        return None
    return (end - start) / start * 100


def _outlook(rs_vs_spy, stage, ret_3m):
    if rs_vs_spy is None:
        return "NEUTRAL"
    if rs_vs_spy >= 5 and (ret_3m is None or ret_3m > 0):
        return "LEADING"
    if rs_vs_spy >= 2:
        return "STRONG"
    if rs_vs_spy >= -2:
        return "NEUTRAL"
    if rs_vs_spy >= -5:
        return "LAGGING"
    return "WEAK"


def fetch_sector_performance(client, spy_df, from_date):
    spy_close = spy_df["close"]
    spy_1m = _pct_return(spy_close, 21)

    unique_etfs = {}
    for gics, (etf, short) in GICS_TO_ETF.items():
        if etf not in unique_etfs:
            unique_etfs[etf] = short

    rows = []
    for etf, short_name in unique_etfs.items():
        try:
            ohlcv = client.ohlcv(etf, from_date=from_date)
            if not ohlcv or len(ohlcv) < 60:
                continue
            df = to_dataframe(ohlcv)
            close = df["close"]

            ret_1d = _pct_return(close, 1)
            ret_5d = _pct_return(close, 5)
            ret_1m = _pct_return(close, 21)
            ret_3m = _pct_return(close, 63)
            rs_vs_spy = (ret_1m - spy_1m) if (ret_1m is not None and spy_1m is not None) else None

            sma_50 = close.rolling(50, min_periods=50).mean()
            sma_150 = close.rolling(150, min_periods=150).mean()
            last_close = float(close.iloc[-1])

            sma_50_now = float(sma_50.iloc[-1]) if not pd.isna(sma_50.iloc[-1]) else None
            sma_150_now = float(sma_150.iloc[-1]) if not pd.isna(sma_150.iloc[-1]) else None

            if sma_150_now is None or sma_50_now is None:
                stage = None
            else:
                above_150 = last_close > sma_150_now
                golden = sma_50_now > sma_150_now
                if above_150 and golden:
                    stage = 2
                elif above_150 and not golden:
                    stage = 3
                elif not above_150 and not golden:
                    stage = 4
                else:
                    stage = 1

            outlook = _outlook(rs_vs_spy, stage, ret_3m)

            rows.append({
                "sector": short_name,
                "etf": etf,
                "ret_1d": ret_1d,
                "ret_5d": ret_5d,
                "ret_1m": ret_1m,
                "ret_3m": ret_3m,
                "rs_vs_spy": rs_vs_spy,
                "stage": stage,
                "outlook": outlook,
            })
        except Exception:
            continue

    rs_order = {"LEADING": 0, "STRONG": 1, "NEUTRAL": 2, "LAGGING": 3, "WEAK": 4}
    rows.sort(key=lambda r: (rs_order.get(r["outlook"], 99), -(r["rs_vs_spy"] or -99)))
    return rows
