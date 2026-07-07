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
    "earnings_blackout_days": 3,          # TIER B (owner decision 15): no NEW entry within 3d of earnings; fail-open if sensor null
    "alt_reddit_min_mentions": 10,
    "alt_insider_min_dollar_value": 10000,
    "portfolio_max_sector_concentration": 0.50,
    # WHY 24h: deliberate pattern-day-trader (PDT) avoidance for the sub-$25k live-capital future -
    # NOT a quirk. A same-day scale-out consumed on every winner would burn the 3-day-trade budget of
    # a small margin account. No session may change this without a NORTH_STAR amendment. (The ratchet
    # backstop's same-day STOP fills are the accepted exception: capital safety outranks returns, and
    # every day trade consumed is logged.) ROADMAP item 14 decides margin vs CASH at the live gate.
    "min_hold_hours": 24,                 # 24h minimum-hold (swing rule): gates the +30% scale-out only
    "take_profit_pct": 30,                # Strategy B tier 1: SCALE OUT 50% at +30% (gated by 24h hold)
    "scale_out_pct": 50,                  # % of the position sold at the +take_profit_pct scale-out
    "break_even_pct": 0,                  # Strategy B tier 2: break-even shield on the runner after scale-out
    "trail_activate_pct": 50,             # Strategy B tier 3: arm the MFE trail once the runner crosses +50%
    "trail_drawdown_pct": 20,             # 20% trail off the peak MFE (peak +100% -> stop +80%)
    "stop_loss_pct": 50,                  # hard stop: close a leg at <= -50% unrealized (overrides 24h hold)
    "expiry_exit_dte": 3,                 # hard exit: close a leg within 3d of expiry (overrides 24h hold)
    "min_contracts": 2,                   # AFFORDABILITY GATE: skip the trade if <2 contracts fit the $800 budget
    "one_position_per_underlying": True,  # TIER B (owner decision 21): hard block - SUPERSEDES max_contracts_per_ticker
    "max_contracts_per_ticker": 3,        # SUBORDINATED to one_position_per_underlying (kept only as a belt-and-braces ceiling)
    "ticker_cooloff_hours": 4,            # 4h cool-off (was 24h) - allow same-day re-entry on a fresh setup
    "stale_order_max_minutes": 30,        # cancel unfilled limit orders older than this (3 cycles)
    "daily_brake_stopouts": 3,            # TIER B (owner decision 19): 3 stop-outs today -> no new entries this session
    "daily_brake_loss_multiple": 2.0,     # ... OR realized session loss >= 2x the $800 allocation
    "backstop_enabled": False,            # TIER B (owner decision 20): ratchet broker-side stop; OFF until the canary passes
    "backstop_canary_occ": "",            # canary mode: when set, ONLY this OCC gets a backstop (one full lifecycle first)
    "backstop_type": "stop",              # T5 DECISION (2026-07-06): plain stop - affordable-band p90 spread 17.9% < 30%,
                                          # and a bad fill beats no fill (NORTH_STAR: capital safety outranks returns)
    "backstop_limit_buffer_pct": 25,      # only if backstop_type=stop_limit: limit = stop x (1 - this)
    "backstop_min_delta": 0.01,           # min stop-price move ($) worth a cancel+resubmit (T3: replace unsupported)
    "close_fail_park_after": 5,           # PARK a leg after N consecutive rejected closes with no live bid (orphan fix)
    "scanner_min_premium": 50000,         # V11: min UW flow premium ($) to surface a candidate (loose discovery)
    "scanner_flow_limit": 600,            # rows pulled from UW flow per scan (wide net for the cheap tail)
    "scanner_premium_min": 0.30,          # per-contract premium floor for the affordable mid-cap band
    "scanner_premium_max": 4.00,          # per-contract premium ceiling (2ct x $4 x 100 = $800)
    "harvest_topn": 20,                   # counterfactual: full-payload harvest of top-N contracts by flow per cycle
    "harvest_random": 10,                 # TIER B (owner decision 23): MIN random samples/day 5 -> 10; near-close top-up guarantees it
    "harvest_random_p": 0.007,            # per-candidate Bernoulli prob over the whole non-topn pool, spread across the day
    "harvest_daily_cap": 300,             # CEILING for the adaptive cap (owner decision 22) - see harvest_logger._adaptive_cap
    "harvest_api_budget_per_day": 6000,   # daily provider-call budget the adaptive cap floats inside
    "harvest_calls_per_payload": 3,       # est. provider calls per full-payload computation
    "poller_chunk": 100,                  # mirrors poller.CHUNK - quotes per poller API call
    "poller_runs_per_day": 26,            # */15 during 13:30-20:00 UTC market hours
    "scanner_barrier_up": 0.30,           # triple-barrier up touch, stamped per candidate row
    "scanner_barrier_down": -0.50,        # triple-barrier down touch, stamped per candidate row
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
