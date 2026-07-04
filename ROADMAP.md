# ROADMAP

Status legend: SHIPPED · IN-FLIGHT · QUEUED. SYSTEM_ARCHITECTURE.md is ground truth for how the live
system works; this file is the forward plan and the pinned parameters that must not drift.

## Execution track (the live engine + harvest path)

1. **Single-engine consolidation (V9 retirement)** — SHIPPED 2026-07-04. One engine (V10) on one branch
   (main); V9 and its workflows removed; the two-engines-one-account collision closed.
2. **Server-side exit backstop** — QUEUED. An Alpaca-side GTC take-profit + stop as a backstop under the
   cron-evaluated exits (Alpaca rejects OCO/bracket/trailing on options - see SYSTEM_ARCHITECTURE Known
   Gaps). Cron reconciliation stays PRIMARY; resting siblings cancelled before the cron close.
3. **Slippage ledger** — QUEUED. Measured round-trip slippage per fill, replacing the EV cost-model
   placeholder (currently the per-row half-spread at signal time, GATE 2). This is the `ROADMAP item 3`
   the brain's cost model points at.
4. **Inbox retention prune** — QUEUED. Poller-side prune of committed inbox files older than 14 days,
   only after every candidate_id is confirmed in the DB and a newer off-box backup exists.

## Brain track (V12 - the isolated analytical layer, src/brain/)

The brain reads ONLY the nightly gzipped snapshots from the private harvest-snapshots repo; it never
touches the live harvest.db or the trading path. Two-way import isolation is asserted by
`test_brain.py::test_isolation`.

5. **Data Foundry (Stage 0)** — SHIPPED 2026-07-04. Loader (fetch → decompress → PRAGMA integrity_check
   → row counts) + `build_dataset()` (join candidates↔labels; exclude censored/open; executed & skipped
   kept together, distinguished by `executed` + `sample_tier`; per-row realized_return / time-to-
   resolution / MFE / MAE; payload expanded via an auto-generated feature dictionary; full provenance;
   quality gates - null-rate spike, zero-random-tier days, duplicate ids [hard-fail]) → versioned
   parquet + dataset card, deterministic, incrementally cached.
   Shipped hardening:
   - **GATE 1** - overlap weights via per-underlying average uniqueness (de Prado ch. 4). Concurrency is
     counted across intersecting windows on the same UNDERLYING (contract-level isolation forbidden);
     short-nested contracts weight down hard. Unit-tested (3d-inside-30d → 0.50 / 0.95; non-overlap → 1.0).
   - **GATE 4a** - incremental weight cache: a weight is FINAL once newest_signal_ts > window_end + one
     trading week; only unstable underlying groups recompute. Cache==full-recompute asserted.
6. **Truth Harness (Stage 1)** — SHIPPED 2026-07-04. Model-agnostic evaluation; first customer is the V10
   rules engine. PurgedKFold + embargo (leakage test: naive KFold inflated, purged near-chance - a build
   failure if it can't discriminate). CPCV documented (N=10, k=2 → C(10,2)=45 splits, k·C(N,k)/N=9 paths);
   PBO (CSCV) + Deflated Sharpe (trials as explicit input) - render N/A until CPCV row minimums are met.
   Weekly edge report on the rules engine with hard sample-size minimums → UNDERPOWERED below them.
   Automation: `brain_weekly.yml` (Sun 22:00 UTC + dispatch) → report to `reports/v12_weekly/` + one-line
   Telegram summary.
   Shipped hardening:
   - **GATE 2** - EV engine v2 (empirical, not binary): conditional return distributions by outcome class
     (up-touch / down-touch / vertical-±) capturing gap-throughs; EV(p) from empirical class means;
     thresholds with BOOTSTRAP CIs; expected shortfall of the loss tail (for Kelly). The closed-form
     binary breakeven (62.5% pre-cost) is kept ONLY as a sanity floor - empirical below it is a red flag.
   - **GATE 3** - adaptive calibration: Platt/sigmoid AND isotonic, fitted on OOF only, per model version;
     auto-select sigmoid < 1,000 OOF n else isotonic; Brier for both every run. (Idle until Stage 2.)
   - **GATE 4b** - compute guard: wall-clock / memory budget; degrade CPCV N 10→8→6 with a loud note
     rather than dying. Insurance, not a current constraint at this system's scale.
7. **Sequential edge test (SPRT)** — SHIPPED 2026-07-04. Wald SPRT on executed trades, evaluated weekly.
   **Pinned parameters (do not change quietly):**
   - H0: win rate = empirical hurdle (GATE 2 breakeven) + cost.
   - H1: win rate = empirical hurdle + **0.05** (a stated 5-percentage-point minimum edge).
   - alpha = **0.05**, beta = **0.20**.
   - Reported weekly as CONTINUE / REJECT (no edge) / ACCEPT (edge).

### Brain flywheel — QUEUED

- **Stage 2 - Student** (~10-15k labeled rows). LightGBM (or peer) on the Foundry dataset with GATE-1
  sample weights, purged-CV out-of-fold predictions, GATE-3 calibration. Acceptance: OOS Wilson lower
  bound on the calibrated hit rate exceeds the empirical hurdle; PBO below threshold; Deflated Sharpe
  positive with trials counted; beats the rules engine on the same purged splits.
- **Stage 3 - Council**. Diverse model ensemble + disagreement/abstention. Acceptance: council OOS edge
  ≥ best single student, with lower variance across CPCV paths and a usable abstain rate.
- **Stage 4 - Governor**. Lifecycle: shadow → gate → sizing. Champion/challenger promotion, and
  kill-switches (drift, drawdown, calibration decay). Acceptance: shadow tracks live for N weeks within
  tolerance before any sizing authority; kill-switches proven on injected faults.
- **Stage 5 - Flywheel**. Continuous retrain + monitoring loop feeding the weekly report. Acceptance: a
  hands-off weekly cycle (snapshot → retrain → evaluate → govern → report) with alerting, no manual step.
