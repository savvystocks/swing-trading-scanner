"""V11 context sensors (STANDALONE, LOG-DON'T-BLOCK).

Every function here is pure instrumentation: it returns a dict of logged fields and a
"source" tag, and FAILS OPEN to nulls on any error. None of these values is ever read by an
entry/sizing/rejection path - the Autopsy Engine consumes them later to learn cluster-level
edges. See collect_metadata() in sandbox_proactive_lab.py for the injection point.
"""

import os
import math
import json
import time
from datetime import date, datetime, timedelta, timezone

_PROFILE_CACHE = {}        # ticker -> (day, profile)   in-process, dedups within a cycle

SECTOR_ETF = {
    "Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV",
    "Consumer Cyclical": "XLY", "Consumer Defensive": "XLP", "Energy": "XLE",
    "Industrials": "XLI", "Basic Materials": "XLB", "Utilities": "XLU",
    "Real Estate": "XLRE", "Communication Services": "XLC",
}

_NEWS_TYPES = [
    ("Earnings", ("earnings", "eps", "beat", "miss", "guidance", "revenue", "quarter", "profit")),
    ("Macro", ("fed", "fomc", "cpi", "inflation", "rate cut", "rate hike", "jobs", "tariff", "gdp", "yields")),
    ("Analyst", ("upgrade", "downgrade", "price target", "initiated", "reiterate", "rating", "outperform")),
    ("MnA", ("acqui", "merger", "buyout", "takeover", "stake", "all-cash", "deal to")),
    ("Product", ("launch", "unveil", "release", "approval", "fda", "chip", "model", "partnership", "contract")),
]


def _alpaca_keys():
    k = os.environ.get("ALPACA_PAPER_API_KEY") or os.environ.get("ALPACA_API_KEY")
    s = os.environ.get("ALPACA_PAPER_SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY")
    return k, s


def _daily_closes(symbol, days=40):
    k, s = _alpaca_keys()
    if not (k and s):
        return []
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed
        cli = StockHistoricalDataClient(k, s)
        start = datetime.utcnow() - timedelta(days=days + 20)
        bars = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day,
                                                   start=start, feed=DataFeed.IEX)).data.get(symbol, [])
        return [float(b.close) for b in bars]
    except Exception:
        return []


def _sma_distance(symbol):
    closes = _daily_closes(symbol)
    if len(closes) < 21:
        return None
    sma20 = sum(closes[-20:]) / 20.0
    return round((closes[-1] - sma20) / sma20 * 100, 3) if sma20 else None


# ----------------------------------------------------------------------------
# SENSOR 1a - Fundamental profile (yfinance: sector / market cap / short interest)
# ----------------------------------------------------------------------------
def company_profile(ticker, mock=False):
    base = ticker.split(".")[0]
    today = date.today().isoformat()
    cached = _PROFILE_CACHE.get(base)
    if cached and cached[0] == today:
        return cached[1]
    out = {"sector": None, "industry": None, "market_cap": None,
           "short_pct_float": None, "short_ratio": None, "source": "unavailable"}
    if not mock:
        try:
            import yfinance as yf
            info = yf.Ticker(base).info or {}
            spf = info.get("shortPercentOfFloat")
            out = {"sector": info.get("sector"), "industry": info.get("industry"),
                   "market_cap": info.get("marketCap"),
                   "short_pct_float": round(spf * 100, 2) if isinstance(spf, (int, float)) else None,
                   "short_ratio": info.get("shortRatio"), "source": "yfinance"}
        except Exception:
            pass
    _PROFILE_CACHE[base] = (today, out)
    return out


# ----------------------------------------------------------------------------
# SENSOR 1b / Phase 3 - News context, VADER sentiment, catalyst type, half-life
# ----------------------------------------------------------------------------
def _classify_news(text):
    t = (text or "").lower()
    for label, kws in _NEWS_TYPES:
        if any(kw in t for kw in kws):
            return label
    return "Unknown"


def news_context(ticker, mock=False, limit=8):
    out = {"headline_count": 0, "latest_age_hours": None, "vader_compound": None,
           "news_type": "Unknown", "top_headline": None, "source": "unavailable"}
    if mock:
        return out
    try:
        k, s = _alpaca_keys()
        if not (k and s):
            return out
        from alpaca.data.historical.news import NewsClient
        from alpaca.data.requests import NewsRequest
        res = NewsClient(k, s).get_news(NewsRequest(symbols=ticker.split(".")[0], limit=limit))
        items = getattr(res, "data", None) or getattr(res, "news", None) or res
        if isinstance(items, dict):
            items = items.get("news") or (list(items.values())[0] if items else [])
        items = list(items or [])
        if not items:
            out["source"] = "alpaca_news_empty"
            return out
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            sia = SentimentIntensityAnalyzer()
        except Exception:
            sia = None
        heads, scores = [], []
        newest = None
        for a in items:
            h = getattr(a, "headline", None) or (a.get("headline") if isinstance(a, dict) else None)
            summ = getattr(a, "summary", "") or (a.get("summary", "") if isinstance(a, dict) else "")
            ca = getattr(a, "created_at", None) or (a.get("created_at") if isinstance(a, dict) else None)
            if h:
                heads.append(h)
                if sia:
                    scores.append(sia.polarity_scores(f"{h}. {summ}")["compound"])
            ts = _parse_ts(ca)
            if ts and (newest is None or ts > newest):
                newest = ts
        age_h = None
        if newest:
            age_h = round((datetime.now(timezone.utc) - newest).total_seconds() / 3600.0, 2)
        out = {"headline_count": len(heads),
               "latest_age_hours": age_h,
               "vader_compound": round(sum(scores) / len(scores), 3) if scores else None,
               "news_type": _classify_news(" ".join(heads[:3])),
               "top_headline": heads[0][:140] if heads else None,
               "source": "alpaca_news+vader" if scores else "alpaca_news"}
    except Exception:
        pass
    return out


def _parse_ts(x):
    if x is None:
        return None
    try:
        if isinstance(x, datetime):
            return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except Exception:
        return None


# ----------------------------------------------------------------------------
# SENSOR 2 - Micro (sector ETF) vs Macro (SPY) regime stack
# ----------------------------------------------------------------------------
def regime_stack(ticker, sector, ticker_dist_pct, mock=False):
    out = {"ticker_dist_pct": ticker_dist_pct, "market_spy_dist_pct": None,
           "sector_etf": None, "sector_dist_pct": None,
           "sector_vs_market_spread": None, "source": "unavailable"}
    if mock:
        return out
    try:
        etf = SECTOR_ETF.get(sector)
        spy = _sma_distance("SPY")
        sec = _sma_distance(etf) if etf else None
        spread = round(sec - spy, 3) if (sec is not None and spy is not None) else None
        out = {"ticker_dist_pct": ticker_dist_pct, "market_spy_dist_pct": spy,
               "sector_etf": etf, "sector_dist_pct": sec,
               "sector_vs_market_spread": spread,
               "source": "alpaca_bars" if spy is not None else "unavailable"}
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------------
# SENSOR 4 - Relative skew: 25-delta put IV vs 25-delta call IV (delta-free capable)
# ----------------------------------------------------------------------------
def _front_chain(ticker, side, dte_lo=21, dte_hi=45):
    k, s = _alpaca_keys()
    if not (k and s):
        return {}
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
        cli = OptionHistoricalDataClient(k, s)
        gte = (date.today() + timedelta(days=dte_lo)).isoformat()
        lte = (date.today() + timedelta(days=dte_hi)).isoformat()
        return cli.get_option_chain(OptionChainRequest(
            underlying_symbol=ticker.split(".")[0], type=side,
            expiration_date_gte=gte, expiration_date_lte=lte)) or {}
    except Exception:
        return {}


def _strike_from_sym(sym):
    s = sym if isinstance(sym, str) else str(sym)
    try:
        return int(s[-8:]) / 1000.0
    except Exception:
        return None


def _pick_25delta(snaps, target_strike):
    best = None
    best_d = 1e18
    used_delta = False
    for sym, snp in (snaps or {}).items():
        iv = getattr(snp, "implied_volatility", None)
        if not iv:
            continue
        g = getattr(snp, "greeks", None)
        delta = getattr(g, "delta", None) if g else None
        if delta is not None:
            d = abs(abs(float(delta)) - 0.25)
            if d < best_d:
                best_d, best, used_delta = d, float(iv) * 100, True
        elif not used_delta:
            k = _strike_from_sym(sym)
            if k is None:
                continue
            d = abs(k - target_strike)
            if d < best_d:
                best_d, best = d, float(iv) * 100
    return best, used_delta


def relative_skew(ticker, spot, atm_iv_pct, mock=False, front_dte=30):
    out = {"put_iv_25d": None, "call_iv_25d": None, "skew_ratio": None,
           "skew_bias": None, "delta_source": None, "source": "unavailable"}
    if mock or not (spot and atm_iv_pct):
        return out
    try:
        sigma = atm_iv_pct / 100.0
        t = max(front_dte, 1) / 365.0
        drift = 0.674 * sigma * math.sqrt(t)              # ~25-delta moneyness proxy
        k_call = spot * math.exp(drift)
        k_put = spot * math.exp(-drift)
        call_iv, c_dlt = _pick_25delta(_front_chain(ticker, "call"), k_call)
        put_iv, p_dlt = _pick_25delta(_front_chain(ticker, "put"), k_put)
        if call_iv and put_iv:
            ratio = round(put_iv / call_iv, 3)
            bias = "crash_hedging" if ratio > 1.05 else "call_skew" if ratio < 0.95 else "balanced"
            out = {"put_iv_25d": round(put_iv, 1), "call_iv_25d": round(call_iv, 1),
                   "skew_ratio": ratio, "skew_bias": bias,
                   "delta_source": "greeks" if (c_dlt or p_dlt) else "moneyness_proxy",
                   "source": "alpaca_snapshots"}
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------------
# SENSOR 3 - Per-leg execution cost (bid/ask spread of the resolved OCC)
# ----------------------------------------------------------------------------
def option_spread(occ_symbol):
    out = {"bid": None, "ask": None, "mid": None, "bid_ask_spread_pct": None, "source": "unavailable"}
    if not occ_symbol:
        return out
    try:
        k, s = _alpaca_keys()
        if not (k and s):
            return out
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionLatestQuoteRequest
        cli = OptionHistoricalDataClient(k, s)
        q = (cli.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=occ_symbol)) or {}).get(occ_symbol)
        bid = getattr(q, "bid_price", None) if q else None
        ask = getattr(q, "ask_price", None) if q else None
        if bid is not None and ask is not None and (bid + ask) > 0:
            mid = (bid + ask) / 2.0
            out = {"bid": round(bid, 4), "ask": round(ask, 4), "mid": round(mid, 4),
                   "bid_ask_spread_pct": round((ask - bid) / mid * 100, 3) if mid else None,
                   "source": "alpaca_quote"}
    except Exception:
        pass
    return out
