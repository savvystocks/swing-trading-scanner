# Correction to the official Student verdict of 2026-07-24 (commit 0beafa4a)

**The verdict is UNCHANGED: STUDENT REJECTED — gates failed.** This note records that two of the four
gates were measured with defective instruments, what the corrected instruments say, and why the
verdict stands regardless. The original report is left in place as the record of what was believed at
the time; this file is the correction. (NORTH_STAR: provenance on everything — future-us must be able
to audit past-us.)

## What was wrong

Found 2026-07-25 by adversarial verification (five independent agents attacking the backtest
machinery), then reproduced directly before any fix was written.

1. **PBO was not CSCV.** `harness.probability_of_backtest_overfitting` selected the winning trial on a
   row of the performance matrix and then ranked that *same row* inside the winner's column — no
   train/test separation, and ranking across time-groups instead of across trials. Measured on 200
   pure-noise matrices (strategies with no edge by construction): the old code returned mean PBO 0.012
   and passed the ≤0.20 gate in **100%** of cases. Correct CSCV returns mean 0.531 and passes 16%. The
   statistic whose sole purpose is catching flukes was systematically certifying them, which made a
   false ACCEPT reachable had gates 1 and 4 both passed.
2. **Deflated Sharpe received the wrong units.** `sr_variance` was passed the variance of the raw
   performance cells where it requires the variance of the trials' Sharpe ratios. On dollar-scale
   matrices this pins the statistic at exactly 0 regardless of input.

Both fixed in commit 1f6fa787, with a ground-truth regression test (`test_pbo_dsr_correctness`) that
locks them: pure noise must not certify clean, a planted edge must score low.

## Corrected gate readings (same snapshot, `harvest_20260724_2130`)

| gate | as published 2026-07-24 | corrected | verdict |
|---|---|---|---|
| 1. OOS Wilson lower bound > hurdle | 0.3231 vs 0.5944 | unchanged (arithmetic, untouched) | **FAIL** |
| 2. PBO ≤ 0.20 | 0.333 | **0.232** | **FAIL** |
| 3. Deflated Sharpe > 0.5 | 0.000 | unchanged (genuine: the selections lost money, so the Sharpe is negative and deflates to ~0 in any units) | **FAIL** |
| 4. beats the engine on the same purged splits | net −0.0792 vs −0.7125 | unchanged | **PASS** |

Verdict: **STUDENT REJECTED — gates failed.** Unchanged.

## An honest note on the direction of the error

When the defect was first found it was stated that correcting it would make gate 2 *harsher*, on the
reasoning that the broken statistic was biased toward passing. That was wrong. The corrected PBO came
out **lower** (0.232 vs 0.333) — closer to passing, though still failing. A broken statistic is not
reliably biased in one direction on any particular input: it read 0.01 on pure noise and 0.333 here,
while correct CSCV reads 0.232. That unpredictability is precisely why the defect mattered, and
"it failed anyway" was too comfortable a conclusion to have drawn before re-running it.

## Scope of the blast radius

The defective PBO fed: the Student's gate 2 (all runs to date), the discovery rig's campaign PBO, and
the strategy bake-off. Every PBO figure published before 2026-07-25 should be treated as unreliable —
specifically the discovery campaign's `PBO 0.133` (2026-07-20) and `0.267` (stock-horizon, 2026-07-25).
Those runs' *conclusions* were NO-EDGE / not-supported, which a stricter statistic cannot overturn,
but their PBO numbers were not measuring what they claimed. Re-runs from 2026-07-26 onward use the
corrected implementation.
