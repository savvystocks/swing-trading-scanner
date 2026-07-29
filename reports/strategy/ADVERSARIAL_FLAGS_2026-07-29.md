# ADVERSARIAL FLAGS — resolution report — 2026-07-29

Standing-directive exercise. Read-only analysis except the named B2 spec amendment. Every flag
carries its FALSIFIER and a status: CLOSED / AMENDED / ANSWERED / PROPOSED / LOGGED.

## B1 — day-level correlation, quantified — **ANSWERED (one verdict downgraded)**

Measured on 9,110 graded feature-bearing rows across 20 trading days (harvest_20260728_2130):

- Within-day intraclass correlation of net returns: **ICC = 0.012** — far lower than feared. The
  per-day mean net return is astonishingly stable (−0.2 to −0.45 every single day): the "common
  factor" in option outcomes is mostly the constant cost drag, not violent same-day covariance.
- Effective sample size: reported ticker-day n_eff 3,025 → **ICC-model 1,393 (overstated ~2.2×)**;
  extreme every-day-is-one-bet bound: 17 (~178×). The truth sits near the model estimate given the
  tiny ICC; both are now on the record.
- **Re-reads:** the 26-trade pocket's REJECT stands and strengthens (day-clustered Wilson LB 0.198
  vs the 0.594 hurdle; was 0.323). The persistence kill stands (killed on sign-flip, not power). The
  8-K null stays null (still zero signal, merely less power). The 0.58 incumbent bar survives as a
  bar (point estimate on 20 days; CI ~1.5× wider — noted, not restated).
- **The casualty is VRP.** Its "both halves clear" evidence rested on halves of 5 and 4 trading
  days. Day-clustered, the share-above bars fail badly (LB 0.41 and 0.24 vs the 0.60 bar). The
  2026-07-28 PASS-interest is **downgraded to: strong point estimates, statistically thin window —
  9 daily observations of one vol regime.** Sunday's lane case may not lean on it; it must lean on
  the structural record (B3).

FALSIFIER OUTCOME: partially fired — day correlation IS negligible for option outcomes (most
conclusions hold with ~2.2× shrink), but for regime-driven quantities (VRP) the day is the honest
unit and the window was 9 days. Standing rule adopted: every future study reports day-clustered
n_eff alongside ticker-day.

## B2 — concentration slot — **AMENDED (spec v2.2, awaiting Sunday approval)**

Amendment written into PREMIUM_LANE_SPEC: correlated underlyings occupy ONE slot. SPY/QQQ/IWM/XSP
are declared one INDEX cluster outright; any other pair with 60-day daily-return correlation > 0.70
(computed at the Sunday universe refresh) shares a slot. Two concurrent spreads only if in different
clusters; else max 1. Revised worst case: **max $450 on any correlated cluster** (was $900 on what
was effectively one index bet), book still ≤ $900 only when genuinely diversified. Sizing note added:
at the £1–5k live-intent scale, one $450 cluster is 7–35% of the account — the lane's own risk line,
in writing, for the live-gate discussion someday.

FALSIFIER: 60-day correlations between candidate underlyings below 0.70 would relax the shared-slot
rule at a Sunday refresh — measured, not assumed.

## B3 — the retail-form question — **ANSWERED, uncomfortably**

Pulled the actual 19.6-year records tonight (yfinance, £0): CBOE PutWrite index (^PUT, the
INSTITUTIONAL cash-secured form): **+7.1% CAGR, 17.0% vol, −37% maxDD**. S&P 500 over the identical
window: +8.8%, 19.7% vol, −57% maxDD. BuyWrite (^BXM): +5.9%.

The honest reading: even the institutional form — full premium, no wing, cash-secured, 500 names,
through two decades including 2008 — earned **index-like risk-adjusted returns** (Sharpe ≈ 0.42 vs
0.45), its edge being drawdown shape, not free money. Our proposed form dilutes that three times
over: (1) **the wing tax** — a put credit spread buys back the steepest-skew corner of the surface,
the most overpriced insurance there is; defined-risk condor-type indices historically lag PUT by a
wide margin (stated from knowledge; the CNDR index wasn't fetchable free tonight); (2) two
underlyings vs hundreds; (3) measured retail crossing costs of 14–46% of target profit. There is
**no supporting evidence** that defined-risk, two-name, retail-scale VRP capture is net positive
after costs — and reasonable theory says thin-to-negative.

**Therefore, stated before Sunday as the directive requires: the premium exists; THIS FORM may well
not capture it. The lane's only honest justification is as a COST-MEASUREMENT instrument — its
40-fill kill is the experiment, not a profit expectation — and the Sunday ask should be read in
exactly that light.** The falsifier is the lane's own ledger: 40 real fills showing positive net
capture would retire this concern; theory predicts they won't.

## Q1 — lifetime trials at the portfolio level — **PROPOSED (no deploy without go)**

Mechanism: `lifetime_trials.json` at repo root — every study runner increments {study, date, trials}
and a cumulative total; retroactive backfill from committed reports (~740 counted so far: 396+396
student runs, 64,862-trial discovery campaign counted once as its own regime, 256+45 source hunts,
34 bake-off, 8+15+30 event studies — exact backfill list in the file when built). DSR calls take
n_trials = lifetime total; the Governor scoreboard renders the count weekly so the search's size is
always visible. Cost: ~20 lines. Awaiting your go.

## Q2 — exit-side fill realism — **QUANTIFIED (instrument-limited), enrichment PROPOSED**

Yesterday's 26 matchable exit fills vs the last fresh poller bid (≤15 min old): median +21% (the bid
moved before the fill), **tails to −63 / −51 / −51%** (BMY, AG, ONON — stop-day gap-throughs on
illiquid names, matching the bake-off's crash-day exit-crossing warning), 14/26 at-or-above the
reference bid. Verdict: exits are not systematically catastrophic, but the tail is real and the
15-minute poll cadence is too coarse to price it. PROPOSED (one line, ledger-only, no deploy without
go): record the decision-time bid/ask into `exit_submit` events so friction is measured against a
synchronous quote.

## WATCH — logged, no action

Council/Student duplication (consolidation candidate once the Governor holds track record) ·
sandbox + autonomous_affiliate working-tree clutter · the disabled NEUTRAL/calendar route ·
VIX-only regime detection (blind to rates/liquidity regimes). Falsifiers: consolidation decided by
Governor data; clutter by a cleanup commit; regime blindness by a future macro-sensor birth
certificate if evidence demands one.
