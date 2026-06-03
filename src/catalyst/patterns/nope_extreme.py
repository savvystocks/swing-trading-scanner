"""Pattern 6: NOPE Extreme (Tier S).

Net Option Position Effect measures dealer-induced delta pressure on the stock.
|NOPE| > 3 = extreme positioning that mechanically drives next-day price action.

NOPE > +3:  call delta exposure dominates -> dealers must buy stock -> UPWARD pressure -> CALL bias
NOPE < -3:  put delta exposure dominates  -> dealers must sell stock -> DOWNWARD pressure -> PUT bias

UW endpoint: /stock/{t}/nope returns minute-by-minute NOPE series.

Score contribution: 25 points (Tier S).
"""


def detect(uw_client, ticker, pick=None):
    nope_data = uw_client.nope(ticker)
    if not nope_data:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    rows = nope_data.get("data") if isinstance(nope_data, dict) else nope_data
    if not isinstance(rows, list) or not rows:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    # Latest entry is most recent
    latest = rows[0] if rows[0].get("timestamp") else rows[-1]
    try:
        nope_val = float(latest.get("nope", 0))
    except (TypeError, ValueError):
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    # Continuous scoring: |NOPE| 0.3-2.5+ -> 5-30 points (linear scale)
    abs_nope = abs(nope_val)
    if abs_nope < 0.3:
        return {"fires": False, "side": None, "score": 0,
                "label": f"NOPE {nope_val:+.2f} (neutral, no signal)",
                "details": {"nope": nope_val}}
    side = "CALL" if nope_val > 0 else "PUT"
    # 0.3 -> 6, 0.5 -> 10, 0.8 -> 14.8, 1.5 -> 23, 2.5+ -> 30 cap
    score = round(min(30, 2 + abs_nope * 12.5))
    strength = "extreme" if abs_nope >= 1.5 else ("strong" if abs_nope >= 0.8 else "moderate")
    label = f"NOPE {nope_val:+.2f} ({strength}) = dealer delta pressure -> {side} bias"

    return {
        "fires": True,
        "side": side,
        "score": score,
        "label": label,
        "details": {
            "nope": nope_val,
            "call_delta": latest.get("call_delta"),
            "put_delta": latest.get("put_delta"),
            "as_of": latest.get("timestamp"),
        },
    }
