# The debit spread: the biggest improvement found this week, and not for the reason proposed

Owner order 2026-09-16 01:54 BST. `scripts/spread_access_build.py` ->
`reports/research/spread_access_v1.jsonl` (gitignored, rebuildable), analysed by
`scripts/spread_access_analyse.py`.

## The design

One population - qualifying flow prints (cumulative premium >= $50k, ask-side), the same universe as
the entry-timing study - priced two ways on the SAME contract-day:

- **SINGLE**: buy the trigger contract outright, if the budget affords it.
- **SPREAD**: buy it and sell the furthest same-expiry strike whose credit still brings the net
  debit inside the budget, so the rule keeps the most upside subject to affording it.

Unwound at long bid minus short ask, the price you could actually get, never a mid. Exits BASE
-50 / +50 / 0.20. Three budgets side by side. Close-to-close basis (both legs from
`contracts_daily` NBBO), so SPREAD-vs-SINGLE is the result and the levels are not comparable to a
v3 cell.

## 1. The spread beats the single at every budget

Paired, same contract-day:

| Budget | Spread minus single | t | Halves | Paired n |
|---|---|---|---|---|
| $1,000 | **+4.82 pts/day** | +6.04 | +5.3 / +4.3 | 4,553 |
| $1,600 | +4.68 | +6.43 | +4.3 / +5.0 | 6,901 |
| $2,500 | +3.59 | +6.48 | +3.1 / +4.0 | 9,170 |

Levels, for context (whole qualifying-print universe, not a strategy cell):

| Budget | Outright | Spread |
|---|---|---|
| $1,000 | -7.77/day | -6.34 |
| $1,600 | -5.31 | -2.34 |
| $2,500 | -3.95 | -0.32 (halves +1.6 / -2.2) |

## 2. The proposed mechanism was WRONG

The idea was that a spread buys access to the $16+ band where the edge lives. It does not pay:

| Spread on legs too expensive to buy outright | Return |
|---|---|
| budget $1,000 (median leg $20, width $20, debit $895) | **-11.25/day**, t -18.49 |
| budget $1,600 (median leg $27, width $30, debit $1,470) | -8.87/day |
| budget $2,500 (median leg $37.60, width $45, debit $2,320) | -9.07/day |

Reaching for expensive legs through a spread is worse than the spread average. That thesis is dead.

## 3. The real mechanism: it cuts the losers harder than it cuts the winners

Budget $1,000, 4,553 paired trades:

| | Count | As a single | As a spread | Change |
|---|---|---|---|---|
| trades that hit the stop | 2,289 (50%) | -50.0% | **-38.5%** | +11.5 saved each |
| trades that returned >= +100% | 294 (6%) | +213.0% | +191.8% | -21.2 given up each |

2,289 losers x 11.5 points saved against 294 winners x 21.2 given up. The short leg is paid for by
the losers, and there are eight times as many of them. This is the opposite of the usual objection
to spreads (that capping the tail kills a tail-driven book) - measured, the cap costs 10% of the
winners' return and buys 23% off every loser.

## 4. Inside the strategy cells - improvement established, level not yet

Joined to the court's corpus by (occ, day); the v1 sample (40/day) is too thin for the narrow cells.

| Cell, budget $1,000, paired | Single | Spread | Diff | t | Diff halves |
|---|---|---|---|---|---|
| FOLLOW_CALLS (n 1,088) | -2.54 | **+2.85** | +5.39 | +2.95 | +5.5 / +5.3 |
| WINNER_PROFILE (n 2,062) | -11.24 | -5.10 | +6.15 | +5.08 | +5.5 / +6.8 |
| POOL (n 2,084) | -11.11 | -5.02 | +6.09 | +5.03 | +5.4 / +6.8 |
| DIP_CONVEXITY (n 248) | +1.88 | +4.05 | +2.17 | +0.60 | thin |
| BULL_DIP (n 112), DIP_CONF_MILD (n 122) | - | - | - | - | too thin |

The IMPROVEMENT is consistent and significant everywhere it can be measured. The LEVEL inside each
cell is not resolved, and BULL_DIP - the cell with the cleanest positive base - is the one still
unmeasured. A deeper run (`scripts/spread_access_build_v2.py`, 260/day) is queued for exactly that.

## 5. What this does and does not license

- It does NOT license an engine change yet. Section 4 is why: the cell that matters most has 112
  rows, and this is a close-to-close basis.
- It DOES make the spread the most promising structural change measured this week, worth roughly
  twice the position-size increase (+4.7 vs +2.5 points), available at the current $1,000 slot, and
  requiring no charter amendment.
- The next gate is the v2 run: if BULL_DIP's spread level holds positive in both halves with a real
  sample, that is the case for building it.
