# The student: train it on what it buys, and search its exit. Both fail.

Owner order 2026-09-16 01:42 BST, after the fragility test showed STUDENT_A's executed-slice mean
(+19.9%/trade) goes to -1.3% with its best three trades removed. Read-only: no spec, no model file,
no court clock touched. `scripts/student_cohort_exit_study.py`.

## 1. Cohort: trained on ALL (live) vs trained on CAP1000 (what the $1,000 seat can buy)

| walk-forward, executed slice | ALL (live) | CAP1000 |
|---|---|---|
| executed trades | 68 | 150 |
| mean per trade | +19.9% | +9.5% |
| best trade removed | +9.2% | +4.4% |
| top three removed | **-1.3%** | **-1.9%** |
| median trade | +2.1% | +3.3% |
| win rate | 50% | 51% |
| hit the -50% stop | 37% | 38% |
| weekly dollars | +413, t 1.26 | +255, t 1.03 |
| live bar | 14.58 | 7.23 |

CAP1000 more than doubles the executed count because every pick fits the cap (the live model discards
57% of its picks as unaffordable). But per-trade return halves, weekly t falls, and the fragility is
unchanged. The arithmetic goes the wrong way: at these effect sizes, reaching t=2 takes ~83 weeks on
ALL and ~136 on CAP1000. **More trades do not compensate for the smaller effect. Do not switch.**

## 2. Exit: 210 configs (7 stops x 6 triggers x 5 givebacks), chosen walk-forward

Searching 210 configs on ~68 trades is curve-fitting, so the config is chosen on the FIRST half of
weeks and scored on the SECOND half it never saw. The in-sample best is printed only as a reference.

| second half, out of sample | chosen exit | BASE (-50/+50/0.20) |
|---|---|---|
| ALL cohort, mean per trade | +35.3% | +33.6% |
| its median trade | -46.4% | +6.0% |
| win rate | 47% | 56% |
| stop-outs | 42% | 33% |
| top three removed | -3.6% | -2.9% |
| CAP1000 cohort, mean per trade | +13.5% | **+19.9%** |
| CAP1000 top three removed | -3.3% | **+4.2%** |

On the live cohort the searched exit wins by 1.7 points of mean and loses on every robustness
measure. On the affordable cohort BASE wins outright. **The exit we already run is the right exit.**

## 3. What this leaves

At every setting tested - three bars, two cohorts, 210 exits - removing three trades from ~68 takes
the book to zero or below, the win rate sits at 50%, and weekly t lands between 0.9 and 1.4. The
model's walk-forward AUC is 0.508 against a coin flip's 0.5, so its fat tail cannot be shown to be
selected rather than met. Neither lever the owner asked for moves any of it, and neither does the
bar (`student_thresholds_2026-09-15.md`) or the entry clock (`entry_timing_2026-09-16.md`).

The remaining honest options are genuinely better inputs, or a judging horizon suited to a fat-tailed
book. At three picks a week the court's eight weeks is ~24 trades and the verdict would be decided by
whether one big winner lands inside the window.

## 4. Honesty notes

- Both cohorts use the same walk-forward machinery as `scripts/student_export.py` (quarterly refits,
  thresholds from the trailing 60 sessions of the OOS stream), so neither is scored in-sample.
- Every cell reports best-removed and top-3-removed because this book's means are carried by a few
  trades; a mean without them is not informative here.
- The exit grid is `reports/research/glide_fine_rows_v3.jsonl`, joined by (occ, day); 68 of 68 and
  150 of 150 executed picks matched.
