"""Flow-Driven Universe Builder.

Replaces the static 1108-ticker universe.json scan with a dynamic 20-30 ticker
universe selected by institutional options flow today.

The educator's framing: "scan for the best trades" not "scan everything".
This module asks UW: "what tickers had unusual options activity today?"

Pipeline:
  1. Pull top contract flow alerts from UW (premium >= threshold)
  2. Aggregate by underlying ticker (sum premium, count trades)
  3. Take top 20-30 unique tickers by flow premium
  4. Add tickers from any live positions Savvas holds (for position monitoring)
  5. Return list ready for enrichment

Fallback: if UW token missing or API down, falls back to universe_builder
(static universe.json).
"""

import os
import logging
from datetime import datetime


logger = logging.getLogger(__name__)


import re

_OPTION_SYM_RE = re.compile(r"^([A-Z]{1,6})\d{6}([CP])\d+")


def _extract_ticker_and_side(option_chain):
    """Parse UW option_chain symbol like 'AAPL260717C00200000' -> ('AAPL', 'CALL')."""
    if not option_chain:
        return None, None
    m = _OPTION_SYM_RE.match(option_chain.upper())
    if not m:
        return None, None
    return m.group(1), ("CALL" if m.group(2) == "C" else "PUT")


def _to_float(v, default=0):
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _aggregate_flow_by_ticker(alerts, min_premium=50_000):
    """Group flow alerts by underlying ticker, sum premium, count trades.

    UW field shapes (from live API probe):
      - option_chain: 'AAPL260717C00200000' (contains ticker + side + strike)
      - total_premium: string number
      - volume, open_interest: numbers
      - issue_type: null for indexes (SPX/NDX), 'ETF', 'Common Stock' for tradeable
      - next_earnings_date: optional date
      - type: per-ticker endpoint uses 'type' field directly ('call_sweep', etc)
    """
    if not alerts:
        return {}
    by_ticker = {}
    skip_indexes = {"SPX", "NDX", "RUT", "VIX", "VVIX", "DJX", "SPXW", "RUTW", "NDXP"}
    for a in alerts:
        if not isinstance(a, dict):
            continue

        # Try to extract from option_chain FIRST (most reliable across endpoints)
        oc_ticker, oc_side = _extract_ticker_and_side(a.get("option_chain") or "")

        # Direct ticker field overrides
        ticker = a.get("ticker") or a.get("underlying_symbol") or a.get("symbol") or oc_ticker
        if not ticker:
            continue

        # Skip indexes (can't trade on Robinhood retail)
        if ticker in skip_indexes:
            continue

        # Determine side
        side = oc_side  # from option_chain regex
        if not side:
            # Per-ticker endpoint uses 'type' field with values like 'call_sweep', 'put_sweep'
            type_field = (a.get("type") or a.get("option_type") or a.get("side") or "").lower()
            if "call" in type_field:
                side = "CALL"
            elif "put" in type_field:
                side = "PUT"

        prem = _to_float(a.get("total_premium") or a.get("premium") or a.get("trade_value"))
        if prem < min_premium:
            continue

        slot = by_ticker.setdefault(ticker, {"ticker": ticker, "total_premium": 0, "trade_count": 0, "calls": 0, "puts": 0})
        slot["total_premium"] += prem
        slot["trade_count"] += 1
        if side == "CALL":
            slot["calls"] += 1
        elif side == "PUT":
            slot["puts"] += 1
    return by_ticker


def build_flow_universe(uw_client=None, max_tickers=30, min_premium=50_000, verbose=False):
    """Build today's flow-driven universe via UW. Falls back to static universe if disabled.

    Returns list of dicts: {ticker, total_premium, trade_count, calls, puts, sources}
    """
    from src.unusual_whales_api import get_client
    if uw_client is None:
        uw_client = get_client()

    if not uw_client.enabled:
        if verbose:
            print(f"  universe_from_flow: UW token missing - falling back to static universe.json")
        from src.catalyst.universe_builder import load_universe
        static = load_universe()[:max_tickers]
        return [{"ticker": e.get("ticker", "").replace(".US", ""),
                  "total_premium": 0, "trade_count": 0, "calls": 0, "puts": 0,
                  "sector": e.get("sector"), "sources": ["static"]} for e in static]

    # Pull whole-market flow alerts (largest premium first)
    alerts = uw_client.flow_alerts(limit=500, min_premium=min_premium) or []
    if isinstance(alerts, dict):
        alerts = alerts.get("data") or alerts.get("alerts") or []

    by_ticker = _aggregate_flow_by_ticker(alerts, min_premium=min_premium)
    ranked = sorted(by_ticker.values(), key=lambda x: x["total_premium"], reverse=True)
    top = ranked[:max_tickers]

    if verbose:
        print(f"  universe_from_flow: UW returned {len(alerts)} flow alerts, "
              f"{len(by_ticker)} unique tickers, top {len(top)} by premium")
        for t in top[:5]:
            print(f"    {t['ticker']:6} ${t['total_premium']/1e6:5.1f}M  "
                  f"({t['trade_count']} trades, {t['calls']}C/{t['puts']}P)")

    # Tag source
    for t in top:
        t["sources"] = ["uw_flow"]

    return top


def merge_live_positions_into_universe(universe, verbose=False):
    """Ensure any open positions are in the universe even if not in flow today.

    We always need to monitor what we're holding for exit triggers.
    """
    try:
        from src.catalyst.portfolio_context import get_position_summary
        positions = get_position_summary() or {}
        open_tickers = set()
        for pos in (positions.get("open_positions") or []):
            t = pos.get("ticker") or pos.get("underlying")
            if t:
                open_tickers.add(t.replace(".US", ""))
    except Exception:
        open_tickers = set()

    existing = {u.get("ticker") for u in universe}
    added = 0
    for t in open_tickers:
        if t not in existing:
            universe.append({
                "ticker": t,
                "total_premium": 0,
                "trade_count": 0,
                "calls": 0,
                "puts": 0,
                "sources": ["live_position"],
            })
            added += 1
    if verbose and added:
        print(f"  universe_from_flow: added {added} live positions to universe for monitoring")
    return universe
