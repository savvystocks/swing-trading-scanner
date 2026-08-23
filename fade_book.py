"""FADE BOOK - the retooled entry/exit rules, gated entirely by fade_book_spec.json.

Spec provenance: winners' autopsy 2026-08-01 + exam replays 2026-08-05 (fade-shaped entries,
tight spreads, mid-size flow, no scale-out; day-clustered t is the life bar). status=OFF means
every hook below is inert and the engine is byte-identical to the incumbent path (MOT-proven).
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

_SPEC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fade_book_spec.json")
_SPEC = None
_REGIME = {"date": None, "val": None}     # daily cache: SPY regime by 50d SMA (fail-open)


def spy_regime():
    """BULL / MILD / BEAR from SPY vs its 50-day SMA (same measure as the 2026-08-23 regime
    backtest: bear<-2%, bull>+2%). Cached per UTC date; fail-OPEN (None) on any error so the
    router never blocks trading on a data hiccup. Reads paper creds from env."""
    today = datetime.now(timezone.utc).date().isoformat()
    if _REGIME["date"] == today:
        return _REGIME["val"]
    val = None
    try:
        k1 = os.environ.get("ALPACA_PAPER_API_KEY"); k2 = os.environ.get("ALPACA_PAPER_SECRET_KEY")
        if k1 and k2:
            u = ("https://data.alpaca.markets/v2/stocks/bars?symbols=SPY&timeframe=1Day"
                 "&start=2026-04-01&limit=120&adjustment=split&feed=iex")
            req = urllib.request.Request(u, headers={"APCA-API-KEY-ID": k1, "APCA-API-SECRET-KEY": k2})
            with urllib.request.urlopen(req, timeout=12) as r:
                bars = (json.loads(r.read()).get("bars") or {}).get("SPY") or []
            cl = [b["c"] for b in bars]
            if len(cl) >= 50:
                sma50 = sum(cl[-50:]) / 50
                dist = (cl[-1] / sma50 - 1) * 100
                val = "BEAR" if dist < -2 else ("BULL" if dist > 2 else "MILD")
    except Exception:
        val = None
    _REGIME["date"], _REGIME["val"] = today, val
    return val


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
        e = spec().get("entry") or {}
        if e.get("regime_router"):
            # 2026-08-23 archive regime split: fade is a BEAR leg (+32 t3.5 bear, -16.6 t-8.4
            # bull). Stand fade DOWN outside a bear regime - purely subtractive (worst case a
            # missed trade, never a wrong-direction one). Fail-open: unknown regime -> allow.
            rg = spy_regime()
            if rg in ("BULL", "MILD"):
                return None
        md_ = e.get("max_depth_pct")
        if isinstance(md_, (int, float)) and abs(sma) >= md_:
            return None                       # depth cap (spec-driven; None = no cap)
        ms = e.get("max_spy_dist_pct")
        if isinstance(ms, (int, float)) and abs(spy) >= ms:
            return None                       # MILD condition (spec-driven)
        return "BULLISH" if side > 0 else "BEARISH"
    return None


def spread_cap(default_cap):
    return (spec().get("entry") or {}).get("max_spread_pct", default_cap) if active() else default_cap


def no_same_day_exit():
    """Owner hold rule 2026-08-12: no position is SOLD the same calendar day it was bought
    (broker day-trade flags). Applies to every book's managed exits and backstop arming;
    owner /flatten is exempt (its flush path does not consult this)."""
    return bool((spec().get("exit") or {}).get("no_same_day_exit")) and active()


def exit_overrides():
    """Spec-driven exit params for the FADE branch: {stop, max_hold_days} or {}."""
    x = spec().get("exit") or {}
    out = {}
    if isinstance(x.get("stop"), (int, float)):
        out["stop"] = abs(x["stop"])
    if isinstance(x.get("max_hold_days"), (int, float)):
        out["max_hold_days"] = x["max_hold_days"]
    if isinstance(x.get("early_cut_hours"), (int, float)) and isinstance(x.get("early_cut_below"), (int, float)):
        out["early_cut_hours"] = x["early_cut_hours"]
        out["early_cut_below"] = x["early_cut_below"]
    return out
