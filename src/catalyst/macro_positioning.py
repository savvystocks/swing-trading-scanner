"""Macro Positioning Layer - regime context beyond stock-specific.

Tracks cross-asset positioning to set the BACKDROP for any trade:
  - HYG/LQD credit spread (credit stress regime)
  - JNK/LQD ratio (junk vs investment grade)
  - DXY (dollar) relative strength
  - Gold relative strength
  - Treasury yield curve (2/10 spread)
  - Copper/gold ratio (growth vs fear)

Free data: all from EODHD as ETF closes.
Compute: 20-day and 90-day relative performance vs SPY to classify regime.
"""

from datetime import datetime, timedelta


MACRO_TICKERS = {
    "HYG": "HYG.US", "LQD": "LQD.US", "JNK": "JNK.US",
    "UUP": "UUP.US", "GLD": "GLD.US",
    "TLT": "TLT.US", "IEF": "IEF.US", "SHY": "SHY.US",
    "CPER": "CPER.US",
    "SPY": "SPY.US",
}


def _fetch_returns(ticker_symbol, days=90):
    try:
        from src.eodhd import EODHDClient
        client = EODHDClient()
        end = datetime.utcnow().date()
        start = end - timedelta(days=days + 30)
        bars = client.ohlcv(ticker_symbol, from_date=start.strftime("%Y-%m-%d"), to_date=end.strftime("%Y-%m-%d"))
        if not bars or len(bars) < 21:
            return None
        closes = [float(b.get("close") or 0) for b in bars if b.get("close")]
        if len(closes) < 21:
            return None
        return {
            "close": closes[-1],
            "ret_20d": (closes[-1] - closes[-21]) / closes[-21] * 100 if closes[-21] > 0 else 0,
            "ret_90d": (closes[-1] - closes[-90]) / closes[-90] * 100 if len(closes) >= 90 and closes[-90] > 0 else None,
        }
    except Exception:
        return None


def get_macro_snapshot(verbose=False):
    snap = {}
    for label, sym in MACRO_TICKERS.items():
        r = _fetch_returns(sym, days=90)
        if r:
            snap[label] = r

    findings = []
    risk_score = 50

    if snap.get("HYG") and snap.get("LQD"):
        hyg_lqd_20d = snap["HYG"]["ret_20d"] - snap["LQD"]["ret_20d"]
        if hyg_lqd_20d < -1:
            findings.append({"signal": "CREDIT_STRESS", "label": f"HYG underperforming LQD by {abs(hyg_lqd_20d):.1f}% 20d - credit stress building", "regime_pressure": "RISK_OFF"})
            risk_score += 10

    if snap.get("CPER") and snap.get("GLD"):
        copper_gold_20d = snap["CPER"]["ret_20d"] - snap["GLD"]["ret_20d"]
        if copper_gold_20d > 3:
            findings.append({"signal": "GROWTH_REGIME", "label": f"copper outpacing gold {copper_gold_20d:+.1f}% 20d - growth regime", "regime_pressure": "RISK_ON"})
        elif copper_gold_20d < -3:
            findings.append({"signal": "FEAR_REGIME", "label": f"gold outpacing copper {abs(copper_gold_20d):.1f}% 20d - defensive regime", "regime_pressure": "RISK_OFF"})
            risk_score += 5

    if snap.get("UUP"):
        if snap["UUP"]["ret_20d"] > 2:
            findings.append({"signal": "DOLLAR_STRENGTH", "label": f"USD strengthening {snap['UUP']['ret_20d']:+.1f}% 20d - tightening risk-off pressure", "regime_pressure": "RISK_OFF"})
        elif snap["UUP"]["ret_20d"] < -2:
            findings.append({"signal": "DOLLAR_WEAKNESS", "label": f"USD weakening {snap['UUP']['ret_20d']:.1f}% 20d - liquidity easing, risk-on", "regime_pressure": "RISK_ON"})

    if snap.get("TLT") and snap.get("SPY"):
        tlt_spy_20d = snap["TLT"]["ret_20d"] - snap["SPY"]["ret_20d"]
        if tlt_spy_20d > 3:
            findings.append({"signal": "BONDS_LEADING", "label": f"TLT outperforming SPY {tlt_spy_20d:+.1f}% 20d - flight to quality", "regime_pressure": "RISK_OFF"})
            risk_score += 5

    if risk_score >= 65:
        regime = "RISK_OFF_PRESSURE"
    elif risk_score <= 40:
        regime = "RISK_ON"
    else:
        regime = "NEUTRAL"

    return {
        "regime": regime,
        "risk_score": risk_score,
        "findings": findings,
        "snapshot": snap,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }


def enrich_picks_with_macro(picks, macro_snapshot=None, verbose=False):
    if not picks:
        return picks
    if macro_snapshot is None:
        macro_snapshot = get_macro_snapshot(verbose=verbose)
    if not macro_snapshot:
        return picks
    for p in picks:
        p["_macro_positioning"] = macro_snapshot
    if verbose:
        print(f"  macro_positioning: regime={macro_snapshot['regime']} ({len(macro_snapshot['findings'])} findings)")
    return picks
