"""Module 2: VCP (Volatility Contraction Pattern) + Quiet Relative Strength.

Minervini's signature setup. Identifies stocks LOADING for a breakout BEFORE
the breakout happens. ~80% of explosive momentum moves are preceded by VCP.

Three checks combined:
1. Bollinger Band squeeze - current BB width in bottom 25% of 6-month range
2. ATR contraction - 20-day ATR declining for 10+ days
3. Quiet RS - stock outperforming sector ETF over 20 days WITHOUT making new highs

Picks meeting 2/3 get a "BREAKOUT SETUP" badge and conviction boost.
Picks meeting 3/3 get a "PRIME BREAKOUT" tag.

All free data (Alpaca + EODHD daily bars). Adds the B archetype to the system.
"""

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


def _get_bars(ticker, days=220, pick=None):
    # Path 3 Fix 4: prefer already-fetched OHLCV from Step 2 enrichment.
    if pick is not None:
        enriched = pick.get("_enriched_data") or {}
        df = enriched.get("df")
        if df is not None and len(df) >= 20:
            tail = df.tail(min(days, len(df)))
            bars = []
            for idx, row in tail.iterrows():
                try:
                    bars.append({
                        "date": str(idx)[:10],
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "open": float(row.get("open", row["close"])),
                        "volume": float(row.get("volume") or 0),
                    })
                except Exception:
                    continue
            if bars:
                return bars
    try:
        from src.alpaca_ohlcv import get_daily_bars
        from datetime import date
        end = date.today()
        start = end - timedelta(days=days + 10)
        bars = get_daily_bars(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if bars:
            return bars
    except Exception:
        pass
    try:
        from src.eodhd import EODHDClient
        from datetime import date
        client = EODHDClient()
        end = date.today()
        start = end - timedelta(days=days + 10)
        bars = client.ohlcv(f"{ticker}.US" if "." not in ticker else ticker,
                            from_date=start.strftime("%Y-%m-%d"),
                            to_date=end.strftime("%Y-%m-%d"))
        return bars or []
    except Exception:
        return []


def _bollinger_band_width(closes, period=20, stddev_mult=2):
    """Return BB width as % of price."""
    if len(closes) < period:
        return None
    window = closes[-period:]
    mean = sum(window) / period
    variance = sum((x - mean) ** 2 for x in window) / period
    sd = variance ** 0.5
    upper = mean + stddev_mult * sd
    lower = mean - stddev_mult * sd
    if mean <= 0:
        return None
    return (upper - lower) / mean * 100


def check_bollinger_squeeze(ticker, bars=None):
    """Factor 1: is current BB width in the bottom 25% of last 6 months?"""
    bars = bars or _get_bars(ticker, days=180)
    if len(bars) < 130:
        return {"pass": None, "verdict": "INSUFFICIENT_BARS", "detail": f"only {len(bars)} bars, need 130+"}
    closes = [float(b.get("close") or 0) for b in bars]
    widths = []
    for i in range(20, len(closes)):
        w = _bollinger_band_width(closes[: i + 1])
        if w is not None:
            widths.append(w)
    if len(widths) < 60:
        return {"pass": None, "verdict": "INSUFFICIENT_BARS", "detail": f"only {len(widths)} BB readings"}
    current_w = widths[-1]
    rank = sum(1 for w in widths if w >= current_w) / len(widths) * 100
    if rank >= 75:
        return {"pass": True, "verdict": "SQUEEZED", "detail": f"BB width {current_w:.1f}% (rank {rank:.0f} - bottom 25% of last 6 months = tightly coiled)", "width_pct": round(current_w, 2), "rank": round(rank, 1)}
    if rank >= 50:
        return {"pass": None, "verdict": "MILD_SQUEEZE", "detail": f"BB width {current_w:.1f}% (rank {rank:.0f} - slight contraction)", "width_pct": round(current_w, 2), "rank": round(rank, 1)}
    return {"pass": False, "verdict": "EXPANDED", "detail": f"BB width {current_w:.1f}% (rank {rank:.0f} - bands wide, no coiling)", "width_pct": round(current_w, 2), "rank": round(rank, 1)}


def _true_range(high, low, prev_close):
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def check_atr_contraction(ticker, bars=None):
    """Factor 2: is 20-day ATR declining vs 10 days ago?"""
    bars = bars or _get_bars(ticker, days=60)
    if len(bars) < 35:
        return {"pass": None, "verdict": "INSUFFICIENT_BARS", "detail": f"only {len(bars)} bars"}
    parsed = []
    for b in bars[-35:]:
        try:
            parsed.append({"high": float(b["high"]), "low": float(b["low"]), "close": float(b["close"])})
        except Exception:
            return {"pass": None, "verdict": "PARSE_ERROR", "detail": "bar parse failed"}
    trs = []
    for i in range(1, len(parsed)):
        trs.append(_true_range(parsed[i]["high"], parsed[i]["low"], parsed[i - 1]["close"]))
    if len(trs) < 30:
        return {"pass": None, "verdict": "INSUFFICIENT_BARS", "detail": "not enough TR readings"}
    atr_now = sum(trs[-20:]) / 20
    atr_10d_ago = sum(trs[-30:-10]) / 20
    if atr_10d_ago <= 0:
        return {"pass": None, "verdict": "UNKNOWN", "detail": "ATR baseline zero"}
    contraction_pct = (atr_now - atr_10d_ago) / atr_10d_ago * 100
    if contraction_pct <= -15:
        return {"pass": True, "verdict": "CONTRACTING_HARD", "detail": f"ATR contracted {contraction_pct:+.0f}% vs 10d ago - vol coiling fast", "contraction_pct": round(contraction_pct, 1)}
    if contraction_pct <= -5:
        return {"pass": True, "verdict": "CONTRACTING", "detail": f"ATR contracted {contraction_pct:+.0f}% vs 10d ago - vol coiling", "contraction_pct": round(contraction_pct, 1)}
    if contraction_pct >= 15:
        return {"pass": False, "verdict": "EXPANDING", "detail": f"ATR expanded {contraction_pct:+.0f}% - vol breakout already happened", "contraction_pct": round(contraction_pct, 1)}
    return {"pass": None, "verdict": "FLAT", "detail": f"ATR change {contraction_pct:+.0f}% - no clear contraction", "contraction_pct": round(contraction_pct, 1)}


def check_quiet_rs(ticker, sector, bars=None):
    """Factor 3: outperforming sector ETF over 20 days without making new highs."""
    etf = SECTOR_ETF_MAP.get((sector or "").lower().strip())
    if not etf:
        return {"pass": None, "verdict": "NO_SECTOR_MAP", "detail": f"no ETF mapped for sector={sector!r}"}
    bars = bars or _get_bars(ticker, days=90)
    etf_bars = _get_bars(etf, days=90)
    if len(bars) < 21 or len(etf_bars) < 21:
        return {"pass": None, "verdict": "INSUFFICIENT_BARS", "detail": "not enough peer bars"}
    try:
        stock_20d = (float(bars[-1]["close"]) - float(bars[-21]["close"])) / float(bars[-21]["close"]) * 100
        etf_20d = (float(etf_bars[-1]["close"]) - float(etf_bars[-21]["close"])) / float(etf_bars[-21]["close"]) * 100
    except Exception:
        return {"pass": None, "verdict": "PARSE_ERROR", "detail": "peer parse failed"}
    rs = stock_20d - etf_20d
    closes = [float(b["close"]) for b in bars[-21:]]
    high_20d = max(closes)
    last = closes[-1]
    pct_off_high = (high_20d - last) / high_20d * 100 if high_20d > 0 else 0
    quiet = pct_off_high >= 3
    if rs >= 5 and quiet:
        return {"pass": True, "verdict": "QUIET_OUTPERFORMER", "detail": f"+{rs:.1f}% RS vs {etf} over 20d, {pct_off_high:.1f}% off 20d high - smart money accumulating quietly", "rs": round(rs, 1), "pct_off_high": round(pct_off_high, 1)}
    if rs >= 5 and not quiet:
        return {"pass": None, "verdict": "STRONG_BUT_PEAKING", "detail": f"+{rs:.1f}% RS vs {etf} but at 20d high - momentum visible, not stealth", "rs": round(rs, 1), "pct_off_high": round(pct_off_high, 1)}
    if rs >= 2 and quiet:
        return {"pass": True, "verdict": "MILD_QUIET_RS", "detail": f"+{rs:.1f}% RS vs {etf}, {pct_off_high:.1f}% off high - mild relative strength building", "rs": round(rs, 1), "pct_off_high": round(pct_off_high, 1)}
    if rs <= -5:
        return {"pass": False, "verdict": "UNDERPERFORMING", "detail": f"{rs:+.1f}% RS vs {etf} over 20d - lagging sector, no edge", "rs": round(rs, 1)}
    return {"pass": None, "verdict": "NEUTRAL", "detail": f"{rs:+.1f}% RS vs {etf}, {pct_off_high:.1f}% off high - inconclusive", "rs": round(rs, 1), "pct_off_high": round(pct_off_high, 1)}


def detect_vcp(ticker, sector, bars=None, verbose=False, pick=None):
    """Run all 3 checks. Returns dict with overall verdict."""
    bars = bars or _get_bars(ticker, days=180, pick=pick)
    bb = check_bollinger_squeeze(ticker, bars=bars)
    atr = check_atr_contraction(ticker, bars=bars)
    rs = check_quiet_rs(ticker, sector, bars=bars)

    pass_count = sum(1 for c in [bb, atr, rs] if c.get("pass") is True)

    if pass_count == 3:
        verdict = "PRIME_BREAKOUT"
        label = "PRIME BREAKOUT SETUP"
        score = 90
    elif pass_count == 2:
        verdict = "BREAKOUT_SETUP"
        label = "BREAKOUT SETUP"
        score = 75
    elif pass_count == 1:
        verdict = "MIXED"
        label = None
        score = 55
    else:
        verdict = "NO_SETUP"
        label = None
        score = 45

    result = {
        "verdict": verdict,
        "badge_label": label,
        "vcp_score": score,
        "pass_count": pass_count,
        "factors": {
            "bollinger_squeeze": bb,
            "atr_contraction": atr,
            "quiet_rs": rs,
        },
    }

    if verbose:
        print(f"  vcp {ticker}: {verdict} ({pass_count}/3) score={score}")
        for fk, fv in result["factors"].items():
            symbol = "+" if fv.get("pass") is True else ("-" if fv.get("pass") is False else "?")
            print(f"    [{symbol}] {fk}: {fv.get('detail')}")
    return result


def enrich_picks_with_vcp(picks, max_picks=30, verbose=False):
    """Attach _vcp_setup dict to top picks. Pure technical, free data."""
    if not picks:
        return picks
    enriched = 0
    primes = 0
    setups = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        sector = p.get("sector", "")
        try:
            res = detect_vcp(ticker, sector, verbose=False, pick=p)
        except Exception:
            continue
        p["_vcp_setup"] = res
        enriched += 1
        if res["verdict"] == "PRIME_BREAKOUT":
            primes += 1
        elif res["verdict"] == "BREAKOUT_SETUP":
            setups += 1
    if verbose:
        print(f"  vcp_detector: enriched {enriched}/{min(max_picks, len(picks))} picks - {primes} PRIME, {setups} SETUP, others mixed/none")
    return picks
