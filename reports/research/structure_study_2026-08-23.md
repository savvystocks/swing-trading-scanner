# Structure study - 2026-08-23 (does delta/DTE pay, or only win more?)

Real triggers, live exit replay (trail 50/20, stop -50). MEAN = day-clustered mean
return (the metric that pays). WIN = per-trade win-rate (what the student optimised).
If MEAN and WIN disagree, WIN is the trap - asymmetric exits pay runners, not accuracy.

## By |delta|

| bucket | trades | day-mean | t | win-rate | 2026 mean |
|---|---|---|---|---|---|
| 0.05-0.15 | 35642 | +7.50% | +2.59 | 0.228 | +24.64% |
| 0.15-0.30 | 60011 | +7.48% | +5.01 | 0.305 | +10.50% |
| 0.30-0.45 | 60184 | +3.01% | +3.17 | 0.328 | +3.85% |
| 0.45-0.60 | 57412 | +1.83% | +2.30 | 0.337 | -1.27% |
| 0.60-0.80 | 33205 | +0.77% | +0.94 | 0.362 | -3.53% |
| 0.80-1.01 | 20333 | -3.47% | -5.83 | 0.399 | -5.45% |

## By DTE

| bucket | trades | day-mean | t | win-rate | 2026 mean |
|---|---|---|---|---|---|
| 0-7d | 53468 | +0.31% | +0.12 | 0.219 | +3.52% |
| 8-21d | 78201 | +1.09% | +0.84 | 0.285 | +5.87% |
| 22-45d | 65619 | +2.76% | +2.19 | 0.333 | +6.63% |
| 46-90d | 18238 | +4.57% | +2.40 | 0.360 | +9.39% |
| 91-400d | 46705 | +7.36% | +8.47 | 0.390 | +4.15% |

## Joint grid (day-mean %, blank = thin)

| delta \ DTE | 0-7d | 8-21d | 22-45d | 46-90d | 91-400d |
|---|---|---|---|---|---|
| 0.05-0.15 | -1.0 (11009) | +8.1 (9127) | +8.6 (6553) | +8.5 (2486) | +20.2 (5162) |
| 0.15-0.30 | +8.5 (12497) | +4.4 (16356) | +5.3 (14197) | +4.7 (3819) | +14.2 (10312) |
| 0.30-0.45 | -0.5 (8729) | +1.4 (17919) | +4.4 (15604) | +0.4 (3899) | +4.0 (10894) |
| 0.45-0.60 | +0.4 (6510) | +0.3 (16565) | +0.0 (17224) | -0.8 (4217) | +4.0 (10130) |
| 0.60-0.80 | -0.4 (5663) | -1.6 (9799) | +0.4 (7207) | -1.4 (1811) | +2.4 (6002) |
| 0.80-1.01 | -5.0 (5310) | -5.8 (6020) | -5.3 (3501) | -7.5 (1340) | -3.2 (2999) |

## Verdict

LIVE BOOK today (4% OTM ~35dte = delta .30-.45, 22-45d): day-mean +4.38%, t +2.74, win 0.346, n=15604
BEST cell (n>=300): delta 0.05-0.15, DTE 91-400d -> day-mean +20.18%, t +6.00, win 0.351, n=5162
LIFT vs live book: +15.80 pts/trade-day

If the best cell is HIGHER delta than .30-.45 AND its day-mean beats the live cell, the structural filter is real. If win-rate rises but day-mean does NOT, the filter is a TRAP (accuracy bought with lost runners) and must NOT be built.
