# STUDENT EXIT SEARCH - 2026-09-11 (full two years, no holdout) - EXPRET/ALL on ASOF features
entry = P(win) student on the AFFORD band, quarterly walk-forward, k picks/week by threshold; exits = 210 fine-grid configs on the v3 basis (close-confirmed trail fills).


## k = 3 picks per week (102 trades)

| exit | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE -50/+50/0.20 | 102 | 43 | +26.7 | 59% | +634 | +2.47 | 67% | +375/+882 | 2461 | +27268 | BEAR:11/+31 BULL:57/+14 MILD:34/+46 |
| IN-SAMPLE #1: -65/+40/0.15 | 102 | 43 | +31.4 | 64% | +746 | +2.74 | 70% | +327/+1146 | 2472 | +32069 | BEAR:11/+38 BULL:57/+15 MILD:34/+56 |
| IN-SAMPLE #2: -45/+40/0.15 | 102 | 43 | +31.2 | 62% | +740 | +2.74 | 70% | +411/+1054 | 2302 | +31835 | BEAR:11/+40 BULL:57/+19 MILD:34/+50 |
| IN-SAMPLE #3: -70/+40/0.15 | 102 | 43 | +30.9 | 64% | +734 | +2.68 | 70% | +315/+1134 | 2623 | +31564 | BEAR:11/+38 BULL:57/+15 MILD:34/+56 |
| IN-SAMPLE #4: -60/+40/0.15 | 102 | 43 | +30.8 | 63% | +730 | +2.72 | 72% | +350/+1093 | 2415 | +31409 | BEAR:11/+39 BULL:57/+16 MILD:34/+52 |
| IN-SAMPLE #5: -75/+40/0.15 | 102 | 43 | +30.6 | 64% | +726 | +2.65 | 67% | +297/+1134 | 2623 | +31206 | BEAR:11/+38 BULL:57/+14 MILD:34/+56 |
| WALK-FORWARD exit choice | 102 | 43 | +23.4 | 57% | +556 | +2.30 | 63% | +365/+738 | 3052 | +23899 | BEAR:11/+18 BULL:57/+11 MILD:34/+46 |
| (walk-forward chose) | 2025Q3:-50/+50/0.20, 2025Q4:-45/+80/0.30, 2026Q1:-45/+80/0.15, 2026Q2:-45/+70/0.30, 2026Q3:-45/+70/0.30 | | | | | | | | | | |
| PER-REGIME best (in-sample) | 102 | 43 | +37.0 | 64% | +878 | +3.11 | 74% | +434/+1301 | 2302 | +37737 | BEAR:11/+64 BULL:57/+19 MILD:34/+59 |
| (per-regime configs) | BULL:-45/+40/0.15, MILD:-65/+90/0.15, BEAR:-45/+40/0.30 | | | | | | | | | | |

## k = 2 picks per week (70 trades)

| exit | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE -50/+50/0.20 | 70 | 40 | +25.2 | 54% | +442 | +1.60 | 50% | +202/+681 | 1848 | +17662 | BEAR:8/+23 BULL:39/+3 MILD:23/+63 |
| IN-SAMPLE #1: -65/+40/0.15 | 70 | 40 | +31.8 | 60% | +556 | +1.93 | 52% | +192/+920 | 1787 | +22240 | BEAR:8/+21 BULL:39/+7 MILD:23/+78 |
| IN-SAMPLE #2: -70/+40/0.15 | 70 | 40 | +31.1 | 60% | +543 | +1.88 | 52% | +179/+908 | 2037 | +21736 | BEAR:8/+21 BULL:39/+6 MILD:23/+77 |
| IN-SAMPLE #3: -75/+40/0.15 | 70 | 40 | +30.8 | 60% | +539 | +1.87 | 52% | +171/+908 | 2037 | +21573 | BEAR:8/+21 BULL:39/+6 MILD:23/+77 |
| IN-SAMPLE #4: -60/+40/0.15 | 70 | 40 | +30.7 | 59% | +537 | +1.90 | 52% | +211/+863 | 1706 | +21482 | BEAR:8/+23 BULL:39/+8 MILD:23/+72 |
| IN-SAMPLE #5: -45/+40/0.15 | 70 | 40 | +30.6 | 57% | +536 | +1.87 | 55% | +251/+820 | 1592 | +21422 | BEAR:8/+25 BULL:39/+10 MILD:23/+68 |
| WALK-FORWARD exit choice | 70 | 40 | +29.9 | 57% | +523 | +1.82 | 52% | +225/+820 | 1592 | +20904 | BEAR:8/+25 BULL:39/+9 MILD:23/+68 |
| (walk-forward chose) | 2025Q3:-50/+50/0.20, 2025Q4:-45/+40/0.15, 2026Q1:-45/+40/0.15, 2026Q2:-45/+40/0.15, 2026Q3:-65/+40/0.15 | | | | | | | | | | |
| PER-REGIME best (in-sample) | 70 | 40 | +34.7 | 60% | +607 | +2.15 | 62% | +276/+939 | 1853 | +24292 | BEAR:8/+25 BULL:39/+10 MILD:23/+80 |
| (per-regime configs) | BULL:-45/+40/0.15, MILD:-65/+90/0.15, BEAR:-45/+40/0.15 | | | | | | | | | | |

READING: IN-SAMPLE and PER-REGIME rows are ceilings - the exit was chosen on the same trades it is scored on (210 trials). The WALK-FORWARD row is what a live system could have done: it picks the exit from the past only. The gap between them is the optimism a no-holdout number carries.
CAVEATS: label returns on the v3 basis; two years dominated by bull and mild tape; picks are ~3 a week so single trades move the weekly numbers.
