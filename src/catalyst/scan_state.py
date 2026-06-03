"""Scan state tracker - detect tier changes between consecutive scans.

Persists per-ticker tier history at data/flow_state/state.json.
Compares current scan against previous to fire Telegram alerts ONLY on
meaningful changes (tier upgrades, new ELITE+, exit signals on holdings).
"""

import json
import pathlib
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
STATE_PATH = PROJECT_ROOT / "data" / "flow_state" / "state.json"
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


TIER_RANK = {
    "PASS": 0,
    "MODERATE": 1,
    "STRONG": 2,
    "ELITE": 3,
    "MAX_CONVICTION": 4,
    "GAMMA_BOMB": 5,
}


def load_state():
    if not STATE_PATH.exists():
        return {"last_scan": None, "tickers": {}}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_scan": None, "tickers": {}}


def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception:
        pass


def diff_scans(scan, prev_state):
    """Compare current scan to previous state, return list of significant events.

    Per Savvas: Telegram only fires on ELITE/MAX_CONVICTION/GAMMA_BOMB tier events.
    STRONG and MODERATE changes are visible in the 3 daily emails but don't push.

    Event types:
      NEW_ELITE_PLUS    new ticker entering ELITE/MAX_CONVICTION/GAMMA_BOMB
      TIER_UPGRADE      existing ELITE+ ticker upgraded further (e.g. ELITE -> MAX)
                        OR ticker upgraded INTO ELITE+ from below
      SIDE_FLIP         direction flipped CALL <-> PUT on ELITE+ ticker
      DROPPED_FROM_TOP  was ELITE+ previously, now below ELITE
    """
    events = []
    current = {}

    ELITE_RANK = TIER_RANK["ELITE"]  # 3

    for stream_name in ("calls", "puts"):
        for p in scan.get(stream_name, []):
            t = p.get("ticker")
            c = p.get("_confluence") or {}
            current[t] = {
                "tier": c.get("tier", "PASS"),
                "score": c.get("score", 0),
                "side": c.get("side"),
                "thesis": c.get("thesis", ""),
                "size_pct": c.get("size_pct", 0),
            }

    prev_tickers = prev_state.get("tickers") or {}

    for t, cur in current.items():
        prev = prev_tickers.get(t) or {"tier": "PASS", "score": 0, "side": None}
        cur_rank = TIER_RANK.get(cur["tier"], 0)
        prev_rank = TIER_RANK.get(prev.get("tier", "PASS"), 0)

        # Only fire if current OR previous tier is ELITE+
        is_elite_event = cur_rank >= ELITE_RANK or prev_rank >= ELITE_RANK
        if not is_elite_event:
            continue

        if cur_rank >= ELITE_RANK and prev_rank < ELITE_RANK:
            events.append({
                "event": "NEW_ELITE_PLUS",
                "ticker": t,
                "tier": cur["tier"],
                "side": cur["side"],
                "score": cur["score"],
                "thesis": cur["thesis"],
                "size_pct": cur["size_pct"],
            })
        elif cur_rank > prev_rank and cur_rank >= ELITE_RANK:
            events.append({
                "event": "TIER_UPGRADE",
                "ticker": t,
                "from_tier": prev.get("tier", "PASS"),
                "to_tier": cur["tier"],
                "side": cur["side"],
                "score": cur["score"],
                "thesis": cur["thesis"],
            })

        if (prev.get("side") and cur["side"] and prev["side"] != cur["side"]
                and cur_rank >= ELITE_RANK):
            events.append({
                "event": "SIDE_FLIP",
                "ticker": t,
                "from_side": prev["side"],
                "to_side": cur["side"],
                "tier": cur["tier"],
                "score": cur["score"],
            })

    # Detect tickers that dropped out of the top picks entirely
    for t, prev in prev_tickers.items():
        if t not in current:
            if TIER_RANK.get(prev.get("tier", "PASS"), 0) >= ELITE_RANK:
                events.append({
                    "event": "DROPPED_FROM_TOP",
                    "ticker": t,
                    "was_tier": prev.get("tier"),
                })

    return events, current


def update_state(scan):
    """Diff current scan against last persisted state, return events, save updated state."""
    prev_state = load_state()
    events, current = diff_scans(scan, prev_state)
    new_state = {
        "last_scan": datetime.utcnow().isoformat() + "Z",
        "tickers": current,
    }
    save_state(new_state)
    return events


def format_event_for_telegram(event):
    e = event["event"]
    t = event["ticker"]
    if e == "NEW_ELITE_PLUS":
        return f"<b>NEW {event['tier']} {event['side']}: {t}</b>\nscore {event['score']} - size {event['size_pct']}%\n{event['thesis'][:200]}"
    if e == "TIER_UPGRADE":
        return f"UPGRADE {t}: {event['from_tier']} -> {event['to_tier']} ({event['side']}) score {event['score']}\n{event['thesis'][:200]}"
    if e == "SIDE_FLIP":
        return f"DIRECTION FLIP {t}: {event['from_side']} -> {event['to_side']} now {event['tier']} score {event['score']}"
    if e == "DROPPED_FROM_TOP":
        return f"WATCH: {t} dropped from {event['was_tier']} tier (no longer in top picks)"
    return f"{e} {t}"
