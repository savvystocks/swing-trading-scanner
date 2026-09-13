# STUDENT CHEAP-PICK PATH - DESIGN FOR PANEL (2026-09-12, Saturday 09:30 BST)

Owner ruling 2026-09-12 ~09:25: "Build the cheap-pick path, A live on it." Standing rules: cap stays
$1,000 per trade (NORTH_STAR v1.7); no picker goes live without the owner's word (given, for A only);
entry-path changes get the adversarial six checks and a panel before code; court judges STUDENT_FAMILY
on trading days (ROADMAP decision 37).

## 1. Why (evidence, honestly graded)

reports/research/student_spread_2026-09-12.md (guarded run):
- Picker A = EXPRET/ALL/BASE/k3, trained and thresholded on ALL candidates, three picks a week.
  Holdout (touched once, 2026-03-01 onward): +49.9%/trade, weekly t 2.20, all regimes positive - on
  contracts the cap cannot buy (median pricey pick $24-644).
- A's picks whose ask fits the cap (<= $10.00), taken exactly as A ranked them among ALL candidates,
  at engine sizing (lots = $1,000 / cost): search window +24.7%/trade, weekly t 1.19, halves +75/+658
  (30 trades, 20 weeks); holdout +52.1%/trade, t 1.46, halves +172/+1594 (24 trades, 14 weeks); ~1.5
  trades a week. Holdout cap-rule row with the single best trade removed: +24.1%/trade, t 2.18.
- The $4.00-9.90 band inside the same cap LOSES (-10.9%/trade, t -1.95, Thursday's test). A's
  cap-fitting edge sits in sub-$1 contracts, mostly 1-7 DTE weeklies, both sides (puts included).
- Refilling three picks a week from cap-fitting candidates only is weaker (holdout +25.0 t 1.25):
  A's conviction against the pricey field is part of the signal, so the seat must SCORE the whole
  field and EXECUTE only what fits.
- Grade: suggestive, consistent sign in both windows, not court-grade (t < 1.8 each), bear n~2. The
  live court on trading days is the test. The cheap-pick slice was identified after the spread
  study's first pass - it is a post-hoc slice of a pre-registered rule, disclosed as such.
- The spread variant is REJECTED (same report). The "$1,600 seat" amendment is WITHDRAWN: none of
  A's expensive holdout picks cost under $16.

## 2. The defect this also fixes (BREAKDOWNS entry to be written in the same commit)

The live STUDENT seat scores `_PRICEY_CANDS[:14]` - the dip strategies' side-pool: CALLS only, ask
$4.00-9.00, premium 50-400k, DTE >= 7. A live today would trade exactly the band where it loses, and
the passive score log since 2026-09-11 has measured that band, not A's evidence. Design defect
(mine, 2026-09-11), zero trades affected.

## 3. Changes

### 3a. Student pool (engine, the UW-rows loop in scan_candidates)
New per-cycle global `_STUDENT_CANDS`, built at CONTRACT level from the same alert rows with the
archive universe A was trained on (probe_tuner build_rows + hourly_library):
- both sides (call and put); non-index roots (existing index_roots exclusion);
- per-alert total_premium 50,000-1,000,000;
- ask-side aggressor: total_ask_side_prem > total_bid_side_prem;
- NBBO at the alert: bid > 0, ask > 0, (ask - bid) / ask <= 2%;
- ask >= 0.30 (the archive floor); NO upper bound - the picker scores the whole field;
- DTE >= 1 (calendar days to expiry; same-day expiry excluded). The archive's own floor was implicit
  (a row needs >= 3 hourly bars on later sessions), i.e. the contract trades the next session;
- keyed by occ (contract identity); largest-premium alert per occ wins; pool capped at the top 30 by
  premium (bounds live quote calls to 30 per cycle); the cap binding is printed;
- entries carry the fields the ranker needs (ticker, flow_type = side, total_premium,
  underlying_price, occ, expiry, strike, alert_ask, alert_bid, the "alert" block with first_seen).
The pricey pool (`aggx` / `_PRICEY_CANDS`) is unchanged for DIP_CONF_MILD and BULL_DIP_X.

### 3b. Seat (the STUDENT branch of the probe loop)
- ranks `_STUDENT_CANDS` (not `_PRICEY_CANDS[:14]`); ranked tuples gain the live ask:
  (score, model, cand, vec, ask).
- a pure helper `_student_select(ranked, exec_max_ask, open_tk)` returns [(pick, action)] with action
  in {"enter", "unaffordable", "open_ticker"}: ask <= exec_max_ask -> enter; ask > exec_max_ask ->
  logged as picked_unaffordable and the picker's weekly budget is CONSUMED (faithful to the study,
  where the three weekly picks were spent on all picks and only the cheap ones traded); an
  underlying already open -> skipped, no budget spent.
- entry via `_PROBE_CONTRACT` (buys the trigger contract) at engine sizing:
  contracts = LEG_BUDGET // (ask * 100), at least 1. Put triggers must be supported by build_legs'
  trigger-contract branch (verify - the pricey pool has only ever sent calls).
- weekly budget: `_student_week_used(name, log)` counts the picker's fills this ISO week (book) PLUS
  its budget-consuming unaffordable picks this ISO week from the passive score log
  (rows with budget_consumed true; the file is persisted by v10_lab.yml every cycle).
- score-log rows gain ask_live, affordable, budget_consumed.
- unchanged: one seat, one entry per cycle, two probes per cycle, bear stand-down (spec, true),
  fail-closed model/quote/vector handling, per-picker names on records (probe_strategy = STUDENT_x),
  per_strategy_max_per_day 8, one-per-underlying and one-record-per-contract guards, PENDING-intent.

### 3c. Export (scripts/student_export.py)
- STUDENT_A.threshold_cohort = "ALL": thresholds from the ALL out-of-sample stream's last 60 sessions
  (k1..k3), exactly the study's calibration.
- new per-picker `exec_max_ask` (spec, default 10.0): the walk-forward picks (pick_weekly on the
  threshold cohort) are EVALUATED on the executed slice only (entry <= exec_max_ask) at engine sizing
  in dollars -> `walk_forward_executed_slice` {trades, weeks, per_trade, win, wk_t, pos_weeks, total,
  share_executed}. The auto-pull rule (wk_t <= -1.5 with n >= 40) applies to THIS slice - what the
  picker actually trades. `walk_forward_on_threshold_cohort` stays (now the ALL slice).
- cohort_mask gains "CAP1000" (0.30-9.90); unknown cohorts still raise.
- re-export stamps probe.tuning.STUDENT_A.applied = today (court clock restart; A has no fills).

### 3d. Spec (VPS-live copy only)
probe.student.pool = {sides: [call, put], ask_min: 0.30, prem_min: 50000, prem_max: 1000000,
spread_max_pct: 2.0, dte_min: 1, max_pool: 30}; probe.student.exec_max_ask = 10.0;
probe.student.budget_counts_unaffordable = true; STUDENT_A: threshold_cohort "ALL", live true (owner's
word 2026-09-12), pulled per the export's executed-slice rule; B/D/E/F shadow, C pulled, unchanged.

### 3e. Harness
- MOT 6.16: seat ranks `_STUDENT_CANDS`; pool filters (sides, DTE >= 1, premium band, spread, ask
  floor, occ key, max_pool); `_student_select` functional (cheap put -> enter, pricey call ->
  unaffordable + budget consumed, open ticker -> skipped); `_student_week_used` counts consumed rows;
  export writes `walk_forward_executed_slice` and the pull rule reads it; spec: A live only if not
  pulled; STUDENT_FAMILY on priority; the passive score log untouched by the MOT (6.15).
- regime drill: scenario 6 pool gains a cheap put and a pricey call; scenario 7 exercises
  `_student_select` and a put trigger through enter_proactive_set (dry run).
- docs: SYSTEM_ARCHITECTURE student paragraph; ROADMAP decision 38; BREAKDOWNS entry 4.

## 4. My six checks (adversarial architect)
1. Edge: none new - A's own walk-forward restricted to what the cap allows. Suggestive, not proven.
2. Fat tail: cheap weeklies at 20-30 lots lose -50% (stop) or -100% (expiry) often; the mean rides
   rare +150-700% trades (SMCI +734%); expect long losing runs; max loss per trade = the $1,000 lot.
3. Frictions: 2% spread gate on a $0.40 contract means a one-cent market; many cheap names fail it
   live (the archive applied the same gate at the alert NBBO, so the universe is consistent); 20-30
   lot fills on weeklies with >= $50k premium that day are plausible but partial fills are likely;
   exits are market sells at the bid - the archive's bid haircut (~2%) may understate live slippage
   on cheap contracts.
4. Data honesty: post-hoc slice of a pre-registered rule; threshold cohort changed AFFORD -> ALL
   after seeing data (disclosed); the court on days is the test; the DTE >= 1 floor is looser than
   the pricey pool's 7 and matches the archive.
5. Dead weight: the seat's pricey-pool wiring and A's AFFORD threshold cohort are retired.
6. Unknowns: put triggers through build_legs; alert `price`/NBBO fields for puts; 1-DTE lots expiring
   inside a blind window (Friday's 55-minute gate outage class) - the exit engine runs every 10 min
   the next session and backstops arm then, but a blind window on expiry day means the lot can
   expire at its max loss; index-root exclusion keeps SPY/QQQ/TLT (ETFs) in - as the archive did.

## 5. Questions for the panel
Q1 DTE >= 1 vs the 2026-09-01 panel's DTE >= 7 for the pricey pool: is a 1-6 DTE cheap lot acceptable
   on a paper probe given the exit engine's cadence and the backstop timing?
Q2 Budget consumption by unaffordable picks: faithful to the evidence, or should the seat refill?
Q3 Any look-ahead in the live as-of vector for cheap contracts vs the archive (first_seen, cum_prem,
   ask_share from the alert block)?
Q4 Put support through the trigger-contract entry path.
Q5 Anything that would make the live executed-slice evidence NOT comparable to the study.
