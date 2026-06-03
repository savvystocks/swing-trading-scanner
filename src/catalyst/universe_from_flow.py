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


def _extract_ticker_from_contract(c):
    """Extract underlying ticker from a contract_screener row."""
    if not isinstance(c, dict):
        return None
    t = c.get("ticker_symbol") or c.get("ticker") or c.get("underlying_symbol")
    if t:
        return t
    sym = c.get("option_symbol") or ""
    t2, _ = _extract_ticker_and_side(sym)
    return t2


def _add_to_universe(universe, ticker, source, premium=0, extra=None):
    """Add or merge a ticker into the universe dict with source tagging."""
    if not ticker:
        return
    if ticker in {"SPX", "NDX", "RUT", "VIX", "VVIX", "DJX", "SPXW", "RUTW", "NDXP"}:
        return
    slot = universe.setdefault(ticker, {
        "ticker": ticker,
        "total_premium": 0,
        "trade_count": 0,
        "calls": 0,
        "puts": 0,
        "sources": [],
    })
    if source not in slot["sources"]:
        slot["sources"].append(source)
    if premium > 0:
        slot["total_premium"] = max(slot["total_premium"], premium)
    if extra:
        for k, v in extra.items():
            slot.setdefault(k, v)


def build_flow_universe(uw_client=None, max_tickers=50, min_premium=50_000, verbose=False):
    """Build TODAY's universe via UNION of multiple UW selection methods.

    Sources we pull (each gives ~15-30 tickers, union ~40-60 unique):
      1. Top by flow premium                  - the "main" institutional flow
      2. Top by sweep volume                  - retail-aggressive entries
      3. Top by block trades                  - off-exchange institutional
      4. Top by % move today                  - momentum/news driven
      5. Recent congressional trades          - politician flow (smart money)
      6. Top sectors by ETF flow              - sector rotation candidates

    Tickers ranked by: TOTAL # of sources they appear in (multi-source = higher conviction),
    tiebreak by total premium. This way a stock that appears in 4 sources beats a stock
    that's just #1 by premium alone.

    Returns: list of {ticker, total_premium, trade_count, calls, puts, sources}
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

    universe = {}

    # SOURCE 1: top by flow premium (whole-market flow alerts)
    alerts = uw_client.flow_alerts(limit=500, min_premium=min_premium) or []
    if isinstance(alerts, dict):
        alerts = alerts.get("data") or alerts.get("alerts") or []
    by_ticker = _aggregate_flow_by_ticker(alerts, min_premium=min_premium)
    for t, slot in sorted(by_ticker.items(), key=lambda kv: -kv[1]["total_premium"])[:30]:
        _add_to_universe(universe, t, "premium_top30", premium=slot["total_premium"])
        # also merge the trade counts
        universe[t]["trade_count"] = slot["trade_count"]
        universe[t]["calls"] = slot["calls"]
        universe[t]["puts"] = slot["puts"]
    if verbose:
        print(f"  universe[source 1]: top by premium = {len([u for u in universe.values() if 'premium_top30' in u['sources']])} tickers")

    # SOURCE 2: top by sweep volume via contract_screener
    try:
        sweep_screen = uw_client.contract_screener(sort_by="sweep_volume", limit=30)
        if sweep_screen:
            rows = sweep_screen.get("data") if isinstance(sweep_screen, dict) else sweep_screen
            for c in (rows or [])[:25]:
                t = _extract_ticker_from_contract(c)
                _add_to_universe(universe, t, "sweep_volume",
                                  premium=float(c.get("premium") or 0) if c.get("premium") else 0)
        if verbose:
            print(f"  universe[source 2]: top sweep volume = {len([u for u in universe.values() if 'sweep_volume' in u['sources']])} added")
    except Exception as e:
        if verbose:
            print(f"  universe source 2 (sweeps) failed: {type(e).__name__}: {e}")

    # SOURCE 3: top movers (% gainers/losers today) - intel/movers
    try:
        movers = uw_client._request("/intel/movers", {"limit": 30}, cache_key="darkpool_recent", ttl=300)
        if movers:
            rows = movers.get("data") if isinstance(movers, dict) else movers
            for m in (rows or [])[:20]:
                if not isinstance(m, dict):
                    continue
                t = m.get("ticker") or m.get("symbol")
                _add_to_universe(universe, t, "top_movers")
        if verbose:
            print(f"  universe[source 3]: top movers = {len([u for u in universe.values() if 'top_movers' in u['sources']])} added")
    except Exception as e:
        if verbose:
            print(f"  universe source 3 (movers) failed: {type(e).__name__}: {e}")

    # SOURCE 4: recent congressional trades (last 7 days)
    try:
        congress = uw_client.congress_recent_trades(limit=30)
        if congress:
            rows = congress.get("data") if isinstance(congress, dict) else congress
            for c in (rows or [])[:30]:
                if not isinstance(c, dict):
                    continue
                t = c.get("ticker") or c.get("symbol")
                _add_to_universe(universe, t, "congress")
        if verbose:
            print(f"  universe[source 4]: congress = {len([u for u in universe.values() if 'congress' in u['sources']])} added")
    except Exception as e:
        if verbose:
            print(f"  universe source 4 (congress) failed: {type(e).__name__}: {e}")

    # SOURCE 5: insider buy/sells today
    try:
        insiders = uw_client._request("/market/insider-buy-sells", None, cache_key="oi_change", ttl=1800)
        if insiders:
            rows = insiders.get("data") if isinstance(insiders, dict) else insiders
            for i in (rows or [])[:20]:
                if not isinstance(i, dict):
                    continue
                t = i.get("ticker") or i.get("symbol")
                _add_to_universe(universe, t, "insider_today")
        if verbose:
            print(f"  universe[source 5]: insiders = {len([u for u in universe.values() if 'insider_today' in u['sources']])} added")
    except Exception as e:
        if verbose:
            print(f"  universe source 5 (insider) failed: {type(e).__name__}: {e}")

    # SOURCE 6: net premium tickers (where institutions are NET buying/selling)
    # Already captured in flow_alerts but the contract_screener with different sort surfaces additional.
    try:
        net_prem = uw_client.contract_screener(sort_by="premium", limit=30, side="call")
        if net_prem:
            rows = net_prem.get("data") if isinstance(net_prem, dict) else net_prem
            for c in (rows or [])[:15]:
                t = _extract_ticker_from_contract(c)
                _add_to_universe(universe, t, "net_call_premium")
    except Exception as e:
        if verbose:
            print(f"  universe source 6 failed: {type(e).__name__}: {e}")

    try:
        net_put = uw_client.contract_screener(sort_by="premium", limit=30, side="put")
        if net_put:
            rows = net_put.get("data") if isinstance(net_put, dict) else net_put
            for c in (rows or [])[:15]:
                t = _extract_ticker_from_contract(c)
                _add_to_universe(universe, t, "net_put_premium")
    except Exception as e:
        pass

    # Rank by # of sources (multi-source = higher conviction), tiebreak by total_premium
    ranked = sorted(
        universe.values(),
        key=lambda x: (len(x["sources"]), x["total_premium"]),
        reverse=True,
    )
    top = ranked[:max_tickers]

    if verbose:
        print(f"  universe_from_flow: {len(universe)} unique tickers across all sources, top {len(top)} selected")
        for t in top[:10]:
            srcs = "+".join(t["sources"])
            print(f"    {t['ticker']:6} sources={len(t['sources'])} ({srcs[:40]:40}) ${t['total_premium']/1e6:.1f}M")

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
