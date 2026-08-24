# Executable-price restudy - 2026-08-23

THE HONESTY PASS. Entry at the ASK, outcomes on the BID (project rule), live exits.
Every other archive result today used VWAP->VWAP and is therefore spread-optimistic.
'pass2%' = share of the bucket that would clear the LIVE book's <=2% spread filter -
an edge in contracts we cannot trade is not an edge.

## Delta x DTE (executable day-mean %, n)

| delta \ DTE | 0-7d | 8-21d | 22-45d | 46-90d | 91-400d |
|---|---|---|---|---|---|
| 0.05-0.15 | +8.8 (11009) | -0.6 (9127) | -0.7 (6557) | +2.0 (2486) | +6.7 (5167) |
| 0.15-0.30 | +9.8 (12497) | -3.6 (16357) | -3.5 (14198) | -2.5 (3819) | +4.0 (10314) |
| 0.30-0.45 | -3.7 (8729) | -5.0 (17921) | -4.6 (15604) | -8.2 (3900) | -4.2 (10898) |
| 0.45-0.60 | -7.1 (6510) | -8.9 (16565) | -9.7 (17225) | -9.2 (4217) | -3.7 (10149) |
| 0.60-0.80 | -11.9 (5664) | -13.4 (9801) | -11.5 (7221) | -9.6 (1816) | -4.6 (6020) |
| 0.80-1.01 | -17.3 (5362) | -15.8 (6073) | -13.3 (3552) | -13.1 (1360) | -9.1 (3026) |

## Spread reality

| bucket | median spread | pass<=2% | executable day-mean | t | tradeable day-mean (spread<=2%) |
|---|---|---|---|---|---|
| delta 0.05-0.15 | 5.9% | 9.4% | +2.67% | +0.96 | -14.92% (n=3342) |
| delta 0.15-0.30 | 5.8% | 13.0% | +0.39% | +0.28 | -7.55% (n=7786) |
| delta 0.30-0.45 | 5.2% | 15.1% | -4.35% | -5.01 | -9.25% (n=9070) |
| delta 0.45-0.60 | 4.8% | 17.3% | -7.30% | -10.20 | -9.15% (n=9919) |
| delta 0.60-0.80 | 5.3% | 15.7% | -9.85% | -14.16 | -10.41% (n=5212) |
| delta 0.80-1.01 | 6.2% | 14.1% | -13.11% | -25.75 | -10.46% (n=2904) |
| DTE 0-7d | 6.3% | 10.2% | +1.70% | +0.43 | -13.66% (n=5484) |
| DTE 8-21d | 5.6% | 12.7% | -7.42% | -6.59 | -12.24% (n=9929) |
| DTE 22-45d | 5.9% | 12.2% | -6.70% | -5.64 | -10.16% (n=7982) |
| DTE 46-90d | 4.5% | 21.3% | -3.68% | -1.90 | -7.97% (n=3891) |
| DTE 91-400d | 4.3% | 20.7% | -1.50% | -1.82 | -5.35% (n=9668) |

## Headline strategies, rebased (executable, and tradeable = spread<=2%)

| strategy | executable mean/t | halves | tradeable mean/t (spread<=2%) |
|---|---|---|---|
| FADE (all) | -7.17%/-3.08 | -6/-8 | -10.21%/-4.49 (n=16623) |
| FADE bear-regime | +33.12%/+2.64 | +27/+40 | +24.39%/+2.49 (n=1462) |
| FADE bull-regime | -19.05%/-8.93 | -22/-16 | -21.06%/-8.38 (n=10080) |
| CONSENSUS | -0.29%/-0.14 | -2/+2 | -7.40%/-3.37 (n=13594) |
| CONSENSUS+calls | +8.63%/+3.29 | +4/+14 | +0.69%/+0.24 (n=10593) |
| FOLLOW+calls | +6.59%/+3.35 | +7/+6 | +1.50%/+0.71 (n=18505) |
