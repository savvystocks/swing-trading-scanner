# CREDIT_SPREAD_W

## What
Once a week, sell the 2%-OTM XSP put and buy the 4%-OTM put, cash-settled at Friday's close;
stands down in a BEAR regime. The income seat's candidate and the closest thing to a court
verdict in the system.

## Evidence cell
Archive: none in the options corpus. The 2.5-year XSP backtest in `scripts/fivek_backtests.py`
(about +$2.3k over 114 weeks) is on the superseded basis and is quoted only as history. The LIVE
weekly record is the evidence.

## Numbers
- live: [[strategies.CREDIT_SPREAD_W.live.n_closed = 6]] settled weeks, [[strategies.CREDIT_SPREAD_W.live.per_trade = +4.3]]
  per week as a percentage of $1,000, dollars [[strategies.CREDIT_SPREAD_W.live.total_usd = +256]],
  weeks shared with the control [[strategies.CREDIT_SPREAD_W.live.shared_units = 5]],
  t vs control [[strategies.CREDIT_SPREAD_W.live.t_vs_control = -0.24]].

## Recompute
`./.venv/bin/python scripts/returns_ledger.py` (row CREDIT_SPREAD_W).

## Healthy
Court standing: [[strategies.CREDIT_SPREAD_W.court.standing = 4/8 live virgin weeks vs control - HOLD]]. The weekly court needs eight
shared weeks, the same trimmed t of 1.8, and a weekly floor of +5%.

## Live
Records with `probe_strategy: CREDIT_SPREAD_W` and a `settle` block (xsp close, pnl_usd).

## Checks
- Drill scenario 5 (wings first); the court's weekly branch; the feature map's credit-spread.md.

## Traps
- Its max loss (about $1,200) exceeds the $1,000 proof cap, so a promotion cannot seat it on the
  proof account until a larger rung or the v1.8 narrower width. Court progress is not a path to
  real money by itself.
- A week with no entry (bear stand-down, or the 15:00 UTC window missed) is a paused week, not a
  lost one; the court counts shared weeks.
