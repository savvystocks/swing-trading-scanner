"""Multi-source candidate discovery.

The original pipeline finds candidates one way: scan universe → detect
catalysts → score → narrow. That biases toward press-release-driven names
and misses stealth smart-money setups (e.g. a stock with 5 insiders quietly
buying $2M total but no recent news catalyst).

This module gathers candidate tickers from MULTIPLE external sources in
parallel, tags each candidate with the source(s) that surfaced it, and
returns the union. Downstream the scanner enriches and scores the full
union, so a name discovered via OpenInsider gets the same deep analysis
as a name discovered via catalyst detection.

Sources:
1. OpenInsider cluster buys (insider conviction)
2. WallStreetBets heavy buzz (retail conviction)
3. Google Trends spikes (broad attention)
4. Analyst upgrade headlines from news feed (institutional conviction)
5. Stage 2 prime-entry technical scan (momentum + clean trend)

Each source returns: dict {ticker: {source, reason, score}}.
Aggregator returns: dict {ticker: {sources: [list], reasons: [list], composite_score}}.
"""

import os


SOURCE_WEIGHTS = {
    "openinsider_cluster": 35,
    "openinsider_ceo_cfo": 50,
    "wsb_heavy_buzz": 20,
    "google_trends_spike": 15,
    "analyst_upgrade_cluster": 30,
    "stage2_prime_entry": 25,
}


def _discover_openinsider(min_buyers=2, min_value_usd=100_000, days_back=14):
    try:
        from src.catalyst.openinsider_scraper import fetch_recent_cluster_buys
        data = fetch_recent_cluster_buys(days_back=days_back, min_buyers=min_buyers, min_value_usd=min_value_usd)
    except Exception:
        return {}
    if not isinstance(data, dict) or "_error" in data:
        return {}
    out = {}
    for ticker, info in data.items():
        if not ticker or len(ticker) > 6:
            continue
        ceo = info.get("ceo_or_cfo_bought", False)
        source = "openinsider_ceo_cfo" if ceo else "openinsider_cluster"
        out[ticker] = {
            "source": source,
            "reason": f"{info['buyers_count']} insiders bought ${info['total_value_usd']:,}{' (CEO/CFO)' if ceo else ''} in last {days_back}d",
            "score": SOURCE_WEIGHTS[source],
            "raw": info,
        }
    return out


def _discover_wsb_heavy_buzz(min_mentions=10, min_spike=3.0, ticker_universe=None):
    """Scan WSB-popular tickers for buzz spikes. Universe seeded from a known
    high-momentum list since we can't enumerate WSB easily."""
    if not ticker_universe:
        return {}
    try:
        from src.catalyst.wsb_mentions import compute_wsb_signal
    except Exception:
        return {}
    out = {}
    import time
    for t in ticker_universe[:30]:
        try:
            sig = compute_wsb_signal(t)
            if not sig or sig.get("verdict") != "HEAVY_BUZZ":
                continue
            if sig.get("mentions_7d", 0) < min_mentions or sig.get("spike_ratio", 0) < min_spike:
                continue
            out[t] = {
                "source": "wsb_heavy_buzz",
                "reason": f"WSB {sig['mentions_7d']} mentions/7d ({sig['spike_ratio']}x baseline)",
                "score": SOURCE_WEIGHTS["wsb_heavy_buzz"],
                "raw": sig,
            }
            time.sleep(0.5)
        except Exception:
            continue
    return out


def _discover_trends_spikes(ticker_universe=None):
    if not ticker_universe:
        return {}
    try:
        from src.catalyst.google_trends_buzz import compute_trends_signal
    except Exception:
        return {}
    out = {}
    import time
    for t in ticker_universe[:20]:
        try:
            sig = compute_trends_signal(t)
            if not sig or sig.get("verdict") != "TRENDING_UP":
                continue
            out[t] = {
                "source": "google_trends_spike",
                "reason": f"Google Trends {sig['spike_ratio']}x baseline retail interest spike",
                "score": SOURCE_WEIGHTS["google_trends_spike"],
                "raw": sig,
            }
            time.sleep(1.0)
        except Exception:
            continue
    return out


def _discover_stage2_prime_entry(existing_picks=None):
    """Already-discovered picks that classify as PRIME_ENTRY. Promotes them."""
    if not existing_picks:
        return {}
    try:
        from src.catalyst.stage2_entry import stage2_zone
    except Exception:
        return {}
    out = {}
    for p in existing_picks:
        try:
            z = stage2_zone(p)
            if z and z.get("zone") == "PRIME_ENTRY":
                ticker = p.get("ticker")
                if not ticker:
                    continue
                out[ticker] = {
                    "source": "stage2_prime_entry",
                    "reason": z.get("note", "PRIME_ENTRY"),
                    "score": SOURCE_WEIGHTS["stage2_prime_entry"],
                    "raw": z,
                }
        except Exception:
            continue
    return out


def discover_external_candidates(existing_picks=None, verbose=False):
    """Run all external discovery sources in sequence. Returns merged candidates."""
    all_candidates = {}

    if verbose:
        print("  candidate_aggregator: discovering from OpenInsider...")
    oi = _discover_openinsider(min_buyers=2, min_value_usd=100_000, days_back=14)
    _merge_into(all_candidates, oi)

    existing_tickers = [p.get("ticker") for p in (existing_picks or []) if p.get("ticker")]
    if existing_tickers:
        if verbose:
            print(f"  candidate_aggregator: discovering Stage 2 prime entries from {len(existing_tickers)} existing picks...")
        s2 = _discover_stage2_prime_entry(existing_picks)
        _merge_into(all_candidates, s2)

    if verbose:
        n_external = sum(1 for t in all_candidates if t not in (existing_tickers or []))
        print(f"  candidate_aggregator: discovered {len(all_candidates)} candidates, "
              f"{n_external} NOT in original scan output (new picks to deep-analyze)")

    return all_candidates


def _merge_into(merged, new_source):
    for ticker, info in new_source.items():
        if ticker not in merged:
            merged[ticker] = {
                "ticker": ticker,
                "sources": [info["source"]],
                "reasons": [info["reason"]],
                "composite_score": info["score"],
                "raw_by_source": {info["source"]: info.get("raw", {})},
            }
        else:
            existing = merged[ticker]
            existing["sources"].append(info["source"])
            existing["reasons"].append(info["reason"])
            existing["composite_score"] += info["score"]
            existing["raw_by_source"][info["source"]] = info.get("raw", {})


def find_missed_high_quality_candidates(scan_results, all_external):
    """Return tickers that have strong external signals but are NOT in our scan output."""
    scan_tickers = set()
    for tier in ("A++", "A+", "A"):
        for p in (scan_results or {}).get(tier, []) or []:
            scan_tickers.add(p.get("ticker"))

    missed = []
    for ticker, info in all_external.items():
        if ticker not in scan_tickers and info.get("composite_score", 0) >= 35:
            missed.append({
                "ticker": ticker,
                "composite_score": info["composite_score"],
                "sources": info["sources"],
                "reasons": info["reasons"],
            })
    missed.sort(key=lambda x: -x["composite_score"])
    return missed
