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
   `day_trade` marker. MOT extended (Dimension 6, 26 checks incl. order-reconciliation). Accept: every
   open position carries a working broker-side floor at all times, and cron exits cancel resting
   siblings before closing.
   Also in this drop (2026-07-06 live-day audit, built): `flush_positions` now marks a record FLUSHED
   only when its broker close actually succeeded (the PFE orphan class is closed), and a give-up/PARK
   state stops per-cycle retry spam on zero-bid corpses (one alert, digest-visible, auto-resolves at
   expiry). One-per-underlying (dec 21) exempts orphaned/PARKED stragglers.
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
8. **Meta-labeling model — Student (Stage 2)** — QUEUED. The V10 rules engine stays primary; a
   gradient-boosted binary filter answers only "is this signal real?" on the harvested features. Feature
   clustering to kill redundancy, MDA importance under purged CV, SHAP on every prediction. Trained on
   full history with time-decay weights + regime features (no rolling-window amnesia). Gate: ~10–15k
   labeled rows. Accept: trained, calibrated, and evaluated only through items 5–7 (OOS Wilson lower bound
   on the calibrated hit rate exceeds the empirical hurdle; PBO below threshold; Deflated Sharpe positive
   with trials counted; beats the rules engine on the same purged splits).
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

## Scheduled decisions

- **Gating temperament** - decided at the first real calibration reliability curve (how aggressively the
  brain gates). Owner call.
- **Position cap + paper-parallel** - decided at the live-capital gate (item 14): the per-underlying and
  portfolio caps, and whether live runs in parallel with paper as a slippage control group (recommendation
  on record: yes, parallel).
- **Ceiling review** - per item 10's Ceiling Review gate; only the owner raises the brain's authority.
