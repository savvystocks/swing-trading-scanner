"""Flow-First Scanner - the NEW primary scanner.

UW backbone. 7-pattern confluence. Bidirectional output.

Pipeline:
  Step 1: Flow universe (UW)             - top 20-30 tickers by institutional flow
  Step 2: Macro context (free sources)   - CFTC + sentiment + FINRA + CBOE VIX
  Step 3: Per-ticker enrichment (UW)     - GEX, IV rank, OI, dark pool, NOPE
  Step 4: Spot + chain (Alpaca)          - live price + Greeks for top picks
  Step 5: Confluence scoring             - 7 patterns + macro tide alignment
  Step 6: LLM verification (Haiku)       - top 10 by confluence score
  Step 7: Final ranking + output         - email + telegram
  Step 8: Position monitoring            - WebSocket triggers (later)
"""

import os
import sys
from datetime import datetime, timedelta


def _ascii(t):
    """Replace non-ASCII chars in console output."""
    if not isinstance(t, str):
        return t
    return t.encode("ascii", errors="replace").decode("ascii")


def run_flow_scan(target_date=None, verbose=True):
    """Main flow-first scan entry point. Returns scan dict."""
    from src.unusual_whales_api import get_client as get_uw_client
    uw_client = get_uw_client()

    if not uw_client.enabled:
        if verbose:
            print("UNUSUAL_WHALES_TOKEN not set. Cannot run flow-first scan.")
        return None

    scan_date = (target_date if isinstance(target_date, str) else (target_date or datetime.utcnow().date()).strftime("%Y-%m-%d"))

    if verbose:
        print(f"=== FLOW SCAN ({scan_date}) ===")
        print(f"Step 0/8: macro context (CFTC + sentiment + FINRA + CBOE)")

    # Step 0: macro context
    macro = {}
    try:
        from src.catalyst.cftc_cot import get_market_positioning_snapshot, classify_positioning
        from src.catalyst.macro_meta_regime import classify_meta_regime, build_cot_meta
        cot_snap = get_market_positioning_snapshot(refresh=False, verbose=False)
        macro["cot_meta"] = build_cot_meta(cot_snap)
    except Exception as e:
        if verbose:
            print(f"  cot failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.finra_margin import analyze_margin_regime
        macro["finra_margin"] = analyze_margin_regime(verbose=False)
    except Exception as e:
        if verbose:
            print(f"  finra failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.sentiment_stack import get_sentiment_snapshot
        macro["sentiment_stack"] = get_sentiment_snapshot(verbose=False)
    except Exception as e:
        if verbose:
            print(f"  sentiment failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.options_positioning import get_options_market_snapshot
        macro["options_positioning"] = get_options_market_snapshot(verbose=False)
    except Exception as e:
        if verbose:
            print(f"  options positioning failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.macro_positioning import get_macro_snapshot
        mp = get_macro_snapshot(verbose=False)
        if mp:
            macro["macro_positioning"] = mp
    except Exception as e:
        if verbose:
            print(f"  macro positioning failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.macro_meta_regime import classify_meta_regime
        meta = classify_meta_regime(macro, verbose=verbose)
        if meta:
            macro["meta_regime"] = meta
    except Exception as e:
        if verbose:
            print(f"  meta regime failed: {type(e).__name__}: {e}")

    # Step 1: flow universe (50 candidates from 14 UW screeners)
    if verbose:
        print(f"Step 1/8: flow universe (50 candidates from 14 UW screeners)")
    try:
        from src.catalyst.universe_from_flow import build_flow_universe, merge_live_positions_into_universe
        flow_universe = build_flow_universe(uw_client=uw_client, max_tickers=50, min_premium=250_000, verbose=verbose)
        flow_universe = merge_live_positions_into_universe(flow_universe, verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  flow universe failed: {type(e).__name__}: {e}")
        return None

    if not flow_universe:
        if verbose:
            print("  flow universe empty - cannot proceed")
        return {"scan_date": scan_date, "macro": macro, "picks": []}

    # Step 1b: FUNNEL - take top 20 by conviction (# sources + premium)
    # Bottom 30 of universe rarely score MODERATE+ but burn API calls if enriched.
    # Save budget by dropping them BEFORE enrichment.
    flow_universe.sort(
        key=lambda u: (len(u.get("sources") or []), u.get("total_premium", 0)),
        reverse=True,
    )
    deep_n = 20
    flow_universe = flow_universe[:deep_n]
    if verbose:
        print(f"  funnel: top {len(flow_universe)} by conviction selected for deep dive")
        for u in flow_universe[:10]:
            srcs = "+".join(u.get("sources") or [])
            print(f"    {u['ticker']:6} {len(u.get('sources') or []):1}src  ${u.get('total_premium',0)/1e6:5.1f}M  ({srcs[:50]})")

    # Step 2: enrich each ticker with stock info + live spot (UW only)
    if verbose:
        print(f"Step 2/8: enrich tickers with stock info + live spot")
    enriched_picks = []
    dropped_etf = 0
    for entry in flow_universe:
        ticker = entry["ticker"]
        try:
            stock_info = uw_client.stock_info(ticker)
            info = None
            if stock_info and isinstance(stock_info, dict):
                info = stock_info.get("data")
        except Exception:
            info = None

        # Stocks only - drop ETFs (universe blacklist is first pass, this is backstop)
        issue_type = (info or {}).get("issue_type") or ""
        if "ETF" in issue_type.upper():
            dropped_etf += 1
            continue

        # Live spot from UW stock_state (current close, sub-minute fresh during market hours)
        live_spot = None
        try:
            state = uw_client.stock_state(ticker)
            if state and isinstance(state, dict):
                state_data = state.get("data") or state
                live_spot = float(state_data.get("close") or 0) or None
        except Exception:
            live_spot = None

        # Fallback to UW 1-minute candle latest bar
        if live_spot is None:
            try:
                ohlc = uw_client.stock_ohlc(ticker, candle_size="1m")
                if ohlc:
                    rows = ohlc.get("data") if isinstance(ohlc, dict) else ohlc
                    if rows:
                        latest = rows[0] if isinstance(rows[0], dict) else rows[-1]
                        live_spot = float(latest.get("close") or 0) or None
            except Exception:
                pass

        pick = {
            "ticker": ticker,
            "name": (info or {}).get("full_name") or ticker,
            "sector": (info or {}).get("sector"),
            "market_cap": (info or {}).get("marketcap"),
            "next_earnings_date": (info or {}).get("next_earnings_date"),
            "beta": (info or {}).get("beta"),
            "price": live_spot or 0,
            "live_spot": live_spot,
            "_uw_flow_initial": {
                "total_premium": entry.get("total_premium", 0),
                "trade_count": entry.get("trade_count", 0),
                "calls": entry.get("calls", 0),
                "puts": entry.get("puts", 0),
            },
            "sources": entry.get("sources", ["uw_flow"]),
        }
        if pick["price"] and pick["price"] > 0:
            enriched_picks.append(pick)

    if verbose:
        print(f"  enriched: {len(enriched_picks)} of {len(flow_universe)} (dropped {dropped_etf} ETFs)")

    # Step 3: per-ticker UW enrichment (GEX, IV, OI, dark pool)
    if verbose:
        print(f"Step 3/8: UW deep enrichment per ticker (GEX + IV + OI + dark pool)")
    try:
        from src.catalyst.uw_enrichment import enrich_universe_with_uw
        enrich_universe_with_uw(enriched_picks, uw_client=uw_client, max_picks=len(enriched_picks), verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  UW enrichment failed: {type(e).__name__}: {e}")

    # Step 4: positioning_first scoring (uses macro + UW signals already attached)
    if verbose:
        print(f"Step 4/8: positioning_first scoring")
    try:
        from src.catalyst.positioning_first import apply_positioning_first
        apply_positioning_first(enriched_picks, macro=macro, verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  positioning_first failed: {type(e).__name__}: {e}")

    # Step 5: master confluence scoring (7 patterns + positioning + tide)
    if verbose:
        print(f"Step 5/8: master confluence scoring")
    try:
        from src.catalyst.confluence_score import apply_confluence_scoring, rank_picks_by_confluence
        apply_confluence_scoring(enriched_picks, uw_client=uw_client, macro=macro, verbose=verbose)
        ranked = rank_picks_by_confluence(enriched_picks, top_n=15)
    except Exception as e:
        if verbose:
            print(f"  confluence_score failed: {type(e).__name__}: {e}")
        ranked = enriched_picks[:15]

    # Step 6: LLM verification on top 10
    if verbose:
        print(f"Step 6/8: LLM verification on top 10 by confluence")
    try:
        from src.catalyst.llm_grader import grade_candidates
        # grade_candidates expects 'catalysts' field on each pick. Inject minimal stub.
        for p in ranked[:10]:
            p["catalysts"] = [{"label": p.get("_confluence", {}).get("thesis", ""), "key": "confluence"}]
        llm_grades = grade_candidates(ranked[:10], max_grade=10, verbose=verbose)
        for p in ranked[:10]:
            grade = llm_grades.get(p["ticker"])
            if grade:
                p["_llm_grade"] = grade
    except Exception as e:
        if verbose:
            print(f"  LLM grading failed: {type(e).__name__}: {e}")

    # Step 7: bidirectional output
    if verbose:
        print(f"Step 7/8: bidirectional output")
    calls = [p for p in ranked if (p.get("_confluence") or {}).get("side") == "CALL"]
    puts = [p for p in ranked if (p.get("_confluence") or {}).get("side") == "PUT"]
    calls.sort(key=lambda p: (p.get("_confluence") or {}).get("score", 0), reverse=True)
    puts.sort(key=lambda p: (p.get("_confluence") or {}).get("score", 0), reverse=True)

    by_tier = {}
    for p in ranked:
        t = (p.get("_confluence") or {}).get("tier", "PASS")
        by_tier[t] = by_tier.get(t, 0) + 1

    tide_label = ((macro.get("meta_regime") or {}).get("label") or "unknown regime")

    if verbose:
        print(f"=== FLOW SCAN COMPLETE ===")
        print(f"  Universe: {len(enriched_picks)} tickers")
        print(f"  Top by confluence: {len(ranked)}")
        print(f"  Tiers: {by_tier}")
        print(f"  Direction: {len(calls)} CALL / {len(puts)} PUT")
        print(f"  Macro: {tide_label}")
        print(f"  UW calls used: {uw_client.calls_made}")

    return {
        "scan_date": scan_date,
        "macro": macro,
        "universe_size": len(enriched_picks),
        "ranked_picks": ranked,
        "calls": calls[:10],
        "puts": puts[:5],
        "by_tier": by_tier,
        "uw_calls_made": uw_client.calls_made,
    }
