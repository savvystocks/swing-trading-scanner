# ROADMAP TEST BATTERY - 2026-08-28

## A. Execution alpha (same trades, entry price discipline)

ask = pay the ask (current); mid+25 = limit filled a quarter-spread above mid
(realistic patient order); mid = perfect mid fill (upper bound). Exits unchanged.

| cohort | entry=ask | entry=mid+25% | entry=mid | reclaimed (realistic) |
|---|---|---|---|---|
| FADE_bear_live | +9.5%/d (t+2.1) | +10.0% | +10.2% | **+0.5 pts/day** |
| DIP_CONVEXITY | +52.9%/d (t+8.9) | +53.7% | +54.0% | **+0.8 pts/day** |
| CONSENSUS_CALLS | +9.8%/d (t+6.2) | +10.4% | +10.6% | **+0.6 pts/day** |
| FOLLOW_CALLS | +9.3%/d (t+7.3) | +9.9% | +10.1% | **+0.6 pts/day** |

## B. True-trigger entry timing (same-day after the print vs next session)

trades with real print timestamps + same-day bars: 6650
  ENTER SAME-DAY (first close after print): +2.3%/day t+1.50
  ENTER NEXT SESSION (current rule):        +0.8%/day t+0.56
  TIMING VALUE: +1.5 pts/day

## C. Student v2 - trained on hourly-truth outcomes

cohort 101838 trades | day-grouped OOF AUC: 0.629
  TOP-DECILE picks : +21.2%/day t+11.95 (n=10184)
  the rest         : +0.5%/day t+0.78
  RANKING LIFT: +20.7 pts/day

## D. Regime-aware sizing (flat $1k vs scaled) on the proven book

| | total P&L | worst day | max drawdown |
|---|---|---|---|
| flat $1k | $+71,845 | $-818 | $-5,984 |
| regime-scaled | $+82,991 | $-1,052 | $-8,051 |

scaling multiplies return 1.16x with drawdown 1.35x
