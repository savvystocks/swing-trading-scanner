# Student (Stage 2) - harvest_20260731_2130 - OFFICIAL

**STUDENT REJECTED - gates failed**

- feature-bearing rows: 11284 (gate 8000 - MET)
- OOF weighted AUC 0.739 on 11284 out-of-fold rows; calibration isotonic; features 53 (clustered out 30 redundant)
- trials this run: {'features_clustered_out': 30, 'student_fits': 186, 'thresholds': 180, 'TOTAL': 396}

## The four acceptance gates (item 8)

1. OOS Wilson lower bound N/A > hurdle 0.6006: **FAIL** (selection: n 0, n_eff 0.0, hit N/A, net N/A)
2. PBO 0.294 <= 0.2: **FAIL** (15 CPCV splits x 12 configs, 5 paths)
3. Deflated Sharpe 0.000 > 0.5: **FAIL** 
4. Beats the engine on the same purged splits: **FAIL** (student net N/A vs engine net -0.7043; student hit N/A vs engine hit 0.0273, engine n 477)

## Calibration plateau map (step-cliff visibility; report-only)

- 25 distinct calibrated levels across 11284 rows; max p = 0.500
- largest plateaus (p, rows, distance to bar): 0.089 (n=1162, -0.511), 0.267 (n=1064, -0.334), 0.252 (n=993, -0.349), 0.161 (n=984, -0.439), 0.425 (n=869, -0.175)
- mass near the bar: at/above 0 | 0-5pts below 0 | 5-10pts below 0 | 10-20pts below 1802
- **CLIFF WARNING: zero mass within 10pts below the bar - selection counts will JUMP in steps, not ramp, as plateaus cross (the 3-to-54 mechanism of 07-26). Read week-over-week selection-count changes accordingly.**

## Shadow (reporting only - the engine is untouched)

- last-days candidates scored: 2631 | student TAKE 0 / VETO 2631
- of the engine's 15 executed picks the student agreed with 0 and would have vetoed 15
- full table: `shadow_harvest_20260731_2130.csv` (per-candidate p, decision, stated reason, outcome)

## Provenance

- config (pinned): {'half_life_days': 21, 'cluster_corr': 0.85, 'n_folds': 5, 'embargo': 0.02, 'seed': 7, 'learning_rate': 0.08, 'max_depth': 3}
- model artifact: `student_harvest_20260731_2130.joblib` (workdir; not committed)
- run: 772.2s | brain-side only, zero live changes