"""Live Data Refresh - intraday update before email fires.

Why this exists:
  Scan fires at ~15:00 BST (30 min after US market open) but EODHD OHLCV is
  yesterday's close. By the time the scan completes, prices have moved 1-5%
  intraday on average and 5-15% on volatile/catalyst names. The technical
  signals (VCP, pocket pivot, MA distance) are still valid based on yesterday's
  patterns, but the POSITIONING signals (am I extended above 200dma RIGHT NOW?
  is this a gap-up chase?) need live data.

What runs here (LATE in pipeline, before email render):
  1. Batch-fetch live spot prices for top 30 ranked_picks (1 Alpaca call, free)
  2. Recompute pct_above_200dma, ret_5d, ret_30d using live spot
  3. Compute gap_pct vs yesterday's close
  4. Re-run positioning_first._bear/bull_positioning_score on top 30 so
     extension/vertical signals reflect intraday move
  5. Pull live option chains + IV/Greeks for top 10 picks (10 Alpaca calls)
     so the Robinhood order block in email shows current-market IV not stale IV
  6. Flag chase risk: gap > +15% = DO_NOT_CHASE, gap < -7% = THESIS_BROKEN

All free via Alpaca. Adds ~20-30s to scan time.

NOTE: We do NOT recompute VCP/pocket pivot/MTF here. Those are end-of-day
pattern detectors and rely on clean closes - intraday noise would corrupt them.
"""

import os
import logging
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


def _batch_fetch_live_spots(tickers):
    """Batch fetch live spots via Alpaca latest-trade. ~1 call per 200 symbols."""
    try:
        from src.catalyst.opening_action import fetch_live_quotes
        quotes, err = fetch_live_quotes(tickers)
        if err:
            logger.debug(f"live_spot fetch error: {err}")
        return quotes
    except Exception as e:
        logger.debug(f"live_spot import/run fail: {e}")
        return {}


def _recompute_live_signals(pick, live_spot):
    """Update positioning fields using live spot. Returns dict of updates applied."""
    updates = {}
    prev_close = pick.get("price")
    if not prev_close or prev_close <= 0:
        return updates

    try:
        gap_pct = (live_spot - prev_close) / prev_close * 100
        updates["gap_pct"] = round(gap_pct, 2)
        pick["gap_pct"] = round(gap_pct, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return updates

    # Update pct_above_200dma using live spot vs the same 200dma value
    df = (pick.get("_enriched_data") or {}).get("df")
    if df is not None and len(df) >= 200:
        try:
            sma_200 = float(df["close"].iloc[-200:].mean())
            if sma_200 > 0:
                new_pct = (live_spot - sma_200) / sma_200 * 100
                pick["pct_above_200dma"] = round(new_pct, 2)
                updates["pct_above_200dma"] = round(new_pct, 2)
        except Exception:
            pass

    # Update pct_above_50dma
    if df is not None and len(df) >= 50:
        try:
            sma_50 = float(df["close"].iloc[-50:].mean())
            if sma_50 > 0:
                new_pct = (live_spot - sma_50) / sma_50 * 100
                pick["pct_above_50dma"] = round(new_pct, 2)
                updates["pct_above_50dma"] = round(new_pct, 2)
        except Exception:
            pass

    # Recompute 5-day return using live spot vs close from 5 days ago
    if df is not None and len(df) >= 6:
        try:
            p5 = float(df["close"].iloc[-6])
            if p5 > 0:
                new_ret = (live_spot - p5) / p5 * 100
                pick["ret_5d"] = round(new_ret, 2)
                updates["ret_5d"] = round(new_ret, 2)
        except Exception:
            pass

    # Recompute 30-day return using live spot
    if df is not None and len(df) >= 31:
        try:
            p30 = float(df["close"].iloc[-31])
            if p30 > 0:
                new_ret = (live_spot - p30) / p30 * 100
                pick["ret_30d"] = round(new_ret, 2)
                updates["ret_30d"] = round(new_ret, 2)
        except Exception:
            pass

    # Recompute % off 52w low
    if df is not None and len(df) >= 252:
        try:
            low_52w = float(df["close"].iloc[-252:].min())
            if low_52w > 0:
                new_pct = (live_spot - low_52w) / low_52w * 100
                pick["pct_off_52w_low"] = round(new_pct, 2)
                updates["pct_off_52w_low"] = round(new_pct, 2)
        except Exception:
            pass

    # Store the live spot and overwrite the "price" field used by downstream consumers
    pick["live_spot"] = round(live_spot, 4)
    pick["price"] = round(live_spot, 4)  # downstream sees current price
    pick["price_eod_prior"] = round(prev_close, 4)  # preserve yesterday's close for reference

    return updates


def _fetch_live_chain_iv(ticker, current_price):
    """Pull live option chain + ATM IV/Greeks for the Robinhood block.

    Returns dict with summary stats - not the full chain (would bloat the JSON).
    """
    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not secret or not current_price:
        return None
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionChainRequest
        import re
    except ImportError:
        return None
    try:
        client = OptionHistoricalDataClient(api_key, secret)
        today = datetime.now()
        # Pull 25-45 day expiration band (where swing-trade options live)
        min_exp = (today + timedelta(days=25)).strftime("%Y-%m-%d")
        max_exp = (today + timedelta(days=45)).strftime("%Y-%m-%d")
        chain_req = OptionChainRequest(
            underlying_symbol=ticker,
            expiration_date_gte=min_exp,
            expiration_date_lte=max_exp,
            strike_price_gte=str(round(current_price * 0.85, 2)),
            strike_price_lte=str(round(current_price * 1.15, 2)),
        )
        snaps = client.get_option_chain(chain_req)
    except Exception:
        return None
    if not snaps:
        return None

    atm_call_iv = None
    atm_put_iv = None
    atm_call_delta = None
    atm_put_delta = None
    atm_call_gamma = None
    atm_call_strike = None
    atm_put_strike = None
    best_call_dist = float("inf")
    best_put_dist = float("inf")

    for sym, s in snaps.items():
        try:
            m = re.match(r"[A-Z]+\d{6}([CP])(\d+)", sym if isinstance(sym, str) else str(sym))
            if not m:
                continue
            is_call = m.group(1) == "C"
            strike = int(m.group(2)) / 1000
            dist = abs(strike - current_price)
            g = getattr(s, "greeks", None)
            iv = getattr(s, "implied_volatility", None)
            if g is None or iv is None or iv <= 0:
                continue
            delta = getattr(g, "delta", None)
            gamma = getattr(g, "gamma", None)
            if delta is None:
                continue
            if is_call and dist < best_call_dist:
                best_call_dist = dist
                atm_call_iv = float(iv)
                atm_call_delta = float(delta)
                atm_call_gamma = float(gamma) if gamma is not None else None
                atm_call_strike = strike
            elif (not is_call) and dist < best_put_dist:
                best_put_dist = dist
                atm_put_iv = float(iv)
                atm_put_delta = float(delta)
                atm_put_strike = strike
        except Exception:
            continue

    if atm_call_iv is None and atm_put_iv is None:
        return None

    return {
        "atm_call_iv_pct": round(atm_call_iv * 100, 1) if atm_call_iv else None,
        "atm_put_iv_pct": round(atm_put_iv * 100, 1) if atm_put_iv else None,
        "atm_call_delta": round(atm_call_delta, 3) if atm_call_delta else None,
        "atm_put_delta": round(atm_put_delta, 3) if atm_put_delta else None,
        "atm_call_gamma": round(atm_call_gamma, 5) if atm_call_gamma else None,
        "atm_call_strike": atm_call_strike,
        "atm_put_strike": atm_put_strike,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }


def apply_live_refresh(picks, macro=None, top_n_spot=30, top_n_chain=10, verbose=False):
    """Apply intraday live refresh to top picks before email render.

    Order:
      1. Batch fetch live spots for top N (cheap - 1 Alpaca call per 200)
      2. Recompute positioning fields using live spot
      3. Flag chase risk (gap > 15% or thesis-broken gap < -7%)
      4. Re-run positioning_first on refreshed top N
      5. Pull live option chain + ATM IV/Greeks for top M (~$0 cost)
    """
    if not picks:
        return picks

    spot_pool = picks[:top_n_spot]
    tickers = [p.get("ticker") for p in spot_pool if p.get("ticker") and "." not in p.get("ticker")]
    quotes = _batch_fetch_live_spots(tickers)

    if not quotes:
        if verbose:
            print(f"  live_refresh: no live quotes returned (Alpaca creds missing or weekend?)")
        return picks

    refreshed = 0
    chase_flagged = 0
    thesis_broken = 0
    for p in spot_pool:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        q = quotes.get(ticker.replace(".US", ""))
        if not q:
            continue
        live_spot = q.get("price")
        if not live_spot or live_spot <= 0:
            continue
        updates = _recompute_live_signals(p, live_spot)
        if updates:
            refreshed += 1
            gap = updates.get("gap_pct", 0)
            if gap >= 15:
                p["_live_action"] = {"flag": "DO_NOT_CHASE", "label": f"gapped +{gap:.1f}% already - chase risk", "gap_pct": gap}
                chase_flagged += 1
            elif gap <= -7:
                p["_live_action"] = {"flag": "THESIS_BROKEN", "label": f"gapped {gap:.1f}% - thesis broken", "gap_pct": gap}
                thesis_broken += 1
            elif abs(gap) >= 3:
                session = q.get("timestamp", "")
                p["_live_action"] = {"flag": "GAP_NOTABLE", "label": f"gap {gap:+.1f}% from prior close", "gap_pct": gap}

    if verbose:
        print(f"  live_refresh spots: {refreshed} of {len(spot_pool)} picks refreshed "
              f"({chase_flagged} DO_NOT_CHASE, {thesis_broken} THESIS_BROKEN)")

    # Re-run positioning_first on refreshed top N - now extension/vertical signals
    # reflect intraday move
    try:
        from src.catalyst.positioning_first import apply_positioning_first
        apply_positioning_first(spot_pool, macro=macro, verbose=False)
        if verbose:
            print(f"  live_refresh positioning_first: re-scored top {len(spot_pool)} with live data")
    except Exception as e:
        if verbose:
            print(f"  live_refresh positioning_first failed: {type(e).__name__}: {e}")

    # Pull live chains + IV/Greeks for the top M picks (used by Robinhood block)
    chain_pool = spot_pool[:top_n_chain]
    chain_tagged = 0
    for p in chain_pool:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        spot = p.get("live_spot") or p.get("price")
        try:
            live_chain = _fetch_live_chain_iv(ticker, spot)
        except Exception:
            live_chain = None
        if live_chain:
            p["_live_chain"] = live_chain
            chain_tagged += 1
    if verbose:
        print(f"  live_refresh chains: {chain_tagged} of {len(chain_pool)} picks tagged with live ATM IV/Greeks")

    return picks
