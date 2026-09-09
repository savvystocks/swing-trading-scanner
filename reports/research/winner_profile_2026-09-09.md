# WINNER PROFILE - built 2026-09-09
corpus: 25597 labeled trades (all strategies, all eras), base win rate 27.7%
profile features (separation >= 0.535 AUC), winner side vs pooled median:

- spread_pct: winners sit below 5.556 (winner med 3.922 vs loser med 6.452, AUC 0.3637, coverage 100%)
- rule_score: winners sit above 73200.0 (winner med 90251.5 vs loser med 68999.0, AUC 0.5583, coverage 100%)
- iv_term.iv_front: winners sit below 47.7 (winner med 44.0 vs loser med 49.0, AUC 0.4617, coverage 78%)

rejected (no winner/loser separation): macro.distance_to_sma20_pct, regime_stack.market_spy_dist_pct, iv_term.iv_ratio, gex.net_gex, gex.distance_to_zero_gamma_pct, vrp.vrp
insufficient coverage: macro.atr_pct, macro.rvol_10d, regime_stack.vix, technical.rsi_5, technical.rsi_15, dark_pool.dp_ratio, dark_pool.dp_volume_pct, skew.skew_25d, flow_aggression.ask_side_pct, flow_persistence.n_alerts_today, dealer_greeks.vanna, dealer_greeks.charm
