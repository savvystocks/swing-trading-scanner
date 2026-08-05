"""FADE BOOK - the retooled entry/exit rules, gated entirely by fade_book_spec.json.

Spec provenance: winners' autopsy 2026-08-01 + exam replays 2026-08-05 (fade-shaped entries,
tight spreads, mid-size flow, no scale-out; day-clustered t is the life bar). status=OFF means
every hook below is inert and the engine is byte-identical to the incumbent path (MOT-proven).
"""
import json
import os

_SPEC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fade_book_spec.json")
_SPEC = None


def spec():
    global _SPEC
    if _SPEC is None:
        try:
            with open(_SPEC_PATH, encoding="utf-8") as f:
                _SPEC = json.load(f)
        except Exception:
            _SPEC = {"status": "OFF"}
    return _SPEC


def active():
    if os.environ.get("FADE_BOOK_FORCE_OFF") == "1":
        return False           # deterministic OFF for test harnesses (passivity/MOT legacy chain)
    return (spec().get("status") or "OFF").upper() == "LIVE"


def flow_band(cands):
    """Keep only tickers whose aggregated flow premium sits in the mid band."""
    e = spec().get("entry") or {}
    lo, hi = e.get("flow_min", 50000), e.get("flow_max", 250000)
    return [c for c in cands if lo <= (c.get("total_premium") or 0) <= hi]


def direction(md, candidate):
    """Fade shape: take the FLOW side only when ticker trend AND market both oppose it.
    Returns BULLISH/BEARISH to trade, or None to skip (not fade-shaped)."""
    ft = (candidate or {}).get("flow_type")
    if ft not in ("call", "put"):
        return None
    side = 1 if ft == "call" else -1
    sma = (md.get("macro") or {}).get("distance_to_sma20_pct")
    spy = (md.get("regime_stack") or {}).get("market_spy_dist_pct")
    if not isinstance(sma, (int, float)) or not isinstance(spy, (int, float)):
        return None
    if sma * side < 0 and spy * side < 0:
        return "BULLISH" if side > 0 else "BEARISH"
    return None


def spread_cap(default_cap):
    return (spec().get("entry") or {}).get("max_spread_pct", default_cap) if active() else default_cap
