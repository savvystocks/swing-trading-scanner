# STUDENT EXIT SEARCH - 2026-09-11 (full two years, no holdout)
entry = P(win) student on the AFFORD band, quarterly walk-forward, k picks/week by threshold; exits = 210 fine-grid configs on the v3 basis (close-confirmed trail fills).


## k = 3 picks per week (140 trades)

| exit | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE -50/+50/0.20 | 140 | 54 | +24.4 | 70% | +634 | +4.37 | 74% | +894/+373 | 3249 | +34230 | BEAR:2/+52 BULL:77/+28 MILD:61/+19 |
| IN-SAMPLE #1: -65/+90/0.30 | 140 | 54 | +33.5 | 66% | +869 | +3.74 | 67% | +1424/+314 | 3679 | +46923 | BEAR:2/+127 BULL:77/+39 MILD:61/+24 |
| IN-SAMPLE #2: -65/+80/0.25 | 140 | 54 | +33.1 | 67% | +859 | +3.92 | 70% | +1326/+392 | 3679 | +46376 | BEAR:2/+102 BULL:77/+40 MILD:61/+22 |
| IN-SAMPLE #3: -75/+90/0.30 | 140 | 54 | +32.9 | 66% | +854 | +3.60 | 67% | +1421/+287 | 4495 | +46103 | BEAR:2/+127 BULL:77/+40 MILD:61/+21 |
| IN-SAMPLE #4: -70/+90/0.30 | 140 | 54 | +32.9 | 66% | +852 | +3.63 | 65% | +1428/+277 | 4329 | +46028 | BEAR:2/+127 BULL:77/+39 MILD:61/+22 |
| IN-SAMPLE #5: -65/+90/0.25 | 140 | 54 | +32.8 | 66% | +850 | +3.79 | 69% | +1385/+314 | 3679 | +45880 | BEAR:2/+102 BULL:77/+40 MILD:61/+21 |
| WALK-FORWARD exit choice | 140 | 54 | +26.5 | 69% | +688 | +3.68 | 72% | +1073/+302 | 4329 | +37138 | BEAR:2/+102 BULL:77/+30 MILD:61/+19 |
| (walk-forward chose) | 2025Q3:-50/+50/0.20, 2025Q4:-70/+90/0.25, 2026Q1:-70/+90/0.30, 2026Q2:-65/+90/0.30, 2026Q3:-65/+90/0.30 | | | | | | | | | | |
| PER-REGIME best (in-sample) | 140 | 54 | +36.5 | 71% | +946 | +4.40 | 76% | +1432/+460 | 3679 | +51088 | BEAR:2/+127 BULL:77/+41 MILD:61/+28 |
| (per-regime configs) | BULL:-75/+80/0.25, MILD:-65/+70/0.35, BEAR:-55/+70/0.30 | | | | | | | | | | |

## k = 2 picks per week (86 trades)

| exit | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BASE -50/+50/0.20 | 86 | 49 | +21.9 | 69% | +384 | +2.96 | 63% | +537/+238 | 2012 | +18837 | BEAR:1/-54 BULL:48/+27 MILD:37/+18 |
| IN-SAMPLE #1: -65/+90/0.30 | 86 | 49 | +32.3 | 63% | +567 | +2.28 | 63% | +961/+190 | 3405 | +27798 | BEAR:1/+55 BULL:48/+37 MILD:37/+26 |
| IN-SAMPLE #2: -65/+90/0.25 | 86 | 49 | +31.8 | 63% | +557 | +2.32 | 65% | +947/+184 | 3309 | +27316 | BEAR:1/+55 BULL:48/+37 MILD:37/+25 |
| IN-SAMPLE #3: -70/+90/0.30 | 86 | 49 | +31.6 | 63% | +555 | +2.21 | 63% | +981/+146 | 4083 | +27212 | BEAR:1/+55 BULL:48/+37 MILD:37/+24 |
| IN-SAMPLE #4: -60/+90/0.30 | 86 | 49 | +31.4 | 62% | +550 | +2.25 | 63% | +897/+218 | 3365 | +26964 | BEAR:1/+55 BULL:48/+38 MILD:37/+22 |
| IN-SAMPLE #5: -70/+90/0.25 | 86 | 49 | +31.1 | 63% | +546 | +2.24 | 65% | +968/+140 | 3987 | +26730 | BEAR:1/+55 BULL:48/+37 MILD:37/+23 |
| WALK-FORWARD exit choice | 86 | 49 | +21.4 | 64% | +376 | +2.30 | 67% | +576/+185 | 2501 | +18441 | BEAR:1/-47 BULL:48/+26 MILD:37/+18 |
| (walk-forward chose) | 2025Q3:-50/+50/0.20, 2025Q4:-70/+90/0.25, 2026Q1:-45/+90/0.30, 2026Q2:-65/+90/0.30, 2026Q3:-65/+90/0.30 | | | | | | | | | | |
| PER-REGIME best (in-sample) | 86 | 49 | +33.2 | 63% | +583 | +2.39 | 65% | +996/+186 | 3405 | +28547 | BEAR:1/+55 BULL:48/+38 MILD:37/+26 |
| (per-regime configs) | BULL:-60/+90/0.25, MILD:-65/+90/0.30, BEAR:-55/+70/0.15 | | | | | | | | | | |

READING: IN-SAMPLE and PER-REGIME rows are ceilings - the exit was chosen on the same trades it is scored on (210 trials). The WALK-FORWARD row is what a live system could have done: it picks the exit from the past only. The gap between them is the optimism a no-holdout number carries.
CAVEATS: label returns on the v3 basis; two years dominated by bull and mild tape; picks are ~3 a week so single trades move the weekly numbers.
