# Candidate scan and pools

## What
Turns the Unusual Whales flow alerts of the last window into the candidate lists every book reads:
a per-ticker aggregate with the cheapest in-band contract per side (the affordable band), the
dip strategies' expensive-contract side-pool, the whale side-pool, the full-band list, and the
student pool. "Affordable" means three different bands in three places; know which one you are in.

## Where
- `sandbox_proactive_lab.py:scan_candidates` - the rows loop. Per alert row `r`: `price` is the
  per-contract premium, `bid`/`ask` the alert NBBO, `option_chain` the OCC, `total_premium`,
  `total_ask_side_prem`/`total_bid_side_prem` the aggressor split, `expiry`, `strike`, `created_at`.
- Ticker aggregate `agg`: rows with `prem_lo <= price <= prem_hi` (the scan's affordable band,
  $0.30-$4.00) -> `afford_call` / `afford_put` (cheapest in-band contract per side, DTE >= 7),
  `call_prem`/`put_prem`, `flow_type`, `tight_spread_pct` (free liquidity hint).
- Pricey pool `aggx` -> `_PRICEY_CANDS` (top 14 by premium): CALLS only, ask $4.00-9.00, premium
  50-400k, ask-side aggressor, spread <= 2%, DTE >= 7, one contract per ticker, carries the
  `alert` block. Read by DIP_CONF_MILD and BULL_DIP_X only.
- Student pool `sagg` -> `_STUDENT_CANDS` (top `probe.student.pool.max_pool` = 30): the ARCHIVE
  universe the pickers were trained on - both sides, premium 50k-1M, ask-side aggressor, alert
  spread <= 2% of ask, ask >= 0.30 with no ceiling, DTE >= 1, keyed by OCC, `student: True`,
  `first_seen` from one pass over the rows. Config: `sandbox_proactive_lab.py:_student_pool_cfg`.
- `_FULL_CANDS` (premium 50k-1M, top 20) feeds FOLLOW_CALLS and WINNER_PROFILE; `_WHALE_CANDS`
  (400k-1M) the fade whale probe.

## Exercise
- Offline pool logic: `./.venv/bin/python v11_mot_harness.py | grep "student pool"`.
- Live: `gh run view <id> --log | grep -n "UW flow scan\|student pool\|pre-skipped"`.

## Healthy
- `UW flow scan: 10 market-wide candidates (top: ['SMR', 'QQQ', ...])`
- `  student pool: 41 archive-universe contracts, top 30 by premium kept (pool cap)` (only when the cap binds)
- `  student pool: spec probe.student.pool missing - archive-universe defaults in force` means the spec block is gone; fix the spec.

## Evidence
- Every scored candidate reaches the harvest (`harvest_logger.py`) whether or not it trades.
- Student pool rows are scored into `reports/shadow_lab/student_scores.jsonl`.

## Checks
- MOT 6.17 "student pool: both sides, archive premium band, ask floor with no ceiling, DTE floor 1, keyed by contract".
- MOT 6.10e roster-focus (which strategies exist).

## Traps
- 2026-09-03 THE BULL-DAY AFFORDABILITY DROUGHT: synthesized contracts on mega-caps priced over
  the budget; fixed by the affordable identity (`afford_call`) and the trigger-contract fallback.
- 2026-09-12 (fourth entry) THE STUDENT SEAT SCORED THE WRONG SLICE: the seat read the $4-9 call
  pool; its evidence lived in sub-$1 contracts on both sides. A seat inherits the universe of the
  pool it reads - diff the pool's filters against the evidence's universe before wiring.
- Index roots (SPX, NDX, VIX ...) are dropped up front; ETFs (SPY, QQQ, TLT) stay, as in the archive.
