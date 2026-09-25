# Evidence chain and the court

## What
- 2026-09-21: the Unusual Whales evidence chain is RETIRED - the prints puller, the hourly bar library and the
  nightly and Friday corpus chains no longer run, and the flow archive is frozen history.
- 2026-09-26: the COURT is RETIRED - its three cron slots (Fri 22:35, Wed 10:00, nightly 22:00) are gone with their
  sentinel rows; `scripts/sunday_boundary.py` stays in the tree and runs from nothing; the shadow ledger it read froze
  on 2026-09-18 and `reports/shadow_lab/trajectory.log` and `reports/shadow_lab/sentinels.jsonl` stop growing. The one live strategy is
  judged by `scripts/proof_stint.py` (docs/feature_map/proof-book.md), not by a court.
The archive corpora that every backtest number comes from, the weekly tuner that judges anchor
exits against incumbents, the Friday court that promotes or holds every probe against the control,
and the scoreboard that reports where the system stands against the North Star.

## Where
- Archive pull: scripts/uw_history_pull.py (deleted 2026-09-21) (22:30 UTC daily, `data/uw_history.db`: contracts_daily,
  flow_prints) and scripts/uw_flow_prints.py (deleted 2026-09-21) (00:15 UTC, per-print NBBO); both defer zero-result
  days inside a recent window instead of marking them done.
- Bars: scripts/hourly_library.py (deleted 2026-09-21) -> `data/hourly_paths.db` (hour bars for every archive contract).
- Corpora (gitignored): `reports/research/probe_tuner_rows_v3.jsonl` (ask at the qualifying
  print + 10-minute delay, prior-close regime columns, 8 exit configs) from `scripts/probe_tuner.py`;
  `reports/research/glide_fine_rows_v3.jsonl` (210 exit configs) from `scripts/glide_sim.py`;
  `reports/research/student_asof_v3.jsonl` from scripts/student_asof_build.py (deleted 2026-09-21). Nightly chain
  01:45 UTC Tue-Sat: hourly_library -> probe_tuner build (TUNER_BUILD_ONLY=1) -> glide_sim build,
  logged to `/home/poller/corpus_nightly.log`.
- Tuner: Friday 20:15 UTC `scripts/probe_tuner.py` (report), 21:45 `scripts/tuner_apply.py`
  (verify-after-push, density guard; incumbents `pricey_4_9`).
- Court (retired 2026-09-26, described as it ran): `scripts/sunday_boundary.py` Friday 22:35 UTC (Wednesday 10:00
  report-only; nightly 22:00 trajectory): per probe, shared scoreable days with the control (weeks for `_W` structures),
  n >= 8, symmetric trim, t >= 1.8, own mean above the floor, both halves positive -> PROMOTE;
  the tuning clock `probe.tuning.<name>.applied` excludes pre-change days; demotion symmetry.
- Scoreboard: `scripts/trajectory_scoreboard.py` Friday 22:25 (North Star block); the fade meta
  student gate `scripts/fade_meta.py` 22:10 weekdays.
- Research reports: `reports/research/*.md` (basis diffs, capture ratio, spread study, formula
  searches); superseded corpora in `reports/research/superseded/`.

## Exercise (frozen 2026-09-25; retired 2026-09-26 - these read logs and corpora nothing writes any more)
- `./.venv/bin/python scripts/returns_ledger.py` - the one-command performance table (live as the
  court reads it, archive on the executable basis, court standing), written to
  `reports/performance/ledger.md`; `--update-map` refreshes `docs/performance_map/`.
- `tail -40 /home/poller/sunday_boundary.log`, `/home/poller/tuner.log`, `/home/poller/corpus_nightly.log`.
- Density: `wc -l reports/research/probe_tuner_rows_v3.jsonl` and the sentinel's `jsonl_density` rows.
- A strategy's honest cell: `grep <NAME> reports/research/basis_diff_v2_v3_2026-09-11.md`.

## Healthy
- `PROBE FOLLOW_CALLS: 1/8 live virgin days vs control - HOLD` (historical; no court run after 2026-09-25)
- `row build complete: 210 new` in the corpus log; `STUDENT EXPORT COMPLETE`.
- Tuner: every anchor HOLD is the normal first honest pass.

## Evidence (frozen 2026-09-25; retired 2026-09-26)
- The court's verdict lines in `/home/poller/sunday_boundary.log`; `reports/shadow_lab/ledger.jsonl`;
  `reports/shadow_lab/trajectory.log`.

## Checks
- MOT 6.10f (no v1/v2 corpus names), 6.10g-j (basis, regime_basis, gitignore), 6.10h (pullers
  defer, sentinel density rows, tuner density guard); `scripts/glide_sim.py` single-writer lock.

## Traps
- 2026-09-04 FROZEN ARCHIVE WINDOW; 2026-09-07 FROZEN TUNER CORPUS and CHECKPOINT-FROZEN BARS;
  2026-09-10 (second entry) EVIDENCE CHAIN EFFECTIVELY FROZEN AT AUG 31 -> the sentinel rows.
- 2026-09-09 (third entry) EVERY BACKTEST NUMBER WAS OPTIMISTIC BY ~4-5 POINTS/DAY (bar-close
  entry); 2026-09-11 CORPUS LEAKS #2 and #3 (first-print entry; entry-day regime) -> v3 basis.
- All numbers before 2026-09-11 on the old bases are superseded; quote only v3 cells.
- A t-stat from the search window is selection-biased by construction; only the holdout row is evidence.
- UW-side print gaps happen: 2026-09-09 and 09-10 returned zero prints per contract and 09-08 was
  thin, confirmed directly against the API on 09-14, while contracts_daily had all four days. The
  v3 corpus cannot build rows for such days (no qualifying print), so it stops at the last complete
  day; the puller's zero-result defer retries for seven days, then the days stay holes. Read the
  sentinel's "uw prints cohort density" and "session_holes" rows before trusting a recent cell.
- 2026-09-15 THE LEDGER'S DIP_CONVEXITY CELL WAS NOT THE LIVE CELL: it omitted the SPY-below-20d
  confirmation and ran the BASE exit while the seat runs -70/+80/0.30. Re-cut; MOT 6.23 pins the ledger's
  cell and exit to the engine's (`sandbox_proactive_lab.py:PROBE_EXITS` mirrored as `DEFAULT_EXITS` in
  `scripts/returns_ledger.py`). A cell must mirror the live filter AND the exit the seat runs.
- 2026-09-15 CROSS-STRATEGY OVERLAP IS NOW POSSIBLE AND THE COURT DOES NOT MODEL IT: decisions 41 and 44
  let several probes hold the SAME underlying on the same day (held-name rule loosened; the contract cap
  scoped to each probe's own contracts). The court compares each strategy's day means against a shared
  control and treats days as independent samples. Same-name overlap correlates them, which flatters a
  t-stat built on the assumption of independence. Nothing de-duplicates or flags same-name-same-day
  overlap yet; read a promotion case with that in mind and check the trades behind it.
