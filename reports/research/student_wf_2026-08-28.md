# STUDENT V2 - STRICT WALK-FORWARD - 2026-08-28

## 1. train<2026 -> test 2026

test AUC 0.501 | picked 7% of test trades
  TOP picks (train-set decile cut): +10.1%/day t+2.86 (n=1349, 102d)
  REST: +1.2%/day t+1.01
  WALK-FORWARD LIFT: +8.9 pts/day

## 2. Rolling quarters (train on all history before Q, test Q)

| test quarter | AUC | top-decile mean/t | rest mean | lift |
|---|---|---|---|---|
| 2025-01 | 0.393 | -8.3/t-2.8 | +8.0 | -16.3 |
| 2025-04 | 0.529 | +10.2/t+2.4 | +5.5 | +4.7 |
| 2025-07 | 0.673 | +32.8/t+12.3 | +4.4 | +28.4 |
| 2025-10 | 0.483 | -2.9/t-0.7 | +2.3 | -5.2 |
| 2026-01 | 0.456 | +8.2/t+1.2 | +2.3 | +5.9 |
| 2026-04 | 0.543 | +13.1/t+3.0 | -0.3 | +13.4 |
| 2026-07 | 0.617 | +8.8/t+1.1 | -0.7 | +9.5 |

quarters with POSITIVE lift: 5/7 | median lift +5.9 pts/day
