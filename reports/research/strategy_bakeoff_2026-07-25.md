# Strategy bake-off — 2026-07-25

Research only (Lane A). **No strategy here is recommended or deployed**; deployment is a separate governed decision. Snapshot: `harvest_20260724_2130.db.gz`.

All figures use executable prices only (buy at the ask, mark/sell on the bid). The `independent bets` column is a cluster-aggregated effective sample size: a burst of near-identical bets on one ticker-day counts as roughly one bet.

> **Corrected 2026-07-25 after adversarial verification.** Five independent agents attacked this backtest's arithmetic; four found real defects, all fixed before these numbers were produced: spread entry legs were priced at two different instants; the debit-spread payoff lacked a floor at zero (13.8% of trades booked mathematically impossible losses); the effective-sample-size formula returned the raw trade count; and each structure split at its own median, making the out-of-sample columns non-comparable. A fifth found that the harness's PBO statistic itself was not CSCV — see the note under the overfitting section.

- universe: **24,617** candidates with usable non-stale paths
- synthesized strike pairs available for spread structures: **5,937**
- structures tested (each a counted trial): **12**

## (a) IN-SAMPLE — every structure on its whole applicable universe

| structure | trades | independent bets | win rate (wt) | avg net (wt) | total P&L per $800 | per trade |
|---|---|---|---|---|---|---|
| 1. naked long +30/-50 (baseline) | 24617 | 6806.0 | 0.209 | -0.205 | $-3,036,397 | -123.3/trade |
| 1b. naked long +15/-30 | 24617 | 6806.0 | 0.216 | -0.157 | $-2,344,521 | -95.2/trade |
| 1c. naked long +10/-20 | 24617 | 6806.0 | 0.201 | -0.122 | $-1,826,935 | -74.2/trade |
| 1d. naked long, 2h mark-out | 24617 | 6806.0 | 0.117 | -0.143 | $-1,975,483 | -80.2/trade |
| 2. debit spread (with flow), hold | 5472 | 1181.4 | 0.081 | -0.451 | $-1,640,216 | -299.7/trade |
| 2b. debit spread +50/-50 | 5472 | 1181.4 | 0.072 | -0.344 | $-1,292,237 | -236.2/trade |
| 3. credit spread (FADE flow), hold | 5388 | 1162.4 | 0.095 | -0.339 | $-1,176,263 | -218.3/trade |
| 3b. credit spread (FADE) +50/-100 | 5388 | 1162.4 | 0.093 | -0.359 | $-1,266,401 | -235.0/trade |
| 5. 2. high_iv: debit spread (with flow), hold | 515 | 196.4 | 0.074 | -0.525 | $-182,115 | -353.6/trade |
| 5. 2. low_iv: debit spread (with flow), hold | 473 | 153.9 | 0.086 | -0.461 | $-115,025 | -243.2/trade |
| 5. 3. high_iv: credit spread (FADE flow), hold | 487 | 186.1 | 0.079 | -0.375 | $-115,356 | -236.9/trade |
| 5. 3. low_iv: credit spread (FADE flow), hold | 472 | 150.6 | 0.112 | -0.322 | $-81,096 | -171.8/trade |

## (b) OUT-OF-SAMPLE — the later time half only (walk-forward)

A structure chosen on early data and applied to later data. One that only worked in a single stretch is exposed here.

| structure | trades | independent bets | win rate (wt) | avg net (wt) | total P&L per $800 | per trade |
|---|---|---|---|---|---|---|
| 1. naked long +30/-50 (baseline) [later half] | 12221 | 3444.9 | 0.202 | -0.200 | $-1,451,389 | -118.8/trade |
| 1b. naked long +15/-30 [later half] | 12221 | 3444.9 | 0.210 | -0.155 | $-1,127,264 | -92.2/trade |
| 1c. naked long +10/-20 [later half] | 12221 | 3444.9 | 0.197 | -0.121 | $-889,373 | -72.8/trade |
| 1d. naked long, 2h mark-out [later half] | 12221 | 3444.9 | 0.110 | -0.134 | $-889,827 | -72.8/trade |
| 2. debit spread (with flow), hold [later half] | 2789 | 586.4 | 0.074 | -0.457 | $-820,946 | -294.4/trade |
| 2b. debit spread +50/-50 [later half] | 2789 | 586.4 | 0.063 | -0.349 | $-656,971 | -235.6/trade |
| 3. credit spread (FADE flow), hold [later half] | 2758 | 578.3 | 0.098 | -0.347 | $-603,381 | -218.8/trade |
| 3b. credit spread (FADE) +50/-100 [later half] | 2758 | 578.3 | 0.097 | -0.368 | $-650,032 | -235.7/trade |
| 5. 2. high_iv: debit spread (with flow), hold [later half] | 270 | 101.5 | 0.100 | -0.491 | $-80,153 | -296.9/trade |
| 5. 2. low_iv: debit spread (with flow), hold [later half] | 216 | 63.3 | 0.056 | -0.503 | $-50,744 | -234.9/trade |
| 5. 3. high_iv: credit spread (FADE flow), hold [later half] | 259 | 96.3 | 0.085 | -0.377 | $-59,047 | -228.0/trade |
| 5. 3. low_iv: credit spread (FADE flow), hold [later half] | 218 | 65.2 | 0.117 | -0.333 | $-29,491 | -135.3/trade |

## Overfitting statistics across the structure SET

> The PBO implementation was **rewritten on 2026-07-25**: the previous version selected the winner on a row and ranked that same row, with no train/test separation. On pure-noise matrices it returned ~0.01 ('certainly not overfit') where correct CSCV returns ~0.53 — it would have certified a fluke. Numbers below use real CSCV (winner chosen on train rows, ranked among trials on held-out rows).

- **PBO (probability the best structure is a fluke): 0.0** CSCV over 20 partitions
- Deflated Sharpe of the champion: 0.0 
- champion by mean P&L across time groups: `1c. naked long +10/-20` (of 12 structures with coverage)

PBO and deflated Sharpe belong to the SEARCH, not to any single rule: they answer 'if I pick the best of these, how likely is it luck?'

## Cost-realism split (synthetic vs real spreads)

| structure / era | trades | independent bets | win rate (wt) | avg net (wt) | total P&L | per trade |
|---|---|---|---|---|---|---|
| 1. naked long +30/-50 (baseline) | pre-07-09 (SYNTHETIC costs) | 5974 | 2470.8 | 0.229 | -0.217 | $-773,146 | -129.4/trade |
| 1. naked long +30/-50 (baseline) | post-07-09 (REAL costs) | 18643 | 7880.5 | 0.203 | -0.201 | $-2,263,251 | -121.4/trade |
| 3. credit spread (FADE flow), hold | pre-07-09 (SYNTHETIC costs) | 1331 | 530.8 | 0.093 | -0.332 | $-277,585 | -208.6/trade |
| 3. credit spread (FADE flow), hold | post-07-09 (REAL costs) | 4057 | 1575.4 | 0.095 | -0.341 | $-898,678 | -221.5/trade |

## What this data CANNOT honestly tell us

- **3- and 5-day holds are NOT backtestable.** Stored option quotes cover ~1.6% of candidates at 3 trading days and ~0% at 5, because polling stops when a label resolves (~1 day median). Repricing with a constant-IV model would systematically overstate longer-hold returns (IV crush is a main reason these lose), so it was not done. The honest proxy is the underlying's own move at 3/5 days: 47–49% direction accuracy, negative mean (reports/discovery/stock_horizon_*.md).
- **Spread structures cover only the strike-pair subset**, which skews to the most actively harvested, most liquid names — so spread rows flatter a fleet-wide spread strategy. Coverage is stated above; treat spread rows as an upper bound.
- **Credit spreads assume close-before-expiry with no early assignment and no pin risk.** Quotes cannot model either; both are real risks absent from these numbers.
- **Regime split uses a reconstructed IV proxy** (median IV ratio from stored features, median 0.989), not the engine's own regime label, which is not stored per harvested candidate.
- **Model gating:** not run.
- **The engine's own 462 executed rows carry a synthetic entry price.** For `executed=1` candidates `entry_ref` is a closed-form model premium x1.01 (the limit price sent to the broker), not the quote actually paid — found by adversarial verification 2026-07-25. Those rows' measured returns are anchored on a price that was never traded. The fill ledger (live since the Phase-1 merge) records real fills and fixes this going forward; historical executed rows cannot be repaired in place.
- **History is ~3 weeks of one broadly calm regime**, costs synthetic before 2026-07-09 and real after, and the label horizon resolves in ~1 day. Nothing here speaks to a volatile regime, a crash, or a multi-week hold.
