"""Active positions tracker.

Stored as JSON list at data/positions.json. WebSocket worker polls this
file every 60s to subscribe/unsubscribe per-ticker monitoring channels.

Schema:
[
  {
    "ticker": "NVDA",
    "side": "CALL",
    "strike": 215.0,
    "expiry": "2026-07-02",
    "entry_premium": 14.63,
    "entry_date": "2026-06-03",
    "size_pct": 30
  },
  ...
]
"""

import json
import os
import pathlib
from datetime import date


POSITIONS_PATH = pathlib.Path(__file__).parent.parent / "data" / "positions.json"
POSITIONS_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_positions():
    if not POSITIONS_PATH.exists():
        return []
    try:
        with open(POSITIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_positions(positions):
    with open(POSITIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(positions, f, indent=2, default=str)


def add_position(ticker, side, strike, expiry, entry_premium=None, size_pct=None):
    positions = load_positions()
    positions.append({
        "ticker": ticker.upper(),
        "side": side.upper(),
        "strike": float(strike),
        "expiry": expiry,
        "entry_premium": float(entry_premium) if entry_premium else None,
        "entry_date": date.today().isoformat(),
        "size_pct": size_pct,
    })
    save_positions(positions)
    return positions


def remove_position(ticker, side=None, strike=None):
    positions = load_positions()
    new_positions = []
    for p in positions:
        if p.get("ticker") != ticker.upper():
            new_positions.append(p)
            continue
        if side and p.get("side") != side.upper():
            new_positions.append(p)
            continue
        if strike is not None and p.get("strike") != float(strike):
            new_positions.append(p)
            continue
        # else drop
    save_positions(new_positions)
    return new_positions


def get_active_tickers():
    return sorted({p["ticker"] for p in load_positions() if p.get("ticker")})


def file_mtime():
    try:
        return POSITIONS_PATH.stat().st_mtime
    except OSError:
        return 0
