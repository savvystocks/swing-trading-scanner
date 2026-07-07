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


# ----------------------------------------------------------------------------
# V11 EXPANSION - advanced microstructure edges (all LOG-DON'T-BLOCK, fail-open)
# ----------------------------------------------------------------------------
def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _uw():
    try:
        from src.unusual_whales_api import UnusualWhalesClient
        c = UnusualWhalesClient()
        return c if getattr(c, "enabled", False) else None
    except Exception:
        return None


# EDGE 1 - Sweep aggression: ask-side SWEEP premium as a share of total flow
def flow_aggression(ticker, mock=False):
    out = {"sweep_aggression_pct": None, "ask_sweep_prem": None, "total_flow_prem": None, "source": "unavailable"}
    if mock:
        return out
    uw = _uw()
    if not uw:
        return out
    try:
        rows = (uw.flow_alerts(ticker=ticker.split(".")[0], limit=100) or {}).get("data") or []
        if not rows:
            out["source"] = "uw_empty"
            return out
        total = sum(_f(r.get("total_premium")) for r in rows)
        ask_sweep = sum(_f(r.get("total_ask_side_prem")) for r in rows if r.get("has_sweep"))
        out = {"sweep_aggression_pct": round(ask_sweep / total * 100, 2) if total else None,
               "ask_sweep_prem": round(ask_sweep, 0), "total_flow_prem": round(total, 0), "source": "uw_flow"}
    except Exception:
        pass
    return out


# EDGE 3 - Dark-pool heaviest volume node (recent-session window) vs spot
def darkpool_node(ticker, spot, mock=False):
    out = {"distance_to_heaviest_dp_node_pct": None, "heaviest_node_price": None, "node_size": None,
           "n_prints": 0, "window_start": None, "window_end": None, "source": "unavailable"}
    if mock or not spot:
        return out
    uw = _uw()
    if not uw:
        return out
    try:
        prints = (uw.darkpool_ticker(ticker.split(".")[0], limit=200) or {}).get("data") or []
        if not prints:
            out["source"] = "uw_empty"
            return out
        binsize = spot * 0.0025                               # 0.25%-of-spot price bins
        buckets = {}
        for p in prints:
            px, sz = _f(p.get("price")), _f(p.get("size"))
            if px <= 0 or binsize <= 0:
                continue
            b = round(round(px / binsize) * binsize, 4)
            buckets[b] = buckets.get(b, 0.0) + sz
        if not buckets:
            return out
        node = max(buckets, key=buckets.get)
        ts = [p.get("executed_at") for p in prints if p.get("executed_at")]
        out = {"distance_to_heaviest_dp_node_pct": round((spot - node) / spot * 100, 3) if spot else None,
               "heaviest_node_price": round(node, 2), "node_size": round(buckets[node], 0),
               "n_prints": len(prints), "window_start": min(ts) if ts else None,
               "window_end": max(ts) if ts else None, "source": "uw_darkpool"}
    except Exception:
        pass
    return out


# EDGE 4 - Post-earnings momentum drift: days since report + IV-crush flag
def post_earnings_drift(ticker, mock=False, crush_iv_rank=30.0):
    out = {"days_since_earnings": None, "post_earnings_iv_crush_flag": None,
           "days_to_earnings": None, "next_earnings_date": None,
           "iv_rank_1y": None, "last_earnings_date": None, "source": "unavailable"}
    if mock:
        return out
    base = ticker.split(".")[0]
    days, last_ed, days_to, next_ed = None, None, None, None
    try:
        import yfinance as yf
        ed = yf.Ticker(base).get_earnings_dates(limit=12)
        idx = getattr(ed, "index", None)
        idx = list(idx) if idx is not None else []          # never boolean-test a DatetimeIndex (ambiguous)
        today = date.today()
        past = [d.date() for d in idx if hasattr(d, "date") and d.date() <= today]
        if past:
            last_ed = max(past)
            days = (today - last_ed).days
        # TIER B: forward calendar off the SAME fetch (no extra call) - powers the 3-day earnings
        # blackout in enter_proactive_set. Fail-open: null -> the blackout never blocks.
        future = [d.date() for d in idx if hasattr(d, "date") and d.date() > today]
        if future:
            next_ed = min(future)
            days_to = (next_ed - today).days
    except Exception:
        pass
    ivr = None
    try:
        uw = _uw()
        if uw:
            rows = (uw.iv_rank(base) or {}).get("data") or []
            if rows:
                ivr = _f(rows[-1].get("iv_rank_1y"))
    except Exception:
        pass
    flag = bool(days is not None and days <= 5 and ivr is not None and ivr < crush_iv_rank) if days is not None else None
    src = "yfinance+uw" if (days is not None or days_to is not None or ivr is not None) else "unavailable"
    return {"days_since_earnings": days, "post_earnings_iv_crush_flag": flag,
            "days_to_earnings": days_to, "next_earnings_date": next_ed.isoformat() if next_ed else None,
            "iv_rank_1y": round(ivr, 2) if ivr is not None else None,
            "last_earnings_date": last_ed.isoformat() if last_ed else None, "source": src}


# EDGE 5 - Variance Risk Premium: front IV minus 20-day annualised realized vol
def vrp_sensor(ticker, front_iv_pct, mock=False):
    out = {"realized_vol_20d": None, "front_iv": front_iv_pct, "vrp": None, "vrp_regime": None, "source": "unavailable"}
    if mock or not front_iv_pct:
        return out
    try:
        closes = _daily_closes(ticker, days=40)
        if len(closes) < 21:
            return out
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(len(closes) - 20, len(closes)) if closes[i - 1] > 0]
        if len(rets) < 2:
            return out
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        rv = math.sqrt(var) * math.sqrt(252) * 100.0
        vrp = round(front_iv_pct - rv, 2)
        out = {"realized_vol_20d": round(rv, 2), "front_iv": round(front_iv_pct, 1), "vrp": vrp,
               "vrp_regime": "rich" if vrp > 0 else "cheap", "source": "alpaca_bars"}
    except Exception:
        pass
    return out


# EDGE 6 - Flow persistence: how one-sided + how late-building the day's net premium is
def flow_persistence(ticker, mock=False):
    out = {"net_directional_prem": None, "flow_persistence_pct": None, "flow_direction": None,
           "closing_accel": None, "n_ticks": 0, "source": "unavailable"}
    if mock:
        return out
    uw = _uw()
    if not uw:
        return out
    try:
        ticks = (uw.net_prem_ticks(ticker.split(".")[0]) or {}).get("data") or []
        if not ticks:
            out["source"] = "uw_empty"
            return out
        dirs = [_f(t.get("net_call_premium")) - _f(t.get("net_put_premium")) for t in ticks]   # bullish minus bearish $
        net = sum(dirs)
        absum = sum(abs(x) for x in dirs)
        n = len(dirs)
        q = max(1, n // 4)
        out = {"net_directional_prem": round(net, 0),
               "flow_persistence_pct": round(abs(net) / absum * 100, 2) if absum else None,   # 100 = all one side, 0 = chop
               "flow_direction": "bullish" if net > 0 else "bearish" if net < 0 else "neutral",
               "closing_accel": round(sum(dirs[-q:]) - sum(dirs[:q]), 0),                       # >0 = bullish flow building into close
               "n_ticks": n, "source": "uw_net_prem_ticks"}
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------------
# ML-PREP PAYLOAD - price-action/shape/volume + macro context (LOG-DON'T-BLOCK)
# ----------------------------------------------------------------------------
def _daily_ohlcv(symbol, days=70):
    k, s = _alpaca_keys()
    if not (k and s):
        return []
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from alpaca.data.enums import DataFeed
        cli = StockHistoricalDataClient(k, s)
        start = datetime.utcnow() - timedelta(days=days + 25)
        bars = cli.get_stock_bars(StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day,
                                                   start=start, feed=DataFeed.IEX)).data.get(symbol, [])
        return [{"o": float(b.open), "h": float(b.high), "l": float(b.low),
                 "c": float(b.close), "v": float(b.volume)} for b in bars]
    except Exception:
        return []


def _rsi(closes, period):
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(len(closes) - period, len(closes))]
    ag = sum(d for d in deltas if d > 0) / period
    al = sum(-d for d in deltas if d < 0) / period
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    return round(100 - 100 / (1 + ag / al), 2)


# SENSOR 7 - price action, shape & volume
def price_action(ticker, mock=False, bars=None):
    out = {"nvi": None, "vwma_20": None, "rsi_5": None, "rsi_15": None, "gap_pct": None,
           "day_range": None, "candle_body": None, "dist_sma50": None, "source": "unavailable"}
    if mock:
        return out
    try:
        bars = bars if bars is not None else _daily_ohlcv(ticker)
        if len(bars) < 51:
            return out
        c = [b["c"] for b in bars]
        v = [b["v"] for b in bars]
        o, h, l = bars[-1]["o"], bars[-1]["h"], bars[-1]["l"]
        spot, prev = c[-1], c[-2]
        sma50 = sum(c[-50:]) / 50.0
        vw_num = sum(c[i] * v[i] for i in range(len(c) - 20, len(c)))
        vw_den = sum(v[-20:])
        nvi = 1000.0
        for i in range(1, len(bars)):
            if v[i] < v[i - 1] and c[i - 1] > 0:
                nvi *= (1 + (c[i] - c[i - 1]) / c[i - 1])
        rng = h - l
        out = {"nvi": round(nvi, 2),
               "vwma_20": round(vw_num / vw_den, 2) if vw_den else None,
               "rsi_5": _rsi(c, 5), "rsi_15": _rsi(c, 15),
               "gap_pct": round((o - prev) / prev * 100, 3) if prev else None,
               "day_range": round(rng / spot * 100, 3) if spot else None,
               "candle_body": round(abs(spot - o) / rng, 3) if rng else None,
               "dist_sma50": round((spot - sma50) / sma50 * 100, 3) if sma50 else None,
               "source": "alpaca_bars"}
    except Exception:
        pass
    return out


# SENSOR 8 - deep microstructure & macro context
def macro_context(ticker, iv_front, iv_back, sector, mock=False, now=None):
    now = now or datetime.now(timezone.utc)
    out = {"iv_term_skew": None, "vix_level": None, "execution_hour": now.hour,
           "day_of_week": now.weekday(), "sector_vs_spy": None, "source": "partial"}
    if iv_front is not None and iv_back is not None:
        out["iv_term_skew"] = round(iv_front - iv_back, 2)
    if mock:
        return out
    try:
        import yfinance as yf
        vh = yf.Ticker("^VIX").history(period="5d")
        if vh is not None and len(vh):
            out["vix_level"] = round(float(vh["Close"].iloc[-1]), 2)
    except Exception:
        pass
    try:
        etf = SECTOR_ETF.get(sector)
        if etf:
            se = _daily_closes(etf)
            sp = _daily_closes("SPY")
            if len(se) >= 6 and len(sp) >= 6:
                se_r = (se[-1] / se[-6] - 1) * 100
                sp_r = (sp[-1] / sp[-6] - 1) * 100
                out["sector_vs_spy"] = round(se_r - sp_r, 3)
    except Exception:
        pass
    out["source"] = "yfinance+alpaca"
    return out


# SENSOR 8b - per-leg open-interest day-over-day change (stamped at order-gen)
def oi_change(occ_symbol, mock=False):
    out = {"oi_today": None, "oi_prev": None, "oi_change": None, "source": "unavailable"}
    if mock or not occ_symbol:
        return out
    uw = _uw()
    if not uw:
        return out
    try:
        chains = (uw.option_contract_historic(occ_symbol) or {}).get("chains") or []   # newest-first
        if len(chains) >= 2:
            t0 = _f(chains[0].get("open_interest"))
            t1 = _f(chains[1].get("open_interest"))
            out = {"oi_today": t0, "oi_prev": t1, "oi_change": round(t0 - t1, 0), "source": "uw_historic"}
        elif chains:
            out = {"oi_today": _f(chains[0].get("open_interest")), "oi_prev": None,
                   "oi_change": None, "source": "uw_historic_1d"}
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------------
# MID-CAP MICROSTRUCTURE PAYLOAD (LOG-DON'T-BLOCK) - liquidity / momentum / float
# ----------------------------------------------------------------------------
# BLOCK 1 - liquidity & slippage: underlying equity top-of-book spread + depth
def liquidity_slippage(ticker, mock=False):
    out = {"equity_spread_pct_of_ask": None, "bid": None, "ask": None,
           "bid_size": None, "ask_size": None, "obi": None, "source": "unavailable"}
    if mock:
        return out
    k, s = _alpaca_keys()
    if not (k and s):
        return out
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        from alpaca.data.enums import DataFeed
        cli = StockHistoricalDataClient(k, s)
        sym = ticker.split(".")[0]
        q = (cli.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=sym, feed=DataFeed.IEX)) or {}).get(sym)
        bid = getattr(q, "bid_price", None) if q else None
        ask = getattr(q, "ask_price", None) if q else None
        if bid is not None and ask is not None and ask > 0:
            bs, asz = getattr(q, "bid_size", None), getattr(q, "ask_size", None)
            depth = _f(bs) + _f(asz)
            out = {"equity_spread_pct_of_ask": round((ask - bid) / ask * 100, 3),
                   "bid": round(bid, 4), "ask": round(ask, 4), "bid_size": bs, "ask_size": asz,
                   "obi": round((_f(bs) - _f(asz)) / depth, 4) if depth else None,   # order-book imbalance -1..+1
                   "source": "alpaca_quote"}
    except Exception:
        pass
    return out


# BLOCK 2 - relative momentum: RVOL vs 20-day average + opening gap %
def relative_momentum(ticker, mock=False, bars=None):
    out = {"rvol_20d": None, "gap_pct": None, "source": "unavailable"}
    if mock:
        return out
    try:
        bars = bars if bars is not None else _daily_ohlcv(ticker)
        if len(bars) < 21:
            return out
        vols = [b["v"] for b in bars]
        avg20 = sum(vols[-21:-1]) / 20.0                          # prior 20 days (excl. today)
        o, prev = bars[-1]["o"], bars[-2]["c"]
        out = {"rvol_20d": round(vols[-1] / avg20, 2) if avg20 else None,
               "gap_pct": round((o - prev) / prev * 100, 3) if prev else None,
               "source": "alpaca_bars"}
    except Exception:
        pass
    return out


# BLOCK 3 - float mechanics: short interest % + total float size
def float_mechanics(ticker, mock=False):
    out = {"short_pct_float": None, "float_shares": None, "shares_short": None, "source": "unavailable"}
    if mock:
        return out
    try:
        import yfinance as yf
        info = yf.Ticker(ticker.split(".")[0]).info or {}
        spf = info.get("shortPercentOfFloat")
        out = {"short_pct_float": round(spf * 100, 2) if isinstance(spf, (int, float)) else None,
               "float_shares": info.get("floatShares"), "shares_short": info.get("sharesShort"),
               "source": "yfinance"}
    except Exception:
        pass
    return out


# BLOCK 4 - dealer greeks: net DEX / vanna / charm (the delta-hedging flows beyond gamma)
def dealer_greeks(ticker, mock=False):
    out = {"net_dex": None, "net_vanna": None, "net_charm": None, "delta_imbalance": None, "source": "unavailable"}
    if mock:
        return out
    uw = _uw()
    if not uw:
        return out
    try:
        rows = (uw.greek_exposure(ticker.split(".")[0]) or {}).get("data") or []   # 1y daily, newest last
        if not rows:
            out["source"] = "uw_empty"
            return out
        r = rows[-1]
        cd, pd = _f(r.get("call_delta")), _f(r.get("put_delta"))
        out = {"net_dex": round(cd + pd, 0),                                       # dealer net delta exposure
               "net_vanna": round(_f(r.get("call_vanna")) + _f(r.get("put_vanna")), 0),   # delta sens. to IV (vol-crush melt-up)
               "net_charm": round(_f(r.get("call_charm")) + _f(r.get("put_charm")), 0),   # delta decay (OPEX pin/drift)
               "delta_imbalance": round(cd / abs(pd), 3) if pd else None,          # call vs put dealer delta magnitude
               "source": "uw_greek_exposure"}
    except Exception:
        pass
    return out
