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

    sweeps = []
    floors = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        type_field = (r.get("type") or r.get("trade_type") or "").lower()
        is_sweep = "sweep" in type_field
        is_floor = "floor" in type_field
        side = None
        if "call" in type_field:
            side = "CALL"
        elif "put" in type_field:
            side = "PUT"
        ts = _parse_time(r.get("created_at") or r.get("start_time"))
        prem = _to_float(r.get("total_premium") or r.get("premium"))
        if is_sweep:
            sweeps.append({"ts": ts, "side": side, "premium": prem})
        if is_floor:
            floors.append({"ts": ts, "side": side, "premium": prem})

    if len(sweeps) < 10 or not floors:
        return {"fires": False, "side": None, "score": 0,
                "label": f"sweeps={len(sweeps)}, floors={len(floors)} - pattern requires 10+ sweeps + floor",
                "details": {"sweep_count": len(sweeps), "floor_count": len(floors)}}

    # For each floor trade, count sweeps in 30 min before it on same side
    best_setup = None
    for f in floors:
        if not f["ts"] or not f["side"] or f["premium"] < 100_000:
            continue
        window_start = f["ts"] - timedelta(minutes=30)
        same_side_sweeps = [s for s in sweeps if s["ts"] and s["side"] == f["side"]
                            and window_start <= s["ts"] <= f["ts"]]
        if len(same_side_sweeps) >= 10:
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
