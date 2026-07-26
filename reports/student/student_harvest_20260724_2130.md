# Student (Stage 2) - harvest_20260724_2130 - OFFICIAL

**STUDENT REJECTED - gates failed**

- feature-bearing rows: 8653 (gate 8000 - MET)
- OOF weighted AUC 0.723 on 8653 out-of-fold rows; calibration isotonic; features 53 (clustered out 30 redundant)
- trials this run: {'features_clustered_out': 30, 'student_fits': 186, 'thresholds': 180, 'TOTAL': 396}

## The four acceptance gates (item 8)

1. OOS Wilson lower bound 0.3231 > hurdle 0.5944: **FAIL** (selection: n 26, n_eff 12.0, hit 0.5878, net -0.0792)
2. PBO 0.232 <= 0.2: **FAIL** (15 CPCV splits x 12 configs, 5 paths)
3. Deflated Sharpe 0.000 > 0.5: **FAIL** 
4. Beats the engine on the same purged splits: **PASS** (student net -0.0792 vs engine net -0.7125; student hit 0.5878 vs engine hit 0.0244, engine n 462)

## Shadow (reporting only - the engine is untouched)

- last-days candidates scored: 2756 | student TAKE 6 / VETO 2750
- of the engine's 132 executed picks the student agreed with 0 and would have vetoed 132
- full table: `shadow_harvest_20260724_2130.csv` (per-candidate p, decision, stated reason, outcome)

## Provenance

- config (pinned): {'half_life_days': 21, 'cluster_corr': 0.85, 'n_folds': 5, 'embargo': 0.02, 'seed': 7, 'learning_rate': 0.08, 'max_depth': 3}
- model artifact: `student_harvest_20260724_2130.joblib` (workdir; not committed)
- run: 604.4s | brain-side only, zero live changes