# Trailing the top end of a debit spread: measured, and it does not work

Owner question 2026-09-16 03:50 BST: the short leg caps the winners, can the cap be trailed?
`scripts/spread_trail_build.py` -> `reports/research/spread_trail_v1.jsonl` (gitignored,
rebuildable), analysed by `scripts/spread_trail_analyse.py`.

## The design

44,954 qualifying-print contract-days over 466 sessions, PAIRED: the same trade, same entry, same
exit rule, carried six ways.

| Arm | |
|---|---|
| single | buy the trigger contract outright |
| hold | buy it, sell the furthest strike that fits $1,000, hold the pair |
| buyback 50 / 100 | as hold, but once the position is +50% (or +100%) up, pay the short leg's ASK to close it and run the long leg uncapped |
| roll 50 / 100 | as hold, but at the trigger buy the short back and sell the next strike further out |

Accounting is in dollars against the ORIGINAL debit, so the arms stay comparable: closing the short
ADDS to what the trade has cost, selling a new one subtracts. Every leg is priced where it could
trade - sell at the bid, buy at the ask - so the buyback is charged at the ask exactly when it has
become expensive, which is the honest cost of the idea. Close-to-close basis, daily resolution: the
comparison between arms is the result, the levels are not comparable to a v3 cell.

## 1. Every trailing variant loses to simply holding

| Paired against holding the spread | $/trade | t | Halves |
|---|---|---|---|
| close the short at +50% | **-3.65** | -2.08 | -2.17 / -5.14 |
| close the short at +100% | **-5.36** | -4.26 | -3.67 / -7.04 |
| roll the short out at +50% | -1.08 | -1.75 | -0.25 / -1.91 |
| roll the short out at +100% | -0.56 | -1.26 | +0.09 / -1.21 |
| buy the option outright instead | -22.84 | -9.66 | -22.24 / -23.44 |

## 2. Why: most trades that trigger the trail then reverse

| | Fired on | Of those, ended WORSE than holding | Costing |
|---|---|---|---|
| close the short at +50% | 17.2% of trades (7,737) | **57.3%** | -$200 each |
| roll the short out at +50% | 13.8% (6,207) | 68.1% | -$96 each |

You pay to release the ceiling at the moment the option being bought back is most expensive, and the
trade then gives the move back more often than it extends it.

## 3. And the prize was never large

On the 1,740 trades where holding the spread made 100% or more:

| Arm | $/trade | mean |
|---|---|---|
| hold | +1,061 | +217.1% |
| close the short at +50% | +1,087 | +206.7% |
| roll the short out at +50% | +1,035 | +211.3% |
| close the short at +100% | +1,014 | +200.1% |

The best variant beats holding by $26 on the very best trades, and loses on everything else. The cap
was never tight: the rule already sells the furthest affordable strike, a median $33 apart on a
$5.40 option, so there is little ceiling left to raise.

## 4. What this settles, and one thing it confirms

- **The structure stands as it is.** Buy the spread, sell the furthest strike you can afford, leave
  it alone until the exit rule fires. Rolling is the least bad variant (-$0.56, t -1.26,
  indistinguishable from zero) but adds a second decision and a second order for nothing measurable.
- **The spread beat the outright buy again**, by $22.84 a trade at t -9.66, on a third independent
  sample built by different code. That result has now reproduced three times
  (spread_access v1, v2, and this run).

## 5. Honesty notes

- Paired throughout: every arm carries the same contract-days, so no arm is advantaged by selection.
- The absolute levels here differ from spread_access_v2 (different sample, seed and inclusion rule);
  only the within-run paired comparisons are claimed, which is the same discipline applied to the
  entry-timing and whole-market studies.
- 150 qualifying contract-days sampled per session, seed 23, recorded in the file header.
