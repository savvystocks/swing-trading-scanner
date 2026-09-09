# CAPTURE RATIO - 2026-09-09
Live realized vs archive expected, SAME strategy, SAME calendar days.
capture = live day-mean / archive day-mean on those days. THIN = under 5 shared days (reported for completeness, never a verdict).

GAP = live minus archive in percentage points (the ratio is UNDEFINED when the archive day-mean sits near zero - a division that produced -2530x on the first run). MEDIAN columns resist a single monster trade dominating a small sample.

| strategy | shared days | live mean | arch mean | GAP | live med | arch med | GAP med | note |
|---|---|---|---|---|---|---|---|---|
| CONSENSUS | 11 | -20.58 | +0.01 | -20.59 | -48.20 | -0.18 | -48.02 |  |
| DP_HEAVY | 4 | -29.60 | -6.93 | -22.67 | -33.55 | -6.45 | -27.10 | THIN |
| EXEC_BASELINE | 11 | +26.90 | +1.84 | +25.05 | +5.70 | +4.67 | +1.03 |  |
| FADE_UNROUTED | 3 | -46.10 | -5.07 | -41.03 | -48.70 | -24.32 | -24.38 | THIN |
| QUIET_TAPE | 6 | -12.27 | -4.06 | -8.21 | -9.10 | -5.95 | -3.15 |  |

WEIGHTED (non-THIN rows, 28 strategy-days): live -0.15%/day vs archive -0.14%/day - GAP -0.01 points.

READING: a GAP near zero means the lab reproduces its backtest; a large negative GAP means the edge does not survive contact and must be attributed (execution friction, replay optimism, or selection) BEFORE any real-money gate passes, since every promotion bar is denominated in archive-scale returns. POWER WARNING: with this many days and option returns this skewed, no gap smaller than roughly 10 points is distinguishable from noise - this study is a measurement instrument that is not yet loaded, and its own honest output today is 'not enough closed evidence'.

CAVEATS: archive exits are bar-replays on the same config; live exits include real fills, slippage and the no-same-day rule. Live entries are at the ask; archive entries use the post-print bar close. Those differences ARE the friction this ratio is designed to expose - they are not a reason to discount it.

## STRUCTURAL FINDING - what the live book actually buys (occ_source audit, all PROBE fills)

| strategy | contract bought |
|---|---|
| DIP_CONF_MILD | uw_trigger_verbatim x1 |
| EXEC_BASELINE | alpaca_resolved x26, afford_fallback x6 |
| CONSENSUS | alpaca_resolved x19 |
| QUIET_TAPE | alpaca_resolved x10 |
| DP_HEAVY | alpaca_resolved x5 |
| FADE_UNROUTED | alpaca_resolved x4 |
| FOLLOW_CALLS | alpaca_resolved x4 |
| FADE_WHALE | alpaca_resolved x1 |
| FADE_DP | afford_fallback x1 |

ONE probe fill out of ~76 bought the contract the archive measures. The archive corpus is
built per-OCC from real flow prints - it is the return of buying THE CONTRACT THE WHALE
BOUGHT. Every alpaca_resolved fill is a DIFFERENT instrument the engine synthesized to a
target delta/DTE. So for every strategy except DIP_CONF_MILD (fixed 2026-09-01 after the
instrument-mismatch panel) the backtest and the live book are not trading the same thing,
and archive-scale expectations do not transfer to them.

## HONEST LIMITS OF THIS RUN

- The CONTROL is the one row whose archive comparator is unambiguous (the pool = take
  everything), and it CAPTURES: live median +5.70 vs archive +4.67, gap +1.03 points. That is
  the reassuring half - execution friction, spreads and the no-same-day rule are NOT
  destroying returns at the day-mean level.
- The per-strategy gaps below the control are NOT yet trustworthy: several live filters were
  mapped to approximate archive predicates (DP_HEAVY's live filter is dark-pool print count,
  which the archive does not carry at all, so its row is mapped to the pool and means
  nothing). Those rows measure the mapping as much as the strategy.
- Sample: 11 shared days for the widest row. No gap under ~10 points is distinguishable.

## THE ACTION THIS IMPLIES (queued, not taken tonight)

Extend the trigger-contract path (_PROBE_CONTRACT verbatim, already live for DIP_CONF_MILD
and BULL_DIP_X) to every strategy whose evidence is trigger-contract-based - FOLLOW_CALLS,
CONSENSUS_CALLS, WINNER_PROFILE, WINNER_PROFILE_X. Until then their live results cannot be
compared to the numbers that justified them, and no promotion of theirs should be read as
confirming an archive cell. This is an entry-path change: panel + regime drill + MOT before
it ships.
