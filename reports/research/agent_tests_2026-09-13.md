# TRADING-AGENT TESTS - 2026-09-13

Bars were written in the script header before the run. Fine corpus 72659 rows (v3 basis), BASE exit for anything not about exits.

## A. Exit agent - walk-forward exit choice vs BASE (day means, v3 basis)

| book | rows | days | BASE %/day | WALK-FORWARD %/day | diff | paired t | WF halves | per-REGIME WF %/day | paired t | in-sample ceiling %/day | chosen (last 4 quarters) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| POOL | 72659 | 455 | -4.44 | -4.07 | +0.37 | +1.65 | -2.3/-5.8 | -3.81 | +2.45 | -3.95 | 2025Q4:-45/+90/0.15, 2026Q1:-45/+40/0.15, 2026Q2:-45/+40/0.15, 2026Q3:-45/+40/0.15 |
| FOLLOW_CALLS | 40954 | 455 | -0.01 | +0.72 | +0.74 | +1.01 | +2.5/-1.1 | +1.47 | +2.37 | +3.02 | 2025Q4:-75/+90/0.35, 2026Q1:-75/+90/0.35, 2026Q2:-75/+90/0.35, 2026Q3:-75/+90/0.35 |
| BULL_DIP | 4846 | 208 | +2.89 | +0.58 | -2.31 | -2.14 | +8.0/-6.8 | +0.58 | -2.14 | +3.45 | 2025Q4:-75/+90/0.35, 2026Q1:-75/+90/0.35, 2026Q2:-75/+90/0.35, 2026Q3:-50/+90/0.35 |
| DIP_CONF_MILD | 3438 | 79 | +0.19 | -0.60 | -0.79 | -0.88 | +2.0/-3.1 | -0.60 | -0.88 | +1.16 | 2025Q4:-65/+40/0.15, 2026Q1:-65/+40/0.15, 2026Q2:-45/+40/0.15, 2026Q3:-45/+40/0.15 |
| DIP_CONVEXITY | 3581 | 63 | +8.11 | +18.73 | +10.62 | +4.11 | -1.9/+38.7 | +18.73 | +4.11 | +25.23 | 2025Q4:-75/+90/0.35, 2026Q1:-75/+90/0.35, 2026Q2:-75/+90/0.35, 2026Q3:-75/+90/0.35 |

Exit agent bar (paired t >= 2.0 on the pool AND on >= 2 strategies): FAIL (pool no, strategies passing 1/4).

## B. Allocation agent - regime-aware budget vs the roster as it is (day means, BASE exit)

| policy | days | %/day | halves | paired t vs ROSTER | active days |
|---|---|---|---|---|---|
| POOL (every trigger) | 455 | -4.44 | -2.7/-6.2 | -4.32 | 455 |
| ROSTER (every firing strategy, equal) | 455 | +0.46 | +4.3/-3.4 | +0.00 | 455 |
| VETO (roster minus negative-prior strategies) | 455 | -0.09 | +1.7/-1.9 | -0.73 | 317 |
| WALK-FORWARD ALLOCATION (best prior strategy per regime, else cash) | 455 | +0.72 | +5.3/-3.9 | +0.26 | 225 |

last choices (quarter, regime -> strategy, prior %/day): 2026Q2 BEAR -> FOLLOW_CALLS (4.66); 2026Q2 BULL -> BULL_DIP (6.32); 2026Q2 MILD -> DIP_CONF_MILD (-1.05); 2026Q3 BEAR -> FOLLOW_CALLS (7.8); 2026Q3 BULL -> FOLLOW_CALLS (1.57); 2026Q3 MILD -> DIP_CONF_MILD (-1.33)

Allocation agent bar (paired t >= 2.0 vs ROSTER and positive second half): FAIL (t +0.26, second half -3.87).

## C. Execution agent - what our fills actually cost, and what a mid-price limit would have done

683 entry-fill events, 683 joined to a book record with a decision quote; terminal states: {'filled': 618, 'canceled': 57, 'expired': 8}

| measure | n | mean | median | p90 |
|---|---|---|---|---|
| fill vs decision ask, % of ask | 602 | -0.43 | +0.59 | +2.77 |
| fill vs limit, % | 602 | -31.25 | -30.29 | -5.72 |
| signal to fill, seconds | 602 | +46.04 | +8.45 | +12.22 |
| partial fills | 0 of 602 | | | |

| decision-ask band | orders | filled | cancelled/expired | fill rate | mean slip vs ask % |
|---|---|---|---|---|---|
| $0-1 | 204 | 192 | 12 | 94% | +0.08 |
| $1-4 | 376 | 339 | 37 | 90% | -0.60 |
| $4-10 | 49 | 44 | 5 | 90% | -1.91 |
| $10-up | 34 | 27 | 7 | 79% | +0.44 |

| decision spread band | orders | fill rate | mean slip vs ask % |
|---|---|---|---|
| 0-1% | 28 | 89% | +1.43 |
| 1-2% | 106 | 100% | +0.59 |
| 2-5% | 56 | 98% | +0.78 |
| 5-up% | 473 | 88% | -0.96 |

Mid-limit simulation on 42 filled orders whose contracts have hourly bars: a limit at the decision mid would have filled within two bars 95% of the time, saving 1.6% of premium on average; the trades it would have MISSED realized -51.2% (n 2) vs +0.6% for the ones it would have caught (n 32).
Execution agent bar (mid-limit fills >= 70% within two bars, saving >= 3%, missed trades not the winners): FAIL.

Reading: paper fills are a FLOOR on real costs (fill ledger header). The decision ask is the quote the engine priced its limit on; a positive slip means the fill printed above it.

## Verdicts

- Exit agent: FAIL
- Allocation agent: FAIL
- Execution agent: FAIL

A PASS means the agent is worth building and taking through the panel, the drill and the gate; a FAIL means the data we hold does not support it on the pre-registered bar, whatever a weaker bar would say.
