# Counterfactual harvest and transport

## What
Every scored candidate, traded or not, is logged with its features and later labeled with a
path-dependent triple-barrier outcome on executable prices. It is the training pile for the
student and the brain. Logging is passive: it may never alter or crash the trade path.

## Where
- Logger (GHA): `harvest_logger.py` `harvest_scan(params, executed_record, mock, engine_skips)` -
  per-contract-per-day dedup, top-N and Bernoulli random tiers, cheap rows for the rest; appends to
  `data/harvest_inbox/candidates_YYYYMMDD.jsonl` and updates `data/harvest_state.json`; committed
  by the persist step.
- Poller (VPS, `scripts/run_poller_vps.sh` every 15 min 13-21 UTC weekdays): `poller.py --once`
  pulls `main` first, ingests the inbox into `data/harvest.db` (idempotent on candidate_id), polls
  open candidates, writes bid paths and labels (`harvest_labeler.py`, XNYS-calendar vertical
  barrier), `harvest_db.py` schema.
- Backups: `/home/poller/backup_snapshot.sh` 21:30 UTC weekdays to the private snapshots repo; the archiver
  workflow and `scripts/archiver_watch.sh`.

## Exercise
- `./.venv/bin/python test_harvest_passivity.py` (mandatory after ANY change touching the logger or the trade path).
- `./.venv/bin/python test_harvest.py`, `test_harvest_harvester.py`, `test_harvest_poller.py`.
- `sqlite3 data/harvest.db "select count(*), max(day) from candidates"` on the VPS.

## Healthy
- `harvest: {'logged': 33, 'topn': 20, 'random': 6, ...}` at the end of a cycle.
- `harvest skipped (fail-open): <Error>` is a logger fault that did not touch trading; fix it anyway.

## Evidence
- `data/harvest.db` (never committed); `reports/research/freshness_registry_*.json`;
  `SYSTEM_ARCHITECTURE.md` sections 4-7.

## Checks
- The four harvest suites in `~/vps_ship_grid.sh`; MOT dimension 1 (input and schema).

## Traps
- 2026-09-22: `harvest_logger.py:_flow_rows` was NOT covered by the spec's `uw_scanner` switch and kept
  calling Unusual Whales every cycle after the scanner was switched off. A switch named for a dependency must be
  read at every call site of that dependency (MOT 6.34).
- 2026-07-06 HARVEST ROW LOST TO A TRIGGER RACE; 2026-07-02 MANDATORY RANDOM SAMPLE EMPTY.
- 2026-07-16 61% OF TRAINING PILE FEATURELESS; 2026-07-26 LOOKAHEAD CONTAMINATION.
- 2026-07-10 POLLER GIT RACES -> git-pull-first, `--ff-only`.
- The labels are bid-only and executable-price-only; entry_ref is the ask at signal.
