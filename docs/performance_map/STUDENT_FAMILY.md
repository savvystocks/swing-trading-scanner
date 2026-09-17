# STUDENT_FAMILY

## What
The student pickers judged as one book. Picker A (expected-return regressor trained on every
archive trade, thresholded on the whole field) is live from 2026-09-14 on picks whose live ask is
under $10, at budget sizing, three picks a week; B, D, E, F score in shadow; C is pulled. The
seat scores the archive universe and executes only what fits the cap.

## Evidence cell
Archive: the live pickers' EXECUTED SLICE from their exported model files (walk-forward over the
whole stream, picks under the cap, engine sizing). A's holdout on the unaffordable slice
(+49.9% per trade, t 2.20, all regimes) is the strongest number in the system and cannot be
traded under the cap; it is context, not the promise. The spread variant was rejected 2026-09-12.

## Numbers
- archive (executed slice): [[strategies.STUDENT_FAMILY.archive.per_trade = +31.0]] per trade over
  [[strategies.STUDENT_FAMILY.archive.trades = 56]] trades and [[strategies.STUDENT_FAMILY.archive.weeks = 35]] weeks,
  weekly t [[strategies.STUDENT_FAMILY.archive.wk_t = +1.64]].
- live: [[strategies.STUDENT_FAMILY.live.n_closed = 0]] closed, [[strategies.STUDENT_FAMILY.live.per_trade = n/a]] per trade,
  units [[strategies.STUDENT_FAMILY.live.units = 0]] ([[strategies.STUDENT_FAMILY.live.unit = days]]),
  t vs control [[strategies.STUDENT_FAMILY.live.t_vs_control = n/a]], open [[strategies.STUDENT_FAMILY.live.open = 0]].

## Recompute
`./.venv/bin/python scripts/returns_ledger.py` (row STUDENT_FAMILY); retrain with
`./.venv/bin/python scripts/student_export.py` (restarts the court clock).

## Healthy
Court standing: [[strategies.STUDENT_FAMILY.court.standing = 0/8 live virgin days vs control - HOLD]]. About one and a half trades a
week expected; long losing runs are normal for sub-$1 weeklies; the mean rides rare large winners.
The exit search on live fills runs once twenty have closed.

## Live
Records with `probe_strategy: STUDENT_A` (and any picker flipped live), `student_p`,
`student_model`; the passive score log `reports/shadow_lab/student_scores.jsonl`.

## Checks
- MOT 6.11 / 6.17; drill scenarios 6-7; the export's auto-pull on the executed slice.

## Traps
- Four corrections in three days (2026-09-09 to 11): every pre-v3 student number is superseded.
- The $4-9.90 band loses (-10.9% per trade); the cheap-pick slice was found after the spread
  study, a post-hoc slice of a pre-registered rule, disclosed as such.
- The first live day's threshold cohort (AFFORD) and pool ($4-9 calls) measured the wrong slice;
  fixed 2026-09-13 (BREAKDOWNS fourth entry).
