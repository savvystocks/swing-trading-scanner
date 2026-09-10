# STUDENT_SELECT - WIRING DESIGN (owner order 2026-09-10 23:20, pre-panel)

Owner ruling: the student goes live as a roster probe, panel first, target Monday 15 Sep.
Reason: its shadow book has beaten the shadow control on 24 unseen days and the pipeline's
"page the owner at 10 days" gate never fired (fixed 2026-09-10, weekly page while met).

## 1. Which model - the finding the panel must not lose
fade_meta.py trains TWO models nightly. The shadow books tell them apart:

| book | model | cohort | shared unseen days | own %/day | shadow control | edge | t | ahead |
|---|---|---|---|---|---|---|---|---|
| META_SELECT | NARROW (fade cohort, n~1,150, OOF AUC ~0.57) | fade-shaped candidates only | 24 | +6.1 | -4.1 | +10.2 | +1.79 | 14/24 |
| META_SELECT_60 | NARROW, picks with P >= 0.60 | same | 14 | +9.8 | -1.5 | +11.3 | +1.46 | 9/14 |
| META_WIDE | WIDE (whole funnel, n~25,600, OOF AUC 0.673) | every candidate | 24 | -7.0 | -4.1 | -2.9 | -0.36 | 11/24 |
| META_WIDE_60 | WIDE, P >= 0.60 | every candidate | 7 | +2.4 | -5.6 | +8.0 | +0.69 | 4/7 |

The selector with shadow edge is the NARROW model applied INSIDE the fade shape (ticker below
its 20-day and SPY below its 20-day for calls; the mirror for puts). The wide student, despite
the better AUC, shows no edge as a picker. So STUDENT_SELECT = fade shape AND narrow-model
P(win) >= 0.60. (FADE_UNROUTED, the shape alone, lost -$1,289 live: the selection is the edge.)

## 2. Definition (roster entry)
- Candidate gate (free, before any sweep): `_shape(md, c)` is md-level so it needs the sweep;
  the free pre-check is only the side/calls test and the live pre-quote. Attempt accounting as
  for every other probe (per-probe ceiling 4, live pre-quote, 10 per cycle).
- After the sweep: build the feature vector (section 3), score, enter only if P >= 0.60.
- Both sides, all regimes. Contract: the synthesized leg as today (this is what the labels
  measured: the harvest labels an executable-price path on the candidate the ENGINE would buy).
- Daily cap for this probe: 3 fills (the shadow book took top-3 per day); $1,000 auditions.
- Record stamps `student_p` and `student_model_date` on every leg for calibration audits.

## 3. Feature parity - one builder, two callers
New module `src/student_features.py` exporting `vector(md, side, spread_pct, premium, rv20,
prev_oi, iv_front)` used by BOTH fade_meta.cohort() (training) and the engine (live). Narrow
vector = 18 NUMERIC_PATHS from the md blocks + side + rv20 + prev_oi + iv_front = 22 floats,
NaN where missing (the model imputes).
- rv20: 20-day close-to-close vol ENDING D-1. The sweep already holds the daily closes it uses
  for sma20; compute rv20 from closes[-21:-1]. Training uses the same definition (fade_meta).
- prev_oi: the archive's prev_oi is the PRIOR-DAY OI level (never same-day). Live: the resolved
  contract's `open_interest` from Alpaca, which is the prior close's OI at any intraday time -
  same quantity. Panel to confirm no post-entry leak either way.
- iv_front: md.iv_term.iv_front, present on both paths.
Parity MOT: a frozen fixture (md + candidate) must produce byte-identical vectors through
training and live builders.

## 4. Model transport - no new dependency in the trade path (recommended)
Option A (recommended): nightly JSON EXPORT of the narrow HistGradientBoosting model - the
predictors' node arrays (feature index, threshold, left/right, value, missing-go-left) plus the
baseline prediction and the sigmoid link. A ~40-line pure-Python evaluator in
src/student_features.py reproduces predict_proba. Parity MOT: exported evaluator vs sklearn on
200 fixture rows within 1e-6. The engine on GitHub Actions needs NO scikit-learn, and no
version coupling (VPS sklearn 1.9.0 / numpy 2.5.1 vs the engine's numpy 2.1.3 pin).
Option B: joblib dump + scikit-learn==1.9.0 pinned into requirements-sandbox.txt (+30-40 s per
cycle install; pickle/version coupling; a broken import would take the whole cycle down unless
guarded). Rejected unless the panel finds A unsound.
File: reports/fade_meta/student_narrow.json, written by fade_meta nightly, committed by the
evening persist so the engine's checkout carries it. Sentinel row: newest_file_day <= 5 sessions.
Engine: fail-CLOSED - missing/stale/unparseable model => STUDENT_SELECT skips with a loud line,
never a crash (the 2026-09-10 exit-engine lesson: one record must not take the cycle down).

## 5. The moving-hypothesis problem (the panel's main question)
A nightly-retrained model is a strategy that changes every night; the court would be judging
24 different pickers. Proposal: TEACHER-FREEZE at wiring - the model exported on the wiring
night is the one the roster trades until the court returns a verdict (8 shared days), then
retrain only on a completed verdict (the same evidence-cadence rule the masters panel set).
The nightly training keeps running for the shadow book and the export is written to a
DATED file; the roster reads the pinned filename from the spec (`probe.student.model_file`).

## 6. Court treatment
Same bar as every probe (8 shared virgin days vs EXEC_BASELINE, symmetric trim, t >= 1.8,
both halves, +3%/day floor); own evidence clock from the first live day; it joins
probe.priority. The shadow book continues in parallel: STUDENT_SELECT becomes the first
strategy with a shadow-vs-live capture ratio on the same days - publish it weekly.

## 7. Honest caveats to carry into the roster comment
- Shadow returns are LABEL returns on the harvest's executable-price path; live fills pay the
  spread twice and the no-same-day rule. Expect a haircut.
- The OOF scores are day-grouped k-fold, not strict walk-forward: training folds contain
  FUTURE days relative to a scored day. No label leak, some regime leak. The live court is
  strict walk-forward by construction.
- n~1,150 training rows; max_depth 3 limits overfit but the picker is young.

## 8. Coverage (ships in the same commits)
MOT: model file present + parseable + fresh; feature parity fixture; evaluator parity fixture;
fail-closed on missing model (fixture); roster entry present; per-probe cap honoured.
Regime drill: one scenario where the model is absent (probe skips, cycle completes).
Sentinel: model file newest_file_day row. Odometer: trial entry.

## 9. Sequence
Fri 12 Sep morning: panel (evidence-transfer / entry-path / moving-hypothesis lenses).
Fri: build + parity fixtures + drill + MOT; land after the close with the model pinned.
Mon 15 Sep: first live cycles; Friday 19 Sep court: first standing.
