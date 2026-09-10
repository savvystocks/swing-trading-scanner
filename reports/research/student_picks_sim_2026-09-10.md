# STUDENT PICKS SIMULATION - 2026-09-10 (strict walk-forward)
rows 26039, 39 scored days, expanding-window retrain every day; label returns; feature coverage 96%; base win rate 28%

| book | days | picks/day | %/day | trimmed | paired t (vs CONTROL; TRADEABLE books vs TRADEABLE) | ahead | halves | pick win rate |
|---|---|---|---|---|---|---|---|---|
| CONTROL | 39 | 530.5 | -21.8 | -21.7 | +0.00 | 0/39 | -25.4/-18.4 | 28% |
| FADE_SHAPE | 39 | 143.9 | -21.1 | -21.5 | +0.27 | 20/39 | -24.6/-17.8 | 29% |
| CALLS | 39 | 324.1 | -21.4 | -21.4 | +0.30 | 22/39 | -24.0/-18.9 | 29% |
| MOMO_SHAPE | 39 | 189.6 | -19.6 | -20.0 | +1.03 | 25/39 | -21.3/-17.9 | 30% |
| WIDE_TOP3 | 39 | 3.0 | -12.2 | -12.4 | +1.95 | 23/39 | -13.8/-10.7 | 38% |
| WIDE_60 | 11 | 2.5 | -19.0 | -21.4 | +0.37 | 4/11 | -4.0/-31.5 | 32% |
| CALLS_TOP3 | 39 | 3.0 | -16.7 | -17.5 | +0.94 | 17/39 | -25.2/-8.6 | 37% |
| NARROW_TOP3 | 39 | 3.0 | -10.4 | -11.1 | +1.97 | 25/39 | -17.5/-3.8 | 40% |
| NARROW_60 | 15 | 2.6 | -15.1 | -17.2 | +0.71 | 8/15 | +8.5/-35.8 | 36% |
| TRADEABLE | 39 | 76.8 | -5.4 | -5.6 | +0.00 | 0/39 | -6.8/-4.0 | 41% |
| TRADEABLE_FADE | 39 | 26.7 | -1.8 | -3.0 | +0.90 | 24/39 | -5.2/+1.4 | 45% |
| TRADEABLE_MOMO | 39 | 30.2 | -7.4 | -8.4 | -0.55 | 18/39 | -7.7/-7.2 | 39% |
| TRADEABLE_TOP1 | 39 | 1.0 | -4.8 | -6.9 | +0.07 | 21/39 | -3.8/-5.8 | 41% |
| TRADEABLE_TOP3 | 39 | 3.0 | -4.0 | -4.9 | +0.21 | 22/39 | -3.4/-4.5 | 41% |
| TRADEABLE_CALLS_TOP3 | 39 | 3.0 | -7.4 | -7.5 | -0.37 | 19/39 | -17.7/+2.4 | 44% |
| TRADEABLE_NARROW_TOP3 | 39 | 3.0 | -2.0 | -2.6 | +0.53 | 21/39 | -1.6/-2.4 | 45% |
| TRADEABLE_FADE_WIDE_TOP3 | 39 | 3.0 | -2.9 | -3.8 | +0.40 | 18/39 | -6.9/+0.8 | 44% |
| TRADEABLE_FADE_WIDE_TOP1 | 39 | 1.0 | -4.8 | -7.1 | +0.06 | 18/39 | -7.2/-2.6 | 41% |

READING: if the picker books (WIDE_TOP3/60, NARROW_TOP3/60, CALLS_TOP3) sit above their parent shapes AND above CONTROL with t near or beyond 1.8 on both halves, selection is the strategy and the fixed identity is only the pool it selects from. If the shapes alone match the pickers, the model adds nothing beyond the filter.
CAVEATS: label returns (executable-price path, no live friction); ~25 scored days; one path; the narrow model here uses ALL fade-shaped rows (no band filters) so it has every row at its disposal - the nightly narrow model uses the banded fade cohort.
