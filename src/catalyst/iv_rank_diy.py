"""DIY IV Rank — replaces Barchart Premier (£192/year saved).

Pulls current 30-day ATM IV from Alpaca options chain, appends to a per-ticker
history file. After 30-60 days of daily snapshots, computes rolling percentile.

Method (matches industry-standard IV Rank):
  IV Rank = (current_IV - 52w_low_IV) / (52w_high_IV - 52w_low_IV) × 100

Returns 0-100. <30 = "IV cheap, buy calls". >70 = "IV expensive, sell premium".

Storage: data/iv_history/<TICKER>.jsonl, one line per scan day:
  {"date": "2026-05-30", "atm_iv_30d": 35.2}

Warm-up period:
  - Days 1-29: returns None (insufficient history)
  - Days 30-59: returns approximate rank with low confidence flag
  - Days 60+: full IV rank with high confidence

During warm-up, the iv_window module's straddle-based proxy still works.
"""

import os
import json
import pathlib
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
IV_HISTORY_DIR = PROJECT_ROOT / "data" / "iv_history"
IV_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

MIN_HISTORY_DAYS = 30
FULL_HISTORY_DAYS = 60
HISTORY_WINDOW_DAYS = 252


def _history_path(ticker):
    safe = ticker.replace("/", "_").replace(".", "_")
    return IV_HISTORY_DIR / f"{safe}.jsonl"


def _load_history(ticker):
    path = _history_path(ticker)
    if not path.exists():
        return []
    out = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return out


def _append_history(ticker, entry):
    path = _history_path(ticker)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass


def _get_current_atm_iv(ticker, spot_price=None):
    """Pull ATM 30-day IV from Alpaca chain. Returns IV % or None."""
    try:
        from src.alpaca_options import get_options_chain, get_live_price
        if spot_price is None:
            spot_price = get_live_price(ticker)
        if not spot_price:
            return None
        chain = get_options_chain(ticker, "call", float(spot_price))
        if chain and chain.get("iv_pct") is not None:
            return float(chain["iv_pct"])
    except Exception:
        pass
    return None


def record_today_iv(ticker, atm_iv=None):
    """Add today's IV reading to the ticker's history. Returns the entry."""
    today = datetime.utcnow().date().isoformat()
    history = _load_history(ticker)
    for h in history:
        if h.get("date") == today:
            return h

    if atm_iv is None:
        atm_iv = _get_current_atm_iv(ticker)
    if atm_iv is None:
        return None

    entry = {"date": today, "atm_iv_30d": round(float(atm_iv), 2)}
    _append_history(ticker, entry)
    return entry


def compute_iv_rank(ticker):
    """Return dict with iv_rank, confidence, sample_days, current_iv, high, low."""
    history = _load_history(ticker)
    if not history:
        return None
    cutoff = (datetime.utcnow().date() - timedelta(days=HISTORY_WINDOW_DAYS)).isoformat()
    window = [h for h in history if h.get("date", "") >= cutoff and h.get("atm_iv_30d") is not None]
    if not window:
        return None
    ivs = [float(h["atm_iv_30d"]) for h in window]
    current = ivs[-1]
    iv_low = min(ivs)
    iv_high = max(ivs)
    if iv_high <= iv_low:
        return {"iv_rank": 50, "confidence": "LOW", "sample_days": len(window), "current_iv": current, "iv_high_52w": iv_high, "iv_low_52w": iv_low}
    rank = (current - iv_low) / (iv_high - iv_low) * 100

    if len(window) >= FULL_HISTORY_DAYS:
        confidence = "HIGH"
    elif len(window) >= MIN_HISTORY_DAYS:
        confidence = "MED"
    else:
        confidence = "LOW"

    return {
        "iv_rank": round(rank, 1),
        "confidence": confidence,
        "sample_days": len(window),
        "current_iv": round(current, 2),
        "iv_high_52w": round(iv_high, 2),
        "iv_low_52w": round(iv_low, 2),
    }


def enrich_picks_with_diy_iv_rank(picks, max_picks=30, verbose=False):
    if not picks:
        return picks
    recorded = 0
    ranked = 0
    cheap = 0
    expensive = 0
    for p in picks[:max_picks]:
        ticker = p.get("ticker")
        if not ticker or "." in ticker:
            continue

        live_option = p.get("_live_option") or {}
        atm_iv = live_option.get("iv_pct")
        if atm_iv is None:
            atm_iv = _get_current_atm_iv(ticker, spot_price=p.get("live_spot") or p.get("price"))
        if atm_iv is not None:
            entry = record_today_iv(ticker, atm_iv=atm_iv)
            if entry:
                recorded += 1

        rank = compute_iv_rank(ticker)
        if rank:
            p["_iv_rank_diy"] = rank
            ranked += 1
            if rank.get("confidence") in ("MED", "HIGH"):
                if rank["iv_rank"] <= 30:
                    cheap += 1
                elif rank["iv_rank"] >= 70:
                    expensive += 1

    if verbose:
        print(f"  iv_rank_diy: {recorded} samples recorded, {ranked} ranks computed, {cheap} CHEAP, {expensive} EXPENSIVE")
    return picks
