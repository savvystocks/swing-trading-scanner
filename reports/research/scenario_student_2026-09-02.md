# SCENARIO STUDENT - 2026-09-02

corpus: 316312 scenario outcomes (39539 real triggers x 8 exit configs, true-trigger hourly replays; labels are BAR-PRICE - shape of edge, not executable)

skill: day-grouped OOF AUC 0.621 | strict walk-forward AUC 0.585
ranking lift (walk-forward): top-decile picks +13.7%/day vs rest +1.0%/day = +12.6 pts/day

## What carries signal (permutation importance, walk-forward slice)
| variable | importance | live system gates on it? |
|---|---|---|
| ask | +0.0289 | NO - candidate missed variable |
| sp | +0.0261 | yes/partial |
| dte | +0.0252 | NO - candidate missed variable |
| reg | +0.0237 | yes/partial |
| trig | +0.0214 | yes/partial |
| side_call | +0.0159 | yes/partial |
| stop | +0.0045 | yes/partial |
| smd | +0.0030 | yes/partial |
| weekday | +0.0021 | NO - candidate missed variable |
| prem | +0.0008 | no (weak) |
| prem_band_whale | +0.0000 | yes/partial |
| give | +0.0000 | yes/partial |
| price_band_49 | -0.0000 | yes/partial |

## Conditional skill (walk-forward AUC by slice)
  bull: AUC 0.555 (n=18288)
  mild: AUC 0.626 (n=15800)
  exit (-50.0, 50.0, 0.2): AUC 0.563
  exit (-50.0, 80.0, 0.3): AUC 0.580
  exit (-50.0, 80.0, 0.2): AUC 0.580
  exit (-50.0, 50.0, 0.3): AUC 0.563
  exit (-70.0, 50.0, 0.2): AUC 0.562
  exit (-70.0, 80.0, 0.3): AUC 0.573
  exit (-70.0, 80.0, 0.2): AUC 0.573
  exit (-70.0, 50.0, 0.3): AUC 0.562

GUARDRAILS: research instrument only - wires into nothing; any use walks the
META_SELECT gate (virgin days + owner sign-off). Replay labels flatter returns;
the AUC (rank skill) is the honest number here, not the day-means.
