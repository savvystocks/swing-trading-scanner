# STUDENT FORMULA SEARCH - 2026-09-11
rows 70976 (search 60512, holdout 10464); 72 configurations on the SEARCH window (before 2026-03-01); walk-forward quarterly refits; $1,000 per trade.

## Search window - ranked by weekly t (consistency), >= 40 trades

| config | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean | all regimes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXPRET/ALL/BASE/k3 | 61 | 25 | +19.9 | 57% | +484 | +1.97 | 68% | +495/+475 | 2302 | +12112 | BULL:44/+12 MILD:17/+39 | no |
| EXPRET/CALLS/WIDE/k3 | 48 | 23 | +31.9 | 50% | +665 | +1.37 | 48% | +1286/+95 | 5073 | +15293 | BULL:35/+32 MILD:13/+31 | no |
| PBIG/CALLS/WIDE/k3 | 54 | 23 | +14.1 | 52% | +330 | +1.30 | 57% | +174/+474 | 3156 | +7599 | BULL:38/+11 MILD:16/+22 | no |
| EXPRET/ALL/BASE/k2 | 42 | 24 | +17.5 | 52% | +306 | +1.18 | 46% | +297/+316 | 1848 | +7348 | BULL:30/+3 MILD:12/+53 | no |
| PWIN/AFFORD/BASE/k3 | 74 | 28 | +7.1 | 53% | +187 | +0.89 | 54% | +368/+7 | 4123 | +5245 | BULL:49/+14 MILD:25/-6 | no |
| PWIN/AFFORD/BASE/k2 | 44 | 23 | +8.6 | 57% | +164 | +0.83 | 48% | +128/+197 | 2562 | +3778 | BULL:31/+16 MILD:13/-9 | no |
| EXPRET/CALLS/BASE/k3 | 43 | 19 | +8.2 | 53% | +186 | +0.63 | 58% | +287/+94 | 3597 | +3526 | BULL:32/+18 MILD:11/-21 | no |
| EXPRET/FADE/BASE/k3 | 42 | 18 | +13.3 | 45% | +310 | +0.60 | 56% | -299/+918 | 5360 | +5574 | BULL:12/-38 MILD:30/+34 | no |
| PBIG/CALLS/BASE/k3 | 49 | 22 | +4.3 | 55% | +95 | +0.48 | 41% | +131/+59 | 1709 | +2092 | BULL:44/+6 MILD:5/-12 | no |
| EXPRET/FADE/WIDE/k3 | 40 | 16 | +5.2 | 50% | +129 | +0.33 | 44% | -215/+474 | 3763 | +2067 | BULL:20/-21 MILD:20/+31 | no |
| PBIG/AFFORD/WIDE/k2 | 43 | 23 | -5.6 | 49% | -104 | -0.51 | 35% | -38/-165 | 3880 | -2398 | BULL:30/+8 MILD:13/-36 | no |
| EXPRET/ALL/WIDE/k3 | 56 | 25 | -4.5 | 48% | -101 | -0.52 | 48% | +101/-287 | 7159 | -2521 | BULL:41/-2 MILD:15/-12 | no |
| PWIN/FADE/WIDE/k3 | 41 | 16 | -13.0 | 39% | -334 | -0.80 | 31% | -578/-89 | 5095 | -5336 | BULL:21/-31 MILD:20/+6 | no |
| EXPRET/AFFORD/BASE/k3 | 62 | 24 | -7.7 | 40% | -199 | -0.92 | 25% | -109/-288 | 6405 | -4765 | BULL:44/+4 MILD:18/-36 | no |
| PBIG/AFFORD/WIDE/k3 | 73 | 26 | -9.6 | 47% | -268 | -1.04 | 38% | -165/-371 | 8636 | -6972 | BULL:49/+2 MILD:24/-34 | no |
| PBIG/ALL/WIDE/k3 | 59 | 23 | -15.2 | 37% | -390 | -1.10 | 35% | -1068/+231 | 11754 | -8979 | BULL:35/-37 MILD:24/+17 | no |
| PBIG/AFFORD/BASE/k2 | 48 | 27 | -11.2 | 40% | -200 | -1.24 | 30% | +49/-430 | 6798 | -5389 | BULL:30/-1 MILD:18/-27 | no |
| PWIN/AFFORD/WIDE/k3 | 65 | 30 | -12.6 | 45% | -273 | -1.37 | 37% | +6/-552 | 10042 | -8201 | BULL:37/-1 MILD:28/-28 | no |
| PBIG/AFFORD/BASE/k3 | 79 | 29 | -13.3 | 35% | -362 | -1.61 | 41% | -74/-632 | 12428 | -10504 | BULL:45/-1 MILD:34/-30 | no |
| EXPRET/AFFORD/WIDE/k2 | 48 | 26 | -17.4 | 38% | -322 | -2.05 | 35% | -166/-478 | 9648 | -8370 | BULL:29/-9 MILD:19/-30 | no |
| PBIG/ALL/BASE/k3 | 55 | 25 | -14.3 | 38% | -314 | -2.05 | 36% | -384/-250 | 9411 | -7858 | BULL:38/-13 MILD:17/-18 | no |
| EXPRET/AFFORD/WIDE/k3 | 76 | 28 | -20.0 | 37% | -544 | -2.40 | 32% | -55/-1032 | 19267 | -15221 | BULL:44/-5 MILD:32/-40 | no |

## Baselines on the search window (BASE exit)

| config | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean | all regimes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RANDOM k1 (200 draws) | - | - | - | - | - | median -0.70, 95th pct +0.85 | - | - | - | - | - | - |
| TOP-PREMIUM k1 | 68 | 68 | +5.1 | 47% | +51 | +0.55 | 47% | +2/+100 | 4840 | +3479 | BEAR:9/-4 BULL:28/-10 MILD:31/+22 | no |
| RANDOM k2 (200 draws) | - | - | - | - | - | median -0.77, 95th pct +0.85 | - | - | - | - | - | - |
| TOP-PREMIUM k2 | 136 | 68 | -1.1 | 46% | -21 | -0.20 | 46% | +15/-57 | 8535 | -1436 | BEAR:18/+10 BULL:56/-11 MILD:62/+5 | no |
| RANDOM k3 (200 draws) | - | - | - | - | - | median -1.07, 95th pct +0.53 | - | - | - | - | - | - |
| TOP-PREMIUM k3 | 204 | 68 | -0.2 | 48% | -5 | -0.04 | 43% | +55/-65 | 10635 | -356 | BEAR:27/+11 BULL:84/-8 MILD:93/+3 | no |
| POOL (every trade) | 60512 | 68 | -2.9 | 46% | -25851 | -4.16 | 29% | -22938/-28765 | 1756284 | -1757895 | BEAR:5183/+1 BULL:33882/-3 MILD:21447/-4 | no |

## Pre-registered winner

EXPRET/ALL/BASE/k3 - chosen by weekly t (NO config carried the all-regimes flag; top by t instead).

## Holdout (2026-03-01 onward) - touched once, winner only

| config | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean | all regimes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| HOLDOUT EXPRET/ALL/BASE/k3 | 41 | 18 | +49.9 | 66% | +1135 | +2.20 | 78% | +883/+1388 | 1216 | +20439 | BEAR:12/+61 BULL:15/+18 MILD:14/+74 | YES |
| HOLDOUT POOL (every trade) | 10464 | 27 | -6.1 | 43% | -23664 | -4.63 | 19% | -23245/-24053 | 610286 | -638924 | BEAR:1885/-1 BULL:4830/-7 MILD:3749/-7 | no |
| HOLDOUT RANDOM k3 (200 draws) | - | - | - | - | - | median -1.10, 95th pct +0.55 | - | - | - | - | - | - |

## The formula the student found (winner stream, final search-window fit)

Feature importances (permutation, top 10):
- side: +0.0596
- reg: +0.0457
- sp: +0.0333
- entry_ask: +0.0157
- iv_prev: +0.0085
- dte: +0.0072
- spread_frac: +0.0063
- smd: +0.0046
- hour: +0.0020
- oi_prev: +0.0016

Picked-trade profile vs the cohort (medians, search window):

| feature | picked | cohort |
|---|---|---|
| side | 1 | 1 |
| dte | 45 | 36 |
| hour | 15.4 | 15.9 |
| dow | 1 | 2 |
| reg | 3.17 | 2.35 |
| sp | 1.37 | 1.05 |
| smd | 0.51 | 1.46 |
| entry_ask | 15.2 | 10.9 |
| spread_frac | 0.0196 | 0.0101 |
| cum_prem | 6.97e+04 | 7.67e+04 |
| ask_share | 1 | 1 |
| mins_since_first | 0 | 0 |
| oi_prev | 3.07e+03 | 1.1e+03 |
| prem_oi_asof | 20 | 76.5 |
| iv_prev | 0.385 | 0.413 |

CAVEATS: label returns on the executable basis (ask at the print, bid-side exits) with no live friction beyond the spread; two years dominated by bull and mild tape (bear ~12% of days); 72 configurations searched - the search-window numbers are selection-biased by construction, which is why only the holdout row is evidence. A weekly-budget picker is implementable live as written (threshold on prior scores, cap per ISO week).
