# EXEC_BASELINE (the control)

## What
The frozen flow-following control: whale alerts on the affordable band, synthesized 4%-OTM
35-DTE legs (or the affordable trigger contract when those price over the budget), the standard
exit. It exists to be beaten. Every court verdict is a comparison against its day means.

## Evidence cell
Archive analogue: the POOL, every whale trigger of the corpus on the executable basis, BASE exit.
Live: its own PROBE records since the 2026-08-18 $1,000 reset.

## Numbers
- live: [[strategies.EXEC_BASELINE.live.n_closed = 65]] closed, [[strategies.EXEC_BASELINE.live.per_trade = +10.2]] per trade,
  win [[strategies.EXEC_BASELINE.live.win = 45%]], best trade removed [[strategies.EXEC_BASELINE.live.best_removed_per_trade = +3.5]],
  day mean [[strategies.EXEC_BASELINE.live.unit_mean = +12.4]] over [[strategies.EXEC_BASELINE.live.units = 23]] days,
  halves [[strategies.EXEC_BASELINE.live.h1 = +30.9]] / [[strategies.EXEC_BASELINE.live.h2 = -4.5]], dollars [[strategies.EXEC_BASELINE.live.total_usd = +2,557]].
- archive (pool): [[strategies.EXEC_BASELINE.archive.per_day = -5.1]] per day over [[strategies.EXEC_BASELINE.archive.days = 492]] days,
  halves [[strategies.EXEC_BASELINE.archive.h1 = -4.4]] / [[strategies.EXEC_BASELINE.archive.h2 = -5.8]].

## Recompute
`./.venv/bin/python scripts/returns_ledger.py` (row EXEC_BASELINE).

## Healthy
The control is not judged; it is the bar. A negative control day mean is expected in a market
where blind flow-following loses (the pool is negative on the executable basis).

## Live
Records with `probe_strategy: EXEC_BASELINE`; the court's `ctrl` day means.

## Checks
- The court's symmetric trim drops the control's best and worst shared day, so its jackpot cannot
  make a good strategy look bad, and vice versa.

## Traps
- 2026-09-10 review: the control's realized record was +10.6%/day raw and about -7%/day trimmed;
  one trade (IBIT, +348%) paid for a wall of -50% stops. Never read the control's mean without
  the best-removed figure beside it.
- 2026-09-09 CONTROL STARVED THE ROSTER: attempts spent by the control are attempts the probes
  never get; the per-probe ceiling exists because of it.
