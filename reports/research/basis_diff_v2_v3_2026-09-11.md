# CORPUS BASIS DIFF v1 -> v2 - 2026-09-11

v1 rows 79045 (entry = trade-bar close ~90min post-print, look-ahead in the entry bar, exits at the exact level)
v2 rows 69666 (entry = NBBO ASK at the print, entry bar excluded from the peak loop, exits haircut to the bid)

| cell | v1 %/day | v2 %/day | DIFF | v1 days | v2 days | v1 n | v2 n |
|---|---|---|---|---|---|---|---|
| POOL (every trigger) | +1.67 | -4.53 | -6.20 | 452 | 455 | 79045 | 69666 |
| FOLLOW_CALLS | +4.49 | +0.09 | -4.40 | 452 | 455 | 43984 | 38950 |
| CONSENSUS_CALLS | +3.17 | -0.84 | -4.01 | 450 | 451 | 37706 | 33515 |
| BULL_DIP | +4.70 | +2.30 | -2.41 | 206 | 206 | 4514 | 4138 |
| DIP_CONF_MILD | +5.59 | +0.52 | -5.07 | 78 | 79 | 3372 | 2942 |
| DIP_CONVEXITY (wide) | +14.49 | +13.88 | -0.61 | 56 | 56 | 3473 | 2942 |
| WINNER_PROFILE_X | +1.95 | -4.66 | -6.61 | 452 | 455 | 71431 | 65867 |

LARGEST DEGRADATION: -6.61 points/day.
PANEL ACCEPTANCE RULE: a gap beyond the promotion floor (3.0 points/day) means the v1 numbers were never a bar - every published cell citing them is SUPERSEDED and no strategy may be promoted or seated on a v1 figure.

Note the two bases also differ in population: v2 drops any contract with no executable ask banked at its print (never faked from the daily quote), and v2 was built after the bar-library top-up, so row counts are not directly comparable - the day-means are.
