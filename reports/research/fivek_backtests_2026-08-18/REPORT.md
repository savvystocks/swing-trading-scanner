# $5k strategy backtests - 2.5y real option bars (2026-08-18)

Trade-bar prices (not quotes); weeks with missing legs skipped and counted; the
naked put is the untradable-at-5k REFERENCE for what the credit spread gives up.

| strategy (1 lot) | periods | total P&L | win% | worst period | max drawdown |
|---|---|---|---|---|---|
| NAKED_PUT_W SPY (reference) | 114 | $+3,831 | 89% | $-3,921 | $-4,559 |
| CREDIT_SPREAD_W SPY | 114 | $+2,302 | 88% | $-929 | $-1,584 |
| CONDOR_W | 89 | $-3,020 | 75% | $-899 | $-4,079 |
| WHEEL_CSP_F | 23 | $+92 | 91% | $-86 | $-86 |

DEBIT_SPREAD (vertical, real short legs): 53 trades/51d day-mean +16.61% t=1.25
LONG-ONLY same sample (comparison):      53 trades/51d day-mean +18.78% t=1.52

coverage: 114/114 weeks priced for spreads; sensitivity: a 20% credit
haircut scales spread P&L roughly linearly - apply mentally before believing totals.
