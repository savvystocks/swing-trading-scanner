# CAPABILITY DIAGNOSTIC — what is missing to find an edge faster? — 2026-07-28

Planning report (Lane A). No builds; spec freeze holds; £0-first throughout. Known findings
(operational fixes, machinery weaknesses, seven closed games) are NOT re-listed — everything below
is new ground.

## 1. The binding constraint

**Regime coverage of option-priced outcomes.** One number proves it: the insider study on a 7-week
window read "promising" (+2.05%, both halves positive); the SAME study on 5 months read "sign-flip,
killed." Our option pile — the basis of every structure, cost, and selection conclusion — is 3
weeks old, one calm regime, and CANNOT be given that 5-month check at any price we're allowed to
pay: deep historical option quotes are the classically expensive dataset (OptionMetrics-class, four
figures a year). Everything else is demonstrably not binding: throughput ran ~10 studies in 3 days;
statistical power is purchasable for free on stock-horizon questions (7,000 independent 8-K events
in one evening); execution realism is closing itself via the fill ledger; volume grows 500 rows/day
without help. The bottleneck is that our option conclusions cannot yet see a second regime — and
only time or a workaround moves it.

## 2. Capability gaps vs a serious edge-finding shop

| dimension | status | does lacking it SLOW edge-finding? | cheapest close |
|---|---|---|---|
| deep historical OPTION data | **LACK** | YES — the binding constraint above | can't buy (£0 rule); three workarounds: archive our own chains from now (UW `option_chains`, already paid for), import free CBOE index-vol history (PUT/BXM/VIX back decades) for the premium question, re-base questions onto stocks where possible |
| deep stock/index history | HAVE (yfinance, proven at 5 months × 3,800 tickers) | — | — |
| event feeds | PARTIAL → closing (insider/congress/analyst opened this week; EDGAR proven) | mildly | the two fixed-window feeds (congress 199 rows, analyst ~4 days) are LOSSY — every unarchived day is unrecoverable |
| regimes observed | LACK for options; HAVE for stocks/vol via free indices (2008/2020/2022 all visible in VIX/PUT index history) | YES | import the free history; wait for our own |
| experiment throughput | HAVE (10 studies/3 days demonstrated) | no | — |
| statistical machinery | HAVE (CSCV/DSR/pre-registration — above amateur grade) | no | — |
| structures reachable | PARTIAL (options level 3: spreads yes; naked/futures/VIX derivs no) | no — defined-risk spreads are the sane frontier anyway | XSP already under evaluation |
| execution realism | PARTIAL → closing (ledger live, assignment probe live) | shrinking weekly | in motion |
| systematic literature ingestion | PARTIAL (ad hoc) | nice-to-have, not binding | occasional deep-research passes |
| intraday/tick data | LACK | no — latency games are a NORTH_STAR non-goal | none needed |

## 3. Blind spots — assumptions never tested

1. **Universe conditioning (the pond itself).** Every option row exists because UW's scanner
   flagged unusual flow. Untested: whether flow-flagged names are systematically DIFFERENT terrain
   (elevated realized vol, crowded, premium already stripped) — i.e. whether any within-universe
   search could ever have worked. Test: flow-flagged vs matched non-flagged controls on
   RV/VRP/forward drift, yfinance, one evening, £0.
2. **Target definition (direction vs magnitude).** Every label we've ever made scores DIRECTION.
   The Student's AUC 0.72 may largely be predicting MOVEMENT SIZE (winners are big movers), which
   would point at straddle/vol structures, not directional ones — a different game entirely. Test:
   relabel the existing pile for magnitude (vol-scaled |move|) and re-run separation/AUC
   head-to-head vs direction. Hours, £0. Possibly the highest-information cheap test left.
3. **The option wrapper vs the signal.** We concluded "features can't clear costs" — never separated
   "features carry nothing" from "the 1-day option wrapper eats what they carry." Test:
   underlying-path labels for the SAME candidates at matched horizons with vol-scaled barriers
   (yfinance), £0.
4. **Random-tier thinness.** ~8 Bernoulli rows/day anchor all pool baselines; fine pooled, too thin
   for per-regime cuts later. Note for a governed budget tweak someday; not urgent.
5. **Calendar structure in outcomes** (day-of-week/expiry-cycle effects) — never swept; cheap; low
   prior; parked behind 1–3.

## 4. Pre-mortem — February 2027, still no edge; what do we regret not doing in July?

1. **"We never archived option chains."** By February we'd have had 7 months of our OWN option
   history — every structure/VRP/skew backtest we currently cannot run would be runnable on data no
   one sells us. The regret compounds DAILY and it is not on any roadmap. (UW `option_chains` is in
   the client already; the snapshots repo is the natural store.)
2. **"The fixed-window feeds rolled over us."** Congress serves 199 rows, analyst ~4 days; unarchived
   days are gone forever. Planned in the frontier plan's daily layer — not yet built; the pre-mortem
   upgrades its urgency.
3. **"We kept scoring direction after July's own data could have told us the signal was about
   magnitude."** Blind spot 2 — cheap and never asked.
4. **"A VIX spike came and went while the premium lane waited for perfect paperwork."** The
   once-a-quarter regime event is the scarce resource; being in measurement position when it
   arrives beats spec elegance. (Sunday's decision covers this — noted, not new work.)
5. **"We never checked the pond"** — blind spot 1.

## 5. The shortlist (max five, ranked by learning-rate per unit effort)

1. **CHAIN + FEED ARCHIVER** — daily snapshots of UW option chains (the liquid list + engine names)
   plus the congress/analyst windows, append-only into the snapshots repo. £0, cron-class,
   governed-lite (VPS cron + one script; no engine contact). Evidence: pre-mortem #1/#2 — the only
   asset whose absence is IRREVERSIBLE daily. Measure: rows/day landing; in 8 weeks, our first
   own-data two-regime option study.
2. **TARGET-DEFINITION STUDY** (report-only, £0, one evening): magnitude labels vs direction labels
   on the existing pile, same features, same OOF discipline. Measure: magnitude-AUC vs 0.72
   direction-AUC; if magnitude wins decisively, the hunt reorients from "which side" to "how much" —
   vol structures, not directional ones.
3. **UNIVERSE-CONDITIONING STUDY** (report-only, £0, one evening): flow-flagged vs matched controls.
   Measure: if the pond is poisoned, within-universe searching deprioritises permanently — a
   negative worth more than most positives.
4. **FREE INDEX-VOL REGIME BASELINE** (report-only, £0): CBOE PUT/BXM + VIX/VIX3M history —
   what premium-selling actually earned through 2008/2020/2022. Measure: Sunday's premium-lane
   decision made against 30 years of regime context instead of 3 calm weeks.
5. **UNDERLYING-PATH LABELS for the existing pile** (report-only, £0): resolves blind spot 3;
   separates dead-signal from wrapper-eaten-signal. Measure: stock-label separation vs option-label
   separation on identical candidates.

## 6. Honest verdict

The binding constraint — regime coverage of option-priced outcomes — is **not directly actionable
this week**; it is time, and pretending otherwise would be busywork. But its cost has three real
reducers, all on the shortlist: start the archiver so the constraint is finite (every week of delay
is a week added to its life); import the free 30-year index-vol record so the premium decision
borrows regimes we haven't lived; and re-base the cheap questions onto deep stock history where the
constraint doesn't bind. Beyond the five shortlist items, the correct posture is the one already
running: daily accumulation, weekly judgement, kill fast, and wait for the market to deal a second
regime.
