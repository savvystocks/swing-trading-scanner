# LAB GROUND TRUTH — as-built facts for the external audit engine (2026-08-19 00:55, spec v2.0)

Purpose: the exact, code-verified mechanics the audit's simulation assumed. Rerun the Monte
Carlo against THESE rules. Nothing here is aspiration; every line is what the code does tonight.

## A. Answers to the audit's three open questions (from code, not memory)
1. SPRT/LLR (scripts/sunday_boundary.py): diffs = book day-mean minus comparator day-mean per
   shared virgin day. LLR = sum(2.0 * (d_i - 1.0)) / s2, where s2 = max(sample variance of
   diffs, 25.0). DESIGN DELTA = +2.0 pts/day vs comparator (~= annualized Sharpe ~2 at our
   ~15pt daily sd: the test hunts MONSTERS). Promote >= +2.94 (min 5 days) AND book mean > 0
   AND both halves > 0. Reject <= -2.94 (min 5 days). Sequential promotions may fire ANY
   night (SEQ_APPLY on the 22:00 UTC run); one promotion max per run.
2. FIXED BAR (Fridays only, >= 10 virgin days): NOT a t-test. Requires ALL of: book day-mean
   > 0; mean(diffs vs comparator) > +2.0; first-half day-mean > 0; second-half day-mean > 0.
3. PROBATION: each promotion stores prior key values; on later runs, once >= 10 NEW virgin
   days exist post-promotion, if mean(diffs vs same comparator) < 0 -> keys auto-revert,
   entry marked demoted. One-shot check (not continuous; audit's CUSUM point stands).

## B. Anti-gaming machinery (exact)
- Evidence clocks: ANY auto promotion/demotion restarts ALL books' evidence at that date
  (blanket reset - the audit's "treadmill" is real as-built). Keys changed within 14 calendar
  days are frozen (cooldown). One spec change per run; changes compound in series.
- Comparators: default BASELINE (unrouted fade shape, band 50-250k); "_vs LIVE_SPEC" books
  (FADE_WHALE, BAND_50_400, EXIT_STOP40, SOFT_ROUTER) judge against the live-book replica.
- Throughput floor: live fills < 3/wk while >= 15 qualifying -> RESTRICTIVE promotions
  (V13_DEPTH, MILD_ONLY, OPT_WINNER) blocked. Currently OK (3 fills / 89 quals).
- PLACEBO_RANDOM (added tonight, first data 08-19): hash-picked ~1/7 of candidates. In our
  replay the spread toll IS embedded (entries at ask, all marks at BID), so the placebo
  SHOULD read negative; ~zero would indicate pricing flattery - treat as alarm either way.
- Trials ledger: 30,947 registered trials; RECORDS only, never vetoes (audit finding 6
  confirmed). Most trials are parameter-sweep variants - effective independent count is
  far below 30k; no one has computed the correlation-clustered number yet.

## C. Replay pricing (what every shadow verdict is priced on)
bid_path polls every ~10 min while a candidate is tracked; entry_ref = REAL ask at signal;
all subsequent marks = REAL bids => round-trip spread cost is inside every replay number.
Exit engine in replay: trail arms at +50%, gives back 20% of peak; hard stop -50; else last
mark. Labels (harvest DB) use the same bid-only executable-price rule. Live fills use limit
orders at quoted ask (entries) and market/limit exits next-day-or-later (no-same-day rule).

## D. What is REGISTERED vs MINED (honesty flags for prior-deflation)
- Pre-registered before data: fade shape itself (from the 74 executed winners), router 1.5,
  band 50-250k, trail 50/20, stop -50.
- MINED post-hoc (deflate hard): DP >= 150 (chosen after seeing 40.9% vs 19.3%), IV/ATM
  echoes, EARLY_CUT (2h/-15), OPT_WINNER (argmax of 25,920 configs), stop -40 (sweep + corpus
  convergence), band 400k ceiling (1,296-sweep no-harm), whale 400k-1M tier (asked-then-tested).
- Corpus caveats (self-declared): proxy triggers not real sweeps; next-morning entries;
  hourly trade-bar prices with 2% haircut variant; liquidity survivorship in path coverage;
  98-name universe is period-start objective but survivor-tilted.

## E. The fourteen live auditions (exact entry/exit rules, all $1k seats)
FADE: flow print $50-400k, flow side contra ticker-20dSMA AND contra SPY-vs-its-SMA (router
  OFF: max_spy_dist 99), real spread <= 2% (one 4s re-quote retry, budget 2/cycle), premium
  <= $10, max 5 concurrent, 2/cycle, 2/ticker/day, earnings blackout 3d. Exits: trail 50/20,
  stop -50, deferred to next day by the no-same-day rule (backstops arm day 2).
Probe roster (2/cycle max, 5/strategy/day, 25/day, candidate ranks 3-12, never on an open
  underlying): EXEC_BASELINE (none), FADE_UNROUTED (shape), CONSENSUS (anti-shape),
  DP_HEAVY (dp>=150), QUIET_TAPE (rvol<0.8), FADE_DP, OPT_WINNER (shape+depth<3+<=250k),
  FADE_WHALE (400k-1M side-pool), GEX_PIN (|zero-gamma dist|<0.3), IV_EXTREME (ivr>=85 or
  <=10). Same exits as FADE via the shared engine.
EARLY_STRENGTH: watches every fade entry's OCC; buys its own lot only if +5..15% within
  20-150min AND the fade record is closed/cancelled (no same-OCC stacking). 5/day.
OVERNIGHT: buys 1 SPY share-lot <= 25 min before close (clock-derived), sells next first
  cycle. TURN_OF_MONTH: buys on/after 25th, sells on/after 4th. Broker-qty idempotency guard.
CREDIT_SPREAD_W (first entry 08-19): weekly XSP; BUY 4%-OTM put wing FIRST, then sell 2%-OTM
  put; European cash settle vs ^XSP Friday close; one/week; defined risk ~width - credit.
Retired with evidence preserved: PUTW, VRP_DAILY (settle out this week), CONDOR_W (killed by
  its own backtest pre-trade), MOMENTUM_ROT (owner scope), premium naked shorts (5k-unusable).

## F. Cycle order of operations (every 10 min, 13:31-20:51 UTC, dual-heart GHA + VPS failover)
(0) orphan roll-call: adopt untracked OPTION positions only; 45-min both-sides fill grace;
    bare-occ/occ_more/shares/PUTW records exempt. (1) daily reconcile marker. (2) backstop
    ratchet (day-2+). (3) exit pass (manage_open_positions; deferral rule; pdt_deferred
    stamped). (4) owner HALT/flatten flags. (5) EARLY_STRENGTH pass. (6) PUTW/VRP settles.
    (7) shares probes. (8) fivek weeklies. (9) UW scan -> candidates (fade band + whale
    side-pool). (10) FADE entries. (11) harvest logger (passivity-tested). (12) fill ledger
    sweep (book-tagged). (13) probe roster. (14) persist with record-level merge resolver;
    success stamps data/last_cycle_ok (ts + engine SHA).
Failure ladder: heartbeat stale > 35 min -> VPS full failover cycle. Heartbeat fresh but
  sentinel stale 2 ticks -> AUTO-ROLLBACK of *.py+scripts/ to last-good SHA (commits are
  pathspec-limited CODE-ONLY after the 08-18 mass-adoption bug), one page, once per episode.
  All proven live: failover 08-06, rollback 08-18 (its own two bugs found+fixed same day).

## G. Nightly chain (UTC): 21:50 shadow lab rolling 5-day rescore (~23 books) -> 22:00
boundary trajectory + SEQ_APPLY promotions -> 22:05 integrity gate -> 22:10 student retrain
(narrow n=750 AUC 0.468; WIDE n=16,570 AUC 0.680, within-day META_WIDE book accumulating)
-> 22:30 off-box backup -> Fri 22:20/22:35 deep review -> first-Sat corpus refresh.

## H. Current standings (tonight, 11 virgin days)
LLRs vs comparator: BAND_WIDE -0.77 (7d), EARLY_CUT -0.22 (5d), V13_DEPTH +0.05 (5d),
BAND_50_400 0.00 (5d), FADE_WHALE 0.00 (4d), SOFT_ROUTER 0.00 (1d), EXIT_STOP40 0d (needs
mild-day LIVE_SPEC cohort, now accruing). TREND_CONSENSUS 3d: +13.2/-13.1/-12.0.
Live realized to date: OVERNIGHT +$5 (4/4), FADE $0 (3 open, day one), CONSENSUS -$508,
QUIET_TAPE -$507, EXEC_BASELINE -$86 (control), 08-18 day P&L +$815. Labeled fade cohort
750; total labels ~20k; harvest ~500 labels/day.

## I. Divergences from the audit's assumed model (for their rerun)
1. Fixed bar is 4-condition (halves rule), stricter than t=1.83 - their noise-pass 4.5% is
   an overestimate for our bars. 2. SPRT delta is 2.0 pts/day (Sharpe~2 hunting) - harsher
   on modest edges than their "large" scenario. 3. A passing book CANNOT be net-losing
   (mean>0 required). 4. Spread toll is embedded in replay pricing (ask-in/bid-marked).
5. Comparator is a same-day book (crude CUPED-lite: market heave partially cancels in the
   diff), though no factor residualization. 6. Blanket clock resets confirmed as-built.
7. Corpus priors are ADVISORY-print only - they gate nothing.
