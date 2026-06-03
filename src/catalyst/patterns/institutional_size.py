"""Pattern 4: $250k+ Institutional Premium Filter (Tier B).

Quality filter that cuts retail noise on liquid tickers.
Any ticker with $250k+ total premium today qualifies (already filtered upstream
in universe builder), but this pattern ADDS POINTS if total premium is large
AND directionally concentrated.

Score contribution: 15 points (Tier B).
Bonus +5 if total premium >= $5M (heavy institutional commitment).
"""


def _to_float(v, default=0):
    try:
        return float(v) if v else default
    except (TypeError, ValueError):
        return default


def detect(uw_client, ticker, pick=None):
    # Most picks will already have _uw_flow attached from enrichment
    uw_flow = (pick or {}).get("_uw_flow") or {}

    if not uw_flow:
        # Fallback - fetch fresh
        alerts = uw_client.flow_alerts(ticker=ticker, limit=100)
        if not alerts:
            return {"fires": False, "side": None, "score": 0, "label": None, "details": None}
        rows = alerts.get("data") if isinstance(alerts, dict) else alerts
        if not isinstance(rows, list):
            return {"fires": False, "side": None, "score": 0, "label": None, "details": None}
        total_prem = 0
        calls = 0
        puts = 0
        for r in rows:
            if not isinstance(r, dict):
                continue
            prem = _to_float(r.get("total_premium"))
            if prem < 250_000:
                continue
            total_prem += prem
            t = (r.get("type") or "").lower()
            if "call" in t:
                calls += 1
            elif "put" in t:
                puts += 1
        uw_flow = {"total_premium": total_prem, "calls": calls, "puts": puts}

    total_prem = uw_flow.get("total_premium", 0)
    calls = uw_flow.get("calls", 0)
    puts = uw_flow.get("puts", 0)

    if total_prem < 250_000:
        return {"fires": False, "side": None, "score": 0,
                "label": f"only ${total_prem/1e6:.1f}M premium - below institutional threshold",
                "details": uw_flow}

    # Direction concentration
    total_trades = calls + puts
    if total_trades == 0:
        return {"fires": False, "side": None, "score": 0, "label": None, "details": None}

    # Direction concentration
    call_ratio = calls / total_trades
    if call_ratio >= 0.55:
        side = "CALL"
        concentration_pct = call_ratio
    elif call_ratio <= 0.45:
        side = "PUT"
        concentration_pct = 1 - call_ratio
    else:
        return {"fires": False, "side": None, "score": 0,
                "label": f"${total_prem/1e6:.1f}M but no directional concentration ({calls}C/{puts}P)",
                "details": uw_flow}

    # Continuous premium-based score: log10 scale
    # $250k=7, $1M=12, $5M=20, $25M=28, $100M=35
    import math
    base = min(35, 7 + math.log10(max(total_prem / 250_000, 1)) * 7.5)
    # Concentration multiplier: 0.55=1.0, 0.70=1.10, 0.85=1.20
    if concentration_pct >= 0.85:
        base *= 1.20
    elif concentration_pct >= 0.70:
        base *= 1.10
    score = round(min(35, base))

    label = (f"INSTITUTIONAL: ${total_prem/1e6:.1f}M premium, "
             f"{calls}C/{puts}P ({int(concentration_pct*100)}% {side} concentration)")

    return {
        "fires": True,
        "side": side,
        "score": score,
        "label": label,
        "details": uw_flow,
    }
