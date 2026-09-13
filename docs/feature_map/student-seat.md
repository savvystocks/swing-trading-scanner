# Student seat

## What
One roster seat, `STUDENT`, that scores every contract in the student pool with every configured
picker (dependency-free JSON models trained on the archive), ranks the picks best-first, and enters
the top pick that clears its picker's threshold, fits the cap, and has weekly budget. Picker A
(EXPRET/ALL) is live since 2026-09-13 on picks whose live ask is under $10; B, D, E, F score in
shadow; C is pulled. The court judges STUDENT_FAMILY on trading days.

## Where
- Config: `fade_book_spec.json` `probe.student` (enabled, mode live/shadow, bear_standdown,
  max_model_age_days, pool, exec_max_ask, probes.<name>: target, cohort, exit_label, k_per_week,
  model, pulled, live, threshold_cohort). Read by `sandbox_proactive_lab.py:_student_cfg`.
- Pool: see candidate-scan.md (`_STUDENT_CANDS`, `sandbox_proactive_lab.py:_student_pool_cfg`).
- Rank: `sandbox_proactive_lab.py:_student_rank` - per candidate: prior-close SPY readings
  (`fade_book.spy_prev_readings`), the ticker's prior-close 20d distance from `_alpaca_daily`, a
  live indicative quote (`sandbox_proactive_lab.py:_live_quote`), the as-of block
  (`src/student_features.py:asof_from_alert`) and the 15-float vector (`src/student_features.py:vector`),
  then each picker's score (`src/student_features.py:predict`), threshold
  (`sandbox_proactive_lab.py:_student_threshold`) and weekly budget
  (`sandbox_proactive_lab.py:_student_week_used`, which adds the deduplicated unaffordable picks
  from `sandbox_proactive_lab.py:_student_consumed_this_week`). Returns (score, picker, cand, vec, live_ask).
- Select: `sandbox_proactive_lab.py:_student_select` - enter / unaffordable / open_ticker. The
  test is the LIVE ask against `probe.student.exec_max_ask` (10.0 = the $1,000 cap in per-share
  dollars); sizing (`LEG_BUDGET // (ask * 100)`) happens later in build_legs and never decides
  affordability. An unaffordable pick spends one of the picker's `k_per_week` (3) units once per
  contract-day, logged with `budget_consumed`; units are never refunded, exactly as the study
  spent them.
- Entry: the STUDENT branch in the probe loop sets `_PROBE_CONTRACT["c"]` with `student: True` and
  `live_ask`; `sandbox_proactive_lab.py:build_legs` returns the contract on its own side sized
  `LEG_BUDGET // (ask * 100)`; the trigger-leg repricing keeps that sizing off the live ask.
- Models: `reports/fade_meta/student_<NAME>_<date>.json`, loaded fail-closed by
  `sandbox_proactive_lab.py:_student_model` (age, kind, n_features, sha stamp).
- Export / retrain: `scripts/student_export.py` (walk-forward thresholds from the last 60 OOS
  sessions of the threshold cohort; `executed_slice` under exec_max_ask; auto-pull on wk_t <= -1.5
  with n >= 40 or AUC <= 0.50; refuses during an open case; commits the spec and models).
- Research: `scripts/student_formula_sim.py` (the pre-registered search), `scripts/student_asof_build.py`
  (the as-of corpus), `scripts/student_spread_sim.py` (the spread study), `scripts/student_live_exit.py`
  (exit search on live fills, weekly, gated on 20 closed fills).

## Exercise
- `./.venv/bin/python scripts/regime_drill.py | grep STUDENT` (scenarios 6 and 7).
- `./.venv/bin/python v11_mot_harness.py | grep -i student`.
- Live: `gh run view <id> --log | grep -n "student"`; the passive log
  `tail -3 reports/shadow_lab/student_scores.jsonl`.
- Retrain: `./.venv/bin/python scripts/student_export.py` (writes dated models, restarts the court clock).

## Healthy
- `  student: 41 pool contract(s), 1 eligible pick(s) across pickers (live)`
- `  PROBE[STUDENT_A] entered SOFI (student pick p=21.310)`
- `  student[STUDENT_A]: pick GOOGL GOOGL271217C00345000 ask 50.65 over the cap - budget unit spent, not traded`
- `  student: prior-close SPY readings unavailable - pickers stand down` (fail-closed, acceptable once; recurring means the SPY bars call is broken)

## Evidence
- Fills: records with `probe_strategy: STUDENT_<x>`, `student_p`, `student_model`.
- Scores: `reports/shadow_lab/student_scores.jsonl` (persisted by the workflow every cycle).
- Research: `reports/research/student_formula_asof_2026-09-11.md`,
  `reports/research/student_spread_2026-09-12.md`, the dated student_live_exit reports under
  reports/research; the design `reports/student_cheap_pick_design_2026-09-12.md`.

## Checks
- MOT 6.11 (vector, evaluator parity, prior-close inputs, one-seat wiring, pulled never live);
  MOT 6.15 (the drill never writes the live score log); MOT 6.17 (pool, select, budget dedup,
  sized put leg, dip legs unchanged, export executed slice, spec keys); drill scenarios 6-7.

## Traps
- 2026-09-12 (third entry) A DRILL WROTE FIXTURE ROWS INTO THE LIVE SCORE LOG.
- 2026-09-12 (fourth entry) THE STUDENT SEAT SCORED THE WRONG SLICE (see candidate-scan.md).
- Never flip a picker live without the owner's word; the flip is `probes.<name>.live` in the VPS
  spec, refused for a pulled picker.
- `reports/research/student_asof_v3.jsonl` is rebuilt only by `scripts/student_asof_build.py`; the export uses
  whatever is on disk (70,976 rows as of 2026-09-13).
