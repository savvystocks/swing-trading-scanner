import json
import os
from datetime import datetime, timedelta


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INCLUSIONS_PATH = os.path.join(PROJECT_ROOT, "data", "catalyst", "index_inclusions.json")


def load_index_inclusions():
    if not os.path.exists(INCLUSIONS_PATH):
        return {"inclusions": [], "exits": []}
    try:
        with open(INCLUSIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"inclusions": [], "exits": []}


def get_index_signals(target_date=None, max_days_until=14):
    if target_date is None:
        today = datetime.utcnow().date()
    elif isinstance(target_date, str):
        try:
            today = datetime.strptime(target_date, "%Y-%m-%d").date()
        except Exception:
            today = datetime.utcnow().date()
    else:
        today = target_date

    data = load_index_inclusions()
    signals = {}

    for entry in data.get("inclusions", []):
        try:
            eff = datetime.strptime(entry["effective_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        days_until = (eff - today).days
        if days_until < 0 or days_until > max_days_until:
            continue
        ticker = entry.get("ticker")
        if not ticker:
            continue
        signals[ticker] = {
            "key": "index_inclusion",
            "details": (f"{entry.get('index', '?')} inclusion {entry['effective_date']} "
                        f"({days_until}d, replaces {entry.get('replaces', '?')}, "
                        f"~${entry.get('expected_buying_usd_b', '?')}B index buying)"),
            "direction": "bull",
            "days_until": days_until,
            "index_name": entry.get("index"),
            "effective_date": entry["effective_date"],
        }

    for entry in data.get("exits", []):
        try:
            eff = datetime.strptime(entry["effective_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        days_until = (eff - today).days
        if days_until < 0 or days_until > max_days_until:
            continue
        ticker = entry.get("ticker")
        if not ticker:
            continue
        signals[ticker] = {
            "key": "lawsuit",
            "details": (f"{entry.get('index', '?')} exit {entry['effective_date']} "
                        f"({days_until}d, replaced by {entry.get('replaced_by', '?')}, "
                        f"~${entry.get('expected_selling_usd_b', '?')}B forced selling)"),
            "direction": "bear",
            "days_until": days_until,
            "index_name": entry.get("index"),
            "effective_date": entry["effective_date"],
        }

    return signals
