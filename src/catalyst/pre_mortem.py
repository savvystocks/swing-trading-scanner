def generate_pre_mortem(candidate):
    cats = candidate.get("catalysts") or []
    catalyst_keys = {c.get("key") for c in cats if isinstance(c, dict)}
    landmines = candidate.get("_landmine_flags") or []
    counter = candidate.get("counter_thesis") or {}
    bracket = candidate.get("bracket") or "unknown"
    analog_set = candidate.get("analog_set") or {}
    stats = analog_set.get("statistics") or {}
    iv_analysis = candidate.get("iv_percentile_analysis") or {}

    failure_modes = []

    if counter.get("what_kills_this_trade"):
        failure_modes.append({"mode": counter["what_kills_this_trade"], "source": "counter_thesis", "severity": "HIGH"})

    for f in landmines:
        if f["severity"] == "YELLOW":
            failure_modes.append({"mode": f["label"], "source": "landmine", "severity": "MEDIUM"})

    if "earnings_bmo_tomorrow" in catalyst_keys or "earnings_amc_today" in catalyst_keys or "earnings_bmo_with_beat_streak" in catalyst_keys:
        failure_modes.append({
            "mode": "Earnings miss or in-line print with soft forward guidance → IV crushes, stock fades -8-15%",
            "source": "catalyst_type",
            "severity": "HIGH",
        })

    iv_pct = iv_analysis.get("iv_percentile")
    if iv_pct and iv_pct > 75:
        failure_modes.append({
            "mode": f"IV percentile {iv_pct} = peak vol entry → IV crush will eat 30-40% of premium even on small underlying move",
            "source": "iv_analysis",
            "severity": "HIGH",
        })

    worst_case = stats.get("worst_outcome_pct")
    if worst_case is not None and worst_case < -10:
        failure_modes.append({
            "mode": f"Analog worst case was {worst_case}% — this exact setup HAS failed badly before",
            "source": "analog_history",
            "severity": "MEDIUM",
        })

    sector_rot = candidate.get("_sector_rotation") or {}
    if sector_rot.get("verdict") == "HEADWIND":
        failure_modes.append({
            "mode": f"Sector ETF in downtrend ({sector_rot.get('reason')}) — even a good print won't be bought",
            "source": "sector_rotation",
            "severity": "HIGH",
        })

    if not failure_modes:
        failure_modes.append({
            "mode": "Generic risk: catalyst doesn't materialize OR materializes weaker than priced — fade post-event",
            "source": "default",
            "severity": "LOW",
        })

    failure_modes.sort(key=lambda f: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(f["severity"], 3))
    most_likely = failure_modes[0]["mode"] if failure_modes else "unknown"

    warning_signs = []
    if counter.get("warning_signs_to_watch"):
        warning_signs.extend(counter["warning_signs_to_watch"][:3])
    warning_signs.extend([
        "Stock gaps DOWN at open on catalyst date (thesis broken immediately)",
        "Underlying breaks below 50dMA on volume (sentiment reversal)",
        "Sector ETF rolls over (breadth collapse)",
        "Volume on day-2 post-catalyst dries up (no continuation)",
    ])

    return {
        "most_likely_failure": most_likely,
        "all_failure_modes": failure_modes,
        "warning_signs": warning_signs[:5],
        "exit_trigger": failure_modes[0].get("mode", "") if failure_modes else "",
    }


def apply_pre_mortem(candidates, verbose=False):
    for s in candidates:
        s["pre_mortem"] = generate_pre_mortem(s)
    if verbose:
        print(f"  pre_mortem: generated for {len(candidates)} candidates")
    return candidates
