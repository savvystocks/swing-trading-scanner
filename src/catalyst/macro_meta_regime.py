"""Macro Meta-Regime Aggregator.

The OLD macro_regime_detector + macro_positioning together only look at:
  - SPY trend + VIX
  - HYG/LQD credit spread
  - Copper/gold ratio
  - Dollar / TLT vs SPY

Today (2026-06-03) all those say NEUTRAL. But the NEW positioning stack we built
in Path 3 shows clear PEAK EUPHORIA:
  - FINRA margin debt EUPHORIC_LATE_CYCLE (+25.7% YoY)
  - Investors Intelligence 58% bulls vs 19% bears (extreme)
  - COT ES 100th %ile + NQ 100th %ile (crowded long)
  - Sentiment stack STACKED_GREED firing
  - VIX deep contango (complacency)

The old macro detector is BLIND to these. So positioning_first scores under
"NEUTRAL macro" when reality is RISK_OFF_PRESSURE.

This module aggregates the full new stack into one verdict:
  RISK_OFF_PRESSURE / RISK_ON / NEUTRAL

Rule: classify by votes from each sub-system.
  +1 = pro-bear evidence (push toward RISK_OFF)
  -1 = pro-bull evidence (push toward RISK_ON)
   0 = neutral / no signal

If net votes >= +2 -> RISK_OFF_PRESSURE
If net votes <= -2 -> RISK_ON
Otherwise NEUTRAL.

Called from wide_pool_positioning so the meta verdict is in macro['meta_regime']
when positioning_first runs.
"""


def classify_meta_regime(macro, verbose=False):
    """Aggregate all positioning sub-signals into one regime verdict.

    Returns dict with:
      regime: RISK_ON / NEUTRAL / RISK_OFF_PRESSURE
      net_votes: int (positive = bearish, negative = bullish)
      sub_votes: list of {source, vote, label}
    """
    if not isinstance(macro, dict):
        return None

    sub_votes = []

    # FINRA margin debt
    finra = macro.get("finra_margin") or {}
    finra_regime = finra.get("regime")
    if finra_regime == "EUPHORIC_LATE_CYCLE":
        sub_votes.append({"source": "FINRA margin", "vote": 1, "label": finra.get("label", "EUPHORIC_LATE_CYCLE")})
    elif finra_regime == "CAPITULATION_BOTTOM":
        sub_votes.append({"source": "FINRA margin", "vote": -1, "label": finra.get("label", "CAPITULATION_BOTTOM")})
    elif finra_regime == "ELEVATED":
        sub_votes.append({"source": "FINRA margin", "vote": 1, "label": finra.get("label", "ELEVATED leverage")})

    # Sentiment stack stacked extremes
    sentiment = macro.get("sentiment_stack") or {}
    if sentiment.get("extreme_count_short", 0) >= 2:
        sub_votes.append({"source": "Sentiment stack", "vote": 1,
                          "label": f"{sentiment['extreme_count_short']} surveys agree extreme greed (contrarian short)"})
    elif sentiment.get("extreme_count_long", 0) >= 2:
        sub_votes.append({"source": "Sentiment stack", "vote": -1,
                          "label": f"{sentiment['extreme_count_long']} surveys agree extreme fear (contrarian long)"})

    # COT - count crowded long across equity indexes
    cot_findings = macro.get("cot_meta") or {}
    crowded_long = cot_findings.get("crowded_long_count", 0)
    crowded_short = cot_findings.get("crowded_short_count", 0)
    if crowded_long >= 2:
        sub_votes.append({"source": "COT", "vote": 1,
                          "label": f"{crowded_long} contracts at CROWDED long (mean reversion short)"})
    elif crowded_short >= 2:
        sub_votes.append({"source": "COT", "vote": -1,
                          "label": f"{crowded_short} contracts at CROWDED short (mean reversion long)"})

    # Options positioning findings
    opt_pos = macro.get("options_positioning") or {}
    findings = opt_pos.get("findings") or []
    opt_bearish = 0
    opt_bullish = 0
    for f in findings:
        sig = f.get("signal") if isinstance(f, dict) else None
        if sig in ("VIX_BACKWARDATION", "SHORT_TERM_FEAR", "SKEW_ELEVATED", "VVIX_ELEVATED",
                   "CPC_EXTREME_CALLS", "CPCE_RETAIL_CALLS"):
            opt_bearish += 1
        elif sig in ("VIX_DEEP_CONTANGO", "SKEW_LOW", "CPC_EXTREME_PUTS", "CPCE_RETAIL_PUTS"):
            opt_bullish += 1
    if opt_bearish >= 2:
        sub_votes.append({"source": "Options positioning", "vote": 1,
                          "label": f"{opt_bearish} bearish options signals (skew/calls/backwardation)"})
    elif opt_bullish >= 2:
        sub_votes.append({"source": "Options positioning", "vote": -1,
                          "label": f"{opt_bullish} bullish options signals (puts/contango)"})

    # Existing macro_positioning regime (HYG/LQD, copper/gold, dollar, TLT)
    mp = macro.get("macro_positioning") or {}
    mp_regime = mp.get("regime")
    if mp_regime == "RISK_OFF_PRESSURE":
        sub_votes.append({"source": "Macro positioning", "vote": 1, "label": "credit/dollar/bonds = risk-off"})
    elif mp_regime == "RISK_ON":
        sub_votes.append({"source": "Macro positioning", "vote": -1, "label": "credit/dollar/bonds = risk-on"})

    # VIX absolute level
    vix = macro.get("vix")
    if vix is not None:
        try:
            vix_val = float(vix)
            if vix_val >= 25:
                sub_votes.append({"source": "VIX absolute", "vote": -1, "label": f"VIX {vix_val:.1f} elevated - fear priced in (contrarian long)"})
            elif vix_val <= 13:
                sub_votes.append({"source": "VIX absolute", "vote": 1, "label": f"VIX {vix_val:.1f} low - complacency (contrarian short)"})
        except (TypeError, ValueError):
            pass

    net_votes = sum(v["vote"] for v in sub_votes)
    if net_votes >= 2:
        regime = "RISK_OFF_PRESSURE"
    elif net_votes <= -2:
        regime = "RISK_ON"
    else:
        regime = "NEUTRAL"

    result = {
        "regime": regime,
        "net_votes": net_votes,
        "sub_votes": sub_votes,
        "n_signals": len(sub_votes),
    }

    if verbose:
        print(f"  macro_meta_regime: {regime} (net votes: {net_votes:+d}, {len(sub_votes)} signals)")
        for v in sub_votes:
            sign = "+" if v["vote"] > 0 else ("-" if v["vote"] < 0 else " ")
            print(f"    {sign} {v['source']}: {v['label']}")

    return result


def build_cot_meta(cot_snapshot):
    """Convert cftc_cot snapshot into meta counts for the regime aggregator."""
    if not cot_snapshot:
        return None
    crowded_long = 0
    crowded_short = 0
    moderately_long = 0
    moderately_short = 0
    equity_contracts = ("ES", "NQ", "RTY")
    for sym in equity_contracts:
        entry = cot_snapshot.get(sym) or {}
        cls = entry.get("classification") or {}
        regime = cls.get("regime")
        if regime == "CROWDED_LONG":
            crowded_long += 1
        elif regime == "CROWDED_SHORT":
            crowded_short += 1
        elif regime == "MODERATELY_LONG":
            moderately_long += 1
        elif regime == "MODERATELY_SHORT":
            moderately_short += 1
    return {
        "crowded_long_count": crowded_long,
        "crowded_short_count": crowded_short,
        "moderately_long_count": moderately_long,
        "moderately_short_count": moderately_short,
    }
