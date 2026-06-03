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


ETF_BLACKLIST = {
    # Broad index trackers
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "IVV", "SPLG", "VEA", "VWO", "EFA", "EEM",
    # Sector SPDRs
    "XLE", "XLF", "XLK", "XLV", "XLP", "XLB", "XLY", "XLI", "XLU", "XLRE", "XLC",
    # Leveraged
    "TQQQ", "SQQQ", "SOXL", "SOXS", "SPXL", "SPXS", "UPRO", "SPXU",
    "FAS", "FAZ", "TNA", "TZA", "LABU", "LABD",
    "NUGT", "JNUG", "DUST", "JDST", "UVXY", "VXX", "SVXY", "VIXY",
    "URTY", "SRTY", "TECL", "TECS", "FNGU", "FNGD", "WEBL", "WEBS",
    "BOIL", "KOLD", "ERX", "ERY",
    # Bond / rate
    "TLT", "IEF", "SHY", "LQD", "HYG", "AGG", "BND", "TBT", "TMF",
    # Commodity
    "GLD", "SLV", "USO", "UNG", "GDX", "GDXJ", "GLDM", "IAU",
    # Country / regional
    "EWZ", "FXI", "INDA", "MCHI", "EWJ", "EWG", "EWY",
    # Crypto-adjacent
    "GBTC", "ETHE", "BITO", "BITX", "IBIT", "FBTC", "ETHA",
    # Innovation / thematic
    "ARKK", "ARKG", "ARKW", "ARKQ", "ARKF",
    # Dividend / value
    "SCHD", "DGRO", "VYM", "VIG", "JEPI", "JEPQ",
    # Other levered single-name
    "TSLL", "TSDD", "NVDL", "NVDS", "MSFU", "AAPU", "AAPD",
}


def _add_to_universe(universe, ticker, source, premium=0, extra=None):
    """Add or merge a ticker into the universe dict with source tagging."""
    if not ticker:
        return
    if ticker in {"SPX", "NDX", "RUT", "VIX", "VVIX", "DJX", "SPXW", "RUTW", "NDXP"}:
        return
    if ticker in ETF_BLACKLIST:
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


# Source-to-pattern coverage matrix.
# Each source surfaces tickers that are likely to score on certain confluence patterns.
# Patterns: P1=NOPE Extreme, P2=Gamma Flip, P3=Sweeps+Floor, P4=Vol>OI,
#           P5=Above-Ask Urgency, P6=$250k Institutional, P7=Whisper Delta
SOURCE_PATTERN_MAP = {
    "premium_top30":   ["P1", "P5", "P6"],      # high concentrated premium
    "sweep_volume":    ["P3", "P5"],            # sweep urgency
    "top_movers":      ["P2", "P5"],            # % movers hit gamma walls
    "congress":        ["P6"],                  # smart money positioning
    "insider_today":   ["P6"],                  # insider conviction
    "net_call_premium":["P1", "P6"],            # directional CALL flow
    "net_put_premium": ["P1", "P6"],            # directional PUT flow
    "pattern_calls":   ["P4", "P5", "P6"],      # pre-matched stack via screener filters
    "pattern_puts":    ["P4", "P5", "P6"],      # pre-matched stack via screener filters
    "high_volume":     ["P3", "P4"],            # volume leaders
    "oi_changers":     ["P4"],                  # OI building = new positioning
    "earnings_today":  ["P7"],                  # whisper opportunities
    "earnings_tmrw":   ["P7"],                  # tomorrow's catalyst
    "darkpool_top":    ["P6"],                  # institutional dark prints
    "news_today":      ["P5", "P7"],            # news-driven flow
    "shorts_squeeze":  ["P5"],                  # squeeze setups
    "analyst_changes": ["P5", "P6"],            # rating moves drive flow
}


def build_flow_universe(uw_client=None, max_tickers=60, min_premium=50_000, verbose=False):
    """Build TODAY's universe via UNION of 14 UW selection methods.

    Each source pulls top 25-30 tickers from a DIFFERENT angle so we don't
    self-select on one metric. Ranked by # of sources appeared in (multi-source
    = higher conviction), tiebreak by total premium.

    See SOURCE_PATTERN_MAP for which patterns each source feeds.

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
    source_counts = {}

    def _log_source(idx, name, intent):
        n = len([u for u in universe.values() if name in u["sources"]])
        source_counts[name] = n
        patterns = SOURCE_PATTERN_MAP.get(name, [])
        if verbose:
            print(f"  [src {idx:2}] {name:18} {n:3}t  {intent:38} -> {','.join(patterns)}")

    # SOURCE 1: top by flow premium (whole-market flow alerts)
    alerts = uw_client.flow_alerts(limit=500, min_premium=min_premium) or []
    if isinstance(alerts, dict):
        alerts = alerts.get("data") or alerts.get("alerts") or []
    by_ticker = _aggregate_flow_by_ticker(alerts, min_premium=min_premium)
    for t, slot in sorted(by_ticker.items(), key=lambda kv: -kv[1]["total_premium"])[:30]:
        _add_to_universe(universe, t, "premium_top30", premium=slot["total_premium"])
        # ETFs/indexes get filtered inside _add_to_universe - only update if survived
        if t in universe:
            universe[t]["trade_count"] = slot["trade_count"]
            universe[t]["calls"] = slot["calls"]
            universe[t]["puts"] = slot["puts"]
    _log_source(1, "premium_top30", "highest total option premium")

    # SOURCE 2: top by sweep volume
    try:
        sweep_screen = uw_client.contract_screener(sort_by="sweep_volume", limit=30)
        if sweep_screen:
            rows = sweep_screen.get("data") if isinstance(sweep_screen, dict) else sweep_screen
            for c in (rows or [])[:25]:
                t = _extract_ticker_from_contract(c)
                _add_to_universe(universe, t, "sweep_volume",
                                  premium=float(c.get("premium") or 0) if c.get("premium") else 0)
        _log_source(2, "sweep_volume", "retail-aggressive sweep urgency")
    except Exception as e:
        if verbose:
            print(f"  [src  2] sweep_volume FAILED: {type(e).__name__}: {e}")

    # SOURCE 3: top movers (% gainers/losers)
    try:
        movers = uw_client._request("/intel/movers", {"limit": 30}, cache_key="darkpool_recent", ttl=300)
        if movers:
            rows = movers.get("data") if isinstance(movers, dict) else movers
            for m in (rows or [])[:20]:
                if not isinstance(m, dict):
                    continue
                _add_to_universe(universe, m.get("ticker") or m.get("symbol"), "top_movers")
        _log_source(3, "top_movers", "biggest % moves today")
    except Exception as e:
        if verbose:
            print(f"  [src  3] top_movers FAILED: {type(e).__name__}: {e}")

    # SOURCE 4: recent congressional trades
    try:
        congress = uw_client.congress_recent_trades(limit=30)
        if congress:
            rows = congress.get("data") if isinstance(congress, dict) else congress
            for c in (rows or [])[:30]:
                if not isinstance(c, dict):
                    continue
                _add_to_universe(universe, c.get("ticker") or c.get("symbol"), "congress")
        _log_source(4, "congress", "politicians' recent buys/sells")
    except Exception as e:
        if verbose:
            print(f"  [src  4] congress FAILED: {type(e).__name__}: {e}")

    # SOURCE 5: insider buy/sells today
    try:
        insiders = uw_client._request("/market/insider-buy-sells", None, cache_key="oi_change", ttl=1800)
        if insiders:
            rows = insiders.get("data") if isinstance(insiders, dict) else insiders
            for i in (rows or [])[:20]:
                if not isinstance(i, dict):
                    continue
                _add_to_universe(universe, i.get("ticker") or i.get("symbol"), "insider_today")
        _log_source(5, "insider_today", "Form 4 buys/sells today")
    except Exception as e:
        if verbose:
            print(f"  [src  5] insider_today FAILED: {type(e).__name__}: {e}")

    # SOURCE 6: PATTERN-MATCHED CALLS — pre-filter for P4+P5+P6 stack in one query
    # Filters: $250k+ premium, 40%+ above ask, vol>OI ratio >= 1.0, calls only
    try:
        pat_calls = uw_client._request("/screener/option-contracts",
                                        {"order": "premium", "limit": 30,
                                         "min_premium": 250000,
                                         "min_ask_pct": 0.4,
                                         "min_volume_oi_ratio": 1.0,
                                         "option_type": "call"},
                                        cache_key="contract_screener", ttl=300)
        if pat_calls:
            rows = pat_calls.get("data") if isinstance(pat_calls, dict) else pat_calls
            for c in (rows or [])[:20]:
                # Filter stocks only (skip ETFs in screener response)
                if isinstance(c, dict) and (c.get("issue_type") or "").upper() == "ETF":
                    continue
                _add_to_universe(universe, _extract_ticker_from_contract(c), "pattern_calls")
        _log_source(6, "pattern_calls", "pre-matched: P4+P5+P6 calls")
    except Exception as e:
        if verbose:
            print(f"  [src  6] pattern_calls FAILED: {type(e).__name__}: {e}")

    # SOURCE 7: PATTERN-MATCHED PUTS — same stack, put side
    try:
        pat_puts = uw_client._request("/screener/option-contracts",
                                       {"order": "premium", "limit": 30,
                                        "min_premium": 250000,
                                        "min_ask_pct": 0.4,
                                        "min_volume_oi_ratio": 1.0,
                                        "option_type": "put"},
                                       cache_key="contract_screener", ttl=300)
        if pat_puts:
            rows = pat_puts.get("data") if isinstance(pat_puts, dict) else pat_puts
            for c in (rows or [])[:20]:
                if isinstance(c, dict) and (c.get("issue_type") or "").upper() == "ETF":
                    continue
                _add_to_universe(universe, _extract_ticker_from_contract(c), "pattern_puts")
        _log_source(7, "pattern_puts", "pre-matched: P4+P5+P6 puts")
    except Exception as e:
        if verbose:
            print(f"  [src  7] pattern_puts FAILED: {type(e).__name__}: {e}")

    # SOURCE 8: top volume contracts (different from premium - captures retail+0DTE)
    try:
        vol_screen = uw_client.contract_screener(sort_by="volume", limit=30)
        if vol_screen:
            rows = vol_screen.get("data") if isinstance(vol_screen, dict) else vol_screen
            for c in (rows or [])[:25]:
                _add_to_universe(universe, _extract_ticker_from_contract(c), "high_volume")
        _log_source(8, "high_volume", "highest contract volume")
    except Exception as e:
        if verbose:
            print(f"  [src  8] high_volume FAILED: {type(e).__name__}: {e}")

    # SOURCE 9: today's earnings (premarket + afterhours) - whisper plays
    try:
        ern_pm = uw_client.earnings_premarket() or {}
        ern_ah = uw_client.earnings_afterhours() or {}
        for src_data, label in ((ern_pm, "earnings_today"), (ern_ah, "earnings_tmrw")):
            rows = src_data.get("data") if isinstance(src_data, dict) else src_data
            for e_row in (rows or [])[:20]:
                if not isinstance(e_row, dict):
                    continue
                _add_to_universe(universe, e_row.get("ticker") or e_row.get("symbol"), label)
        _log_source(9, "earnings_today", "reporting before open")
        _log_source(10, "earnings_tmrw", "reporting after close")
    except Exception as e:
        if verbose:
            print(f"  [src 9-10] earnings FAILED: {type(e).__name__}: {e}")

    # SOURCE 11: darkpool top tickers - institutional dark prints
    try:
        dp = uw_client.darkpool_recent(limit=60)
        if dp:
            rows = dp.get("data") if isinstance(dp, dict) else dp
            # Aggregate by ticker, top 20 by $ volume
            dp_by_ticker = {}
            for r in (rows or []):
                if not isinstance(r, dict):
                    continue
                t = r.get("ticker") or r.get("symbol")
                if not t:
                    continue
                size = _to_float(r.get("size") or r.get("volume"))
                price = _to_float(r.get("price"))
                dp_by_ticker[t] = dp_by_ticker.get(t, 0) + (size * price)
            for t, _v in sorted(dp_by_ticker.items(), key=lambda kv: -kv[1])[:20]:
                _add_to_universe(universe, t, "darkpool_top")
        _log_source(11, "darkpool_top", "biggest dark pool $ prints")
    except Exception as e:
        if verbose:
            print(f"  [src 11] darkpool_top FAILED: {type(e).__name__}: {e}")

    # SOURCE 12: short squeeze candidates (highest short interest)
    try:
        shorts = uw_client._request("/shorts/most-shorted", {"limit": 30},
                                     cache_key="oi_change", ttl=3600)
        if not shorts:
            shorts = uw_client._request("/short/short_screener", {"limit": 30},
                                         cache_key="oi_change", ttl=3600)
        if shorts:
            rows = shorts.get("data") if isinstance(shorts, dict) else shorts
            for s in (rows or [])[:20]:
                if not isinstance(s, dict):
                    continue
                _add_to_universe(universe, s.get("ticker") or s.get("symbol"), "shorts_squeeze")
        _log_source(12, "shorts_squeeze", "highest short interest")
    except Exception as e:
        if verbose:
            print(f"  [src 12] shorts_squeeze FAILED: {type(e).__name__}: {e}")

    # SOURCE 13: analyst rating changes today (upgrade/downgrade momentum)
    try:
        analyst = uw_client._request("/screener/analyst_ratings", {"limit": 30},
                                      cache_key="oi_change", ttl=3600)
        if not analyst:
            analyst = uw_client._request("/screener/analyst-ratings", {"limit": 30},
                                          cache_key="oi_change", ttl=3600)
        if analyst:
            rows = analyst.get("data") if isinstance(analyst, dict) else analyst
            for a in (rows or [])[:20]:
                if not isinstance(a, dict):
                    continue
                _add_to_universe(universe, a.get("ticker") or a.get("symbol"), "analyst_changes")
        _log_source(13, "analyst_changes", "rating upgrades/downgrades")
    except Exception as e:
        if verbose:
            print(f"  [src 13] analyst_changes FAILED: {type(e).__name__}: {e}")

    # SOURCE 14: contracts with largest OI change today (NEW positioning building)
    try:
        oi_screen = uw_client.contract_screener(sort_by="oi_change", limit=30)
        if oi_screen:
            rows = oi_screen.get("data") if isinstance(oi_screen, dict) else oi_screen
            for c in (rows or [])[:25]:
                _add_to_universe(universe, _extract_ticker_from_contract(c), "oi_changers")
        _log_source(14, "oi_changers", "biggest OI build today")
    except Exception as e:
        if verbose:
            print(f"  [src 14] oi_changers FAILED: {type(e).__name__}: {e}")

    # Rank by # of sources (multi-source = higher conviction), tiebreak by total_premium
    ranked = sorted(
        universe.values(),
        key=lambda x: (len(x["sources"]), x["total_premium"]),
        reverse=True,
    )
    top = ranked[:max_tickers]

    if verbose:
        multi = sum(1 for u in top if len(u["sources"]) >= 2)
        print(f"")
        print(f"  UNIVERSE SUMMARY: {len(universe)} unique tickers across {len(source_counts)} sources")
        print(f"  Selected top {len(top)} ({multi} multi-source = higher conviction)")
        print(f"")
        print(f"  TOP 15 TICKERS BY CONVICTION (# sources, then premium):")
        for t in top[:15]:
            srcs = "+".join(t["sources"])
            patterns = set()
            for s in t["sources"]:
                patterns.update(SOURCE_PATTERN_MAP.get(s, []))
            pat_str = ",".join(sorted(patterns)) if patterns else "-"
            print(f"    {t['ticker']:6} {len(t['sources'])}src  patterns={pat_str:20}  ${t['total_premium']/1e6:5.1f}M  ({srcs[:55]})")

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
