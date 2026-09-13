# WINNER_PROFILE (the frozen secondary control)

## What
Any whale-flow candidate, either side, any regime, whose alert premium exceeds $73.2k and whose
front-month implied volatility is under 47.7, the third leg (tight spread) enforced by the 2%
execution cap. Built 2026-09-09 from the shape of 25,597 labeled trades and frozen at build; a
comparator, not a promotion candidate.

## Evidence cell
Archive: PARTIAL only, the premium leg (the corpus carries no IV column), so the ledger's cell is
an upper bound on what the full filter would keep. The 2026-09-09 grid (old basis) put the frozen
cell at a t of 0.68 against the pool, which is noise. Live: its own PROBE records.

## Numbers
- live: [[strategies.WINNER_PROFILE.live.n_closed = 0]] closed, [[strategies.WINNER_PROFILE.live.per_trade = n/a]] per trade,
  open [[strategies.WINNER_PROFILE.live.open = 1]].
- archive (partial cell): [[strategies.WINNER_PROFILE.archive.per_day = -4.6]] per day (pool
  [[strategies.WINNER_PROFILE.archive.pool_per_day_same_days = -4.5]]), t vs pool [[strategies.WINNER_PROFILE.archive.t_vs_pool = -2.90]].

## Recompute
`./.venv/bin/python scripts/returns_ledger.py` (row WINNER_PROFILE).

## Healthy
Not on the promotion track; the court prints nothing for it. Healthy means it trades a little
and its numbers sit near the pool's, which is what a control does.

## Live
Records with `probe_strategy: WINNER_PROFILE`.

## Checks
- MOT 6.10e roster focus (it is one of the seven).

## Traps
- Its tuned sibling WINNER_PROFILE_X went +6.33 -> +1.95 -> -4.66%/day across the three bases and
  was retired with zero fills; the frozen cell shares its ingredients.
- Static averages of three weak features are not a strategy; the student learns the same thing
  from fifteen features per contract and does better on the holdout.
