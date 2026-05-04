BASE_RATES = {
    "S": 0.70,
    "A": 0.58,
    "B": 0.52,
    "C": 0.48,
    "D": 0.42,
    "-": 0.40,
}

CONFIDENCE_MULT = {
    "HIGH": 1.10,
    "MEDIUM": 1.00,
    "LOW": 0.85,
}


def compute_atr_pct(df, period=20):
    if df is None or len(df) < period + 1:
        return None
    recent = df.tail(period + 1).copy()
    tr = []
    for i in range(1, len(recent)):
        h = float(recent["high"].iloc[i])
        l = float(recent["low"].iloc[i])
        prev_c = float(recent["close"].iloc[i - 1])
        tr.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    if not tr:
        return None
    avg_tr = sum(tr) / len(tr)
    last_close = float(recent["close"].iloc[-1])
    if last_close <= 0:
        return None
    return (avg_tr / last_close) * 100


def buy_signal(ticker_data, components, df=None, catalyst_tier="-", confidence="MEDIUM"):
    base = BASE_RATES.get(catalyst_tier, 0.40)
    conf_mult = CONFIDENCE_MULT.get(confidence, 1.0)

    llm = components.get("llm", {}) or {}
    llm_score = llm.get("llm_score") or 0
    if llm_score > 0:
        llm_mult = 0.75 + (llm_score / 20.0)
    else:
        llm_mult = 0.95

    drift = components.get("drift", {}) or {}
    drift_mult = 1.0
    if drift.get("extended"):
        drift_mult = 0.55
    elif drift.get("pre_priced"):
        drift_mult = 0.75

    red = (components.get("red_flags") or {}).get("points", 0)
    if red <= -8:
        rf_mult = 0.65
    elif red < 0:
        rf_mult = 0.85
    else:
        rf_mult = 1.0

    prob = base * conf_mult * llm_mult * drift_mult * rf_mult
    prob = max(0.20, min(0.85, prob))
    prob_pct = round(prob * 100)

    atr_pct = compute_atr_pct(df) if df is not None else None
    if atr_pct:
        catalyst_amplifier = {"S": 2.0, "A": 1.6, "B": 1.3, "C": 1.1, "D": 0.9}.get(catalyst_tier, 1.0)
        expected_low = round(0.5 * atr_pct, 1)
        expected_high = round(catalyst_amplifier * atr_pct, 1)
        if drift.get("extended") or drift.get("pre_priced"):
            expected_low = round(expected_low * 0.5, 1)
            expected_high = round(expected_high * 0.7, 1)
        stop_pct = round(-min(3.0, atr_pct * 0.7), 1)
    else:
        expected_low = None
        expected_high = None
        stop_pct = None

    catalysts_list = components.get("catalyst_quality", {}).get("catalysts_full") or []
    has_overnight = any(c.get("event_timing") == "scheduled_overnight" for c in catalysts_list)
    has_fresh = any(c.get("event_timing") == "fresh_breaking" for c in catalysts_list)
    has_only_post = (not has_overnight and not has_fresh) and any(c.get("event_timing") == "post_event" for c in catalysts_list)

    if drift.get("skip_chase") or red <= -8:
        signal = "SKIP"
        signal_color = "#c94545"
    elif drift.get("extended"):
        signal = "SKIP"
        signal_color = "#c94545"
    elif has_only_post:
        signal = "WATCH" if drift.get("pre_priced") is not True else "SKIP"
        signal_color = "#999"
    elif drift.get("pre_priced"):
        signal = "WATCH"
        signal_color = "#e67e22"
    elif has_overnight and prob_pct >= 60 and confidence == "HIGH":
        signal = "BUY"
        signal_color = "#0d7b34"
    elif has_overnight and prob_pct >= 50:
        signal = "WATCH"
        signal_color = "#4a90e2"
    elif has_fresh and prob_pct >= 55 and confidence == "HIGH":
        signal = "WATCH"
        signal_color = "#4a90e2"
    else:
        signal = "SKIP"
        signal_color = "#999"

    price = ticker_data.get("price")
    entry = round(price, 2) if price else None
    target_1 = round(price * (1 + expected_low / 100), 2) if price and expected_low else None
    target_2 = round(price * (1 + expected_high / 100), 2) if price and expected_high else None
    stop_price = round(price * (1 + stop_pct / 100), 2) if price and stop_pct is not None else None

    return {
        "probability_pct": prob_pct,
        "signal": signal,
        "signal_color": signal_color,
        "expected_move_low_pct": expected_low,
        "expected_move_high_pct": expected_high,
        "stop_pct": stop_pct,
        "entry_price": entry,
        "target_1_price": target_1,
        "target_2_price": target_2,
        "stop_price": stop_price,
        "atr_pct": round(atr_pct, 2) if atr_pct else None,
    }
