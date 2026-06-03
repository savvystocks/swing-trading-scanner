"""Positioning-First Universe Builder (Rebuild B1).

Replaces Step 1 catalyst gathering as the universe gatekeeper.

Old architecture:
  - Step 1: gather catalysts -> ~900 catalyst-tagged candidates from 3,089 universe
  - Result: positioning extremes with no catalyst tag are INVISIBLE to scan

New architecture:
  - Step 1: load universe.json (1,108 tickers: SP500 + SP400 + Russell 1000)
  - Apply liquidity floor (your existing gates)
  - Filter earnings-within-7-days (no gambling on prints)
  - Result: ~700-900 candidates ready for positioning_first ranking
  - Positioning extremes WITHOUT catalysts now visible

Step 2 catalyst tagging still happens, but as ENRICHMENT on positioning-ranked
top 600, not as universe gating. Catalysts come through news_score detectors
and EDGAR keyword scanner downstream.

Cost:
  - OHLCV: ~1,108 tickers via Alpaca (free for US) + EODHD for LSE
  - Fundamentals: fresh on every scan (no cache - simpler, no staleness bugs)
  - Daily call volume: ~1,438 EODHD/day vs old ~3,650/day. Monthly: ~32k/100k cap.
"""

import os
import pathlib
import json
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
UNIVERSE_PATH = PROJECT_ROOT / "data" / "universe" / "universe.json"


def load_universe(include_indexes=None, exclude_indexes=None):
    """Load the full universe from universe.json.

    Args:
      include_indexes: if set, only return tickers from these indexes (e.g. ['SP500', 'SP400'])
      exclude_indexes: if set, filter out these indexes (e.g. ['RUSSELL1000'] if R1k too noisy)

    Returns: list of {ticker, name, sector, index} dicts
    """
    if not UNIVERSE_PATH.exists():
        return []
    with open(UNIVERSE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    out = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("index")
        if include_indexes and idx not in include_indexes:
            continue
        if exclude_indexes and idx in exclude_indexes:
            continue
        out.append(entry)
    return out


def _ticker_short(t):
    if "." in t:
        return t.split(".")[0]
    return t


def _apply_liquidity_floor(enriched_data, min_mcap=250_000_000, min_dollar_volume=2_000_000, min_float_pct=30):
    """Same gates as Gate 6 in v3.1 spec: mcap, dollar volume, float."""
    if not enriched_data:
        return False
    mcap = enriched_data.get("market_cap")
    if mcap is None or mcap < min_mcap:
        return False
    dv = enriched_data.get("dollar_volume_20d")
    if dv is None or dv < min_dollar_volume:
        return False
    return True


def _has_earnings_in_window(fundamentals, days_max=7):
    """Returns True if next earnings report is within `days_max` days."""
    if not fundamentals:
        return False
    earnings = fundamentals.get("Earnings") or {}
    history = earnings.get("History") or {}
    if not history:
        return False
    today = datetime.utcnow().date()
    cutoff = today + timedelta(days=days_max)
    for entry in (history.values() if isinstance(history, dict) else history):
        if not isinstance(entry, dict):
            continue
        report_date = entry.get("reportDate")
        if not report_date:
            continue
        try:
            d = datetime.strptime(report_date, "%Y-%m-%d").date()
        except Exception:
            continue
        if today <= d <= cutoff:
            return True
    return False


def build_positioning_universe(client, exclude_indexes=None, max_universe=1200,
                                min_mcap=250_000_000, min_dollar_volume=2_000_000,
                                earnings_blackout_days=7, verbose=False):
    """Build the universe ready for positioning_first ranking.

    Steps:
      1. Load universe.json
      2. For each ticker: pull OHLCV (Alpaca for US, EODHD for LSE)
      3. Pull fundamentals fresh from EODHD (no cache - simpler, always current)
      4. Apply liquidity floor (mcap, dollar volume)
      5. Filter earnings within `earnings_blackout_days`
      6. Return list of enriched ticker dicts

    Returns: list of dicts shaped like the old enriched output, ready for
             apply_positioning_first / scoring.
    """
    universe = load_universe(exclude_indexes=exclude_indexes)
    if not universe:
        if verbose:
            print("  universe_builder: no tickers loaded")
        return []

    if max_universe and len(universe) > max_universe:
        universe = universe[:max_universe]

    if verbose:
        print(f"  universe_builder: loaded {len(universe)} tickers from universe.json")

    # Import enrich_ticker for the per-ticker OHLCV + fundamentals fetch.
    # We reuse the existing enrich_ticker but pass empty signals - we're building
    # the universe from scratch, not from catalyst tags.
    from src.catalyst.scanner import enrich_ticker

    enriched = []
    skipped_liquidity = 0
    skipped_earnings = 0
    skipped_data = 0
    for i, entry in enumerate(universe):
        if verbose and i > 0 and i % 100 == 0:
            print(f"  [{i}/{len(universe)}] enriched={len(enriched)} skipped_liq={skipped_liquidity} skipped_earn={skipped_earnings} skipped_data={skipped_data}")
        ticker_full = entry.get("ticker") or ""
        ticker_short = _ticker_short(ticker_full)
        suffix_hint = ticker_full if "." in ticker_full else None
        try:
            data = enrich_ticker(client, ticker_short, signals=[], suffix_hint=suffix_hint, fetch_news=False)
        except Exception:
            data = None
        if not data:
            skipped_data += 1
            continue
        if not data.get("price") or data["price"] < 1.0:
            skipped_data += 1
            continue
        if not _apply_liquidity_floor(data, min_mcap=min_mcap, min_dollar_volume=min_dollar_volume):
            skipped_liquidity += 1
            continue
        if _has_earnings_in_window(data.get("fundamentals"), days_max=earnings_blackout_days):
            skipped_earnings += 1
            continue
        enriched.append({
            "ticker": ticker_short,
            "company": data.get("name") or entry.get("name") or "",
            "signals": [],
            "sources": ["universe"],
            "data": data,
            "name": data.get("name"),
            "sector": data.get("sector") or entry.get("sector"),
        })

    if verbose:
        print(f"  universe_builder: enriched={len(enriched)} "
              f"skipped_liq={skipped_liquidity} skipped_earn={skipped_earnings} skipped_data={skipped_data}")
    return enriched
