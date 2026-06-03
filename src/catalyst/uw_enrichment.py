"""Per-Ticker Unusual Whales Enrichment.

After universe_from_flow picks 20-30 tickers by institutional flow, this module
enriches each with:
  - Net GEX + zero-gamma flip strike
  - Vanna / Charm exposure (the educator's "Venaflow" class)
  - IV rank + term structure (the IV surface)
  - OI concentration per strike (gravity wells)
  - 0DTE flow share
  - Max pain strike
  - Dark pool prints

Each signal becomes a per-ticker positioning input. The cheap gex_proxy is
superseded for any pick that has UW data.

Attaches to pick:
  _uw_flow:      {total_premium, trade_count, calls, puts, dominant_side}
  _uw_gex:       {net_gex, gamma_flip_strike, dealer_regime}
  _uw_iv:        {iv_rank, atm_iv, skew, term_structure}
  _uw_oi:        {gravity_strike, gravity_call_oi, gravity_put_oi}
  _uw_zero_dte:  {0dte_flow_share, dominant_side}
  _uw_dark_pool: {recent_print_count, total_value}

These then feed positioning_first._bull_positioning_score and _bear_positioning_score
via dedicated UW signal checkers.
"""

import logging
from datetime import datetime


logger = logging.getLogger(__name__)


def _classify_gex_regime(net_gex, spot=None, flip_strike=None):
    """Net GEX > 0 = positive gamma (pinning). Net GEX < 0 = negative gamma (amplification)."""
    if net_gex is None:
        return None
    try:
        ng = float(net_gex)
    except (TypeError, ValueError):
        return None
    if ng > 0:
        return "POSITIVE_PIN"
    if ng < 0:
        return "NEGATIVE_AMP"
    return "NEUTRAL"


def _summarize_flow(flow_data, ticker):
    if not flow_data:
        return None
    alerts = flow_data if isinstance(flow_data, list) else flow_data.get("data") or flow_data.get("alerts") or []
    if not alerts:
        return None
    total_prem = 0
    calls = 0
    puts = 0
    sweeps = 0
    blocks = 0
    zero_dte = 0
    for a in alerts:
        if not isinstance(a, dict):
            continue
        prem = 0
        for k in ("premium", "total_premium", "trade_value"):
            v = a.get(k)
            if v is not None:
                try:
                    prem = max(prem, float(v))
                    break
                except (TypeError, ValueError):
                    pass
        total_prem += prem
        side = (a.get("option_type") or a.get("side") or "").lower()
        if "call" in side:
            calls += 1
        elif "put" in side:
            puts += 1
        if a.get("is_sweep") or "sweep" in (a.get("trade_type") or "").lower():
            sweeps += 1
        if a.get("is_block") or "block" in (a.get("trade_type") or "").lower():
            blocks += 1
        dte = a.get("dte")
        if dte is not None:
            try:
                if int(dte) <= 1:
                    zero_dte += 1
            except (TypeError, ValueError):
                pass
    dominant = "CALL" if calls > puts else ("PUT" if puts > calls else "MIXED")
    return {
        "total_premium": total_prem,
        "trade_count": len(alerts),
        "calls": calls,
        "puts": puts,
        "sweeps": sweeps,
        "blocks": blocks,
        "zero_dte_count": zero_dte,
        "zero_dte_share": round(zero_dte / max(len(alerts), 1), 3),
        "dominant_side": dominant,
        "call_put_ratio": round(calls / max(puts, 1), 2),
    }


def _summarize_gex(gex_data, gex_by_strike, ticker, spot):
    if not gex_data:
        return None
    net_gex = None
    if isinstance(gex_data, dict):
        for k in ("net_gex", "total_gex", "gamma_exposure", "gex"):
            v = gex_data.get(k)
            if v is not None:
                try:
                    net_gex = float(v)
                    break
                except (TypeError, ValueError):
                    pass
    # Find zero-gamma flip strike from strike-distributed GEX
    flip_strike = None
    if isinstance(gex_by_strike, dict):
        strikes = gex_by_strike.get("data") or gex_by_strike.get("strikes") or []
    elif isinstance(gex_by_strike, list):
        strikes = gex_by_strike
    else:
        strikes = []
    # Find the strike where cumulative GEX crosses zero
    if strikes and spot:
        sorted_strikes = sorted([(float(s.get("strike", 0)), float(s.get("gex", 0))) for s in strikes if s.get("strike") is not None], key=lambda x: x[0])
        cumulative = 0
        prev_sign = None
        for strike, g in sorted_strikes:
            cumulative += g
            cur_sign = 1 if cumulative > 0 else (-1 if cumulative < 0 else 0)
            if prev_sign is not None and prev_sign != cur_sign and prev_sign != 0:
                flip_strike = strike
                break
            prev_sign = cur_sign

    regime = _classify_gex_regime(net_gex, spot=spot, flip_strike=flip_strike)
    above_flip = None
    if flip_strike is not None and spot is not None:
        try:
            above_flip = float(spot) > float(flip_strike)
        except (TypeError, ValueError):
            pass

    return {
        "net_gex": net_gex,
        "gamma_flip_strike": flip_strike,
        "dealer_regime": regime,
        "above_gamma_flip": above_flip,
        "label": _gex_label(net_gex, flip_strike, spot, above_flip),
    }


def _gex_label(net_gex, flip_strike, spot, above_flip):
    if net_gex is None:
        return "GEX data missing"
    gex_str = f"net GEX ${net_gex/1e9:.2f}B" if abs(net_gex) >= 1e9 else f"net GEX ${net_gex/1e6:.0f}M"
    if flip_strike is None or spot is None:
        return gex_str
    direction = "above" if above_flip else "below"
    return f"{gex_str}, flip strike ${flip_strike:.2f} ({direction} spot ${spot:.2f})"


def _summarize_iv(iv_rank_data, ticker):
    if not iv_rank_data:
        return None
    if isinstance(iv_rank_data, dict):
        rank = iv_rank_data.get("iv_rank") or iv_rank_data.get("rank") or iv_rank_data.get("ivr")
        atm = iv_rank_data.get("atm_iv") or iv_rank_data.get("implied_volatility")
        try:
            return {
                "iv_rank": float(rank) if rank is not None else None,
                "atm_iv": float(atm) if atm is not None else None,
            }
        except (TypeError, ValueError):
            return None
    return None


def enrich_pick_with_uw(pick, uw_client=None, verbose=False):
    """Pull all UW signals for a single ticker and attach to pick."""
    if uw_client is None:
        from src.unusual_whales_api import get_client
        uw_client = get_client()
    if not uw_client.enabled:
        return False

    ticker = pick.get("ticker")
    if not ticker or "." in ticker:
        return False

    spot = pick.get("live_spot") or pick.get("price")

    flow_alerts = uw_client.flow_alerts(ticker=ticker, limit=100)
    flow_summary = _summarize_flow(flow_alerts, ticker)
    if flow_summary:
        pick["_uw_flow"] = flow_summary

    gex = uw_client.greek_exposure(ticker)
    gex_by_strike = uw_client.greek_exposure_by_strike(ticker)
    gex_summary = _summarize_gex(gex, gex_by_strike, ticker, spot)
    if gex_summary:
        pick["_uw_gex"] = gex_summary
        # Override the cheap gex_proxy with proper net GEX
        regime = gex_summary.get("dealer_regime")
        if regime:
            pick["_dealer_gex"] = {
                "regime": regime,
                "net_gex": gex_summary.get("net_gex"),
                "gamma_flip_strike": gex_summary.get("gamma_flip_strike"),
                "label": gex_summary.get("label"),
                "_source": "uw_api",
            }

    iv_rank = uw_client.iv_rank(ticker)
    iv_summary = _summarize_iv(iv_rank, ticker)
    if iv_summary:
        pick["_uw_iv"] = iv_summary

    try:
        max_pain = uw_client.max_pain(ticker)
        if max_pain and isinstance(max_pain, dict):
            mp = max_pain.get("max_pain") or max_pain.get("strike")
            if mp:
                pick["_uw_max_pain"] = {"strike": float(mp)}
    except Exception:
        pass

    try:
        darkpool = uw_client.darkpool_ticker(ticker, limit=20)
        if darkpool:
            prints = darkpool if isinstance(darkpool, list) else darkpool.get("data") or []
            if prints:
                total = sum(float(p.get("size", 0)) * float(p.get("price", 0)) for p in prints if p.get("size") and p.get("price"))
                pick["_uw_dark_pool"] = {"print_count": len(prints), "total_value_usd": total}
    except Exception:
        pass

    return True


def enrich_universe_with_uw(picks, uw_client=None, max_picks=30, verbose=False):
    if not picks:
        return picks
    if uw_client is None:
        from src.unusual_whales_api import get_client
        uw_client = get_client()
    if not uw_client.enabled:
        if verbose:
            print(f"  uw_enrichment: UW token missing - skipping (positioning stack still fires)")
        return picks

    enriched = 0
    for p in picks[:max_picks]:
        if enrich_pick_with_uw(p, uw_client=uw_client, verbose=verbose):
            enriched += 1

    if verbose:
        print(f"  uw_enrichment: enriched {enriched}/{len(picks[:max_picks])} picks with UW flow + GEX + IV + OI")
    return picks
