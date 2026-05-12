from datetime import datetime


SLIPPAGE_BY_TIME_ET = {
    "premarket": 0.10,
    "open_30min": 0.07,
    "morning_quiet": 0.04,
    "midday_optimal": 0.03,
    "midday_lunch": 0.05,
    "afternoon": 0.04,
    "close_30min": 0.06,
    "afterhours": 0.10,
    "closed": 0.10,
}


def classify_time_window():
    now = datetime.utcnow()
    et_hour = (now.hour - 4) % 24 + now.minute / 60
    day_of_week = now.weekday()
    if day_of_week >= 5:
        return {"window": "closed", "label": "weekend", "expected_slippage_pct": 10}
    if et_hour < 4 or et_hour >= 20:
        return {"window": "closed", "label": "overnight", "expected_slippage_pct": 10}
    if 4 <= et_hour < 9.5:
        return {"window": "premarket", "label": "pre-market", "expected_slippage_pct": 10}
    if 9.5 <= et_hour < 10:
        return {"window": "open_30min", "label": "opening 30min — wide spreads, avoid market orders", "expected_slippage_pct": 7}
    if 10 <= et_hour < 11:
        return {"window": "morning_quiet", "label": "post-open settle", "expected_slippage_pct": 4}
    if 11 <= et_hour < 12:
        return {"window": "midday_optimal", "label": "tight spreads optimal fills", "expected_slippage_pct": 3}
    if 12 <= et_hour < 14:
        return {"window": "midday_lunch", "label": "lunch lull — thinner liquidity", "expected_slippage_pct": 5}
    if 14 <= et_hour < 15.5:
        return {"window": "afternoon", "label": "afternoon — good fills, last clean window", "expected_slippage_pct": 4}
    if 15.5 <= et_hour < 16:
        return {"window": "close_30min", "label": "MOC imbalance — wide spreads", "expected_slippage_pct": 6}
    return {"window": "afterhours", "label": "after-hours — dangerous", "expected_slippage_pct": 10}


def day_of_week_advice():
    now = datetime.utcnow()
    dow = now.weekday()
    map_ = {
        0: ("Monday", "weekend-news digestion, expect higher open vol — let first 30min settle"),
        1: ("Tuesday", "best execution day historically"),
        2: ("Wednesday", "normal liquidity"),
        3: ("Thursday", "normal liquidity, watch for OpEx Friday positioning"),
        4: ("Friday", "position-squaring, lower conviction — avoid new lottery entries"),
        5: ("Saturday", "market closed"),
        6: ("Sunday", "market closed"),
    }
    return map_.get(dow, ("Unknown", "no advice"))


def execution_context():
    time_window = classify_time_window()
    dow_name, dow_advice = day_of_week_advice()
    return {
        "time_window": time_window,
        "day_of_week": dow_name,
        "day_advice": dow_advice,
        "guidance": _build_guidance(time_window, dow_name),
    }


def _build_guidance(time_window, dow_name):
    guidance = []
    if time_window["window"] == "open_30min":
        guidance.append("WAIT 30 min for spreads to tighten before entering")
    elif time_window["window"] == "close_30min":
        guidance.append("MOC imbalance distortion — wait for tomorrow")
    elif time_window["window"] in ("midday_optimal", "afternoon"):
        guidance.append("GOOD time to enter — spreads tight")
    elif time_window["window"] == "afterhours":
        guidance.append("AVOID new entries — too illiquid")
    if dow_name == "Friday":
        guidance.append("Friday: avoid new lottery, position-squaring distorts pricing")
    if dow_name == "Monday":
        guidance.append("Monday: weekend-news digestion creates entry opportunities AFTER first 30min")
    return guidance
