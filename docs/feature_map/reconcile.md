# Reconciliation roll-calls

## What
Cycle-start passes that make the book and the broker agree before the exit engine runs: settle
PENDING intents, adopt positions with no record, cancel stale limits, refuse to trade on an
unreadable book.

## Where
- `sandbox_proactive_lab.py:_assert_log_integrity` - an unparseable `proactive_sandbox_logs.json`
  aborts the cycle loudly (blind, not flat).
- `sandbox_proactive_lab.py:reconcile_pending` - each PENDING record's legs are looked up at the
  broker by `client_order_id`; an order that exists makes the record OPEN with the order attached;
  none after the grace window, or an order that ended unfilled, VOIDs the leg
  (`VOID_NEVER_SUBMITTED`, return None). Runs BEFORE the orphan roll-call.
- `sandbox_proactive_lab.py:reconcile_orphans` - a broker option position whose OCC appears in no
  record (any status) is ADOPTED into a fresh OPEN record (`trade_set_id ADOPT-...`, regime
  ADOPTED) so the exit engine manages it; fills younger than 45 minutes get a grace period;
  bare-occ PUTW/VRP records and OPEN shares are known, never adopted; equities are never adopted.
- `sandbox_proactive_lab.py:audit_stale_orders` - unfilled limits older than the window are cancelled
  and an AUDIT marker appended.

## Exercise
- `./.venv/bin/python v11_mot_harness.py | grep -n "pending roll-call\|orphan\|adopt"`.
- Live: `gh run view <id> --log | grep -n "orphan reconcile\|pending reconcile\|stale-order"`.

## Healthy
- `  orphan reconcile: NBIS260918C00240000 filled <45min ago - grace period, record likely in flight`
- `pending reconcile: 1 opened, 0 voided` (only when there was something to settle)
- `stale-order audit: 0 unfilled limit(s) cancelled (> 30m)`
- A `TIDY-UP: re-linked N position(s)` telegram (sent from `sandbox_proactive_lab.py:reconcile_orphans`
  through `sandbox_proactive_lab.py:_notify`) means an adoption happened; find out why the record was missing.
- MOT lines to grep after `./.venv/bin/python v11_mot_harness.py`: `[PASS] orphan reconcile` and
  `[PASS] pending roll-call`.

## Evidence
- Adopted records carry `adopted_from`; voided intents carry `leg_exits[...].action`.

## Checks
- MOT 6.14 orphan adoption (July: one-per-underlying reads records; PARKED stays exempt);
  MOT 6.14 pending intent (September: order at broker -> OPEN, none after grace -> VOID).

## Traps
- 2026-08-11 FRIENDLY-FIRE ADOPTION (PUTW's own short put adopted, then bought back).
- 2026-08-14 DOUBLE-CLAIM DISEASE (fresh fills adopted before their record landed) -> the grace window.
- 2026-08-24 MASS-ADOPTION / CORRUPT-LOG (unreadable log read as empty -> 29 adoptions) -> fail-closed integrity.
- An adoption loses the strategy attribution; prefer restoring the lost record from git when it
  exists (2026-09-12 NBIS was restored from the commit that carried it).
