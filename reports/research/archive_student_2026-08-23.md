# Archive-student - 2026-08-23

Cohort 276536 real trades, win-rate 0.314.
Day-grouped OOF AUC: 0.676   (0.5 = no pick skill; live student was ~0.47-0.51)
Walk-forward AUC (train<2026 / test 2026): 0.606

Permutation feature importance (2026 holdout, AUC drop when shuffled):
  delta        +0.0554
  dte          +0.0239
  theta        +0.0129
  spy_trend    +0.0119
  spy_regime   +0.0066
  iv           +0.0066
  tkr_trend    +0.0063
  gamma        +0.0029
  vega         +0.0026
  oi_chg       +0.0011
  sweep_frac   +0.0003
  log_prem     +0.0002
  aggr_imb     +0.0000
  side         -0.0010

Verdict: AUC>>0.55 = the archive HAS learnable pick-signal -> wire META_ARCHIVE ranking into the lab as a challenger (still virgin-day gated). ~0.5 = flow features don't predict winners even at scale; the edge is regime-level, not pick-level.
