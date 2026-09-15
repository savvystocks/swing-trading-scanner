# Student threshold scan - 2026-09-15

Read-only. The out-of-sample stream is rebuilt exactly as `scripts/student_export.py` builds it
(quarterly walk-forward refits, never in-sample); each bar is then applied the way the LIVE seat
applies it (score >= bar, best first within a day, hard cap k_per_week). The executed slice is the
picks whose entry ask fits `exec_max_ask`, sized as the engine sizes them.

## STUDENT_A (target EXPRET, cohort ALL, bar cohort ALL, 3/week, cap $10)

| bar | score | picks | per trade | win | weekly t | positive weeks | executed | exec per trade | exec win | exec weekly t | exec $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| strict | 19.81 | 124 | 10.5% | 0.516 | 1.46 | 0.55 | 61 | 10.2% | 0.492 | 0.89 | 6553 |
| middle | 17.34 | 144 | 22.5% | 0.521 | 2.13 | 0.59 | 65 | 43.4% | 0.538 | 1.99 | 28344 |
| loose (LIVE) | 14.58 | 159 | 9.9% | 0.478 | 1.28 | 0.52 | 68 | 19.9% | 0.5 | 1.27 | 13657 |

Rows scored out of sample: 47983 of 70976 in the cohort; bar cohort rows 47983; corpus reports/research/student_asof_v3.jsonl.

## Reading this

`per trade` is the mean percent return of a pick at the seat's exit configuration; `executed` is the
subset the $1,000 slot can actually buy, in engine sizing, and `exec $` is their summed weekly dollars.
A stricter bar should raise per-trade return and lower the count. If it does not, the bar is not the
lever. Weekly t on a handful of weeks is not evidence of anything - read the counts first.

