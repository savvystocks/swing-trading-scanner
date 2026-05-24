"""Macro Regime Detector - daily 0-100 bearish score.

Combines hard macro (CPI, yields, yield curve) from FRED + market internals
(VIX, bank sector, credit ETFs, DXY) from Alpaca/Yahoo. Outputs a single
score where >50 = bearish regime, with specific component breakdown.

FRED is free with no API key needed for the CSV download endpoint.
Alpaca for ETF prices (already in subscription).

Score components (weighted):
- Yield curve un-inversion + 10Y level: 20%
- VIX level + spike: 15%
- Bank sector relative weakness: 15%
- Credit spreads widening: 15%
- DXY strength: 10%
- Defensive sector leadership: 10%
- CPI > 4%: 10%
- Breadth/Russell underperformance: 5%
"""

import json
import os
import time
from datetime import datetime, timedelta

import requests


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "cache_macro")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL_HR = 6


def _cache_path(name):
    return os.path.join(CACHE_DIR, f"{name}.json")


def _read_cache(name):
    p = _cache_path(name)
    if not os.path.exists(p):
        return None
    if (time.time() - os.path.getmtime(p)) / 3600 > CACHE_TTL_HR:
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(name, data):
    try:
        with open(_cache_path(name), "w", encoding="utf-8") as f:
            json.dump(data, f, default=str)
    except Exception:
        pass


def fetch_fred_series(series_id, periods_back=90):
    """Fetch a FRED time series via the free CSV endpoint (no API key needed)."""
    cached = _read_cache(f"fred_{series_id}")
    if cached is not None:
        return cached
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        r = requests.get(url, timeout=12, headers={"User-Agent": "swing-trading-scanner/1.0"})
        if r.status_code != 200:
            return None
        lines = r.text.strip().split("\n")[1:]
        points = []
        for line in lines[-periods_back:]:
            parts = line.split(",")
            if len(parts) < 2:
                continue
            try:
                date = parts[0].strip()
                val = float(parts[1].strip())
                points.append({"date": date, "value": val})
            except (ValueError, IndexError):
                continue
        _write_cache(f"fred_{series_id}", points)
        return points
    except Exception:
        return None


def _get_alpaca_etf_close(ticker, days_back=10):
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        return None
    try:
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        c = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
        end = datetime.utcnow()
        start = end - timedelta(days=days_back + 5)
        req = StockBarsRequest(symbol_or_symbols=ticker, timeframe=TimeFrame.Day, start=start.isoformat() + "Z", end=end.isoformat() + "Z")
        bars = c.get_stock_bars(req)
        if not bars or ticker not in bars.data:
            return None
        rows = bars.data[ticker]
        out = []
        for b in rows[-days_back:]:
            out.append({"date": b.timestamp.strftime("%Y-%m-%d"), "close": float(b.close)})
        return out
    except Exception:
        return None


def _pct_change(prices, periods=5):
    if not prices or len(prices) < periods + 1:
        return None
    try:
        old = prices[-periods - 1]["close"]
        new = prices[-1]["close"]
        return (new - old) / old * 100 if old else None
    except (KeyError, IndexError, TypeError):
        return None


def _relative_perf(a_prices, b_prices, periods=30):
    """A / B relative performance change."""
    if not a_prices or not b_prices or len(a_prices) < periods + 1 or len(b_prices) < periods + 1:
        return None
    try:
        a_change = (a_prices[-1]["close"] / a_prices[-periods - 1]["close"] - 1) * 100
        b_change = (b_prices[-1]["close"] / b_prices[-periods - 1]["close"] - 1) * 100
        return a_change - b_change
    except (KeyError, IndexError, ZeroDivisionError):
        return None


def detect_macro_regime():
    """Run full macro analysis. Returns dict with score + components."""
    components = {}
    notes = []
    score = 0

    cpi = fetch_fred_series("CPIAUCSL", periods_back=24)
    if cpi and len(cpi) >= 13:
        try:
            current_cpi = cpi[-1]["value"]
            year_ago_cpi = cpi[-13]["value"]
            yoy = (current_cpi - year_ago_cpi) / year_ago_cpi * 100
            components["cpi_yoy"] = round(yoy, 2)
            if yoy >= 4:
                score += 10
                notes.append(f"CPI YoY {yoy:.1f}% (above 4% bear threshold)")
            elif yoy >= 3:
                score += 5
                notes.append(f"CPI YoY {yoy:.1f}% (elevated)")
            else:
                notes.append(f"CPI YoY {yoy:.1f}% (benign)")
        except Exception:
            pass

    t10y2y = fetch_fred_series("T10Y2Y", periods_back=90)
    if t10y2y and len(t10y2y) >= 60:
        try:
            current = t10y2y[-1]["value"]
            past_30d = t10y2y[-30]["value"]
            past_60d = t10y2y[-60]["value"]
            components["yield_curve_2y10y"] = round(current, 3)
            components["yield_curve_30d_change"] = round(current - past_30d, 3)
            if past_60d < 0 and current >= 0:
                score += 15
                notes.append("Yield curve UN-INVERTED in last 60d (recession trigger historically)")
            elif current - past_30d > 0.3 and current > 0:
                score += 8
                notes.append(f"Yield curve steepening rapidly (+{current - past_30d:.2f} in 30d)")
        except Exception:
            pass

    dgs10 = fetch_fred_series("DGS10", periods_back=30)
    if dgs10 and dgs10[-1].get("value"):
        try:
            current_10y = dgs10[-1]["value"]
            components["10y_yield"] = round(current_10y, 2)
            if current_10y >= 4.8:
                score += 10
                notes.append(f"10Y yield {current_10y:.2f}% (high - tightening transmission)")
            elif current_10y >= 4.3:
                score += 5
                notes.append(f"10Y yield {current_10y:.2f}% (elevated)")
        except Exception:
            pass

    vix = _get_alpaca_etf_close("VIXY", days_back=30)
    if vix and len(vix) >= 5:
        try:
            current = vix[-1]["close"]
            five_d_change = _pct_change(vix, 5)
            components["vixy_price"] = round(current, 2)
            components["vixy_5d_change"] = round(five_d_change, 1) if five_d_change else None
            if five_d_change and five_d_change > 25:
                score += 10
                notes.append(f"VIX proxy spiking +{five_d_change:.0f}% in 5d (fear rising)")
            elif five_d_change and five_d_change > 10:
                score += 5
                notes.append(f"VIX proxy +{five_d_change:.0f}% in 5d (mild fear uptick)")
        except Exception:
            pass

    xlf = _get_alpaca_etf_close("XLF", days_back=60)
    spy = _get_alpaca_etf_close("SPY", days_back=60)
    if xlf and spy:
        rel_30d = _relative_perf(xlf, spy, periods=30)
        components["xlf_vs_spy_30d"] = round(rel_30d, 1) if rel_30d is not None else None
        if rel_30d is not None and rel_30d < -3:
            score += 12
            notes.append(f"Banks (XLF) underperforming SPY by {rel_30d:.1f}% (credit concerns)")
        elif rel_30d is not None and rel_30d < -1:
            score += 6

    hyg = _get_alpaca_etf_close("HYG", days_back=30)
    lqd = _get_alpaca_etf_close("LQD", days_back=30)
    if hyg and lqd:
        rel = _relative_perf(hyg, lqd, periods=20)
        components["hyg_vs_lqd_20d"] = round(rel, 1) if rel is not None else None
        if rel is not None and rel < -2:
            score += 12
            notes.append(f"High-yield credit (HYG) underperforming investment-grade (LQD) by {rel:.1f}% (credit stress)")
        elif rel is not None and rel < -0.5:
            score += 5

    uup = _get_alpaca_etf_close("UUP", days_back=30)
    if uup:
        dxy_5d = _pct_change(uup, 5)
        components["uup_5d_change"] = round(dxy_5d, 1) if dxy_5d is not None else None
        if dxy_5d is not None and dxy_5d > 1.5:
            score += 6
            notes.append(f"Dollar (UUP) +{dxy_5d:.1f}% in 5d (tightening for multinationals)")

    xlu = _get_alpaca_etf_close("XLU", days_back=30)
    xlp = _get_alpaca_etf_close("XLP", days_back=30)
    if xlu and xlp and spy:
        xlu_vs_spy = _relative_perf(xlu, spy, periods=15)
        xlp_vs_spy = _relative_perf(xlp, spy, periods=15)
        avg_def = ((xlu_vs_spy or 0) + (xlp_vs_spy or 0)) / 2 if xlu_vs_spy or xlp_vs_spy else None
        components["defensive_vs_spy_15d"] = round(avg_def, 1) if avg_def is not None else None
        if avg_def and avg_def > 2:
            score += 8
            notes.append(f"Defensive sectors (XLU+XLP) leading SPY by +{avg_def:.1f}% (rotation to safety)")

    iwm = _get_alpaca_etf_close("IWM", days_back=60)
    if iwm and spy:
        rel = _relative_perf(iwm, spy, periods=30)
        components["iwm_vs_spy_30d"] = round(rel, 1) if rel is not None else None
        if rel is not None and rel < -5:
            score += 5
            notes.append(f"Small caps (IWM) underperforming SPY by {rel:.1f}% (risk-off)")

    score = min(100, max(0, score))

    if score >= 75:
        regime = "STRONG_BEAR"
        label = "🐻 Strong bearish — multiple confirming signals"
    elif score >= 55:
        regime = "BEAR"
        label = "📉 Bearish regime — defensive positioning + bear plays warranted"
    elif score >= 35:
        regime = "MIXED"
        label = "⚠️ Mixed — some warning signs, neutral to cautious"
    elif score >= 15:
        regime = "BULL"
        label = "📈 Bullish — risk-on conditions"
    else:
        regime = "STRONG_BULL"
        label = "🚀 Strong bullish — no macro headwinds"

    return {
        "score": score,
        "regime": regime,
        "label": label,
        "components": components,
        "notes": notes,
        "computed_at": datetime.utcnow().isoformat(),
    }


def apply_macro_regime(scan_dict, verbose=False):
    """Inject macro regime into scan output."""
    try:
        regime = detect_macro_regime()
        scan_dict["macro_regime"] = regime
        if verbose:
            print(f"  macro_regime: {regime['regime']} ({regime['score']}/100) - {regime['label']}")
            for n in regime["notes"][:5]:
                print(f"    - {n}")
        return regime
    except Exception as e:
        if verbose:
            print(f"  macro_regime failed (non-fatal): {type(e).__name__}: {e}")
        return None
