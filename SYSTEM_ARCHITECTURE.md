# SYSTEM ARCHITECTURE

Point-in-time reference for `savvystocks/swing-trading-scanner`. Written to be an accurate context
anchor: every figure below was read from the source on the current branch, not assumed. Where the
running code differs from earlier design intent, the code wins and the gap is flagged.

- Generated against branch `v10-research-sandbox` @ `e2b2af1b` · 2026-07-02
- Companion documents: `spec/counterfactual-harvest.md` (schema), `reports/harvest_audit_2026-07-02.md` (live-session audit + open defects), `docs/system_map.md` (short map). Regenerate the full source bundle with `python scripts/make_reference.py`.

> ACCURACY NOTES (verified against source, correcting common misconceptions):
> - `harvest_topn = 20` (top-20 by flow premium), not 15.
> - `harvest_daily_cap = 300` full-payload computations/day (dedup keeps the real number far lower — ~190 on the first live day); it is not a 30–80 cap.
> - The vertical barrier is **XNYS-calendar-aware** (fixed 2026-07-02): it resolves to the last trading session of the signal week at 16:00 ET (min expiry), correctly handling holiday-shortened weeks.
> - The poller's quote fallback is **Unusual Whales**, not EODHD — and the current EODHD key has **no options-data access** (401/403 verified), so EODHD cannot supply option prices at all.

---

## 1. EXECUTIVE SYSTEM OVERVIEW

Post-cleanup the repository runs lean. The v3.1 dead weight was amputated on 2026-07-02:

| Metric | Before cleanup | After cleanup (this branch) |
|---|---|---|
| Python files | 259 | **79** |
| Python lines | 53,516 | **16,772** (~69% removed) |
| Total tracked files | 401 | 223 |

Two independent operational engines live in this one repository:

1. **V9 Flow-Scan Pipeline** — the production scanner. GitHub Actions crons pull whole-market Unusual Whales option flow and market data, run the `src/catalyst` "ambush" scoring pipeline, and emit Telegram/email alerts + paper-trade digests. Entry point `scripts/run_live_scan.py`. Frozen; not the subject of active development.
2. **V10/V11 Sandbox + Counterfactual Harvester** — an autonomous paper-options-trading data lab. It scans UW flow, enters directional Call/Put paper trades on Alpaca, manages exits with a state machine, and — passively — logs every scored candidate with a rich feature payload and resolves a path-dependent triple-barrier label on executable prices. This is the Phase-4 training-data engine and the focus of current work.

The two engines share the `src/` core and Alpaca/UW clients; they are separated by branch (Section 2) and never cross-import.

---

## 2. BRANCH STRATEGY & ISOLATION

The system deliberately spans two branches of the same repo. GitHub Actions crons fire from the default branch (`main`).

### `main` — V9 production only (`f95f8b1a`)
- **68 Python files**, zero experimental/harvest code (`sandbox_proactive_lab.py`, `harvest_*.py`, `poller.py`, `v10_params.py` are all absent here — verified).
- Pure flow-scanning + alerting: the 5 V9 workflows (`live_scan`, `macro-review`, `paper-digest`, `robinhood-fills`, `health-check`) plus `sandbox_scheduler.yml`.
- `sandbox_scheduler.yml` lives on `main` (crons fire from the default branch) but **checks out `v10-research-sandbox`** to run — so the sandbox code never has to exist on `main`.

### `v10-research-sandbox` — V9 core + V11 harvester (`e2b2af1b`)
- **79 Python files**: everything `main` has, plus the entire V11 counterfactual harvester (`sandbox_proactive_lab.py`, `harvest_logger.py`, `harvest_db.py`, `harvest_labeler.py`, `poller.py`, `sandbox_v11_sensors.py`, `v10_params.py`), the SQLite DB logic, and the test suites (`test_harvest*.py`, `v11_mot_harness.py`).
- Both branches had the identical dead V9 code removed; the 11-file difference is the extra live V11 code the sandbox carries on top.
- **Isolation rule (standing):** experimental/harvest code stays on `v10-research-sandbox`; the only file ever authorized on `main` for the sandbox is `sandbox_scheduler.yml`.

---

## 3. PIPELINE SPECIFICS & FILE MAPS

### Entry points & critical roles

| File | Branch(es) | Role |
|---|---|---|
| `scripts/run_live_scan.py` | both | **V9 entry point.** Drives the `src/catalyst` ambush/flow-scan pipeline (uw_adapter, alert_engine, scan_safeguards, alpaca_executor, earnings_routing, defined_risk, paper_pipeline, regime_compass, probe_ladder). Run by `live_scan.yml`. |
| `sandbox_proactive_lab.py` | sandbox | **V11 lab orchestrator.** `run_scheduled_cycle()` runs one cycle: stale-order cleanup → exit pass (`manage_open_positions`) → `scan_candidates` (UW flow → affordable band) → `enter_proactive_set` (one directional leg to Alpaca paper, $800 sizing) → **harvest hook**. Run by `sandbox_scheduler.yml` (`python sandbox_proactive_lab.py`). |
| `harvest_logger.py` | sandbox | **Component 1 (logger).** `harvest_scan()` logs every scored candidate. Selection, per-contract-per-day dedup, sample tiers, `_vertical_barrier_ts`. Writes rows to the committed inbox in GHA. |
| `harvest_db.py` | sandbox | **SQLite layer.** Connection PRAGMAs (WAL/busy_timeout), schema DDL, `ingest_inbox`, `insert_candidate`, `append_bid_path`, `upsert_label`, `backup(keep=14)`. |
| `harvest_labeler.py` | sandbox | **Barrier logic (pure function).** `label_path(entry_ref, up_pct, down_pct, vertical_ts, signal_ts, path)` → outcome/label/realized_return/mfe/mae/n_polls/n_stale/ambiguous. No I/O, fully unit-testable. |
| `poller.py` | sandbox | **Component 2 (poller).** `poller.py --once`: XNYS holiday gate → ingest inbox → backup → batched Alpaca option NBBO (UW fallback) → append `bid_path` → resolve labels. Run locally by Windows Task Scheduler. |

### Fail-safe, fail-open passive hook (why the harvester can never break trading)

The harvest logger is invoked from exactly one place in the trade loop, and it is structurally incapable of affecting execution:

```
# sandbox_proactive_lab.run_scheduled_cycle(), AFTER the entry decision:
entered = rec ; entered["_scan_candidate"] = c ; break     # trade already placed by enter_proactive_set
try:                                                       # COUNTERFACTUAL HARVEST (observational)
    import harvest_logger
    summary = harvest_logger.harvest_scan(params, executed_record=entered, mock=mock)
except Exception as e:
    print(f"harvest skipped (fail-open): ...")             # any failure is swallowed here
```

Guarantees:
- **Post-trade:** the order is placed inside `enter_proactive_set` *before* `harvest_scan` runs, so harvest work cannot delay or alter the order.
- **Fail-open:** the entire call is wrapped in `try/except`; any exception (including a total harvest crash) is caught and logged, and the cycle returns the trade record unchanged.
- **`enter_proactive_set` is untouched** by the harvester — no shared mutable state on the execution path.
- Proven empirically by `test_harvest_passivity.py` (Section 7): orders are byte-identical with harvest on, off, and crashing.

Sensors (`sandbox_v11_sensors.py`) follow the same "log, don't block" contract: every sensor fails open to `null` and never gates, filters, or sizes a trade.

---

## 4. THE GHA-TO-LOCAL TRANSPORT LOOP

The logger runs in GitHub Actions (ephemeral, no persistent disk); the database is local-only. The bridge is a committed daily inbox.

```
GHA cron (sandbox_scheduler.yml, checks out sandbox branch)
   run_scheduled_cycle -> harvest_scan
      -> appends rows to  data/harvest_inbox/candidates_YYYYMMDD.jsonl   (one JSON object per line)
      -> updates          data/harvest_state.json                        (per-day dedup + counters)
   "Persist forensic logs" step: git add -f data/harvest_inbox/*.jsonl data/harvest_state.json ; commit ; push -> v10-research-sandbox
                                   |
                                   v  (git)
Local Windows host: poller.py --once  (Task Scheduler)
   -> db.ingest_inbox()  reads every data/harvest_inbox/*.jsonl -> INSERT OR IGNORE into candidates (idempotent on candidate_id)
   -> polls open candidates, writes bid_path + labels into data/harvest.db (never committed)
```

The inbox JSONL is committed (it is the transport); the SQLite DB is gitignored. Ingest is idempotent on the `candidate_id` primary key, so re-ingesting a committed file is a no-op.

### Deduplication & sampling rules (`harvest_scan`, verified)

- **Tracking unit = per-contract-per-day.** State in `data/harvest_state.json` holds `contracts` (occ symbols already logged today) and `tickers` (ticker→payload already computed today). The full feature payload is computed **once upon first qualification** of a ticker that day and reused; a contract already logged today is skipped as `skipped_dup` (executions always log regardless).
- **Daily cap:** `harvest_daily_cap = 300` full-payload computations/day (a hard bound on API usage; incremented only when a *new* ticker payload is computed). On the first live day, 190 computations produced 503 full-payload rows — the cap did not bind. (The "~30–80/day" figure is not the configured cap.)
- **`sample_tier='topn'`:** the top **20** (`harvest_topn`) in-band contracts sorted by `rule_score` (= UW flow `total_premium`) get the full payload.
- **`sample_tier='random'`:** **5** (`harvest_random`) random contracts drawn from *below* the top-N cut (`in_band_rows[topn:]`), the mandatory blind-spot / misscore-detection sample.
- **Everything else:** in-band over the cap → cheap row `skip_reason='quota_cap'`; out-of-band → `skip_reason='prefilter'`. Both carry null features but are still pollable if they have a valid quote.
- **CURRENT LIMITATION:** because `harvest_topn` (20) is usually ≥ the in-band pool per cycle, `below` is empty and the random slice yields **0** rows in practice (0 observed on the first live day). The "mandatory" random sample is not yet actually guaranteed — see Known Gaps.

---

## 5. THE HARDENED SQLITE DATABASE LAYER

`data/harvest.db` — local-only, gitignored, never written inside GitHub Actions.

- **WAL mode** (`PRAGMA journal_mode=WAL`) + **`PRAGMA busy_timeout=30000`** + `synchronous=NORMAL`, so the separate logger-ingest and poller processes can share the file safely (30 s lock wait).
- **Rolling backups:** `backup(keep=14)` writes `data/harvest_backups/harvest_YYYYMMDD.db` via the online backup API and prunes to the last 14 dated copies.
- **Transport:** `data/harvest_inbox/*.jsonl` (committed) is the GHA→local bridge; `data/harvest.db` and `data/harvest_backups/` are gitignored.

### DDL (verbatim from `harvest_db.py` / live schema)

```sql
CREATE TABLE candidates (
    candidate_id TEXT PRIMARY KEY,
    run_id TEXT, code_version TEXT, feature_set_version TEXT, signal_ts_utc INTEGER,
    ticker TEXT, occ_symbol TEXT, expiry TEXT, strike REAL, "right" TEXT, side TEXT,
    bid REAL, ask REAL, bid_size REAL, ask_size REAL, mid REAL, spread_pct REAL, last REAL, underlying_last REAL,
    entry_ref REAL, features TEXT, rule_score REAL, executed INTEGER, skip_reason TEXT,
    vertical_barrier_ts INTEGER, barrier_up_pct REAL, barrier_down_pct REAL, poll_tier TEXT, sample_tier TEXT
);
CREATE TABLE bid_path (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT, poll_ts_utc INTEGER, bid REAL, ask REAL, quote_ts INTEGER, stale INTEGER,
    UNIQUE(candidate_id, poll_ts_utc)
);
CREATE TABLE labels (
    candidate_id TEXT PRIMARY KEY,
    outcome TEXT, label INTEGER, realized_return REAL, touch_ts_utc INTEGER, time_to_touch_min REAL,
    mfe REAL, mae REAL, n_polls INTEGER, n_stale INTEGER, ambiguous_touch INTEGER,
    poll_cadence_min REAL, censored_reason TEXT
);
CREATE INDEX idx_bidpath_cand ON bid_path(candidate_id);
CREATE INDEX idx_candidates_occ ON candidates(occ_symbol);
CREATE INDEX idx_candidates_signal ON candidates(signal_ts_utc);
```

Key constraints: `candidates.candidate_id` and `labels.candidate_id` are PKs (one immutable row / one label per candidate); `bid_path` is append-only with a `UNIQUE(candidate_id, poll_ts_utc)` guard making double-polls idempotent. `barrier_up_pct` / `barrier_down_pct` are stamped per row so historical labels stay self-describing if config changes.

---

## 6. PATH-DEPENDENT TRIPLE-BARRIER STATE MACHINE

`harvest_labeler.label_path(...)` — a pure function over the stored `bid_path`. Executable pricing, no mid-price fantasies:

- **Entry reference = Ask at signal time** (`entry_ref`, stamped on the candidate; never the mid).
- **Exit barriers evaluate strictly on the Bid.** `up_level = entry_ref * (1 + barrier_up_pct)` = **entry × 1.30**; `down_level = entry_ref * (1 + barrier_down_pct)` = **entry × 0.50** (`scanner_barrier_up = 0.30`, `scanner_barrier_down = -0.50`).
- **Vertical (time) barrier** = `min(last-session-of-the-signal-week 16:00 ET, expiry 16:00 ET)`. At the first poll with `poll_ts >= vertical_barrier_ts` and no prior touch, the outcome is a **signed vertical**: `label = +1 if realized_return > 0 else -1` (exactly zero → -1). First touch wins; barriers are checked before the vertical within a poll except the vertical is evaluated first by timestamp.

### Edge cases (verified in `label_path`)
- **Tie-breaker:** if a single poll registers both an up and a down touch (via its high/low), resolve **Down** with `ambiguous_touch = True` and `realized_return = down_pct` (−0.50). Conservative for a long-premium strategy.
- **`bid == 0` (fresh quote):** immediate full loss — outcome `down`, `label = -1`, `realized_return = -1.0`.
- **Missing / stale quote:** evaluation is skipped for that poll and `n_stale` is incremented; it never false-triggers a barrier. A candidate stale for a full session past its vertical is eventually **censored** (`label = null`, reason recorded) by the poller after a 24 h grace, and excluded from training.
- **Expires worthless at the vertical:** `realized_return = -1.0`, outcome `vertical`, `label = -1`.

### Vertical barrier — XNYS-calendar-aware (fixed 2026-07-02)
`_vertical_barrier_ts` resolves the vertical to the **last XNYS trading session of the signal week** at 16:00 ET — via `pandas_market_calendars` (memoized by week, with a Friday walk-back fallback if the lib is unavailable) — then takes `min(..., expiry 16:00 ET)`. Holiday-shortened weeks resolve correctly (the week of Fri 3 Jul 2026 → Thu 2 Jul). `pandas_market_calendars` is in `requirements-sandbox.txt` so GHA computes it too. The pre-fix "yesterday" cohort, whose barrier had already passed with no poll, was **censored** (see fallback below).

### Quote sourcing & fallback (poller)
Primary: batched **Alpaca** option NBBO (`OptionHistoricalDataClient.get_option_latest_quote`, chunk 100). Fallback: **Unusual Whales** flow-derived quotes (`_fetch_uw`). There is **no historical back-fill**: EODHD has no options-data access on the current key (401/403 verified), and the installed Alpaca client exposes no historical option quotes (`OptionQuotesRequest` absent). So a vertical that passed with no in-window poll is **censored** (label null) — never reconstructed from a trade price (bid-only discipline). The XNYS calendar also gates the poller's `_market_open_today()` holiday check.

---

## 7. THE COMPREHENSIVE TEST SUITE

All suites are on `v10-research-sandbox`; the MOT is offline and reproducible.

### Barrier labeler — 8/8 synthetic bid-path profiles (`test_harvest.py`)
1. Clean up-touch mid-week → `+1`, correct `touch_ts`.
2. Clean down-touch → `-1`.
3. Spike to +25% then bleed to −10% at the vertical → `-1`, `mfe ≈ +0.25`.
4. Vertical at +12% → `+1`, outcome `vertical`.
5. Both barriers crossed in one interval → `-1`, `ambiguous_touch = True`.
6. `bid = 0` fresh quote → down touch, `realized −1.0`.
7. Stale-quote run → no false trigger, `n_stale` correct, outcome stays `open`.
8. Expires worthless at the vertical → `realized −1.0`, outcome `vertical`.

### Passivity proof (`test_harvest_passivity.py`)
Proves the logger cannot alter or crash live execution: `run_scheduled_cycle` is driven with harvest **enabled**, **disabled**, and **raising an exception**, and the placed order is **byte-identical** in all three cases. Also asserts executed candidate rows == trades placed exactly.

### Supporting suites
- `test_harvest_harvester.py` — tiering, per-contract-per-day dedup, band filter, barrier-ts stamping, schema.
- `test_harvest_poller.py` — ingest, path accumulation, label resolution (up/down/stale), re-run idempotency.
- `v11_mot_harness.py` — full offline "MOT", **73/73** checks green (routing, exit/autopsy state machine, sizing floor, observability, sourcing filter + flush, edge sensors).

---

## KNOWN GAPS (open)

An honest anchor names what is broken. Full history in `reports/harvest_audit_2026-07-02.md`.

**Resolved 2026-07-02/03 (removed from this list):** the Friday-hardcoded vertical barrier (now XNYS-calendar-aware, Section 6); and orphaned positions not being exit-evaluated — all 72 broker positions were reconciled and now carry OPEN tracking records, so the exit engine manages every one.

Remaining:

1. **No server-side exit orders — and Alpaca cannot fully provide them on options.** Empirically tested 2026-07-02: Alpaca paper accepts `limit` / `stop` / `stop_limit` on options but **rejects OCO, bracket, and `trailing_stop`** ("complex orders not supported for options"). So exits stay cron-evaluated (scale-out / stop / trailing on the bid); the most that can be added server-side is an independent GTC-limit take-profit **plus** a stop-loss with manual sibling-cancel — not yet wired into the live loop. (Related bug fixed: a rejected close no longer marks a leg exited; it retries next cycle.)
2. **Poller does not `git pull`** — it ingests the *local* inbox only, so GHA-harvested candidates reach the local DB only when the repo is pulled. Fix: `git pull` at the start of `run_poller.bat`.
3. **Random sample yields 0** (Section 4) — `harvest_topn ≥` the in-band pool, so the "mandatory" 5 random rows never populate.
4. **Scheduled poller reliability** — Task Scheduler runs only when the host is awake; the poller had not fired on the audit day.

These are limitations of the current commit, not of the design; they are the top of the fix queue.
