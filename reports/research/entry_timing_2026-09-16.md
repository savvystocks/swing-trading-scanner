# Entry timing: chasing is right, and the exit clock is worth more than the entry clock

Owner order 2026-09-16 00:48 BST: run the entry timing study. Design pre-registered in
`reports/research/whole_market_2026-09-15.md` section 6 and in the header of
`scripts/entry_timing_build.py` BEFORE the run.

## The design

36,416 qualifying contract-days over 458 sessions, **paired**: the same contract on the same day
priced three ways and measured two ways, so any difference is entry timing or exit clock and never
selection.

| Entries | |
|---|---|
| AT_PRINT | the ask at the qualifying print - what the engine does live, minutes after the alert |
| AT_CLOSE | the ask at that day's close |
| NEXT_CLOSE | the ask at the next day's close |

| Exits (BASE -50 / +50 / 0.20) | |
|---|---|
| DAILY | one check a day on the closing bid (the whole-market corpus's method) |
| HOURLY | hourly bars, stop on the true LOW, trail on the close |

Pre-registered bar: the comparison of interest is AT_PRINT against AT_CLOSE under HOURLY exits, and
a difference counts only if it holds in BOTH halves and reaches |t| >= 2 on the paired daily
differences.

## 1. Entry timing: the engine is right to chase

| Arm | Exit | Mean per day | t | Win | Halves |
|---|---|---|---|---|---|
| at print | hourly | **+1.37%** | +2.33 | 44.7% | +1.9 / +0.9 |
| at close | hourly | +0.79% | +1.35 | 44.3% | +1.6 / -0.0 |
| next close | hourly | +0.16% | +0.19 | 42.2% | +1.0 / -0.7 |
| at print | daily | -2.08% | -3.01 | 38.0% | -0.4 / -3.7 |
| at close | daily | -2.53% | -4.05 | 37.7% | -0.6 / -4.5 |
| next close | daily | -0.58% | -0.66 | 38.2% | +1.8 / -2.9 |

**Paired, close minus print, hourly exits: -0.57 points per day, t -2.14, negative in both halves.**
The pre-registered bar is met and the sign is against waiting. Buying later costs money.

Where it comes from, by contract price (paired, hourly):

| Ask band | Close minus print | t | Verdict |
|---|---|---|---|
| $0.30-2 | **-4.65** | -2.89 | waiting is much worse |
| $2-4 | +0.77 | +0.64 | nothing |
| $4-6 | -1.24 | -1.42 | nothing |
| $6-9.90 | -0.08 | -0.18 | nothing |
| $16+ | -0.28 | -1.24 | nothing |
| calls, $0.30-9.90 | -1.35 | -1.62 | leans to chasing |

The penalty for patience is concentrated in the cheapest contracts and is absent everywhere else.
Cheap contracts are exactly what the $1,000 slot buys, so the seat that would suffer most from
waiting is the one we run.

**Consequence: no engine change, and speed is justified.** The ten-minute cycle, the rush to fill,
the limit-chasing on synthesized legs - the thing they buy is real, at least for cheap contracts.
Result four of the four I set out (next day beats both) is refuted: NEXT_CLOSE is the worst arm.

## 2. The finding I did not predict: the exit clock is worth more than the entry clock

I expected daily-resolution exits to FLATTER returns by missing intraday stop breaches. The data
says the opposite, and the size is not small.

| Ask band | Stopped out, daily | Stopped out, hourly | Hourly minus daily |
|---|---|---|---|
| $0.30-4 | 57.6% | 46.7% | **+3.35 points** |
| $4-9.90 | 46.0% | 35.4% | **+8.33 points** |
| $9.90+ | 22.3% | 18.2% | **+4.18 points** |

Checking once a day stops a position out MORE often, not less. The mechanism is the trail: managed
intraday, a position that spikes and gives back 20% exits on the trail with a profit; managed on
closes alone the spike is never seen, the position is still held, and it goes on to hit the stop.
Intraday management converts future stop-outs into earlier trail exits, and that is worth three to
eight points a day.

Our engine already manages every ten minutes, so this validates the design rather than changing it.
It also means the whole-market study's absolute numbers are a FLOOR, understated by 3-8 points, and
that its daily-resolution levels can never be ranked against an intraday-measured cell.

## 3. So what was the cheap-versus-expensive flip?

Measurement incompatibility, not signal. The correction between the two clocks is large AND uneven
across price bands (+3.35, +8.33, +4.18), so the two bases cannot be ordered against each other at
all. Nothing about the flip survives as a tradeable claim, and the v3 basis remains the court's.

## 4. One live thread, stated with its caveat

Qualifying-print CALLS in the affordable band, entered at the print and managed hourly, returned
+3.91% a day (t 2.15, halves +6.6 / +1.2, 4,444 trades). That is positive, in the band the archive
elsewhere says is dead. CAVEAT, and it is a real one: the hourly arm only covers contracts present
in `data/hourly_paths.db` (4,444 of 5,879 rows in that cell), so the hourly population is a subset
and may be the more liquid one. Before this is treated as anything, it needs re-running on rows where
both clocks exist, which is the obvious next study and is not claimed here.

## 5. What this settles

1. **Do not delay entries.** Waiting costs 0.57 points a day overall and 4.65 on the cheapest
   contracts, in both halves. The engine's behaviour is correct.
2. **Speed is worth what it costs.** The cycle cadence and the fill chase are justified by evidence
   for the first time.
3. **Exit cadence is worth more than entry cadence**, by roughly an order of magnitude, and we
   already have it.
4. **Retire cross-basis comparisons.** Daily-resolution and intraday-resolution numbers are not
   comparable, in either direction, at any price band.

## 6. Honesty notes

- Paired throughout: every arm prices the same contract-days, so entry differences are not selection.
- The hourly arm has partial coverage (23,236 of 33,154 rows overall); every paired statistic is
  computed only on rows where both arms exist, but the daily-versus-hourly LEVELS in section 1 are
  on different row counts and should be read as within-clock comparisons only. Section 2's
  hourly-minus-daily figures ARE matched-row.
- Sample is 80 qualifying contract-days per session, seed 11, recorded in the file header.
- `reports/research/entry_timing_v1.jsonl` (17MB) is gitignored and rebuilt by
  `scripts/entry_timing_build.py`.
