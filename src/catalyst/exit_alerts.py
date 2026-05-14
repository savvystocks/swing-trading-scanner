import os
import json
import pathlib
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
V4_PICKS_PATH = PROJECT_ROOT / "data" / "paper_trades" / "v4_picks.json"
ALERTS_SEEN_PATH = PROJECT_ROOT / "data" / "paper_trades" / "exit_alerts_seen.json"


TARGET_T1_PCT = 50.0
TARGET_T2_PCT = 100.0
TARGET_T3_PCT = 200.0
STOP_PCT = -40.0

TRAILING_STOP_ACTIVATION_PCT = 30.0
TRAILING_STOP_DRAWDOWN_PCT = 15.0

MAX_AGE_DAYS = 21


def _load_picks():
    if not V4_PICKS_PATH.exists():
        return []
    try:
        with open(V4_PICKS_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def _load_seen():
    if not ALERTS_SEEN_PATH.exists():
        return {}
    try:
        with open(ALERTS_SEEN_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_seen(seen):
    ALERTS_SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    cutoff = (datetime.utcnow() - timedelta(days=60)).isoformat()
    seen = {k: v for k, v in seen.items() if v.get("at", "") >= cutoff}
    with open(ALERTS_SEEN_PATH, "w") as f:
        json.dump(seen, f, indent=2)


def _get_live_price(ticker):
    try:
        from src.alpaca_options import get_live_price
        return get_live_price(ticker)
    except Exception:
        return None


def _classify_trigger(entry_price, current_price, max_seen_price):
    if not entry_price or entry_price <= 0:
        return None
    move_pct = (current_price - entry_price) / entry_price * 100
    max_move_pct = (max_seen_price - entry_price) / entry_price * 100 if max_seen_price else move_pct

    if move_pct >= TARGET_T3_PCT:
        return {
            "trigger": "T3_TARGET_200",
            "severity": "HIGH",
            "action": "SELL ALL - 200% target hit",
            "move_pct": move_pct,
        }
    if move_pct >= TARGET_T2_PCT:
        return {
            "trigger": "T2_TARGET_100",
            "severity": "HIGH",
            "action": "Trim 2/3 - lock 100%+ gain, ride the rest with tight stop",
            "move_pct": move_pct,
        }
    if move_pct >= TARGET_T1_PCT:
        return {
            "trigger": "T1_TARGET_50",
            "severity": "MED",
            "action": "Trim half - lock 50% gain, ride the rest",
            "move_pct": move_pct,
        }
    if move_pct <= STOP_PCT:
        return {
            "trigger": "STOP_HIT",
            "severity": "HIGH",
            "action": "STOP HIT - sell now, preserve capital",
            "move_pct": move_pct,
        }
    if max_move_pct >= TRAILING_STOP_ACTIVATION_PCT:
        drawdown_from_peak = (max_seen_price - current_price) / max_seen_price * 100
        if drawdown_from_peak >= TRAILING_STOP_DRAWDOWN_PCT:
            return {
                "trigger": "TRAILING_STOP",
                "severity": "MED",
                "action": f"Trailing stop hit - was +{max_move_pct:.0f}%, now {move_pct:+.0f}% (gave back {drawdown_from_peak:.0f}% from peak). Lock remaining gain",
                "move_pct": move_pct,
                "peak_pct": max_move_pct,
            }
    return None


def check_open_positions(verbose=False):
    picks = _load_picks()
    if not picks:
        if verbose:
            print(f"  exit_alerts: no v4 picks logged yet")
        return []

    seen = _load_seen()
    today = datetime.utcnow().date()
    cutoff = today - timedelta(days=MAX_AGE_DAYS)

    open_picks = []
    for pick in picks:
        try:
            scan_dt = datetime.strptime(pick.get("scan_date", ""), "%Y-%m-%d").date()
        except Exception:
            continue
        if scan_dt < cutoff:
            continue
        outcomes = pick.get("outcomes") or {}
        if outcomes.get("measured_at"):
            continue
        if not pick.get("entry_price"):
            continue
        open_picks.append(pick)

    if verbose:
        print(f"  exit_alerts: {len(open_picks)} open positions in last {MAX_AGE_DAYS}d to check")

    triggers = []
    for pick in open_picks:
        ticker = pick.get("ticker")
        entry = pick.get("entry_price")
        if not ticker or not entry:
            continue

        current = _get_live_price(ticker)
        if current is None:
            if verbose:
                print(f"    {ticker}: no live price, skipping")
            continue

        try:
            entry_f = float(entry)
            current_f = float(current)
        except (TypeError, ValueError):
            continue

        max_seen = pick.get("_max_seen_price")
        if max_seen is None or current_f > max_seen:
            pick["_max_seen_price"] = current_f
            max_seen = current_f

        trigger = _classify_trigger(entry_f, current_f, max_seen)
        if not trigger:
            continue

        alert_key = f"{ticker}|{pick.get('scan_date')}|{trigger['trigger']}"
        if alert_key in seen:
            if verbose:
                print(f"    {ticker}: {trigger['trigger']} already alerted on {seen[alert_key].get('at', '')}")
            continue

        triggers.append({
            "ticker": ticker,
            "scan_date": pick.get("scan_date"),
            "entry_price": entry_f,
            "current_price": current_f,
            "max_seen_price": max_seen,
            "trigger": trigger,
            "alert_key": alert_key,
            "pick": pick,
        })

        seen[alert_key] = {
            "at": datetime.utcnow().isoformat(),
            "trigger": trigger["trigger"],
            "current": current_f,
            "entry": entry_f,
        }

    if triggers:
        _save_picks_with_max(picks)
        _save_seen(seen)
    if verbose:
        print(f"  exit_alerts: {len(triggers)} NEW triggers detected")
    return triggers


def _save_picks_with_max(picks):
    try:
        with open(V4_PICKS_PATH, "w") as f:
            json.dump(picks, f, indent=2, default=str)
    except Exception:
        pass


def format_alert_message(trigger_data):
    t = trigger_data["trigger"]
    pick = trigger_data.get("pick") or {}
    name = (pick.get("name") or "")[:40]
    bracket = pick.get("bracket", "?")
    tier = pick.get("tier", "?")

    severity_label = ""
    if t["severity"] == "HIGH":
        severity_label = "[HIGH] "
    elif t["severity"] == "MED":
        severity_label = "[MED] "

    move = t["move_pct"]
    move_str = f"+{move:.0f}%" if move >= 0 else f"{move:.0f}%"

    msg = (
        f"{severity_label}EXIT ALERT: {trigger_data['ticker']} ({tier} {bracket} - {name})\n"
        f"Trigger: {t['trigger']}\n"
        f"Entry: ${trigger_data['entry_price']:.2f} -> Current: ${trigger_data['current_price']:.2f} ({move_str})\n"
        f"Scan date: {trigger_data['scan_date']}\n"
        f"Action: {t['action']}"
    )
    return msg
