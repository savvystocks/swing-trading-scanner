# CORPUS BASIS DIFF v1 -> v2 - 2026-09-09

v1 rows 73263 (entry = trade-bar close ~90min post-print, look-ahead in the entry bar, exits at the exact level)
v2 rows 79045 (entry = NBBO ASK at the print, entry bar excluded from the peak loop, exits haircut to the bid)

| cell | v1 %/day | v2 %/day | DIFF | v1 days | v2 days | v1 n | v2 n |
|---|---|---|---|---|---|---|---|
| POOL (every trigger) | +6.03 | +1.67 | -4.36 | 452 | 452 | 73263 | 79045 |
| FOLLOW_CALLS | +9.06 | +4.49 | -4.58 | 452 | 452 | 39919 | 43984 |
| CONSENSUS_CALLS | +7.06 | +3.17 | -3.89 | 450 | 450 | 33694 | 37706 |
| BULL_DIP | +9.36 | +4.70 | -4.66 | 206 | 206 | 3784 | 4514 |
| DIP_CONF_MILD | +11.06 | +5.59 | -5.47 | 78 | 78 | 3323 | 3372 |
| DIP_CONVEXITY (wide) | +18.44 | +14.49 | -3.95 | 56 | 56 | 3468 | 3473 |
| WINNER_PROFILE_X | +6.33 | +1.95 | -4.38 | 452 | 452 | 67324 | 71431 |

LARGEST DEGRADATION: -5.47 points/day.
PANEL ACCEPTANCE RULE: a gap beyond the promotion floor (3.0 points/day) means the v1 numbers were never a bar - every published cell citing them is SUPERSEDED and no strategy may be promoted or seated on a v1 figure.

Note the two bases also differ in population: v2 drops any contract with no executable ask banked at its print (never faked from the daily quote), and v2 was built after the bar-library top-up, so row counts are not directly comparable - the day-means are.
