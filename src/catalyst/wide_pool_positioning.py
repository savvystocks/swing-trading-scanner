"""Wide-Pool Positioning Enrichment - Phase 4a entry point.

Runs the cheap, global-snapshot positioning modules on the FULL final_scored
pool BEFORE bracket routing or AA gates filter anything out.

This is the architectural fix that makes Option C work: positioning intel needs
to be on every candidate when we compute positioning_first scores, not just on
the ~30 names that survived the backward-looking AA gates.

Cheap enrichers (one global snapshot, mapped to N tickers):
  - cftc_cot.enrich_picks_with_cot              (1 CFTC fetch → sector-mapped)
  - macro_positioning.enrich_picks_with_macro   (1 macro snapshot → regime tagged)
  - options_positioning.enrich_picks_with_options_positioning  (1 VIX snapshot)
  - sentiment_stack.enrich_picks_with_sentiment (1 CNN F&G + PB scrape)
  - forward_data.enrich_picks_with_forward_data (TSLA/GM/F delivery dates + EPS revisions)

Expensive enrichers (run later on top-K positioning candidates only):
  - dealer_gex     (Black-Scholes per chain, ~5s/ticker)
  - squeeze_setup  (per-ticker shares stats)
  - auction_market (per-ticker volume profile, 90d bars)
  - activist_13d   (EDGAR per-ticker scrape)
  - earnings_history (EODHD per-ticker)

After this enrichment, positioning_first.apply_positioning_first() can be run
on the full pool to score every ticker by positioning extremes.
"""


def apply_wide_pool_positioning(picks, macro=None, verbose=False, max_picks=400):
    """Run cheap global-snapshot positioning enrichment on the wide pool.

    Picks become tagged with _cot_positioning, _macro_positioning,
    _options_positioning, _sentiment_stack, _analyst_revisions.

    Args:
      picks: list of final_scored dicts (wider than ranked_picks)
      macro: optional macro snapshot dict, gets enriched with macro_positioning
      max_picks: cap to avoid runaway calls (analyst revisions is per-ticker EPS fetch)
    """
    if not picks:
        return picks, macro

    pool = picks[:max_picks]

    try:
        from src.catalyst.cftc_cot import enrich_picks_with_cot
        enrich_picks_with_cot(pool, verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  wide_pool cftc_cot failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.macro_positioning import enrich_picks_with_macro
        enrich_picks_with_macro(pool, verbose=verbose)
        if macro is None:
            macro = {}
        first_with_macro = next((p.get("_macro_positioning") for p in pool if p.get("_macro_positioning")), None)
        if first_with_macro:
            macro["macro_positioning"] = first_with_macro
    except Exception as e:
        if verbose:
            print(f"  wide_pool macro_positioning failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.options_positioning import enrich_picks_with_options_positioning
        enrich_picks_with_options_positioning(pool, verbose=verbose)
        first_with_opt = next((p.get("_options_positioning") for p in pool if p.get("_options_positioning")), None)
        if first_with_opt and isinstance(macro, dict):
            macro["options_positioning"] = first_with_opt
    except Exception as e:
        if verbose:
            print(f"  wide_pool options_positioning failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.sentiment_stack import enrich_picks_with_sentiment
        enrich_picks_with_sentiment(pool, verbose=verbose)
        first_with_sent = next((p.get("_sentiment_stack") for p in pool if p.get("_sentiment_stack")), None)
        if first_with_sent and isinstance(macro, dict):
            macro["sentiment_stack"] = first_with_sent
    except Exception as e:
        if verbose:
            print(f"  wide_pool sentiment_stack failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.forward_data import enrich_picks_with_forward_data
        enrich_picks_with_forward_data(pool, max_picks=min(60, len(pool)), verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  wide_pool forward_data failed: {type(e).__name__}: {e}")

    # Path 3 gap-fill 3: FINRA margin debt regime as a market-wide overlay.
    try:
        from src.catalyst.finra_margin import enrich_picks_with_margin
        enrich_picks_with_margin(pool, verbose=verbose)
        margin_data = next((p.get("_finra_margin_regime") for p in pool if p.get("_finra_margin_regime")), None)
        if margin_data and isinstance(macro, dict):
            macro["finra_margin"] = margin_data
    except Exception as e:
        if verbose:
            print(f"  wide_pool finra_margin failed: {type(e).__name__}: {e}")

    if verbose:
        cot_tagged = sum(1 for p in pool if p.get("_cot_positioning"))
        macro_tagged = sum(1 for p in pool if p.get("_macro_positioning"))
        opt_tagged = sum(1 for p in pool if p.get("_options_positioning"))
        sent_tagged = sum(1 for p in pool if p.get("_sentiment_stack"))
        ar_tagged = sum(1 for p in pool if p.get("_analyst_revisions"))
        print(f"  wide_pool_positioning: COT={cot_tagged} macro={macro_tagged} options={opt_tagged} "
              f"sentiment={sent_tagged} analyst_rev={ar_tagged} (pool={len(pool)})")

    return picks, macro


def apply_per_ticker_positioning(picks, max_picks=30, verbose=False):
    """Run expensive per-ticker positioning enrichment on the top-K from wide pool.

    These are the per-ticker computations that were running on ranked_picks
    in the old pipeline - we keep them limited to top candidates by
    positioning_first score (sorted before this call).
    """
    if not picks:
        return picks

    pool = picks[:max_picks]

    try:
        from src.catalyst.dealer_gex import enrich_picks_with_gex
        enrich_picks_with_gex(pool, max_picks=min(15, len(pool)), verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  per_ticker dealer_gex failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.squeeze_setup import enrich_picks_with_squeeze
        enrich_picks_with_squeeze(pool, max_picks=min(30, len(pool)), verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  per_ticker squeeze_setup failed: {type(e).__name__}: {e}")

    try:
        from src.catalyst.auction_market import enrich_picks_with_auction_levels
        enrich_picks_with_auction_levels(pool, max_picks=min(20, len(pool)), verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"  per_ticker auction_market failed: {type(e).__name__}: {e}")

    if verbose:
        gex_tagged = sum(1 for p in pool if p.get("_dealer_gex"))
        sq_tagged = sum(1 for p in pool if p.get("_squeeze_setup"))
        au_tagged = sum(1 for p in pool if p.get("_auction_levels"))
        print(f"  per_ticker_positioning: GEX={gex_tagged} squeeze={sq_tagged} auction={au_tagged} (top {len(pool)})")

    return picks
