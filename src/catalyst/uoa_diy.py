"""DIY Unusual Options Activity Detector.

Replaces what InsiderFinance/UW/Barchart sell for $50-150/mo. Computes
volume / open interest ratios per contract from existing Alpaca chain data.

A contract where vol > 3× OI on a single day is genuinely unusual — could
be smart money positioning ahead of a catalyst. Stack 3+ unusual contracts
on bullish strikes = strong UOA confirmation signal.

Limitations vs paid:
  - Daily snapshot, not real-time (paid services stream sweeps as they hit)
  - No sweep-vs-block classification (we just see vol/OI ratios)
  - Better for 1-2 week swings (which is what Savvas trades anyway)

Storage: ephemeral per-scan — we read chain data fresh each scan and
score the current day. No history file needed.
"""

from datetime import datetime


VOL_OI_THRESHOLD = 3.0
MIN_VOLUME = 100


def _pull_options_chain(ticker, side="call"):
    """Pull full options chain via Alpaca, return list of contracts with vol + OI."""
    try:
        from src.alpaca_options import get_options_chain_full
        chain = get_options_chain_full(ticker, side=side)
        return chain or []
    except Exception:
        pass
    try:
        from src.alpaca_options import get_options_chain
        chain = get_options_chain(ticker, side, None)
        if isinstance(chain, dict) and chain.get("contracts"):
            return chain["contracts"]
        if isinstance(chain, list):
            return chain
    except Exception:
        pass
    return []


def detect_unusual_activity(ticker, verbose=False):
    """Return list of unusual contracts plus aggregate signal."""
    call_chain = _pull_options_chain(ticker, "call")
    put_chain = _pull_options_chain(ticker, "put")

    unusual = []
    for side, chain in (("call", call_chain), ("put", put_chain)):
        for c in chain or []:
            try:
                vol = float(c.get("volume") or 0)
                oi = float(c.get("open_interest") or c.get("oi") or 0)
                strike = float(c.get("strike") or 0)
            except Exception:
                continue
            if vol < MIN_VOLUME or oi <= 0:
                continue
            ratio = vol / oi
            if ratio >= VOL_OI_THRESHOLD:
                unusual.append({
                    "side": side,
                    "strike": strike,
                    "expiry": c.get("expiration") or c.get("expiry"),
                    "volume": int(vol),
                    "open_interest": int(oi),
                    "vol_oi_ratio": round(ratio, 2),
                })

    unusual.sort(key=lambda x: -x["vol_oi_ratio"])

    bullish = sum(1 for u in unusual if u["side"] == "call")
    bearish = sum(1 for u in unusual if u["side"] == "put")
    if bullish + bearish == 0:
        verdict = "NO_UNUSUAL_ACTIVITY"
        fires = False
    elif bullish >= 3 and bullish >= bearish * 2:
        verdict = "STRONG_BULLISH_UOA"
        fires = True
    elif bullish > bearish:
        verdict = "MILD_BULLISH_UOA"
        fires = bullish >= 2
    elif bearish >= 3 and bearish >= bullish * 2:
        verdict = "STRONG_BEARISH_UOA"
        fires = False
    else:
        verdict = "MIXED_UOA"
        fires = False

    if verbose:
        print(f"  uoa_diy {ticker}: {verdict} ({bullish} bull, {bearish} bear, top ratio {unusual[0]['vol_oi_ratio'] if unusual else 0}x)")

    return {
        "verdict": verdict,
        "fires": fires,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "top_contracts": unusual[:5],
        "all_unusual_count": len(unusual),
    }


def enrich_picks_with_diy_uoa(picks, max_picks=20, verbose=False):
    if not picks:
        return picks
    bullish_fires = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue
        try:
            res = detect_unusual_activity(ticker, verbose=False)
        except Exception:
            continue
        p["_uoa_diy"] = res
        if res.get("fires"):
            bullish_fires += 1
            existing_flow = p.get("_uw_flow") or []
            if not existing_flow:
                synthetic = [
                    {"sentiment": "bullish", "premium_usd": c["volume"] * c["strike"] * 100, "vol_oi_ratio": c["vol_oi_ratio"]}
                    for c in res["top_contracts"][:3] if c["side"] == "call"
                ]
                p["_uw_flow"] = synthetic
    if verbose:
        print(f"  uoa_diy: {bullish_fires} bullish UOA fires out of {min(max_picks, len(picks))} checked")
    return picks
