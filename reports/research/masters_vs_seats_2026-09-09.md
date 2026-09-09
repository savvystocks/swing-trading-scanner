# MASTERS vs SEATS - 2026-09-09
corpus 73263 archive trades over 452 days (~21.5 months); unfiltered pool +6.03%/day
Time-to-verdict = months to reach the court's 8-shared-day bar at the entity's own measured fill-day rate (the bar also needs the control present, so these are FLOORS).

## ARCHITECTURE A - separate seats (today)

| seat | trades | days | %/day | t vs pool | halves | days/mo | months to verdict |
|---|---|---|---|---|---|---|---|
| BULL_DIP | 3784 | 206 | +9.36 | +2.37 | +17.9/-4.6 | 9.6 | 0.8 |
| DIP_CONF_MILD | 3323 | 78 | +11.06 | +1.70 | +6.3/+12.8 | 3.6 | 2.2 |
| DIP_CONVEXITY | 3468 | 56 | +18.44 | +1.19 | +18.3/+18.7 | 2.6 | 3.1 |
| FOLLOW_CALLS | 39919 | 452 | +9.06 | +2.47 | +11.9/+6.3 | 21.0 | 0.4 |
| WINNER_PROFILE_X | 67324 | 452 | +6.33 | +3.37 | +7.3/+5.3 | 21.0 | 0.4 |

## ARCHITECTURE B - three regime masters (anchor + merged winner condition)

| master | trades | days | %/day | t vs pool | halves | days/mo | months to verdict |
|---|---|---|---|---|---|---|---|
| BULL | 3320 | 206 | +9.37 | +2.30 | +17.7/-4.3 | 9.6 | 0.8 |
| MILD | 3110 | 78 | +10.98 | +1.66 | +5.5/+13.0 | 3.6 | 2.2 |
| BEAR | 3170 | 56 | +18.82 | +1.22 | +18.4/+19.6 | 2.6 | 3.1 |

## THE MERGE QUESTION - does absorbing the proven condition improve the anchor?

| master | anchor %/day | master %/day | edge gained | day supply kept | verdict slower by |
|---|---|---|---|---|---|
| BULL | +9.36 | +9.37 | +0.01 | 100% | +0.0 months |
| MILD | +11.06 | +10.98 | -0.08 | 100% | +0.0 months |
| BEAR | +18.44 | +18.82 | +0.38 | 100% | +0.0 months |

MERGE SCORE: 2/3 masters beat their own anchor on day-mean.

EVIDENCE SUPPLY: architecture A accrues 1244 strategy-days across 5 seats; architecture B accrues 340 across 3. Fewer seats means each one's evidence is less fragmented, but every AND-merge removes day supply from the seat that absorbs it - the trade the panel priced.

CAVEATS: bar-replay exits, one historical path, no execution frictions beyond the embedded spread cap; regimes are computed from SPY vs its 50d/20d exactly as the live router does. The live court remains the judge of whatever ships.
