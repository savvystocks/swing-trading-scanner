"""Promote external-discovery stub picks to first-class candidates.

By default the candidate_aggregator produces minimal stubs:
  {ticker, _aa_tier=EXT, _discovered_from, _discovery_reasons, _discovery_composite_score, catalysts}

These stubs lack the fields the scoring pipeline expects (price, market_cap,
sector, ret_5d, fundamentals, etc.), so they never compete in the unified
conviction ranking. They sit dead in the email under EXTERNAL_DISCOVERY.

This module hydrates each external pick with the same data the main universe
gets: live spot via Alpaca, recent OHLCV via Alpaca/EODHD, fundamentals via
EODHD, then optionally Haiku synthesis. After enrichment the pick has every
field the conviction_score / bear_conviction_score modules read.

Budget: enrich top N (default 5) externals only - one EODHD fundamentals call
per pick (~5 credits), one bars call (free via Alpaca), one Haiku synthesis
call (~$0.05). Total cost per scan: ~25 EODHD credits + $0.25 LLM.
"""

import os
from datetime import datetime, timedelta


def _hydrate_from_fundamentals(pick, fund):
    if not fund:
        return
    general = (fund.get("General") or {})
    highlights = (fund.get("Highlights") or {})
    technicals = (fund.get("Technicals") or {})
    pick.setdefault("name", general.get("Name", ""))
    pick.setdefault("sector", general.get("Sector", ""))
    pick.setdefault("industry", general.get("Industry", ""))
    pick.setdefault("description", (general.get("Description") or "")[:400])
    pick.setdefault("market_cap", highlights.get("MarketCapitalization"))
    pick.setdefault("short_pct_float", technicals.get("ShortPercent"))


def _hydrate_from_bars(pick, bars):
    if not bars or len(bars) < 30:
        return
    closes = []
    for b in bars[-90:]:
        try:
            closes.append(float(b.get("close") or 0))
        except Exception:
            continue
    if len(closes) < 30:
        return
    last = closes[-1]
    pick.setdefault("price", round(last, 4))
    pick.setdefault("live_spot", round(last, 4))

    def _safe_ret(periods):
        if len(closes) <= periods:
            return None
        prev = closes[-periods - 1]
        if prev <= 0:
            return None
        return round((last - prev) / prev * 100, 2)

    pick.setdefault("ret_5d", _safe_ret(5))
    pick.setdefault("ret_30d", _safe_ret(30))
    pick.setdefault("ret_90d", _safe_ret(89) if len(closes) >= 90 else None)

    sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
    if sma_50:
        pick.setdefault("above_50dma", last > sma_50)
        pick.setdefault("pct_above_50dma", round((last - sma_50) / sma_50 * 100, 2))

    vol_30d_dollar = None
    try:
        recent = bars[-30:]
        vol_30d_dollar = sum(float(b.get("volume", 0)) * float(b.get("close", 0)) for b in recent) / 30
    except Exception:
        pass
    if vol_30d_dollar is not None:
        pick.setdefault("dollar_volume_20d", round(vol_30d_dollar, 2))


def _eodhd_ticker(t):
    if "." in t:
        return t
    return f"{t}.US"


def _is_us_ticker(t):
    return "." not in t


def enrich_external(pick, eodhd_client, verbose=False):
    ticker = pick.get("ticker")
    if not ticker:
        return False
    if not _is_us_ticker(ticker):
        if verbose:
            print(f"    external enrich {ticker}: skipping non-US ticker")
        return False
    eo_ticker = _eodhd_ticker(ticker)

    try:
        fund = eodhd_client.fundamentals(eo_ticker)
    except Exception as e:
        if verbose:
            print(f"    external enrich {ticker}: fundamentals failed: {type(e).__name__}: {e}")
        fund = None
    if fund:
        _hydrate_from_fundamentals(pick, fund)
        pick["_fundamentals"] = fund

    today = datetime.utcnow().date()
    from_d = (today - timedelta(days=130)).strftime("%Y-%m-%d")
    to_d = today.strftime("%Y-%m-%d")
    try:
        bars = eodhd_client.ohlcv(eo_ticker, from_date=from_d, to_date=to_d)
    except Exception as e:
        if verbose:
            print(f"    external enrich {ticker}: bars failed: {type(e).__name__}: {e}")
        bars = None
    if bars:
        _hydrate_from_bars(pick, bars)

    pick["eodhd_ticker"] = eo_ticker
    pick["_external_enriched"] = True
    return bool(fund) or bool(bars)


def enrich_externals(externals, eodhd_client, max_enrich=5, run_haiku=True, verbose=False):
    if not externals:
        return []

    externals_sorted = sorted(
        externals,
        key=lambda x: -(x.get("_discovery_composite_score") or 0),
    )
    selected = externals_sorted[:max_enrich]

    enriched = []
    for p in selected:
        if not p.get("ticker"):
            continue
        ok = enrich_external(p, eodhd_client, verbose=verbose)
        if not ok:
            continue
        if not p.get("price"):
            if verbose:
                print(f"    external {p['ticker']}: no price after enrichment, skipping")
            continue
        if not p.get("market_cap") or p["market_cap"] < 100_000_000:
            if verbose:
                print(f"    external {p['ticker']}: market_cap below floor, skipping")
            continue
        enriched.append(p)

    if verbose:
        print(f"  external_enrichment: hydrated {len(enriched)} of {len(selected)} externals (top-{max_enrich} by composite)")

    if run_haiku and enriched:
        try:
            from src.catalyst.unified_forensic import apply_haiku_synthesis
            apply_haiku_synthesis(enriched, max_calls=len(enriched), verbose=verbose)
        except Exception as e:
            if verbose:
                print(f"  external_enrichment haiku failed (non-fatal): {type(e).__name__}: {e}")

    for p in enriched:
        p.setdefault("_aa_tier", "EXTERNAL_PROMOTED")

    return enriched
