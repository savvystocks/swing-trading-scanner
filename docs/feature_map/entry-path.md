# Entry path

## What
The one function every buy goes through. Its order of operations is the safety model: guards
before metadata, metadata before legs, legs before the live repricing, the collision guard before
the spread cap, the PENDING record before the order, the OPEN record after.

## Where
`sandbox_proactive_lab.py:enter_proactive_set`, in order:
1. `sandbox_proactive_lab.py:ticker_blocked` - one position per underlying (OPEN and PENDING
   records; cross-book softening for probes), the subordinated `max_contracts_per_ticker`, cool-off.
2. `sandbox_proactive_lab.py:collect_metadata` - the sensor sweep (macro, IV term, GEX, alt
   catalyst, V11 sensors); missing spot or IV -> skip, never fabricate.
3. probe_filter (the strategy's lambda) -> `sandbox_proactive_lab.py:classify_regime` (flow side
   dominates; NEUTRAL is skipped: the calendar route is disabled) -> earnings blackout.
4. `sandbox_proactive_lab.py:build_legs` - the trigger-contract branch when `_PROBE_CONTRACT` is set
   (either side; student picks sized to the budget off the live ask, everything else one contract),
   else synthesized 4%-OTM 35-DTE legs sized `floor(budget / cost)` with the min_contracts gate.
5. Affordability fallback: when every synthesized leg is unaffordable, a PROBE buys the candidate's
   own in-band trigger contract (`afford_call`/`afford_put`, ask 0.30-9.90, DTE >= 7, one contract).
6. `sandbox_proactive_lab.py:_resolve_legs_occ` - real OCCs for synthesized legs; trigger contracts
   are never overwritten (`occ_source` uw_trigger_verbatim / afford_fallback / student_pick).
7. Trigger-leg live repricing - a fresh indicative quote; no quote, crossed, spread > 2%, or ask
   outside `band_lo`-`band_hi` -> skip; entry_premium and the nickel limit come from the live ask.
8. One record per contract, ever: any OPEN or PENDING record or broker position on the OCC -> skip.
9. Spread cap (`fade_book.spread_cap`) on the real quote, with one budgeted retry for non-probes.
10. PENDING record appended (`sandbox_proactive_lab.py:_append_log`) with `client_order_id` per leg
    BEFORE `sandbox_proactive_lab.py:route_to_alpaca_paper` (`_order_payload`, `_submit_paper_order`);
    then the record is rewritten OPEN with the orders, the buy telegram is sent and the flag stored.

## Exercise
- `./.venv/bin/python scripts/regime_drill.py` - scenarios 1 (afford fallback), 2 (trigger
  contract), 3 (fade shape), 4 (occ collision), 7 (student put); dry run, orders never placed.
- `./.venv/bin/python v11_mot_harness.py | grep -n "PENDING\|client_order_id\|spread cap\|one record"`.

## Healthy
- `ENTERED NBIS [BULLISH] | LIVE_PAPER | OCC alpaca_real` followed by the leg line
  `  bullish_call   LONG_CALL  NBIS260918C00240000  x1  @lim $3.65  spread 1.4% -> pending_new <order id>`
- Skips are normal and printed: `  skip T: spread_cap: real spread 7.4% > 2.0% cap (bullish_call)`.

## Evidence
- The record in `proactive_sandbox_logs.json` (trade_set_id, legs, orders, execution_mode,
  buy_alert_delivered); the fill ledger (`fill_ledger.py`) stashes order responses.

## Checks
- MOT 6.14 (PENDING before routing, client_order_id, roll-call order, guards see PENDING);
  MOT 6.16 spread cap; dimension 2 routing; drill 1-4 and 7.

## Traps
- 2026-09-12 (second entry) A FILLED TRADE'S RECORD WAS LOST TO A PUSH RACE - the record is
  written before the order now; the resolver and union guard keep it (persist-and-merge.md).
- 2026-09-01 (evening) INSTRUMENT-MISMATCH near-miss: evidence must be earned on the instrument the
  backtest measured, hence the trigger-contract identity.
- The labels rule: entry_ref is the ask at signal, never mid; exits fill on the bid.
- 2026-09-14 agent tests (reports/research/agent_tests_2026-09-13.md): on synthesized legs the
  limit is set from the premium ESTIMATE, and 602 paper fills printed on average 31% BELOW their
  limit and within half a percent of the live ask. Paper fills at the ask hide that; a real broker
  may fill a limit 30% above the market at the limit. Before any real money, cap every limit at
  the live ask plus one tick, as the trigger-contract path already does.
- `mock=True` metadata is fake; `dry_run=True` routes nothing; the drill uses both.
