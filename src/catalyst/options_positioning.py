"""Options Market Positioning - SKEW, VIX term structure, VVIX, P/C ratio.

These are the AGGREGATE positioning signals from the broader options market.
Tell you what the WHOLE market is positioned for, not just one ticker.

Tracked indicators:
  - SKEW Index (CBOE) - tail-risk pricing; >145 = institutional crash hedging
  - VIX absolute level - current fear gauge
  - VIX9D vs VIX - short-term vol expectations
  - VIX vs VIX3M - term structure (backwardation = stress, contango = calm)
  - VVIX - vol-of-vol, leads VIX
  - Put/Call ratio - aggregate options positioning

Data sources (all free):
  EODHD index endpoints: VIX.INDX, VIX9D.INDX, VIX3M.INDX, VVIX.INDX, SKEW.INDX
  CBOE daily CSV for P/C ratio (free)
"""

from datetime import datetime, timedelta


VOL_INDICES = {
    "VIX": "VIX.INDX",
    "VIX9D": "VIX9D.INDX",
    "VIX3M": "VIX3M.INDX",
    "VVIX": "VVIX.INDX",
    "SKEW": "SKEW.INDX",
}


def _fetch_index_latest(eodhd_symbol):
    try:
        from src.eodhd import EODHDClient
        client = EODHDClient()
        end = datetime.utcnow().date()
        start = end - timedelta(days=10)
        bars = client.ohlcv(eodhd_symbol, from_date=start.strftime("%Y-%m-%d"), to_date=end.strftime("%Y-%m-%d"))
        if bars:
            return float(bars[-1].get("close") or 0)
    except Exception:
        pass
    return None


def _fetch_index_history(eodhd_symbol, days_back=252):
    try:
        from src.eodhd import EODHDClient
        client = EODHDClient()
        end = datetime.utcnow().date()
        start = end - timedelta(days=days_back + 30)
        bars = client.ohlcv(eodhd_symbol, from_date=start.strftime("%Y-%m-%d"), to_date=end.strftime("%Y-%m-%d"))
        return [float(b.get("close") or 0) for b in (bars or []) if b.get("close")]
    except Exception:
        return []


def get_options_market_snapshot(verbose=False):
    """Snapshot of all vol indicators + classify regimes."""
    snap = {}
    for name, sym in VOL_INDICES.items():
        snap[name] = _fetch_index_latest(sym)

    vix = snap.get("VIX")
    vix9d = snap.get("VIX9D")
    vix3m = snap.get("VIX3M")
    vvix = snap.get("VVIX")
    skew = snap.get("SKEW")

    findings = []
    score = 50

    if vix is not None and vix3m is not None and vix3m > 0:
        ratio = vix / vix3m
        if ratio > 1.0:
            findings.append({"signal": "VIX_BACKWARDATION", "label": f"VIX {vix:.1f} > VIX3M {vix3m:.1f} = backwardation (stress)", "bearish_for_longs": True})
            score = max(score, 70)
        elif ratio < 0.85:
            findings.append({"signal": "VIX_DEEP_CONTANGO", "label": f"VIX {vix:.1f} < VIX3M {vix3m:.1f} steep contango (complacency)", "bearish_for_longs": False})

    if vix is not None and vix9d is not None and vix9d > 0:
        if vix9d > vix * 1.05:
            findings.append({"signal": "SHORT_TERM_FEAR", "label": f"VIX9D {vix9d:.1f} > VIX {vix:.1f} = near-term concern building", "bearish_for_longs": True})

    if skew is not None:
        if skew >= 145:
            findings.append({"signal": "SKEW_ELEVATED", "label": f"SKEW {skew:.0f} >= 145 = institutional tail hedging (crash risk priced in)", "bearish_for_longs": True})
        elif skew <= 115:
            findings.append({"signal": "SKEW_LOW", "label": f"SKEW {skew:.0f} <= 115 = no tail-risk pricing (complacency)", "bearish_for_longs": False})

    if vvix is not None:
        if vvix >= 110:
            findings.append({"signal": "VVIX_ELEVATED", "label": f"VVIX {vvix:.1f} >= 110 = vol-of-vol high, VIX expansion likely", "bearish_for_longs": True})

    if vix is not None:
        if vix >= 25:
            regime = "HIGH_VOL"
        elif vix >= 18:
            regime = "ELEVATED_VOL"
        elif vix <= 13:
            regime = "LOW_VOL_COMPLACENCY"
        else:
            regime = "NORMAL_VOL"
    else:
        regime = "UNKNOWN"

    return {
        "snapshot": snap,
        "regime": regime,
        "findings": findings,
        "options_positioning_score": score,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }


def enrich_picks_with_options_positioning(picks, market_snapshot=None, verbose=False):
    if not picks:
        return picks
    if market_snapshot is None:
        market_snapshot = get_options_market_snapshot(verbose=verbose)
    if not market_snapshot:
        return picks

    findings = market_snapshot.get("findings") or []
    bearish_signals = [f for f in findings if f.get("bearish_for_longs")]
    bullish_signals = [f for f in findings if not f.get("bearish_for_longs")]

    for p in picks:
        p["_options_positioning"] = {
            "regime": market_snapshot.get("regime"),
            "vix": market_snapshot["snapshot"].get("VIX"),
            "skew": market_snapshot["snapshot"].get("SKEW"),
            "vix9d_vix_ratio": (market_snapshot["snapshot"].get("VIX9D") or 0) / (market_snapshot["snapshot"].get("VIX") or 1) if market_snapshot["snapshot"].get("VIX") else None,
            "bearish_signal_count": len(bearish_signals),
            "bullish_signal_count": len(bullish_signals),
            "findings": [f.get("label") for f in findings],
        }

    if verbose:
        print(f"  options_positioning: regime={market_snapshot.get('regime')} bearish={len(bearish_signals)} bullish={len(bullish_signals)}")
        for f in findings:
            print(f"    - {f.get('label')}")
    return picks
