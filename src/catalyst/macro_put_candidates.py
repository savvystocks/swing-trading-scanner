"""Macro-driven put candidates - SPY/QQQ/sector ETFs when regime turns bearish.

When the macro regime detector flags bearish (score >= 50), this module
injects index/sector put candidates into the pick pool. These are NOT
single-stock plays - they're macro hedges that profit from broad market
or sector weakness.

The candidates surface in the unified ranking with PUT direction and
high bear conviction (since the macro regime is the catalyst).
"""

import os
from datetime import datetime


MACRO_PUT_UNIVERSE = {
    "SPY": {
        "name": "S&P 500",
        "trigger_score": 50,
        "rationale": "Broad market hedge - profits from SPY decline",
    },
    "QQQ": {
        "name": "Nasdaq 100",
        "trigger_score": 55,
        "rationale": "Tech/growth hedge - higher beta than SPY on selloffs",
    },
    "IWM": {
        "name": "Russell 2000",
        "trigger_score": 50,
        "rationale": "Small-cap puts amplify on risk-off (3x SPY beta typical)",
    },
    "XLF": {
        "name": "Financials sector",
        "trigger_score": 55,
        "rationale": "Bank-sector puts on credit-cycle tightening",
        "trigger_component": "xlf_vs_spy_30d",
        "trigger_value": -3,
    },
    "HYG": {
        "name": "High Yield Bonds",
        "trigger_score": 60,
        "rationale": "Credit hedge - widens before equity selloffs",
        "trigger_component": "hyg_vs_lqd_20d",
        "trigger_value": -2,
    },
    "XLY": {
        "name": "Consumer Discretionary",
        "trigger_score": 60,
        "rationale": "Cyclical hedge - first to decline in slowdown",
    },
}


def _get_live_spot(ticker):
    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_SECRET_KEY"):
        return None
    try:
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        c = StockHistoricalDataClient(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"])
        q = c.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=[ticker]))
        info = q.get(ticker)
        if not info:
            return None
        bid = float(info.bid_price) if info.bid_price else 0
        ask = float(info.ask_price) if info.ask_price else 0
        return (bid + ask) / 2 if (bid > 0 and ask > 0) else (bid or ask)
    except Exception:
        return None


def generate_macro_puts(macro_regime, verbose=False):
    if not macro_regime:
        return []
    score = macro_regime.get("score", 0)
    components = macro_regime.get("components") or {}
    candidates = []

    for ticker, config in MACRO_PUT_UNIVERSE.items():
        trigger_score = config.get("trigger_score", 50)
        if score < trigger_score:
            specific_trigger = config.get("trigger_component")
            if specific_trigger:
                v = components.get(specific_trigger)
                threshold = config.get("trigger_value", 0)
                if v is None or v > threshold:
                    continue
            else:
                continue

        spot = _get_live_spot(ticker)
        if not spot:
            continue

        bear_score_for_macro = min(95, max(70, score + 15))
        candidate = {
            "ticker": ticker,
            "name": config["name"],
            "sector": "Macro Hedge",
            "industry": "ETF",
            "price": spot,
            "live_spot": spot,
            "_aa_tier": "MACRO_PUT",
            "_macro_put": True,
            "_macro_put_rationale": config["rationale"],
            "_macro_regime_at_discovery": macro_regime,
            "catalysts": [{
                "key": "macro_regime_bear",
                "label": f"Macro regime {macro_regime['regime']} ({score}/100)",
                "details": "; ".join(macro_regime.get("notes", [])[:3]),
            }],
            "_bear_conviction": {
                "score": bear_score_for_macro,
                "tier": "TAKE_PUT" if bear_score_for_macro >= 70 else "WATCH_PUT",
                "components": {
                    "macro_driven": bear_score_for_macro,
                },
                "weights": {"macro_driven": 1.0},
            },
            "_conviction": {
                "score": max(15, 50 - score // 2),
                "tier": "SKIP",
                "components": {},
                "weights": {},
            },
            "_direction": {
                "side": "PUT",
                "winning_score": bear_score_for_macro,
                "call_score": max(15, 50 - score // 2),
                "put_score": bear_score_for_macro,
                "edge_pts": bear_score_for_macro - max(15, 50 - score // 2),
                "label": "📉 PUT (macro)",
            },
        }
        candidates.append(candidate)

    if verbose:
        if candidates:
            print(f"  macro_put_candidates: regime score {score} triggered {len(candidates)} macro puts:")
            for c in candidates:
                print(f"    {c['ticker']:5} bear_conv={c['_bear_conviction']['score']} - {c['_macro_put_rationale']}")
        else:
            print(f"  macro_put_candidates: regime score {score} below trigger thresholds, no macro puts")
    return candidates
