# Why the probes do not fill: the funnel and the archive's verdict on loosening it

Owner question, 2026-09-15 00:35 BST: "the control has all the fills, why do the rest of the
strategies have no fills? we need to loosen the parameters so it actually trades. what are the
limiting factors?" Owner ruling after this report: keep the $1,000 slot; ship only the loosenings
the archive supports (spread cap 3%, DIP_CONVEXITY on SPY-below-50d, probes freed from the
control's held names). The price-band amendment was offered and declined for now.

Data: the 31 completed in-session engine cycles of Monday 2026-09-14 (GitHub run logs), the
book (`proactive_sandbox_logs.json`), and the v3 corpus (`reports/research/probe_tuner_rows_v3.jsonl`,
72,659 rows, 455 days, ask_at_qualifying_print basis, bid-side exits). Day means; "vs pool" is the
mean of (cell day mean - same-day pool mean); t is over those daily differences.

## 1. The funnel on 2026-09-14

| Stage | Count | Note |
|---|---|---|
| Names per cycle from the UW scan | 2-16, median 9 | 600 alerts >= $50k premium; pre-filtered at source to $0.30-$4.00 contracts plus the $4-$9 call pool and the student pool |
| Blocked: a book already holds the name | 71 | QQQ 10, SPY 7, NVDA 7, SLV 7, IBIT 7, PLTR 5, AAPL 4. The control is a PROBE-book record, so its positions blocked every other probe |
| Dropped on the live pre-quote (spread > 4% or no quote) | 90 | before any probe saw the name |
| Names reaching the probe filters | 0-5 per cycle, median 2 | |
| Probe-level skips | spread cap 64, price cap 34 | real spreads on capped names: median 6.8%, 8% under 3%, 27% under 4% |
| Regime | MILD every cycle | BULL_DIP needs SPY > +2% vs 50d (last 2026-09-03; 6 of the last 20 sessions); DIP_CONVEXITY needs < -2% (0 of the last 60; 10 of the last 120); DIP_CONF_MILD was ON every session since the cut (SPY below its 20d) and took SLV and GLD |
| Attempt budget (10 sweeps per cycle) | exhausted in 2 of 24 empty cycles | not a limiter |

Entries since the roster cut (2026-09-10 to 09-14): EXEC_BASELINE 11, WINNER_PROFILE 3, DIP_CONF_MILD 2,
FOLLOW_CALLS 2, CREDIT_SPREAD_W 1 weekly, BULL_DIP 0, DIP_CONVEXITY 0.

The court does not demote for silence: 0/8 is HOLD. Demotion needs negative evidence.

## 2. Loosening the regime and dip conditions (BASE exit -50/+50/0.20)

BULL_DIP (calls, ticker below its 20d, SPY-50d threshold):

| threshold | days | own/day | vs pool | t | halves |
|---|---|---|---|---|---|
| > +2.0 (current) | 208 (46%) | +2.88 | +7.40 | 3.94 | +9.8 / -4.0 |
| > +1.5 | 257 (56%) | +0.34 | +4.99 | 2.92 | +9.4 / -8.6 |
| > +1.0 | 292 (64%) | -0.67 | +4.13 | 2.56 | +8.3 / -9.7 |
| > +0.0 | 340 (75%) | -1.13 | +3.81 | 2.49 | +6.0 / -8.3 |

Verdict: widening buys fills that lose on their own return. Not loosened.

DIP_CONF_MILD (calls, |SPY-50d| <= 2, ticker below 20d, SPY below 20d): current own +0.16, vs pool
+7.29, t 2.25 on 79 days. Dropping the SPY-below-20d condition: own -5.25, t 0.35. Dropping the
ticker-below-20d condition: own -1.35, t 2.19. Verdict: the confirmation is the strategy. Not loosened.

DIP_CONVEXITY, the LIVE cell (calls, SPY below its 20d, SPY-50d threshold), both exits:

| threshold | days | BASE own/day, t | WIDE (-70/+80/0.30) own/day, t, halves |
|---|---|---|---|
| < -2.0 (current) | 56 (12%) | +8.38, 2.34 | +19.19, 3.33, +3.0 / +35.4 |
| < -1.0 | 66 (15%) | +7.31, 2.71 | +15.54, 3.59, +4.7 / +26.4 |
| < -0.5 | 86 (19%) | +5.13, 2.66 | +11.92, 3.82, +1.4 / +22.5 |
| < 0.0 | 103 (23%) | +3.79, 2.70 | +8.75, 3.72, +5.3 / +12.2 |

Verdict: at "SPY below its 50-day" the edge survives on both exits, t rises with the day count,
both halves positive on the exit the seat runs. Loosened to < 0. Honesty: this threshold is a
post-hoc pick from a 4-point grid on the same corpus (t flat 3.3-3.8 and both halves positive at
every cut, so a fluke is unlikely, but it is not a holdout); and in the $4-9.90 band the slot can buy
the cell is own -2.33/day (t 0.36) at < 0 and +1.88 (t -0.03) at < -2 (section 4) - the loosening
keeps the cell's edge, it does not make the executable slice positive. Note the ledger's archive cell
omitted the SPY-below-20d confirmation and ran the BASE exit; both corrected in the same commit.
SPY has been below its 50-day on 1 of the last 60 sessions, so this changes little this month.

## 3. The spread cap (alert spread in the corpus; the live cap is on the real quote)

| cell | <= 2% t | <= 3% t | <= 4% t |
|---|---|---|---|
| BULL_DIP | 3.96 | 3.97 | 3.88 |
| DIP_CONF_MILD | 1.79 | 1.93 | 1.99 |
| DIP_CONVEXITY | 2.02 | 2.19 | 2.14 |
| FOLLOW_CALLS | 3.84 | 4.17 | 4.15 |

Pool spread distribution: p50 1.0%, p75 1.7%, p90 2.6%. Verdict: 3% keeps every cell's t. Loosened
to 3%. It recovers few names: of the real spreads that hit the cap on 09-14, 8% were under 3%.
Honesty: the corpus column is the alert-time spread; the live cap gates a fresh quote at attempted
entry. Correlated, not the same quantity; the conclusion is directional, not a measurement of the
live cap.

## 4. The price band (the finding that matters; spread <= 3%)

Own return per day (t vs pool) by contract ask:

| cell | $4-9.90 (the live band) | $9.90-16 | $16-25 | $25-40 | over $40 |
|---|---|---|---|---|---|
| BULL_DIP | +0.02 (1.19) | +3.57 (2.55) | +13.13 (4.31) | +17.04 (5.17) | +5.60 (3.30) |
| DIP_CONF_MILD | -7.03 (0.00) | +2.97 (1.83) | +3.83 (2.21) | +4.37 (1.76) | +6.25 (3.56) |
| DIP_CONVEXITY (< -2, BASE) | -4.04 (-0.72) | +3.22 (0.68) | +10.40 (1.93) | +8.37 (1.43) | +42.99 (9.05) |
| DIP_CONVEXITY (< 0, sp < 0, WIDE) | -2.33 (0.36) | | | | |
| FOLLOW_CALLS | -3.72 (0.42) | +0.41 (3.17) | +5.94 (5.70) | +5.49 (5.81) | +10.60 (11.16) |
| pool | -5.11 (-1.11) | -3.89 (0.74) | +2.57 (7.42) | +3.63 (7.27) | +4.15 (10.16) |

The archive edges the court cites were measured on whole cells; 54% of the pool is priced above
$9.90. Under the $1,000 slot the probes trade the slice below it, where every cell is flat or
negative on its own return. The pattern is monotonic across all cells and the pool (t 7-13 on
the pool bands). Mechanism: cheap contracts are far out of the money and short dated; the
executable spread and time decay eat them. FOLLOW_CALLS at -61.9% per trade live (n 3) is what
its band predicts. The cheap tail the scan is pre-filtered to ($0.30-$4.00) is the worst slice
of all: pool -14.5/day, t -10.9.

This is the 2026-09-09 instrument-mismatch class inside our own cells. Widening any filter while
keeping the slot only adds more of the no-edge slice. The slot is charter (NORTH_STAR), not a
parameter; raising it is the owner's amendment. Offered 2026-09-15 with these numbers; declined
for now (ROADMAP decision 41). Caveat (data honesty): the band split is a post-hoc cut on the
same corpus that produced the cells; the monotone pattern and the size of the pool t-stats make
a fluke unlikely, but a pre-registered cell on fresh days is the standard, and the court is it.

## 5. What ships (owner ruling)

1. `entry.max_spread_pct` 2.0 -> 3.0 (the fade path shares the cap; it is near-dormant).
2. DIP_CONVEXITY's regime gate: the PRIOR-CLOSE SPY below its 50-day and its 20-day
   (`fade_book.spy_prev_readings`, the archive's d1_close basis); one helper used by the loop gate and the filter; the ledger cell re-cut to the
   live cell (calls, reg < 0, sp < 0) on the exit the seat runs.
3. Probes no longer blocked by another strategy's older position on the same underlying: a probe
   blocks only on its own strategy's open record, on any record entered today, and on any pending
   entry order; the contract-level guard (`occ_collision`, one record per contract, ever) stays.
   Both places that decide it changed: `ticker_blocked` and the roster loop's own pre-filter
   (`_roster_open_sets`), which the panel found would otherwise have kept blocking.
4. MOT 6.23 and drill scenario 8 guard all three.

Not done: the price band (owner's call), an engine_watch row for cancelled runs (owed), the
three-minute fixed cost per run (next profile).
