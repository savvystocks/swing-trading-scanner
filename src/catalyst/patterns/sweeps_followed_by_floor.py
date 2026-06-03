"""Pattern 1: Sweeps Followed by Floor (Tier A).

10+ sweep orders followed by 1+ floor trade ($100k+) same direction within 30 min window.
Sweep = retail/HFT desperate to enter. Floor = pro PM following up.
If both side-aligned, retail urgency confirmed by professional entry.

Score contribution: 20 points (Tier A).
"""

from datetime import datetime, timedelta


def detect(uw_client, ticker, pick=None):
    # Get last 100 flow alerts for ticker
    alerts = uw_client.flow_alerts(ticker=ticker, limit=100)
    if not alerts:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    rows = alerts.get("data") if isinstance(alerts, dict) else alerts
    if not isinstance(rows, list) or not rows:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    # Parse: separate sweeps from floor trades, get timestamps
    def _parse_time(t):
        try:
            return datetime.fromisoformat(t.replace("Z", "+00:00"))
        except Exception:
            return None

    def _to_float(v, default=0):
        try:
            return float(v) if v else default
        except (TypeError, ValueError):
            return default

    # UW uses booleans has_sweep / has_floor (NOT a string field).
    # `type` is "call" or "put" only.
    sweeps = []
    floors = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        is_sweep = bool(r.get("has_sweep"))
        is_floor = bool(r.get("has_floor"))
        type_field = (r.get("type") or "").lower()
        side = "CALL" if "call" in type_field else ("PUT" if "put" in type_field else None)
        ts = _parse_time(r.get("created_at") or r.get("start_time"))
        prem = _to_float(r.get("total_premium") or r.get("premium"))
        if is_sweep:
            sweeps.append({"ts": ts, "side": side, "premium": prem})
        if is_floor:
            floors.append({"ts": ts, "side": side, "premium": prem})

    # Threshold lowered: 5+ sweeps + 1 floor (was 10 - rarely fires)
    if len(sweeps) < 5 or not floors:
        return {"fires": False, "side": None, "score": 0,
                "label": f"sweeps={len(sweeps)}, floors={len(floors)} - need 5+ sweeps + 1 floor",
                "details": {"sweep_count": len(sweeps), "floor_count": len(floors)}}

    # For each floor trade, count sweeps in 30 min before it on same side
    best_setup = None
    for f in floors:
        if not f["ts"] or not f["side"] or f["premium"] < 50_000:
            continue
        window_start = f["ts"] - timedelta(minutes=30)
        same_side_sweeps = [s for s in sweeps if s["ts"] and s["side"] == f["side"]
                            and window_start <= s["ts"] <= f["ts"]]
        if len(same_side_sweeps) >= 5:
            total_sweep_prem = sum(s["premium"] for s in same_side_sweeps)
            setup = {
                "side": f["side"],
                "sweep_count": len(same_side_sweeps),
                "total_sweep_premium": total_sweep_prem,
                "floor_premium": f["premium"],
                "floor_time": f["ts"].isoformat() if f["ts"] else None,
            }
            if best_setup is None or setup["sweep_count"] > best_setup["sweep_count"]:
                best_setup = setup

    if not best_setup:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    side = best_setup["side"]
    label = (f"SWEEPS-FOLLOWED-BY-FLOOR fired: {best_setup['sweep_count']} {side} sweeps "
             f"(${best_setup['total_sweep_premium']/1e6:.1f}M premium) "
             f"followed by ${best_setup['floor_premium']/1e3:.0f}k floor trade")

    return {
        "fires": True,
        "side": side,
        "score": 20,
        "label": label,
        "details": best_setup,
    }
