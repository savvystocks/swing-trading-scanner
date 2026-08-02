# Sunday boundary deck — 2026-08-02 (prepared night of 08-01; nothing here is active)

Every item below is a decision for the owner. Nothing trades, activates, or changes without an
explicit yes; every activation is a counted trial.

## 0. Proposed NORTH_STAR amendment (owner ratification required — the night's core lesson)

Draft principle, one sentence:
**"The primary lane always belongs to the best-evidenced method; when the evidence ranking
changes, the primary changes with it — no strategy holds the crown by incumbency."**

Why: the 08-01 evidence scoreboard ranked every method we can run, and the incumbent (V10 flow
engine) came LAST — hit rate 3.8% vs 55.9% hurdle, SPRT REJECT, conviction logic measured
inverted — while the best-evidenced method (index put-write, 19.6y documented record) had no
lane at all. The old standing decision "V10-only, one strategy perfected" (decision 3) built
this inversion in. The amendment replaces perfect-the-incumbent with run-the-best-evidenced.
Supersedes/reframes standing decision 3 if ratified.

## 1. The decisions (in order)

| # | decision | ask | spec |
|---|---|---|---|
| 1 | NORTH_STAR amendment above | ratify yes/no | this file, section 0 |
| 2 | Multi-account tournament (3 paper accounts, 6 books, consolidation by risk type) | approve structure | ACCOUNT_TOURNAMENT_SPEC_2026-08-01.md |
| 3 | Put-write book = PRIMARY lane (the amendment applied: only method with positive-expectation evidence). AMENDED 08-02: Alpaca paper now supports INDEX options (SPX/XSP/VIX, cash-settled European) — the book trades real XSP, deleting early-assignment/pin risk by contract design | activate as primary | tournament spec, book 3 + SOFTWARE_DUE_DILIGENCE sec.5 |
| 4 | Premium lane v2.2 (cost-measurement instrument) | activate yes/no | PREMIUM_LANE_SPEC_2026-07-28.md |
| 5 | V10 demotion to control/data-generator | choose: full cadence as baseline+fill-generator, or throttled | section 2 below |
| 6 | Lessons Engine trigger fix — three evidence-backed SUBTRACTIONS | approve spec | section 3 below |
| 7 | Consensus-fade hypothesis | already registered with tripwires (no ask — informational) | ROADMAP question list, 2026-08-01 entry |
| 8 | Dark-pool sensor retry hardening | approve (passivity battery mandatory) | ROADMAP scheduled decisions |
| 9 | Analyst + congress accumulation sensors | approve forward accumulation | FRONTIER_PLAN sec.4 |
| 10 | Poller extension (fixed-hold answerability) | approve | ROADMAP fixed-hold question |
| 11 | Buy-signal rework blueprint (R1 subtractions now; R2 signed-intent flow columns as measurement, stock-labels-first; R3 = tournament; R4 watches) | approve R1+R2 | BUY_SIGNAL_REWORK_2026-08-01.md |
| 12 | External evidence ranking of every UW indicator family (validates the pivot; adds insider cluster-buys as a ~Sep registrant; downgrades congress expectations; calibrates R2 to probably-null) | informational + approve item 2's insider registration slot | UW_INDICATOR_EVIDENCE_2026-08-02.md |
| 13 | UW SUNSET REVIEW — pre-registered for Sunday 2026-09-27 (owner statement 08-02: "UW doesn't seem effective enough"). Dependency map: every proven-path book (put-write, lane, momentum, insider-via-EDGAR, short-interest conditioning) is UW-independent; UW remains only the flow-books' trigger + three open experiments (R2 signed-intent, dark-pool convergence, archiver history). Kill criteria fixed now: if by 09-27 R2 is null, dark-pool has not survived convergence, insider work runs on free EDGAR, and the flow-book A/Bs have hit their pre-registered floors with no pass — the subscription ends. Any experiment passing its bar before then justifies the spend (NORTH_STAR case-by-case rule; the £ math goes to the owner at the review). | ratify the review date + criteria | this file |
| 14 | Software stack + plan of attack (QuantConnect free + optionsDX free as the dual validation lab; Alpaca unchanged; IBKR UK at the live gate; signal-platform category CLOSED; ThetaData/Option-Omega only on a named Phase-1 gap, one month max, math to owner first) | approve Phase 1 (£0) | SOFTWARE_DUE_DILIGENCE_2026-08-02.md |
| 15 | THE CORE STRATEGY, AMENDED BY THE AMBITION MANDATE (owner order 13:19: minimum 2x S&P) — the LEVERED PREMIUM ENGINE: same VRP mechanism, three books: (A) short-dated 5%-OTM SPX/XSP put-writing with VIX-rank+Kelly sizing at 1.25-2x notional (ERN 13y real money 13-17%/yr; arXiv 2025 17-53% CAGR OOS configs), (B) MEIC 0DTE defined-risk iron condors (20.7% CAGR live since 2023, DD 4.3%), (C) plain monthly put-write as the CONTROL the levered books must beat to keep their leverage. Target 15-25%/yr; NORTH_STAR 30% halt sovereign; paper first; every book a counted trial. | ratify the engine + the beat-the-control leverage deal | AMBITION_MANDATE_2026-08-02.md + CORE_STRATEGY_2026-08-02.md |

Prereq for 2–4: the two new paper accounts' API keys (hidden-input terminal handoff; put-write
first, premium-lane second).

## 2. V10 demotion options (decision 5)

- OPTION A — keep full cadence as control: unchanged baseline every book is measured against;
  keeps generating executed fills for cost models + harvest ground truth. Cost: continued paper
  losses (~-$570/trade expectancy) that mean nothing financially but keep alarm noise.
- OPTION B — throttle (e.g. 1 trade/day): keeps a thin control stream and most harvest value
  (harvest logs candidates regardless of execution; executed tier shrinks). Cost: weaker cost
  ground truth, smaller SPRT stream, control less comparable.
- Recommendation on record: A, unchanged — a control's value is its constancy; paper losses are
  the tuition we are already extracting via the ledger. (Owner decides.)

## 3. Lessons Engine buy-trigger fix (decision 6) — subtractions only, from the autopsy

1. DELETE biggest-premium-first selection → replace with tightest-spread-first among gate
   survivors (cost-justified: the whale rule preferentially bought crowded consensus; 250k+
   won 13.6% vs 17.0% mid-band; spread cost is the one measured, monotone lever).
2. CORRECTED (08-01 forensics, code-verified): there is NO conviction-stack requirement to
   remove — classify_regime's flow weight (±2.0) always beats trend+market (max ±1.5), so flow
   side alone decides every direction and the "stack" is decorative. The real defect is deeper:
   alert TYPE is not INTENT (a big put print may be a bullish put SALE; the code discards the
   ask/bid split, sweep/multileg flags, and opening indication that would sign it). The
   Lessons Engine keeps V10's direction unchanged for control comparability; the signed-intent
   reconstruction is the R2 measurement path in BUY_SIGNAL_REWORK_2026-08-01.md — never a
   silent engine change.
3. REMOVE mock blocks from all scoring paths (alt_catalyst insider/reddit fabricates hardcoded
   constants on ANY failure — the only non-null fail-open in live mode; null it everywhere and
   strike its fictional "determining factor" narratives).
Plus the previously validated lessons: <=2% spread cap, liquidity floor (price >= 5, mcap >=
250M), trail-dominant exits, one position per correlation cluster, earnings blackout enforced.
Honest expectation stated in advance: loses less than V10, likely still negative — it is the
execution-vs-signal instrument, not a profit claim.

## 4. Tonight's Sunday-chain digest (chain run 2026-08-01 21:59 UTC, all jobs green)

- STUDENT: REJECTED — official week 2 of the pivot clock's 6. New this week: the Student
  selected NOTHING (max calibrated p 0.500 vs hurdle 0.6006; 11,284 feature-bearing rows; AUC
  0.739). Gates: 1 FAIL (no selections), 2 FAIL (PBO 0.294 vs 0.20), 3 FAIL (DSR 0.000),
  4 FAIL (nothing to compare; engine itself -0.7043 net, hit 0.0273). Shadow: TAKE 0 / VETO
  2,631; would have vetoed all 15 of the engine's executed picks. CLIFF WARNING stands (zero
  probability mass within 10pts of the bar).
  NOTE: strategy_this_week still prints "Week 1 of 6" — generator counts stale by one; the
  honest count is 2 consecutive official REJECTED cards (07-24, 07-31). Fix queued.
- WEEKLY EDGE REPORT: NO-EDGE. n=477 executed, hit 3.77% vs 55.94% hurdle, expectancy -0.5692,
  SPRT REJECT (18/477, LLR -56.6). Dataset 32,281 rows. By real spread since 07-09: tight n=10
  UNDERPOWERED, medium 2-8% hit 9.2% (best band), wide >=8% hit 3.5% (n=289 — most executions
  still wide; the 5% cap only bites at entry from 07-29).
- COUNCIL: blended AUC 0.7345; TAKEs 0 of 11,284 (all below contract bar); agreed with 0 of 477
  engine picks. TREASURER: 0 TAKEs to size; P(halt) UNDERPOWERED; macro brake would have fired
  on 0 rows. GOVERNOR: student + council both CANDIDATE/AMBER, 0/6 green streak, shadow only;
  lifetime trials 1,222 (+ tonight's autopsy batch). Measurement-lane trigger NOT MET (organic
  tight fills 131 already cover; lane stays down).
- DISCOVERY: "a HINT of an edge — not yet defensible." First rules ABOVE the hurdle appear:
  shares_short:HIGH & execution_hour:LOW & (gex zero-gamma HIGH / atr HIGH) OOS up-rate
  0.66-0.68 at n_eff 14-19 (thin), dealer net_dex variant 0.6495 at n_eff 21.3; 68,402 trials
  counted; promotion bar = survival across convergence angles in consecutive weekly runs.
  Watch, do not touch. day_of_week is the top MDA feature (0.105) — matches the D3 idea-ledger
  entry.
- DEEP DIAGNOSTIC (owner-ordered, run tonight): winners_autopsy_2026-08-01.md — the buy
  trigger's conviction is INVERTED (3/3-aligned 7.0% wins vs 0/3 25.6%); the only profitable
  organ is the exit machinery; 54% of winner dollars = one mock-era week at 4x size.

## 5. Standing watches (unchanged)

F probe (OPASN by Aug-19), FCEL canary rest proven / fleet-wide = owner decision, PEAD re-run
08-24, flagged-name drift re-read ~Sep, pivot clock week 2 of 6 (~Aug-30 decision if streak
holds), Q2 exit-quote data accumulating since 07-29.
