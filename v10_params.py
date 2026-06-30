"""V10 sandbox - tunable-parameter store (STANDALONE).

The whole point of Phase 2 is: NO hardcoded gate values. The scanner reads
v10_tunable_parameters.json at the start of every cycle; the weekly autopsy writes a
tuning advisory; tune_parameters.py turns the knobs. Day-one values are ultra-loose so we
guarantee active daily execution and build a win/loss database, then tighten empirically.
"""

import os
import json

PARAMS_PATH = "v10_tunable_parameters.json"

DEFAULTS = {
    "regime_compass_bypass": True,
    "min_rvol": 1.0,
    "max_bid_ask_spread_pct": 5.0,
    "min_flow_dominance_pct": 30.0,
    "earnings_blackout_days": 1,
    "alt_reddit_min_mentions": 10,
    "alt_insider_min_dollar_value": 10000,
    "portfolio_max_sector_concentration": 0.50,
    "min_hold_hours": 24,                 # 24h minimum-hold (swing rule): gates the +30% scale-out only
    "take_profit_pct": 30,                # Strategy B tier 1: SCALE OUT 50% at +30% (gated by 24h hold)
    "scale_out_pct": 50,                  # % of the position sold at the +take_profit_pct scale-out
    "break_even_pct": 0,                  # Strategy B tier 2: break-even shield on the runner after scale-out
    "trail_activate_pct": 50,             # Strategy B tier 3: arm the MFE trail once the runner crosses +50%
    "trail_drawdown_pct": 20,             # 20% trail off the peak MFE (peak +100% -> stop +80%)
    "stop_loss_pct": 50,                  # hard stop: close a leg at <= -50% unrealized (overrides 24h hold)
    "expiry_exit_dte": 3,                 # hard exit: close a leg within 3d of expiry (overrides 24h hold)
    "min_contracts": 2,                   # AFFORDABILITY GATE: skip the trade if <2 contracts fit the $800 budget
    "max_contracts_per_ticker": 3,        # ticker concentration cap
    "ticker_cooloff_hours": 24,           # 24h cool-off after a close before re-entry
    "stale_order_max_minutes": 30,        # cancel unfilled limit orders older than this (3 cycles)
    "scanner_min_premium": 50000,         # V11: min UW flow premium ($) to surface a candidate (loose discovery)
}


def load(path=PARAMS_PATH):
    if not os.path.exists(path):
        save(dict(DEFAULTS), path)
        return dict(DEFAULTS)
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        d = {}
    out = dict(DEFAULTS)
    out.update(d if isinstance(d, dict) else {})
    return out


def save(params, path=PARAMS_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)
