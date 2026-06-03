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

    side = None
    score = 0
    label = None
    if nope_val >= 3:
        side = "CALL"
        score = 25
        label = f"NOPE +{nope_val:.1f} = dealer delta pressure UPWARD = CALL bias"
    elif nope_val <= -3:
        side = "PUT"
        score = 25
        label = f"NOPE {nope_val:.1f} = dealer delta pressure DOWNWARD = PUT bias"
    elif nope_val >= 2:
        side = "CALL"
        score = 12
        label = f"NOPE +{nope_val:.1f} = moderate call pressure"
    elif nope_val <= -2:
        side = "PUT"
        score = 12
        label = f"NOPE {nope_val:.1f} = moderate put pressure"
    else:
        return {"fires": False, "side": None, "score": 0,
                "label": f"NOPE {nope_val:+.2f} (neutral, no signal)",
                "details": {"nope": nope_val}}

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
