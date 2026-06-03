"""Pattern 5: Whisper EPS vs Consensus Delta (Tier C).

Whisper number > 1 SD above analyst consensus indicates traders are
front-running an expected beat. Combined with call flow 2-3 days before earnings,
this is a high-conviction pre-earnings CALL setup.

Inverse: whisper << consensus = market expects miss = PUT setup.

UW endpoint: /companies/earnings-estimates

Only fires when an earnings event is within 15-21 days (the IV expansion window).

Score contribution: 15 points (Tier C).
"""


def _to_float(v, default=0):
    try:
        return float(v) if v else default
    except (TypeError, ValueError):
        return default


def detect(uw_client, ticker, pick=None):
    estimates = uw_client.earnings_estimates(ticker)
    if not estimates:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    rows = estimates.get("data") if isinstance(estimates, dict) else estimates
    if not isinstance(rows, list) or not rows:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    # Find the next reporting quarter
    upcoming = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get("date_actual") is None and r.get("eps_actual") is None:
            upcoming = r
            break

    if not upcoming:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    consensus = _to_float(upcoming.get("consensus_estimate") or upcoming.get("street_mean_est"))
    whisper = _to_float(upcoming.get("whisper_estimate") or upcoming.get("whisper"))
    high_est = _to_float(upcoming.get("high_estimate"))
    low_est = _to_float(upcoming.get("low_estimate"))

    if consensus == 0:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    # Standard deviation estimate from analyst range
    sd_est = max((high_est - low_est) / 4, abs(consensus * 0.05))
    if sd_est == 0:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    if whisper == 0:
        return {"fires": False, "side": None, "score": 0,
                "label": "no whisper estimate available",
                "details": {"consensus": consensus, "high": high_est, "low": low_est}}

    delta_sd = (whisper - consensus) / sd_est

    side = None
    if delta_sd >= 1.0:
        side = "CALL"
        label = f"WHISPER {whisper:.2f} > consensus {consensus:.2f} by {delta_sd:.1f}SD = traders expect BEAT"
    elif delta_sd <= -1.0:
        side = "PUT"
        label = f"WHISPER {whisper:.2f} < consensus {consensus:.2f} by {abs(delta_sd):.1f}SD = traders expect MISS"
    else:
        return {"fires": False, "side": None, "score": 0,
                "label": f"whisper-consensus delta {delta_sd:+.2f}SD (within normal range)",
                "details": {"consensus": consensus, "whisper": whisper, "delta_sd": delta_sd}}

    return {
        "fires": True,
        "side": side,
        "score": 15,
        "label": label,
        "details": {"consensus": consensus, "whisper": whisper, "delta_sd": delta_sd,
                    "report_date": upcoming.get("date_expected")},
    }
