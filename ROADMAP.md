# ROADMAP

> **Doc discipline (mirrored in CLAUDE.md):**
> - **SYSTEM_ARCHITECTURE.md** is strictly **PRESENT tense** — what the code does now; the code wins; it
>   never carries future intent.
> - **ROADMAP.md** is strictly **FUTURE tense** — every item carries a one-line acceptance criterion and a
>   status (QUEUED / IN-FLIGHT / SHIPPED / REJECTED); it never claims something already exists.
> - **Graduation rule:** when an item ships and its tests pass, the SAME commit flips it to SHIPPED here
>   and writes its reality into SYSTEM_ARCHITECTURE.md. No item is ever silently deleted — it closes as
>   SHIPPED or REJECTED with a one-line reason.
>
> Item numbers are stable IDs; the **Phase (A→D)** conveys priority. Two follow-up prompts (vision
> integration, owner-decisions integration) will amend this file — their placeholders are marked.
>
> **Design constraint (owner, 2026-07-05):** the Foundry and Truth Harness are signal-agnostic and must
> remain so — on a NO verdict from item 7, new signal sources plug into the same machinery. The strategy
> is replaceable; the truth machinery is not.

## Standing decisions

- **Alerting: every-event alerts stay ON** (owner's explicit preference, 2026-07-05) — a standing
  decision, not a task: entries, exits, autopsies, digests, and failures all push to the owner's phone.

## Foundation (shipped)

1. **Single-engine consolidation (V9 retirement)** — SHIPPED 2026-07-04. Accept: one engine (V10) on one
   branch (main), V9 and its workflows removed, the two-engines-one-account collision closed. Reality in
   SYSTEM_ARCHITECTURE.md.

## Phase A — complete the operating system (near-term)

2. **Server-side exit backstop** — IN-FLIGHT (built on the Tier B branch 2026-07-06; ships config-OFF,
   canary flips it on). Design pre-decided (owner decision): the resting broker-side order is ALWAYS a
   **stop**; only its level is dynamic (−50% at entry → break-even past the shield threshold → trailing
   levels), updated each cycle; the +30% scale-out stays cron-managed. **T0–T5 empirical results
   (2026-07-06, Alpaca paper):** T0 plain stop on options ACCEPTED; T1 stop_limit ACCEPTED; T2 GTC
   ACCEPTED (the backstop survives overnight); T3 PATCH-replace REJECTED on queued orders → the mechanic
   is cancel+resubmit; T4 closed-market submissions queue cleanly; **T5 decision: plain STOP** —
   affordable-band p90 spread 17.9% (< the 30% pre-stated threshold; executed-band median 0.99%), and a
   bad fill beats no fill per NORTH_STAR. Config: `backstop_enabled` / `backstop_canary_occ` /
   `backstop_type`. PDT: same-day stop fills are accepted by design and every one is logged as a
   `day_trade` marker. MOT extended (Dimension 6, 39 checks incl. order-reconciliation). Accept: every
   open position carries a working broker-side floor at all times, and cron exits cancel resting
   siblings before closing.
   Also in this drop (2026-07-06 live-day audit, built): `flush_positions` now marks a record FLUSHED
   only when its broker close actually succeeded (the PFE orphan class is closed), and a give-up/PARK
   state stops per-cycle retry spam on zero-bid corpses (one alert, digest-visible, auto-resolves at
   expiry). One-per-underlying (dec 21) exempts orphaned/PARKED stragglers.
   **2026-07-08 (canary lifecycle + session-review fixes, live on main 97cad722 / 39aae9eb):** the BAC
   canary validated arm + ratchet + cancel-before-close but closed before its stop ever fired, so
   stop-fill-and-reconcile is still un-exercised live → a fresh canary `QSR260821C00077500` (liquid,
   2026-08-21) now carries the machinery. Six review findings fixed: `_order_fill` gated on terminal
   status and a terminal PARTIAL is audit-only (`bs['partials']`, no phantom `~bs` leg_exit) — this
   kills the strand that would have blocked re-entry forever AND the stop-out double-count; the daily
   digest is shadow-aware (no longer claims entries were halted in shadow); the executed harvest row
   logs the REAL Alpaca spread (`execution_cost.bid_ask_spread_pct`), not the synthetic premium/limit
   gap (a ~0.99% constant); the VPS watchdog market gate is DST-correct (`poller._market_open_now`).
   Fleet-wide still gated on the full canary lifecycle.
2b. **Cycle-start broker-vs-record reconciliation** — SHIPPED (2026-07-07, `reconcile_orphans`).
   `proactive_sandbox_logs.json` is NOT union-merged (JSON can't be), so a rare double-push collision
   can drop a TRADE RECORD, leaving a live broker position with no OPEN tracking record — unmanaged by
   the exit engine AND invisible to one-per-underlying (which reads OPEN RECORDS, not raw positions).
   `reconcile_orphans` runs at cycle start (step 0, before the exit pass): it diffs `get_open_positions`
   against every record's leg OCCs and ADOPTS any unmatched position into a fresh reconstructed OPEN
   record (entry_ref = avg_entry_price), so the exit engine manages it and one-per-underlying blocks
   the underlying. PARKED / FLUSHED stragglers (known records) are left exempt. MOT Dimension 6 proves
   the before/after: a sub-cap orphan does not block until adopted. **Gates the backstop fleet-wide
   rollout** (with the canary lifecycle).
2c. **Notebook-vs-broker over-count sweep (stale OPEN + unconfirmed closes)** — QUEUED. The DUAL of 2b:
   2b adopts broker positions missing a record; 2c closes the OTHER drift — records the notebook holds
   OPEN/CLOSED that the broker does NOT reconcile with (diagnostic 2026-07-08: 36 OPEN records vs 26 live
   broker positions, delta ~10). Two classes. (a) STALE OPEN: an entry limit that never filled (the
   stale-order-cleanup cancels the order but leaves the record OPEN), and — pre-`one_position_per_underlying`
   — DUPLICATE records for a single filled position (confirmed case: two `SLV260807C00058000` records
   entered 40 min apart on 2026-07-06; the `-50%` stop fired and closed the real position via one record
   (`CLOSE_STOP_LOSS`, `closed_ok=true`), the sibling's own close then failed (`close_fails=1`) and it is
   stuck OPEN, both records sharing the one position's `mae_pct=-51.2` because the exit pass matches by OCC).
   (b) UNCONFIRMED CLOSE: records booked CLOSED with `closed_ok=false` (2026-07-08: 7 legs incl PFE −100%,
   TSLA, AMAT, IGV, JETS, HOOD) where the close order never confirmed, so the broker may still hold the
   position while the notebook shows CLOSED. Accept: a read-only broker-diff roll-call (cycle start or end)
   that, for every OPEN or `closed_ok=false` record with NO matching live position, marks it terminally
   reconciled (e.g. `RECONCILED_GONE`) so it stops blocking `one_position_per_underlying` and stops inflating
   the scoreboard; and for a `closed_ok=false` whose position DOES still exist, hands it back to the exit
   engine (or lets 2b re-adopt). Idempotent, passivity-safe, MOT-covered, changes NO entry selection —
   pure bookkeeping hygiene. Does not gate anything; run it before relying on the live scoreboard.
4. **Inbox retention pruning** — QUEUED. Poller deletes working-tree inbox files older than 14 days only
   after verifying every candidate_id is in the DB and a newer DB backup exists. (Verified not yet built:
   the `keep=14` prune in `harvest_db.backup()` prunes DB *backups*, not the inbox jsonl.) Accept: lean
   checkout, zero data loss.
4b. **NOT-NULL primary keys on the LIVE harvest.db** — QUEUED. The fresh-DB DDL gained
   `NOT NULL` on `candidates`/`labels` PKs (Tier B); the live VPS DB keeps the old DDL until a
   copy-rename rebuild (`integrity_check` before and after, outside market hours). Purely defensive:
   all writers assign uuid4 ids. Accept: live DDL matches `harvest_db._SCHEMA`, zero row loss.

## Phase B — enrich the dataset while it accumulates

3. **Slippage ledger** — QUEUED. Log intended price vs actual fill for every V10 execution into a
   queryable per-trade table; this replaces the EV engine's half-spread placeholder (the brain's
   `ev.cost_model` points at "ROADMAP item 3"; today `entry_slippage_pct` is always null). Accept:
   measured slippage feeding Gate-2 thresholds.
12. **Free orthogonal sensors** — IN-FLIGHT. Each wired into the harvest payload as fail-open, log-only,
    **never gating** (£0, versioned via `feature_set_version`). **Never EODHD.** Priority order (owner
    decision):
    - (1) **Earnings calendar** — the days-since-earnings SENSOR is **SHIPPED** (`post_earnings_drift`,
      log-only, commit `1abde178`); its LOAD-BEARING use, the **entries blackout**, is **QUEUED** and
      ships with the week-one Tier B drop (`earnings_blackout_days` is a dormant param, never enforced).
    - (2) **Regime pack** — VIX **level** is **SHIPPED** (`macro_context`, yfinance `^VIX`, commit
      `d2b02125`); VIX **term structure** (VIX vs VIX3M) is **QUEUED**.
    - (3) **SEC EDGAR full-text S-3 / ATM shelf flag** ("dilution capacity active") — QUEUED.
    - (4) **FINRA daily short-sale volume** — QUEUED.
    - then unranked: **IBKR public borrow-fee/availability** — QUEUED; **SEC fails-to-deliver** — QUEUED;
      **Nasdaq halts** — QUEUED.
    Accept per sensor: null-safe, never backfilled, passivity suite green after each addition.

## Phase C — the brain (V12 isolated analytical layer, `src/brain/`; gate: ~10–15k labeled rows)

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
   - **Weekly-report expected bands (QUEUED enhancement)** - render win rate, expectancy, equity curve,
     and monthly P&L EACH against its statistically expected band (from the fitted return distribution +
     current sample size), labeled NORMAL VARIANCE or DEGRADATION. Accept: no headline number ever
     appears without its band. (Not yet built - the shipped harness renders Wilson intervals + EV/SPRT.)
7. **Sequential edge test (SPRT)** — SHIPPED 2026-07-04. Wald SPRT on executed trades, evaluated weekly.
   **Pinned parameters (do not change quietly):**
   - H0: win rate = the empirical **cost-inclusive breakeven** (GATE 2) **+ a stated margin m = 0.02**.
     (NOT "breakeven + cost" - the breakeven already nets cost, so re-adding it double-counts.)
   - H1: win rate = **H0 + 0.05** (a stated 5-percentage-point minimum edge).
   - alpha = **0.05**, beta = **0.20**.
   - The SPRT **clock starts the trading day AFTER the week-one Tier B drop merges** (after Monday's
     Checkpoint 2). Executed trades before that date are warm-up, excluded from the SPRT; all harvested
     candidates remain in the learning corpus regardless.
   - **Stratified view is reporting only:** the pinned SPRT object is the POOLED executed stream; the
     report's hit rate by source premium (>=50k vs 25-50k) is insight, never a driver of the decision.
   - Reported weekly as CONTINUE / REJECT (no edge) / ACCEPT (edge).
8. **Meta-labeling model — Student (Stage 2)** — IN-FLIGHT (pipeline SHIPPED 2026-07-22:
   `src/brain/student.py` + `src/brain/run_student.py`; weekly `student` job in `brain_weekly.yml` →
   `reports/student/`). The V10 rules engine stays primary; a gradient-boosted binary filter answers
   only "is this signal real?" on the harvested features. Built as specified: correlation clustering
   kills redundancy; MDA under purged CV ranks features (per-prediction reasons are median-substitution
   attribution, honestly labeled — not SHAP, no free SHAP lib); trained on full history with time-decay
   (half-life 21d, pinned) × uniqueness weights + regime features. Selection policy: calibrated
   win-probability ≥ the empirical cost-inclusive hurdle. The four acceptance gates are mechanical in
   `student.acceptance` (OOS Wilson lower bound > hurdle; PBO ≤ 0.20 from the Student's own CPCV config
   grid — the "pending" path-performance PBO now computes; Deflated Sharpe > 0.5 with trials counted;
   beats the engine on the same purged splits). **Gate: 8,000 feature-bearing graded rows** (the
   effective-training-set refinement of the original ~10–15k labeled gate, per the 2026-07-16 readiness
   assessment) — below it every run renders PROVISIONAL and withholds the official verdict. Remaining
   to close this item: the first at-gate OFFICIAL run (expected ~2026-07-24) and its verdict.
8b. **Discovery rig (pre-Student search)** — SHIPPED 2026-07-21 (`src/brain/discovery.py`,
   `src/brain/convergence.py`, `src/brain/run_discovery.py`; weekly via `brain_weekly.yml` discovery
   job → `reports/discovery/`). A systematic, re-runnable search over the graded snapshot: per-feature
   verdict table (fill rate first, uniqueness-weighted band stats, EV at executable prices), a
   gradient-boosted meta-labeler + shallow readable-rule mining evaluated ONLY under purged/embargoed
   splits, a walk-forward dated replay with a trade-by-trade ledger, and the ten-angle Convergence
   Protocol (seeds / time slices / bands / learner / weighting / costs / labels / population / target
   / regime) judged by intersection — SURVIVORS >= 8/10, FLICKERS 4-7, MIRAGES <= 3, accreting across
   weeks in `convergence_state.json`. Every configuration, rule, and threshold is counted; the global
   trials count feeds PBO and the Deflated Sharpe; no winner is reported without its trials count.
   **Promotion rule (owner decision, on the record): a SURVIVOR whose out-of-sample lower confidence
   bound clears the cost-inclusive hurdle with PBO <= 0.20 across consecutive weekly runs becomes a
   SHADOW candidate for the Student pipeline (item 8) — never a live deployment from this rig.**
   scikit-learn added to `requirements-brain.txt` (brain-only dependency; isolation unchanged).
   Accept: weekly dated reports append; leakage caught by `test_brain.py` discovery tests; zero
   live-path changes.
9. **Ensemble abstention — Council (Stage 3)** — QUEUED. ~5 seed/window variants; disagreement above a set
   band = no trade regardless of mean probability. Accept: abstention rate and its P&L effect measured on
   paper.
10. **Champion/challenger MLOps — Governor (Stage 4)** — QUEUED. Weekly retrain of challengers; promotion
    only on predefined out-of-fold plus shadow criteria; kill-switches on feature drift (PSI), calibration
    drift, and drawdown that fall back to the frozen rules engine. Hyperparameters frozen, re-tuned at most
    quarterly under purged CV. Accept: fully automated weekly cycle with human-visible promotion reports.
    - **P(halt) calculator (gate):** before any live capital, compute and present the probability of a 30%
      drawdown from high-water under the fitted distribution at the proposed sizing; the owner signs off on
      the number in writing. Accept: the number and sign-off recorded in `reports/`.
    - **Ceiling Review (gate):** raising the brain's authority beyond gate-plus-sizing (toward originating
      trades) may only be RAISED after a predefined shadow record exists (minimum weeks and prediction
      count stated in advance), and only the owner may decide it. Until then the ceiling is gate + sizing.
      Accept: the predefined thresholds written here before Stage 4 ships.
11. **Probability-mapped sizing (Stage 4+)** — QUEUED. Fractional Kelly on the EMPIRICAL return
    distribution (Gate 2's expected shortfall, not binary assumptions), capped at the per-trade
    allocation, portfolio-level correlation awareness so simultaneous same-thesis candidates size as one
    bet. Accept: sizing driven by calibrated probabilities only after item 7 returns a go; deployed
    shadow → gate → sizing.
16. **Teaching block (Stage 1)** — QUEUED. Every weekly report ends with one concept explained through
    that week's actual rows (uniqueness weighting when overlaps first appear, calibration when the
    reliability curve first draws, PBO when CPCV first runs, and so on). Accept: present in every report;
    the concept rotates with what the data did.

## Phase D — later

13. **Engine off GitHub Actions onto the VPS** — QUEUED. GHA cron is best-effort; the VPS is not. (The
    engine runs on GHA today; the poller already runs on the VPS.) Accept: zero missed cycles over a test
    month.
14. **Live-capital gate** — QUEUED. Predefined, written criteria — edge verdict, slippage bounds, backstop
    reliability, drawdown limits — that must ALL pass before any real money. Accept: the criteria exist in
    this file long before they are tested. Staged amounts: **£1,000–5,000 initial** to prove survival,
    scaling beyond only on live evidence. Best-case calendar (informational): data critical mass
    ~mid-August 2026; Student trained + two-week shadow ~early September; gate-mode on paper through
    September; live-capital review ~early October. **BEST CASE — the gates decide the real dates.**
    Referenced by NORTH_STAR.md as "item 14". **Decide margin vs CASH account at this gate**: a cash
    account is exempt from PDT and may dissolve the 24h-hold constraint at the £1–5k stage (the 24h
    take-profit hold exists as deliberate PDT avoidance — see the decision table and the code comment at
    `min_hold_hours`).
15. **Barrier-configuration optimization** — QUEUED. Using the stored bid paths, executed only under item
    7's PBO discipline. Accept: any barrier change justified with overfitting-adjusted evidence.

## Item table

| # | Item | Phase | Status | Gate / acceptance (one line) |
|---|---|---|---|---|
| 1 | Single-engine consolidation (V9 retirement) | Foundation | SHIPPED | One engine on main; collision closed |
| 2 | Server-side exit backstop | A | IN-FLIGHT | Every open position carries a working broker-side floor; T0–T5 done, ships config-OFF, canary flips on |
| 3 | Slippage ledger | B | QUEUED | Measured slippage feeds Gate-2 thresholds |
| 4 | Inbox retention pruning | A | QUEUED | Lean checkout, zero data loss |
| 5 | Data Foundry (Stage 0) + GATE 1 / 4a | C | SHIPPED | Versioned parquet + card; overlap weights + cache tested |
| 6 | Truth Harness (Stage 1) + GATE 2 / 3 / 4b | C | SHIPPED | Purged-CV leakage caught; EV/calibration/guard shipped; weekly-report bands QUEUED |
| 7 | Sequential edge test (SPRT) | C | SHIPPED | Weekly CONTINUE/REJECT/ACCEPT; params pinned (H0=breakeven+0.02) |
| 8 | Meta-labeling — Student (Stage 2) | C | QUEUED | Gate ~10–15k rows; beats rules engine via items 5–7 |
| 9 | Ensemble abstention — Council (Stage 3) | C | QUEUED | Abstention rate + P&L effect measured on paper |
| 10 | Champion/challenger MLOps — Governor (Stage 4) | C | QUEUED | Automated weekly cycle + kill-switches; P(halt) & Ceiling-Review gates |
| 11 | Probability-mapped Kelly sizing (Stage 4+) | C | QUEUED | Calibrated-prob sizing only after item 7 go; shadow→gate→size |
| 12 | Free orthogonal sensors | B | IN-FLIGHT | earnings-drift + VIX-level SHIPPED; blackout/term-struct/S-3/FINRA/IBKR/FTD/halts QUEUED |
| 13 | Engine off GitHub Actions onto the VPS | D | QUEUED | Zero missed cycles over a test month |
| 14 | Live-capital gate | D | QUEUED | £1–5k initial staged; criteria pass before real money; best-case live review ~early Oct (gates decide); NORTH_STAR "item 14" |
| 15 | Barrier-configuration optimization | D | QUEUED | Barrier changes justified under item-7 PBO discipline |
| 16 | Teaching block (Stage 1) | C | QUEUED | Every weekly report explains one concept via that week's rows |


## Standing owner decisions (2026-07-05)

One line per decision. The charter-level essence of these is mirrored in NORTH_STAR.md; if the two ever
disagree, NORTH_STAR wins on values and this table wins on configuration. (32 decisions; the freeze scope
and SPRT clock are decisions 14/27.)

| # | Area | Decision | Where it lives |
|---|---|---|---|
| 1 | Purpose | Income engine to fund freedom; truth first, profit as consequence | NORTH_STAR Mission + vision |
| 2 | Strategy | Iterate on a NO verdict - the harness stays and hunts new signals | ROADMAP header constraint + item 7 |
| 3 | Strategy | V10-only; one strategy perfected, not a platform | NORTH_STAR non-goals |
| 4 | Money | £1-5k initial live capital to prove survival | NORTH_STAR risk + item 14 |
| 5 | Risk | 30% drawdown auto-halt, with the P(halt) proviso | NORTH_STAR risk + item 10 |
| 6 | Sizing | Aggressive fractional Kelly (half-Kelly+) only via the Governor | NORTH_STAR risk + item 11 |
| 7 | Owner | 5+ hours/week, active co-development | NORTH_STAR owner's part |
| 8 | Brain | Authority ceiling rises only by track record (Ceiling Review gate) | item 10 |
| 9 | Ops | Every-event alerts stay ON | ROADMAP standing decisions |
| 10 | Money | 3-month best-case calendar; gates decide the real dates | item 14 |
| 11 | Owner | Judge the four numbers against expected bands, never feel | NORTH_STAR owner's part + item 6 |
| 12 | Brain | Deep teaching - one concept per weekly report | item 16 |
| 13 | Risk | Unbounded positions for now (revisit at the live gate) | scheduled decisions |
| 14 | Engine | Volume push: cool-off 24h->4h + scanner_min_premium 50k->25k | v10_tunable_parameters.json (Tier A, SHIPPED) |
| 15 | Entry | Earnings blackout: no new entry within 3 days of earnings | item 12 (Tier B) |
| 16 | Exits | Keep the current exit design (state machine) | Phase C exits |
| 16b | Exits | WHY the 24h take-profit hold: deliberate PDT avoidance for the sub-$25k live future, NOT a quirk - changing it requires a NORTH_STAR amendment; backstop same-day stop fills are the accepted, logged exception; margin-vs-CASH decided at item 14 | v10_params min_hold_hours comment + item 14 |
| 17 | Exits | Theta-cliff study decides time exits | scheduled studies |
| 18 | Exits | Hold over weekends | scheduled studies (weekend cost) |
| 19 | Risk | Daily brake (3 stop-outs / loss >= 2x alloc): SHADOW during paper accumulation (evaluates + logs, does NOT suppress entries; would-have-blocked trades tagged `brake_shadow` and measured), ACTIVE only at the live-capital gate proven by that shadow data; eventual form may be a learned Governor rule | `brake_mode` param (shadow now) + item 14 (active) + NORTH_STAR risk |
| 20 | Exits | Ratchet backstop: always a stop, dynamic level | item 2 (Tier B) |
| 21 | Engine | One position per underlying (hard block) | Tier B |
| 22 | Data | Adaptive harvest cap with poller reservation | Tier B |
| 23 | Data | Random blind-spot sample to 10/day | Tier B |
| 24 | Data | Sensor order: earnings -> regime -> EDGAR dilution -> FINRA | item 12 |
| 25 | Brain | Gating temperament decided at the first calibration curve | scheduled decisions |
| 26 | Brain | Eager-within-gates promotion | item 10 |
| 27 | Ops | The freeze: Tier A tonight, Tier B one drop after Monday, 6 weeks solid | items 7 + 27 scope |
| 28 | Ops | 30-minute watchdog, cross-watching (VPS + healthchecks.io) | Tier B |
| 29 | Spend | Spend case-by-case; the math comes to the owner every time | NORTH_STAR principle 7 |
| 30 | Money | Paper-vs-live decided at the live gate (rec: parallel, paper as slippage control) | scheduled decisions |
| 31 | Money | Reinvest everything until further notice | NORTH_STAR + item 14 |
| 32 | Money | Alpaca into live; evidence is final | item 14 |
| 33 | Engine | Dead knobs `min_rvol` + `min_flow_dominance_pct` REMOVED 2026-07-08 (read by nothing; never gated anything). Do NOT restore. `max_bid_ask_spread_pct` kept but is advisory-only, not a gate. `should_enter_proactive()` (a no-op that always returned True) deleted the same day. | v10_params / v10_tunable_parameters (hygiene, behavior-identical) |

## Scheduled studies (week 6, from stored bid paths + counterfactual labels)

| Study | Question | Data source | Decision it settles |
|---|---|---|---|
| Theta-cliff | Do the final ~2 days of hold add or destroy value? | stored bid_path of held positions | whether to add a time-based exit (dec 17) |
| Weekend cost | Friday-hold -> Monday-gap return distribution? | labels of positions held over a weekend | whether to keep holding weekends (dec 18) |
| Brake cost | What would the brake-blocked trades have returned vs the allowed ones? | the `brake_shadow`-tagged executed trades (shadow mode logs them live) vs the rest, in the weekly report | whether/how to arm the brake ACTIVE at the live gate (dec 19) |
| Pyramiding value | Do same-ticker re-fires carry edge worth a 2nd position? | counterfactual labels of one-per-underlying skips | whether to relax one-per-underlying (dec 21) |

## Strategy question list (measure-first; no gate on suspicion)

- **Q: Do trades on over-priced options (high IV rank at entry) lose more?**
  Method: compare piles + the weekly report's IV-rank split (cheap<33 / normal 33-67 / expensive>=67).
  Gate: preliminary weekly now; decision-grade at ~150 completed executed / ~5k graded.
  Tripwire: only a severe, well-sampled band underperformance is harness evidence for ONE entry-gate
  change, done once, with the SPRT/params clock noted. Preliminary (2026-07-07, UNDERPOWERED): NOT
  supported - expensive-IV candidates hit the up-barrier slightly *more* often; returns don't worsen with IV.
- **Q: Do wide-spread contracts underperform after real costs?**
  Method: same, plus the fill-vs-intention (slippage) ledger, item 3.
  Gate + tripwire: same as above. Preliminary (2026-07-07, UNDERPOWERED): supported in the counterfactual
  (wide-spread candidates win 21% vs 34% tight, non-overlapping CIs, worse mean return) - BUT every executed
  trade so far is tight-spread (<2%), so the engine may already dodge the bleed via fill mechanics; the
  executed bleed is unconfirmed until the slippage ledger and more executed rows exist.

- **Q: Would a FIXED-HOLD option horizon (3 and 5 trading days, no barriers) label the same candidates
  differently — and does any measured feature separate winners from losers better under that label?**
  Method: PROSPECTIVE ONLY — feasibility (2026-07-25) showed stored paths cover just 1.6% at 3td / 0%
  at 5td because polling stops at label resolution (median ~1 day). Requires the poller to keep polling
  past resolution to signal+5td: a governed change (API budget from the existing adaptive cap; queued
  for a Sunday boundary, owner go). Columns land as additive nullable measurement fields
  (fixed_hold_3d_ret, fixed_hold_5d_ret), never decision inputs.
  Evidence gate: >= 10k rows carrying prospective fixed-hold values.
  Pre-registered tripwire (written 2026-07-25, before any value exists): a feature separation under
  this label counts as evidence ONLY at OOS lift >= 1.5 with n_eff >= 15, campaign PBO <= 0.20, and
  survival >= 8/10 convergence angles in 2 consecutive weekly rig runs — and may then propose at most
  ONE governed label-definition trial for the Student. Never a live-path change from this question.
- **Q: Does the flow predict the UNDERLYING STOCK 1/3/5 trading days out, even where the option loses
  to costs?** (The pivot rule's designated escape route, measured early.)
  Method: free daily closes (yfinance locally; Alpaca on the VPS as fallback), return signed by flow
  direction (call = long, put = short), computed on the snapshot as additive nullable measurement
  columns (stock_1d/3d/5d_signed_ret); analyzed ONLY through the rig - uniqueness weights mandatory,
  purged evaluation, every configuration counted, PBO reported with every number.
  Evidence gate: >= 80% coverage of graded candidates; >= 5k weighted rows per horizon.
  Pre-registered tripwire (written 2026-07-25, before any value is computed): stock-horizon
  predictability counts ONLY if, in 2 consecutive weekly rig runs, the uniqueness-weighted mean signed
  return's 95% lower bound is > 0 AND the direction hit rate's lower bound is > 52% on the evidence
  gate's sample, with campaign PBO <= 0.20. Meeting it unlocks the PIVOT-RULE measurement discussion
  (owner decision); it never changes the engine, the Student's labels, or any decision path.

- **Q: Does FLOW PERSISTENCE — repeat flow on the same name, which the engine's current read ignores
  entirely — add tradeable value over the existing 82 features?**
  Method: nine CAUSAL persistence features (prior-signal counts at 1d/3d, hours since the last signal
  on that ticker, same-direction repeat count, direction agreement, and expanding-window within-day
  rank/share — all computed from prior rows only). Tested head-to-head THROUGH THE HARNESS: the same
  Student, same seed, same PurgedKFold splits, trained with and without them; compared on out-of-fold
  selection hit rate, net return after executable costs, and the Wilson lower bound against the
  empirical hurdle; PBO and deflated Sharpe on the variant; every configuration counted as a trial.
  Provenance note: an earlier non-causal version of these features (whole-day aggregates that counted
  signals arriving after the decision point) produced a 0.465 separation on 2026-07-25 — that figure
  is void and is not evidence for anything.
  Evidence gate: the existing 8,000 feature-bearing row gate; no separate minimum.
  Pre-registered tripwire (written 2026-07-26, before the head-to-head was computed): persistence
  counts as a real improvement ONLY if, on identical purged splits, adding it (a) raises the OOF
  selection's uniqueness-weighted net return, AND (b) raises the selection hit rate's 95% Wilson lower
  bound, AND (c) does not worsen PBO beyond 0.20 — and (d) the same three hold on a second consecutive
  weekly run. Meeting all four promotes it to a Student feature-set change, which is itself a governed
  change at a Sunday boundary. Anything less is logged as measured-and-rejected; a higher raw
  separation on its own is explicitly NOT sufficient.
  **ANSWERED 2026-07-26: REJECTED.** Run 1 passed (a)-(c) on the 07-24 snapshot (net −0.079 → +0.193,
  Wilson lo 0.323 → 0.436, PBO 0.232 → 0.130). A vintage sweep over five nested snapshots then found
  the advantage present in ONE of five — the newest — absent or reversed in the rest, with the
  selection count running 0/4/1/3/54 across the sequence: one extra trading day multiplied the trade
  count eighteen-fold. Fragility of that kind is a threshold on the edge of a noisy distribution, not
  an effect. The result also never cleared the acceptance gates it would ultimately face (Wilson lo
  0.436 vs the 0.594 hurdle). Closed as measured-and-rejected; persistence does not enter the
  Student's feature set. Full record: reports/research/persistence_harness_2026-07-26.md.

## The pivot rule (pre-registered 2026-07-25; draft pending owner ratification)

The machinery outlives any single signal (NORTH_STAR). The current flow signal is declared MINED OUT
— and the owner pivot conversation opens — only when ALL three hold together, on matured data
(>= 8,000 feature-bearing rows):
  1. the Student is REJECTED for 6 consecutive weekly runs;
  2. no discovery survivor has reached the Governor's SHADOW_PROVEN rung; and
  3. the stock-horizon escape route has failed its tripwire for 2 consecutive runs.
Meeting all three does not pivot anything automatically — it opens a decision (different structures,
or a different signal source) made calmly on evidence, with the harness kept intact. Falling short on
any one keeps the current course. Written before the outcome so a run of bad weeks cannot rush it and
a lucky week cannot mask it. Ratification is the owner's; until then this is the standing draft the
weekly reports measure against. Canonical constants live in LIVE_GATE.md.

## Anti-overengineering (spec freeze, addendum Section 4)

The school blueprint is CLOSED as of 2026-07-23. No new decision organ is built without a MEASURED
failure or gap as its birth certificate (a dated line in an audit or report). Parameters are born
wide and tightened only by the harness at Sunday boundaries — hand-tuning is prohibited. Every future
proposal passes a simplicity test: does a number already in the reports justify it? If not, it waits.

## Scheduled decisions

- **Dark-pool sensor hardening — Sunday 2026-08-02 boundary (governed; birth certificate:
  source_hunt_2026-07-27.md machinery finding #1).** Finding refined 2026-07-28: there is NO
  explicit payload ration — every full payload calls `darkpool_node`, and the 35% coverage is the
  UW darkpool endpoint failing/rate-limiting inside `_safe` (~65% of calls). Spec: add 429-aware
  retry-with-backoff (2 retries) inside `darkpool_node` + lengthen the UW client's darkpool cache
  TTL; expected coverage 35% → ~80%+; cost ≤ 2 extra API calls per failing sensor call, inside
  existing UW limits, £0. Harvest-side change → passivity battery mandatory. NOT deployed until the
  owner's go at the boundary.
- **Weekly-report expected-bands view (queued item 6) + shadow feature-attribution + inbox
  retention — staged, need design/decision.** Bands: how NORMAL-VARIANCE vs DEGRADATION bands are
  drawn around the four owner numbers deserves a considered design, not a 1am one — proposal at the
  boundary. Attribution: SHAP-free "extreme-decile" per-TAKE attribution proposed (£0); confirm
  approach. Inbox retention (item 4): pruning committed jsonl >14 days touches the transport — needs
  an explicit owner ok.
- **Premium lane activation — Sunday 2026-08-02 boundary.** The one-line ask: approve the
  MEASUREMENT_PREMIUM lane (defined-risk short put verticals, mleg-atomic, 1/day, 2 concurrent, $800
  total risk cap, firewalled from all gate evidence) to start Monday 2026-08-03 — yes or no. Spec:
  reports/strategy/PREMIUM_LANE_SPEC_2026-07-28.md (pressure-tested draft; kill conditions
  pre-registered; a low-VIX pass stays provisional until the lane has held through VIX > 25). If
  approved: activation is a counted trial and the flag flips in one commit. Nothing activates
  without the owner's explicit yes.
- **Multi-account strategy tournament — Sunday 2026-08-02 boundary (owner directive 2026-08-01:
  "all of them").** Six methods — V10 control (frozen), premium lane, pure XSP put-write,
  school-gated V10, Lessons Engine, momentum shares — each with pre-registered success/kill bars,
  all six logged as lifetime trials at activation, winner-by-leaderboard explicitly banned (each
  method passes or fails its OWN bar at its OWN sample floor). Alpaca's per-login paper-account
  cap CONFIRMED at 3 (2026-08-01; the two new accounts exist), so the books consolidate by risk
  type: control alone / short-premium account (lane + put-write) / flow-lab account (school-gate
  + lessons-engine + momentum), with pre-registered same-OCC collision rules and
  namespace-scoped quarantine-not-adopt reconcile. Spec:
  reports/strategy/ACCOUNT_TOURNAMENT_SPEC_2026-08-01.md. Remaining owner step: two key pairs
  via the hidden-input pattern. Accept: routing layer ships
  config-OFF per account with MOT off-state proof; activations one per day, each a counted trial.
  The premium-lane decision above folds into this as account 2 if the tournament is approved.

- **Gating temperament** - decided at the first real calibration reliability curve (how aggressively the
  brain gates). Owner call.
- **Position cap + paper-parallel** - decided at the live-capital gate (item 14): the per-underlying and
  portfolio caps, and whether live runs in parallel with paper as a slippage control group (recommendation
  on record: yes, parallel).
- **Ceiling review** - per item 10's Ceiling Review gate; only the owner raises the brain's authority.
