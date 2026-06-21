import os


def _ef(key, default):
    raw = (os.environ.get(key, "") or "").strip()
    try:
        return float(raw) if raw else float(default)
    except ValueError:
        return float(default)


def get_config():
    return {
        "harvest_min_days": _ef("HARVEST_MIN_DAYS", 8),
        "harvest_max_days": _ef("HARVEST_MAX_DAYS", 14),
        "harvest_max_ivr": _ef("HARVEST_MAX_IVR", 30),
        "pemd_min_gap_pct": _ef("PEMD_MIN_GAP_PCT", 10),
        "pemd_max_ivr": _ef("PEMD_MAX_IVR", 40),
        "pemd_recent_earnings_min_days": _ef("PEMD_RECENT_EARN_DAYS", 60),
    }


def classify(candidate, config=None):
    if config is None:
        config = get_config()
    e = candidate.get("earnings_in_days")
    ivr = candidate.get("ivr")
    gap = candidate.get("gap_up_pct")

    if (e is not None and config["harvest_min_days"] <= e <= config["harvest_max_days"]
            and ivr is not None and ivr < config["harvest_max_ivr"]):
        return {
            "setup": "PRE_EARNINGS_HARVEST",
            "structure": "CALENDAR",
            "exit_before_earnings": True,
            "reason": f"{int(e)}d to earnings + IVR {ivr} low -> harvest pre-earnings IV ramp; exit 1d before the print",
        }

    if (gap is not None and gap >= config["pemd_min_gap_pct"]
            and ivr is not None and ivr < config["pemd_max_ivr"]
            and (e is None or e >= config["pemd_recent_earnings_min_days"])):
        return {
            "setup": "PEMD",
            "structure": "DEBIT_VERTICAL",
            "side": "CALL",
            "reason": f"gapped +{gap:.0f}% post-earnings with IV crushed (IVR {ivr}) -> ride 3-5d institutional drift",
        }

    return {"setup": None}
