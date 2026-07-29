"""Lifetime trials ledger (Q1, owner-approved 2026-07-29).

The deflated Sharpe's n_trials previously saw only the CURRENT study's counter, so eleven games and
hundreds of configs of search never raised the bar for believing the next winner. This module makes
the count lifetime-cumulative: studies append their trial counts; DSR consumers read baseline +
appended + their own run. Fail-open everywhere - a missing ledger degrades to the old behavior
(current-run trials only), never blocks a study.
"""
import os
import json
from datetime import datetime, timezone

LEDGER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "lifetime_trials.json")


def _load():
    try:
        return json.load(open(LEDGER_PATH, encoding="utf-8"))
    except Exception:
        return None


def lifetime_total():
    """Baseline + all appended entries. 0 if the ledger is unavailable (fail-open)."""
    d = _load()
    if not d:
        return 0
    return int(d.get("model_config_trials_baseline", 0)) + sum(int(e.get("trials", 0))
                                                               for e in d.get("entries", []))


def append(study, trials):
    """Record a completed study's trial count. Best-effort; never raises."""
    try:
        d = _load()
        if not d:
            return False
        d.setdefault("entries", []).append({"study": str(study), "trials": int(trials),
                                            "utc": datetime.now(timezone.utc).isoformat()})
        json.dump(d, open(LEDGER_PATH, "w", encoding="utf-8"), indent=2)
        return True
    except Exception:
        return False
