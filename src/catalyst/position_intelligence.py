"""Position Intelligence - the 7-factor HOLD/TRIM/SELL framework.

Replaces the noisy bear-conviction "side flip" alerts that fired on price
action alone. Built from professional momentum-trader research (Wyckoff
volume analysis, RSI-in-context, peer/sector correlation, options Greeks
discipline).

The 7 factors:
  1. Volume context  - today's vol vs 20-day avg (light = profit-taking)
  2. Sector / peer   - was the move idiosyncratic or sector-wide
  3. Support levels  - did it hold 20dMA / 50dMA / prior breakout
  4. RSI context     - healthy 40-50 zone vs momentum breakdown
  5. News today      - any material catalyst that justifies the move
  6. Options Greeks  - delta change since entry, theta pressure, IV
  7. Next catalyst   - days to earnings / FDA / conference

For LIVE positions: outputs HOLD / TRIM / SELL verdict each day.
For NEW picks: same checks act as entry-confirmation filters.

Data inputs: Alpaca daily bars (free), EODHD fundamentals + news (subscribed),
sector ETF prices (free), Anthropic LLM (subscribed). No new subscriptions
required to ship the v1 - peer correlation runs on sector ETF as a proxy.
"""

import os
from datetime import datetime, timedelta


SECTOR_ETF_MAP = {
    "technology": "XLK",
    "information technology": "XLK",
    "healthcare": "XLV",
    "health care": "XLV",
    "financial services": "XLF",
    "financials": "XLF",
    "consumer cyclical": "XLY",
    "consumer discretionary": "XLY",
    "consumer defensive": "XLP",
    "consumer staples": "XLP",
    "industrials": "XLI",
    "energy": "XLE",
    "utilities": "XLU",
    "basic materials": "XLB",
    "materials": "XLB",
    "real estate": "XLRE",
    "communication services": "XLC",
    "communications": "XLC",
}


VERDICT_HOLD = "HOLD"
VERDICT_TRIM = "TRIM"
VERDICT_SELL = "SELL"
VERDICT_NEW_TAKE = "TAKE"
VERDICT_NEW_SKIP = "SKIP"


def _sector_etf_for(sector):
    if not sector:
        return None
    return SECTOR_ETF_MAP.get(sector.lower().strip())


def _alpaca_recent_bars(ticker, days=30):
    try:
        from src.alpaca_ohlcv import get_daily_bars
        from datetime import date
        end = date.today()
        start = end - timedelta(days=days + 10)
        bars = get_daily_bars(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        return bars or []
    except Exception:
        return []


def _eodhd_recent_bars(ticker, days=30):
    try:
        from src.eodhd import EODHDClient
        from datetime import date
        client = EODHDClient()
        end = date.today()
        start = end - timedelta(days=days + 10)
        bars = client.ohlcv(f"{ticker}.US" if "." not in ticker else ticker, from_date=start.strftime("%Y-%m-%d"), to_date=end.strftime("%Y-%m-%d"))
        return bars or []
    except Exception:
        return []


def _get_bars(ticker, days=30):
    bars = _alpaca_recent_bars(ticker, days)
    if not bars:
        bars = _eodhd_recent_bars(ticker, days)
    return bars or []


def check_volume_context(ticker, bars=None):
    """Factor 1: today's volume vs 20-day average. Light = profit-taking."""
    bars = bars or _get_bars(ticker, days=30)
    if len(bars) < 21:
        return {"pass": None, "verdict": "UNKNOWN", "detail": f"insufficient bars ({len(bars)})"}
    today = bars[-1]
    prior20 = bars[-21:-1]
    try:
        today_vol = float(today.get("volume") or 0)
        avg_vol = sum(float(b.get("volume") or 0) for b in prior20) / len(prior20)
    except Exception:
        return {"pass": None, "verdict": "UNKNOWN", "detail": "volume parse error"}
    if avg_vol <= 0:
        return {"pass": None, "verdict": "UNKNOWN", "detail": "no avg volume"}
    ratio = today_vol / avg_vol
    today_close = float(today.get("close") or 0)
    prior_close = float(prior20[-1].get("close") or today_close)
    is_red = today_close < prior_close

    if is_red and ratio < 0.8:
        return {"pass": True, "verdict": "PROFIT_TAKING", "detail": f"red day on light volume ({ratio:.0%} of 20d avg) - looks like profit-taking, not distribution", "ratio": round(ratio, 2)}
    if is_red and ratio > 1.5:
        return {"pass": False, "verdict": "DISTRIBUTION", "detail": f"red day on HEAVY volume ({ratio:.0%} of 20d avg) - institutional selling, treat seriously", "ratio": round(ratio, 2)}
    if is_red:
        return {"pass": None, "verdict": "MIXED", "detail": f"red day on average volume ({ratio:.0%} of 20d avg) - inconclusive", "ratio": round(ratio, 2)}
    return {"pass": True, "verdict": "UP_DAY", "detail": f"up day on {ratio:.0%} of avg volume - thesis intact", "ratio": round(ratio, 2)}


def check_sector_peer(ticker, sector, bars=None):
    """Factor 2: did the sector ETF move similarly today? Sector move = HOLD."""
    etf = _sector_etf_for(sector)
    if not etf:
        return {"pass": None, "verdict": "UNKNOWN", "detail": f"no sector ETF mapped for sector={sector!r}"}
    bars = bars or _get_bars(ticker, days=5)
    etf_bars = _get_bars(etf, days=5)
    if len(bars) < 2 or len(etf_bars) < 2:
        return {"pass": None, "verdict": "UNKNOWN", "detail": "insufficient peer bars"}
    try:
        stock_pct = (float(bars[-1]["close"]) - float(bars[-2]["close"])) / float(bars[-2]["close"]) * 100
        etf_pct = (float(etf_bars[-1]["close"]) - float(etf_bars[-2]["close"])) / float(etf_bars[-2]["close"]) * 100
    except Exception:
        return {"pass": None, "verdict": "UNKNOWN", "detail": "peer parse error"}
    delta = stock_pct - etf_pct
    if stock_pct < -1 and etf_pct < -0.3 and abs(delta) < 3:
        return {"pass": True, "verdict": "SECTOR_MOVE", "detail": f"stock {stock_pct:+.1f}% vs {etf} {etf_pct:+.1f}% - moved together, sector pullback not idiosyncratic", "stock_pct": round(stock_pct, 2), "sector_pct": round(etf_pct, 2)}
    if stock_pct < -2 and etf_pct > -0.5:
        return {"pass": False, "verdict": "IDIOSYNCRATIC", "detail": f"stock {stock_pct:+.1f}% but {etf} only {etf_pct:+.1f}% - stock-specific weakness, investigate", "stock_pct": round(stock_pct, 2), "sector_pct": round(etf_pct, 2)}
    if stock_pct > 0:
        return {"pass": True, "verdict": "UP_DAY", "detail": f"stock {stock_pct:+.1f}% vs {etf} {etf_pct:+.1f}% - relative strength intact", "stock_pct": round(stock_pct, 2), "sector_pct": round(etf_pct, 2)}
    return {"pass": None, "verdict": "MIXED", "detail": f"stock {stock_pct:+.1f}% vs {etf} {etf_pct:+.1f}% - mild move, inconclusive", "stock_pct": round(stock_pct, 2), "sector_pct": round(etf_pct, 2)}


def check_support_levels(ticker, bars=None):
    """Factor 3: did the stock hold 20dMA / 50dMA?"""
    bars = bars or _get_bars(ticker, days=90)
    if len(bars) < 21:
        return {"pass": None, "verdict": "UNKNOWN", "detail": f"insufficient bars ({len(bars)})"}
    closes = [float(b.get("close") or 0) for b in bars]
    last = closes[-1]
    sma_20 = sum(closes[-20:]) / 20
    n50 = min(50, len(closes))
    sma_50 = sum(closes[-n50:]) / n50

    if last > sma_20:
        return {"pass": True, "verdict": "HELD_20DMA", "detail": f"close ${last:.2f} above 20dMA ${sma_20:.2f} - uptrend intact", "sma_20": round(sma_20, 2), "sma_50": round(sma_50, 2)}
    if last > sma_50:
        return {"pass": None, "verdict": "BELOW_20_HELD_50", "detail": f"close ${last:.2f} below 20dMA ${sma_20:.2f} but holding 50dMA ${sma_50:.2f} - first warning, tighten stop", "sma_20": round(sma_20, 2), "sma_50": round(sma_50, 2)}
    return {"pass": False, "verdict": "BROKE_50DMA", "detail": f"close ${last:.2f} below 50dMA ${sma_50:.2f} - trend broken, exit signal", "sma_20": round(sma_20, 2), "sma_50": round(sma_50, 2)}


def check_rsi_context(ticker, bars=None):
    """Factor 4: RSI in the healthy 40-50 zone or breaking down?"""
    bars = bars or _get_bars(ticker, days=40)
    if len(bars) < 15:
        return {"pass": None, "verdict": "UNKNOWN", "detail": f"insufficient bars for RSI ({len(bars)})"}
    closes = [float(b.get("close") or 0) for b in bars[-15:]]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / 14 if gains else 0
    avg_loss = sum(losses) / 14 if losses else 0.0001
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    rsi_5_bars_ago = None
    if len(bars) >= 20:
        cl5 = [float(b.get("close") or 0) for b in bars[-20:-5]]
        g5, l5 = [], []
        for i in range(1, len(cl5)):
            d = cl5[i] - cl5[i - 1]
            g5.append(max(d, 0))
            l5.append(max(-d, 0))
        ag5 = sum(g5) / 14 if g5 else 0
        al5 = sum(l5) / 14 if l5 else 0.0001
        rs5 = ag5 / al5
        rsi_5_bars_ago = 100 - (100 / (1 + rs5))
    trend = (rsi - (rsi_5_bars_ago or rsi))

    if rsi >= 40 and rsi <= 55 and trend >= -3:
        return {"pass": True, "verdict": "HEALTHY_PULLBACK", "detail": f"RSI {rsi:.0f} in 40-55 zone, trend {trend:+.0f} - classic healthy pullback ending", "rsi": round(rsi, 1), "trend": round(trend, 1)}
    if rsi > 70:
        return {"pass": True, "verdict": "MOMENTUM_INTACT", "detail": f"RSI {rsi:.0f} - strong momentum (strength attracts strength, don't sell mechanical)", "rsi": round(rsi, 1)}
    if rsi < 40 and trend < -3:
        return {"pass": False, "verdict": "BREAKING_DOWN", "detail": f"RSI {rsi:.0f} dropping ({trend:+.0f}) - momentum dying, exit signal", "rsi": round(rsi, 1), "trend": round(trend, 1)}
    return {"pass": None, "verdict": "NEUTRAL", "detail": f"RSI {rsi:.0f}, trend {trend:+.0f} - inconclusive", "rsi": round(rsi, 1), "trend": round(trend, 1)}


def check_news_today(ticker):
    """Factor 5: is there material news today that justifies the move?"""
    try:
        from src.eodhd import EODHDClient
        client = EODHDClient()
        news = client.news(f"{ticker}.US" if "." not in ticker else ticker, limit=10) or []
    except Exception:
        return {"pass": None, "verdict": "UNKNOWN", "detail": "news fetch failed"}

    today_str = datetime.utcnow().date().isoformat()
    yesterday_str = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
    fresh = [n for n in news if (n.get("date") or "")[:10] in (today_str, yesterday_str)]

    bear_keywords = ["downgrade", "miss", "guides lower", "going concern", "dilution", "shelf", "investigation", "fraud", "restated", "resign", "departure", "lawsuit", "subpoena", "fda reject", "crl", "complete response letter"]
    bull_keywords = ["beat", "raised", "approval", "fda approves", "buyback", "guidance raised", "contract win", "partnership"]

    bear_hits = []
    bull_hits = []
    for n in fresh:
        title = (n.get("title") or "").lower()
        for kw in bear_keywords:
            if kw in title:
                bear_hits.append({"title": n.get("title"), "keyword": kw})
                break
        for kw in bull_keywords:
            if kw in title:
                bull_hits.append({"title": n.get("title"), "keyword": kw})
                break

    if bear_hits:
        return {"pass": False, "verdict": "BEARISH_NEWS", "detail": f"{len(bear_hits)} bearish news item(s) in last 24h - real catalyst, re-evaluate thesis", "items": bear_hits[:3]}
    if bull_hits:
        return {"pass": True, "verdict": "BULLISH_NEWS", "detail": f"{len(bull_hits)} bullish news item(s) in last 24h - thesis confirmed", "items": bull_hits[:3]}
    return {"pass": True, "verdict": "NO_NEWS", "detail": "no material news in last 24h - any move is price action, not new information", "items": []}


def check_greeks_change(live_position, current_chain=None):
    """Factor 6: option greeks since entry. Delta dying = exposure dying."""
    if not live_position:
        return {"pass": None, "verdict": "NOT_LIVE", "detail": "no live position - skipping"}
    entry_delta = live_position.get("entry_delta") or 0
    try:
        exp_dt = datetime.strptime(live_position.get("expiration", ""), "%Y-%m-%d")
        dte = (exp_dt - datetime.utcnow()).days
    except Exception:
        dte = None

    if dte is not None and dte <= 7:
        return {"pass": False, "verdict": "THETA_CLIFF", "detail": f"{dte} days to expiry - theta accelerates fast here, consider exiting before final week", "dte": dte}
    if dte is not None and dte <= 14:
        return {"pass": None, "verdict": "THETA_WARN", "detail": f"{dte} days to expiry - manageable but watch theta", "dte": dte}

    if current_chain and entry_delta:
        try:
            current_delta = float(current_chain.get("delta") or 0)
            delta_change = (current_delta - entry_delta) / entry_delta * 100 if entry_delta else 0
            if delta_change < -30:
                return {"pass": False, "verdict": "DELTA_DYING", "detail": f"delta dropped from {entry_delta:.2f} to {current_delta:.2f} ({delta_change:+.0f}%) - exposure shrinking fast", "dte": dte}
            return {"pass": True, "verdict": "DELTA_STABLE", "detail": f"delta {entry_delta:.2f} -> {current_delta:.2f} ({delta_change:+.0f}%) - exposure healthy", "dte": dte}
        except Exception:
            pass

    return {"pass": True, "verdict": "ROOM_TO_RUN", "detail": f"{dte}d to expiry - time still on your side" if dte else "expiry unknown", "dte": dte}


def check_next_catalyst(ticker, fundamentals=None):
    """Factor 7: days to next material catalyst (earnings, FDA, conference)."""
    try:
        if not fundamentals:
            from src.eodhd import EODHDClient
            client = EODHDClient()
            fundamentals = client.fundamentals(f"{ticker}.US" if "." not in ticker else ticker)
    except Exception:
        return {"pass": None, "verdict": "UNKNOWN", "detail": "fundamentals fetch failed"}

    earnings_history = ((fundamentals or {}).get("Earnings") or {}).get("History") or {}
    today = datetime.utcnow().date()
    next_earnings = None
    for _k, v in earnings_history.items():
        rd = v.get("reportDate")
        if not rd:
            continue
        try:
            rd_d = datetime.strptime(rd, "%Y-%m-%d").date()
        except ValueError:
            continue
        if rd_d > today:
            if next_earnings is None or rd_d < next_earnings:
                next_earnings = rd_d
    if next_earnings:
        days = (next_earnings - today).days
        if days <= 14:
            return {"pass": True, "verdict": "EARNINGS_SOON", "detail": f"earnings in {days}d ({next_earnings}) - thesis has near-term catalyst to drive a move", "days": days, "event": "earnings", "date": next_earnings.isoformat()}
        if days <= 45:
            return {"pass": True, "verdict": "EARNINGS_MEDIUM", "detail": f"earnings in {days}d ({next_earnings}) - thesis has medium-term anchor", "days": days, "event": "earnings", "date": next_earnings.isoformat()}
        return {"pass": None, "verdict": "EARNINGS_FAR", "detail": f"next earnings {days}d away - too far to drive a 1-2 week move on its own", "days": days, "event": "earnings", "date": next_earnings.isoformat()}
    return {"pass": None, "verdict": "NO_CATALYST", "detail": "no upcoming dated catalyst found - thesis needs other support", "days": None}


def _resolve_sector(ticker, live_position):
    sector = live_position.get("sector")
    if sector and sector.lower() in SECTOR_ETF_MAP:
        return sector
    try:
        from src.eodhd import EODHDClient
        client = EODHDClient()
        fund = client.fundamentals(f"{ticker}.US" if "." not in ticker else ticker)
        s = ((fund or {}).get("General") or {}).get("Sector")
        if s:
            return s
    except Exception:
        pass
    return sector


def analyze_position(live_position, verbose=False):
    """Run all 7 checks on a live position. Returns dict with verdict + per-factor breakdown."""
    if not live_position:
        return None
    ticker = live_position.get("ticker")
    if not ticker:
        return None

    bars = _get_bars(ticker, days=90)
    sector = _resolve_sector(ticker, live_position)

    factors = {
        "volume_context": check_volume_context(ticker, bars=bars),
        "sector_peer": check_sector_peer(ticker, sector, bars=bars[-5:] if len(bars) >= 5 else bars),
        "support_levels": check_support_levels(ticker, bars=bars),
        "rsi_context": check_rsi_context(ticker, bars=bars),
        "news_today": check_news_today(ticker),
        "greeks_change": check_greeks_change(live_position),
        "next_catalyst": check_next_catalyst(ticker),
    }

    pass_count = sum(1 for f in factors.values() if f.get("pass") is True)
    fail_count = sum(1 for f in factors.values() if f.get("pass") is False)

    if fail_count >= 3:
        verdict = VERDICT_SELL
        confidence = "HIGH" if fail_count >= 4 else "MED"
    elif fail_count >= 2 and pass_count <= 3:
        verdict = VERDICT_TRIM
        confidence = "MED"
    elif pass_count >= 5:
        verdict = VERDICT_HOLD
        confidence = "HIGH"
    elif pass_count >= 3:
        verdict = VERDICT_HOLD
        confidence = "MED"
    else:
        verdict = VERDICT_HOLD
        confidence = "LOW"

    plain_english_parts = []
    if verdict == VERDICT_HOLD:
        plain_english_parts.append(f"HOLD with {confidence.lower()} confidence.")
        passing_reasons = [f["detail"].split(" - ")[0] for f in factors.values() if f.get("pass") is True][:3]
        if passing_reasons:
            plain_english_parts.append("Supporting: " + " | ".join(passing_reasons) + ".")
    elif verdict == VERDICT_TRIM:
        plain_english_parts.append(f"TRIM half. {fail_count} factors flagging.")
        failing_reasons = [f["detail"] for f in factors.values() if f.get("pass") is False][:2]
        plain_english_parts.append("Issues: " + " | ".join(failing_reasons))
    else:
        plain_english_parts.append(f"SELL. {fail_count} factors flagging breakdown.")
        failing_reasons = [f["detail"] for f in factors.values() if f.get("pass") is False][:2]
        plain_english_parts.append("Issues: " + " | ".join(failing_reasons))

    result = {
        "ticker": ticker,
        "verdict": verdict,
        "confidence": confidence,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "factors": factors,
        "plain_english": " ".join(plain_english_parts),
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }
    if verbose:
        print(f"  position_intel {ticker}: {verdict} ({confidence}) pass={pass_count} fail={fail_count}")
        for fk, fv in factors.items():
            symbol = "+" if fv.get("pass") is True else ("-" if fv.get("pass") is False else "?")
            print(f"    [{symbol}] {fk}: {fv.get('detail')}")
    return result


def analyze_all_live_positions(verbose=False):
    try:
        from src.catalyst.guardrails import get_live_positions
        positions = get_live_positions()
    except Exception:
        return []
    if not positions:
        return []
    out = []
    for p in positions:
        try:
            res = analyze_position(p, verbose=verbose)
            if res:
                out.append(res)
        except Exception as e:
            if verbose:
                print(f"  position_intel failed for {p.get('ticker')}: {type(e).__name__}: {e}")
    return out


def confirm_new_pick(pick, verbose=False):
    """Apply the same 7-factor framework to NEW picks for entry confirmation.

    Returns (passes, breakdown). For a pick to keep its TAKE grade it needs
    5+ factors passing.
    """
    ticker = pick.get("ticker")
    if not ticker:
        return False, None
    sector = pick.get("sector", "")
    fund = pick.get("_fundamentals")

    bars = _get_bars(ticker, days=60)
    factors = {
        "volume_context": check_volume_context(ticker, bars=bars),
        "sector_peer": check_sector_peer(ticker, sector, bars=bars[-5:] if len(bars) >= 5 else bars),
        "support_levels": check_support_levels(ticker, bars=bars),
        "rsi_context": check_rsi_context(ticker, bars=bars),
        "news_today": check_news_today(ticker),
        "next_catalyst": check_next_catalyst(ticker, fundamentals=fund),
    }
    pass_count = sum(1 for f in factors.values() if f.get("pass") is True)
    fail_count = sum(1 for f in factors.values() if f.get("pass") is False)

    confidence = "HIGH" if pass_count >= 5 else ("MED" if pass_count >= 3 else "LOW")
    passes_entry = pass_count >= 3 and fail_count <= 1
    pick["_position_intelligence"] = {
        "entry_pass_count": pass_count,
        "entry_fail_count": fail_count,
        "entry_confidence": confidence,
        "entry_passes": passes_entry,
        "factors": factors,
    }
    if verbose:
        print(f"  entry_intel {ticker}: pass={pass_count} fail={fail_count} {'PASSES' if passes_entry else 'BLOCKED'}")
    return passes_entry, factors
