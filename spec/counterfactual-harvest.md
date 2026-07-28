# Counterfactual Harvest — schema and operation

Logs the full 37-feature payload for scored candidates (executed and skipped) and resolves a
triple-barrier label on executable option prices, so skipped setups become training data. Two
components; the trading path is untouched (logging is observational, fail-open, post-trade).

## Storage

SQLite at `data/harvest.db` (WAL, `busy_timeout=30000`). Lives on the VPS (harvest-poller,
64.176.178.15) — never written inside GitHub Actions. Gitignored, with a same-day crash-cushion
backup at `data/harvest_backups/harvest_YYYYMMDD.db` (last 2 kept; the real archive is the nightly
off-box snapshot repo).

Transport (updated 2026-07-28 to match reality; the code wins): the logger runs in GHA (inside the
scan loop), where the DB does not persist, so it appends candidate rows to
`data/harvest_inbox/candidates_YYYYMMDD.jsonl` (and fill-ledger events to `fills_YYYYMMDD.jsonl`).
That inbox IS committed back to `main`; the VPS poller syncs via fetch+reset, ingests into SQLite on
each run (idempotent on `candidate_id` / `event_id`), then polls. Ingest never deletes the inbox.

## Component 1 — candidate logger

Hook: one fail-open call in `run_scheduled_cycle` after the entry decision (`harvest_logger.harvest_scan`).
`enter_proactive_set` is unmodified. The executed contract is passed in and always logged
(`executed=1`, full payload). Counterfactuals are built from the raw UW flow rows.

Per-contract-per-day dedup (state in `data/harvest_state.json`): the full payload is computed once
per unique contract per day at first qualification; re-flashes log no new row unless executed.
Under the `harvest_daily_cap`, selection is highest `rule_score` first (`sample_tier=topn`) plus a
mandatory 5 random below-threshold contracts (`sample_tier=random`, for misscore detection). All
other in-band scored contracts get a cheap row (`skip_reason=quota_cap`, null features); out-of-band
rows get `skip_reason=prefilter`, null features. `entry_ref = ask` at signal time (never mid).

### Table `candidates` (immutable, one row per scored candidate)
`candidate_id` (uuid pk), `run_id`, `code_version` (git sha), `feature_set_version`, `signal_ts_utc`
(epoch ms UTC), `ticker`, `occ_symbol` (poll join key), `expiry`, `strike`, `right`, `side`,
`bid`, `ask`, `bid_size`, `ask_size`, `mid`, `spread_pct`, `last`, `underlying_last`, `entry_ref`,
`features` (json), `rule_score`, `executed`, `skip_reason`
(prefilter|liquidity|score_below_threshold|budget_exhausted|duplicate_position|quota_cap|other),
`vertical_barrier_ts` (min(Fri 16:00 ET of signal week, expiry)), `barrier_up_pct`,
`barrier_down_pct`, `poll_tier` (standard|reduced|none), `sample_tier` (executed|topn|random|none).

## Component 2 — barrier poller (`poller.py --once`)

Runs on the always-on Vultr VPS from a crontab (`git pull --ff-only origin main` first, then
`poller.py --once`), every 15 min across the RTH window on weekdays. The XNYS session is gated in-code
by `_market_open_now` via `pandas_market_calendars` (holidays/half-days skipped).

Each run: ingest inbox, back up DB, then for every open candidate (no label, `poll_tier != none`)
fetch NBBO via batched Alpaca option snapshots (chunk 100; UW quotes fallback), append to `bid_path`,
and evaluate against `entry_ref`. `poll_tier=standard` every run; `reduced` hourly. The full path is
kept permanently so labels are recomputable under any alternative barrier config — never pruned.

### Barrier rules (`harvest_labeler.label_path`)
Up touch `bid >= entry_ref*1.30`; down touch `bid <= entry_ref*0.50`; vertical when
`poll_ts >= vertical_barrier_ts`. First touch wins. Vertical is signed by realized return (exactly 0
is `-1`). Both barriers in one interval → down + `ambiguous_touch` (conservative for long premium).
`bid=0` fresh → down. Missing/stale quote → skip, `n_stale++`. Expires worthless → realized `-1.0`,
vertical, `-1`. Halts/delistings/adjusted contracts → `censored`, `label null`, reason recorded
(excluded from training, never guessed).

### Table `bid_path` (append-only, permanent)
`id` pk, `candidate_id`, `poll_ts_utc`, `bid`, `ask`, `quote_ts`, `stale`; unique
`(candidate_id, poll_ts_utc)`.

### Table `labels` (one per candidate)
`candidate_id` pk, `outcome` (up|down|vertical|censored), `label` (+1|-1|null), `realized_return`
((exit_bid-entry_ref)/entry_ref), `touch_ts_utc`, `time_to_touch_min`, `mfe`, `mae`, `n_polls`,
`n_stale`, `ambiguous_touch`, `poll_cadence_min`, `censored_reason`.

## VPS setup notes
The poller runs on the Vultr VPS. Paper creds live in `~/.harvest_env` (chmod 600), sourced by the
cron wrapper (`scripts/run_poller_vps.sh`), to fetch Alpaca (else it degrades to UW-only, mostly
stale). `GMAIL_USER` / `GMAIL_APP_PASSWORD` enable the optional one-line daily email summary. The
schedule is a VPS crontab entry; a nightly job also pushes a gzip DB snapshot to the private
`harvest-snapshots` repo.

## Tests
`test_harvest.py` (8 synthetic barrier paths). Harvester, poller, and passivity suites in the
session scratchpad prove tiering/dedup, path/label resolution/idempotency, and that logging never
alters or crashes the trade path (identical orders on/off/crash; executed rows == trades placed).
