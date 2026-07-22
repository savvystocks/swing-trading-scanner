# Student (Stage 2) - harvest_20260722_1058 - PROVISIONAL (below gate)

**WITHHELD - PROVISIONAL run below the 8000 feature-bearing gate**

- feature-bearing rows: 6281 (gate 8000 - 1719 short)
- OOF weighted AUC 0.723 on 6281 out-of-fold rows; calibration isotonic; features 53 (clustered out 30 redundant)
- trials this run: {'features_clustered_out': 30, 'student_fits': 186, 'thresholds': 180, 'TOTAL': 396}

## The four acceptance gates (item 8)

1. OOS Wilson lower bound N/A > hurdle 0.5991: **FAIL** (selection: n 0, n_eff 0.0, hit N/A, net N/A)
2. PBO 0.333 <= 0.2: **FAIL** (15 CPCV splits x 12 configs, 5 paths)
3. Deflated Sharpe 0.000 > 0.5: **FAIL** 
4. Beats the engine on the same purged splits: **FAIL** (student net N/A vs engine net -0.7387; student hit N/A vs engine hit 0.0203, engine n 362)

## Shadow (reporting only - the engine is untouched)

- last-days candidates scored: 949 | student TAKE 0 / VETO 949
- of the engine's 68 executed picks the student agreed with 0 and would have vetoed 68
- full table: `shadow_harvest_20260722_1058.csv` (per-candidate p, decision, stated reason, outcome)

## Provenance

- config (pinned): {'half_life_days': 21, 'cluster_corr': 0.85, 'n_folds': 5, 'embargo': 0.02, 'seed': 7, 'learning_rate': 0.08, 'max_depth': 3}
- model artifact: `student_harvest_20260722_1058.joblib` (workdir; not committed)
- run: 980.4s | brain-side only, zero live changes