# Discovery report - harvest_20260731_2130

## Plain-English close-out

Three best-looking findings (honesty numbers attached - OOS, PBO, trials, sample):
- `float_mechanics.shares_short:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.6638 (n_eff 18.8, lift 4.997) | PBO 0.000 | trials 68402
- `dealer_greeks.net_dex:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.6495 (n_eff 21.3, lift 4.889) | PBO 0.000 | trials 68402
- `dark_pool.n_prints:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4938 (n_eff 233.1, lift 3.717) | PBO 0.000 | trials 68402

Worst-confused features: 4 feature(s) too sparse to band (blind, not useless - sensor repair pending); the per-feature fill rates below separate blind from useless.
Today's data contains a HINT of an edge (survivors exist but have not cleared the promotion bar) - not yet defensible.
Zero live changes were made by this run: it reads the snapshot and writes this report only.

## Part 1 - Feature Verdict Table

- dataset: 32281 graded rows; feature-bearing 11284 (35.0% of the pile - the 'none' prefilter tier carries no feature vector and cannot be searched; that is a fill-rate fact, not a finding)
- cost-inclusive hurdle (empirical, THE bar - never the retired 62.5% figure): 0.6006 CI ['0.5901', '0.6109'] at mean cost 0.0508
- full per-band table: `verdict_harvest_20260731_2130.csv` (fill rate first, then weighted up-rate + CI, mean return, EV per band; thin bands say UNDERPOWERED)

Fill rate by feature block (lowest first - blind-vs-useless disambiguation):
```
block
brake_shadow                        0.031
days_to_earnings                    0.557
days_since_earnings                 0.662
post_earnings_iv_crush_flag         0.662
fundamentals                        0.682
float_mechanics                     0.683
skew                                0.770
iv_term                             0.770
vrp                                 0.770
distance_to_heaviest_dp_node_pct    0.980
price_action                        0.988
distance_to_zero_gamma_pct          0.996
gex                                 0.996
macro                               0.996
technical                           0.996
relative_momentum                   0.996
dealer_greeks                       0.999
flow_persistence_pct                1.000
flow_aggression                     1.000
liquidity_and_slippage              1.000
sweep_aggression_pct                1.000
news_sentiment_score                1.000
dark_pool                           1.000
alt_catalyst                        1.000
flow_persistence                    1.000
pemd                                1.000
macro_context                       1.000
news                                1.000
regime_stack                        1.000
```

Out-of-sample predictive contribution (MDA under purged CV; ranking source for this table - NOT in-sample correlation). Top five, annotated:
- `f.macro_context.day_of_week` MDA 0.1049 (fill 100%): genuinely moves OOS separation this week.
- `f.technical.atr` MDA 0.0334 (fill 100%): genuinely moves OOS separation this week.
- `f.dark_pool.n_prints` MDA 0.0119 (fill 100%): genuinely moves OOS separation this week.
- `f.dealer_greeks.net_charm` MDA 0.0080 (fill 100%): genuinely moves OOS separation this week.
- `f.dealer_greeks.net_vanna` MDA 0.0067 (fill 100%): genuinely moves OOS separation this week.
Bottom five (no OOS contribution this week - dead weight or blind):
- `f.price_action.candle_body` MDA -0.0013 (fill 99%): populated but useless so far.
- `f.iv_term.iv_ratio` MDA -0.0013 (fill 77%): populated but useless so far.
- `f.macro_context.iv_term_skew` MDA -0.0015 (fill 77%): populated but useless so far.
- `f.news.latest_age_hours` MDA -0.0017 (fill 100%): populated but useless so far.
- `f.price_action.nvi` MDA -0.0019 (fill 99%): populated but useless so far.

## Part 2 - The Search (everything counted)

- model: gbm under purged+embargoed folds; OOS weighted AUC 0.731; top-quintile OOS up-rate 0.3492 vs pool 0.1328 (n_eff 721)
- calibration: isotonic, Brier sigmoid 0.153 / isotonic 0.151
- readable rules (depth <= 3), mined on train folds, graded OOS only:
  - `float_mechanics.shares_short:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.6818 (n_eff 14.0, lift 5.132) | PBO 0.000 | trials 68402
  - `float_mechanics.shares_short:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.6638 (n_eff 18.8, lift 4.997) | PBO 0.000 | trials 68402
  - `dealer_greeks.net_dex:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.6495 (n_eff 21.3, lift 4.889) | PBO 0.000 | trials 68402
  - `dark_pool.n_prints:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4938 (n_eff 233.1, lift 3.717) | PBO 0.000 | trials 68402
  - `dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.4905 (n_eff 249.2, lift 3.692) | PBO 0.000 | trials 68402
  - `dark_pool.n_prints:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4528 (n_eff 102.7, lift 3.409) | PBO 0.000 | trials 68402
  - `dark_pool.n_prints:HIGH & flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4378 (n_eff 127.0, lift 3.296) | PBO 0.000 | trials 68402
  - `dealer_greeks.net_vanna:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4268 (n_eff 79.4, lift 3.213) | PBO 0.000 | trials 68402

### THE COUNTER (non-negotiable)

- trials this run, ALL angles aggregated: `{'model_fits': 136, 'verdict_bands': 234, 'rules_evaluated': 67794, 'thresholds': 211, 'angle_runs': 27, 'TOTAL': 68402}`
- PBO fed by the whole campaign: 0.000 CSCV over 4000 partitions, sampled 4000 of C(15,7)
- Deflated Sharpe of the walk-forward champion: UNDERPOWERED (1 OOS windows; needs >= 4)

## Part 3 - The Honest Dated Replay (walk-forward)

- 2026-W28: train 0 -> test 2832 - UNDERPOWERED (train too thin)
- 2026-W29: train 3143 -> test 2702, champion `gbm@p>=0.40`, takes 364 (n_eff 110.3), OOS up-rate 0.3299, OOS net ret -0.2757 
- 2026-W30: train 5897 -> test 2756, champion `gbm@p>=0.50`, takes 0 (n_eff 0.0), OOS up-rate N/A, OOS net ret N/A UNDERPOWERED (takes too thin)
- 2026-W31: train 8653 -> test 2631, champion `gbm@p>=0.45`, takes 2 (n_eff 1.8), OOS up-rate N/A, OOS net ret N/A UNDERPOWERED (takes too thin)

- trade-by-trade ledger (every test-week candidate, decision + stated reason + graded outcome + net P&L): `ledger_harvest_20260731_2130.csv`
- TRUE out-of-sample territory today: 3 scoreable week(s). That is THIN - verdict-grade replay needs months, not weeks; treat every number above accordingly.

Three lines, uniqueness-weighted, cost-inclusive (cumulative weighted net return):
- engine's actual picks: -68.565
- discovered strategy (OOS takes): -9.312
- pool baseline (every candidate): -1088.129

## Part 4 - Standing process

- this rig re-runs with every Sunday brain cycle and appends here (reports/discovery/); the convergence matrix accretes in `convergence_state.json`.
- promotion rule (in ROADMAP): a SURVIVOR whose OOS lower CI clears the cost-inclusive hurdle with PBO <= 0.20 across consecutive runs becomes a SHADOW candidate for the Student pipeline - never a live deployment from this rig.
- nothing clears the promotion bar this run. What would change the odds: more graded weeks (the binding constraint), repaired sparse sensors (earnings/short-float/IV-term/skew/dark-pool blocks), or an owner-decided re-sourcing of the signal itself (the referenced adjudication file does not exist in this repo - flagged).

## Part 5 - The Ten Angles (Convergence Matrix)

Cells: confirmed / weak / absent / UNDERPOWERED. Judged by intersection, never selection.

| finding | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | confirmed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `model_top_quintile` | C | C | C | w | C | C | C | w | C | C | 8/10 |
| `dark_pool.n_prints:HIGH & fundamentals.market_ca` | C | w | w | C | w | C | C | w | C | w | 5/10 |
| `dark_pool.n_prints:HIGH & gex.zero_gamma_strike:` | C | w | w | C | w | C | w | w | w | w | 3/10 |
| `dark_pool.n_prints:HIGH & macro_context.executio` | C | w | w | C | w | C | w | w | w | w | 3/10 |
| `dark_pool.n_prints:HIGH & flow_aggression.total_` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `float_mechanics.shares_short:HIGH & macro_contex` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `float_mechanics.shares_short:HIGH & gex.zero_gam` | U | - | - | U | - | U | w | - | w | w | 0/10 |
| `dealer_greeks.net_dex:HIGH & macro_context.execu` | w | - | w | w | w | w | w | w | w | w | 0/10 |
| `dealer_greeks.net_vanna:HIGH & gex.zero_gamma_st` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `fundamentals.market_cap:HIGH & liquidity_and_sli` | U | - | - | U | - | U | - | - | U | - | 0/10 |
| `dealer_greeks.net_vanna:HIGH & macro_context.exe` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `dark_pool.n_prints:HIGH & dealer_greeks.net_vann` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `fundamentals.market_cap:HIGH & liquidity_and_sli` | U | - | - | U | - | U | - | - | U | - | 0/10 |
| `dark_pool.n_prints:HIGH & liquidity_and_slippage` | w | w | w | w | w | w | w | w | w | w | 0/10 |

Angle sample notes: 1 seeds: 3/3 variants had sample; 2 time slices: 3/3 variants had sample; 3 bands: 3/3 variants had sample; 4 learner: 3/3 variants had sample; 5 weighting: 2/2 variants had sample; 6 costs: 2/2 variants had sample; 7 labels: 2/2 variants had sample; 8 population: 4/4 variants had sample; 9 target: 2/2 variants had sample; 10 regime: 3/3 variants had sample

SURVIVORS (>= 8/10; only shortlist eligible for the shadow path):
- `model_top_quintile` (8/10) SURVIVOR x3 run(s)

FLICKERS (4-7; watch, don't act):
- `dark_pool.n_prints:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` (5/10)

MIRAGES (<= 3; named and buried - do not rediscover):
- `dark_pool.n_prints:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (3/10)
- `dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (3/10)
- `dark_pool.n_prints:HIGH & flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `float_mechanics.shares_short:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `fundamentals.market_cap:HIGH & liquidity_and_slippage.ask_size:LOW & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW` (0/10)
- `fundamentals.market_cap:HIGH & liquidity_and_slippage.bid_size:LOW & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & liquidity_and_slippage.ask_size:LOW & macro_context.execution_hour:LOW` (0/10)
- `fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & float_mechanics.shares_short:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & dealer_greeks.net_dex:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `liquidity_and_slippage.bid:HIGH & macro_context.day_of_week:LOW & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.day_of_week:LOW & macro_context.execution_hour:LOW` (0/10)
- `liquidity_and_slippage.ask:HIGH & macro_context.day_of_week:LOW & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.float_shares:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.float_shares:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro_context.day_of_week:LOW & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & liquidity_and_slippage.bid:HIGH & macro_context.execution_hour:LOW` (0/10)
- `flow_aggression.ask_sweep_prem:HIGH & macro_context.day_of_week:LOW & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & dealer_greeks.net_dex:HIGH & fundamentals.market_cap:HIGH` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_dex:HIGH & flow_persistence.closing_accel:HIGH` (0/10)
- `flow_persistence.net_directional_prem:HIGH & liquidity_and_slippage.ask_size:MID & macro.sma20:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:MID` (0/10)
- `dealer_greeks.net_vanna:LOW & liquidity_and_slippage.ask_size:MID & macro.spot:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro.spot:HIGH & news.latest_age_hours:LOW` (0/10)
- `liquidity_and_slippage.ask_size:MID & liquidity_and_slippage.bid:HIGH & macro.sma20:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & news.latest_age_hours:LOW & price_action.vwma_20:HIGH` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & liquidity_and_slippage.bid:HIGH & news.latest_age_hours:LOW` (0/10)
- `dark_pool.n_prints:HIGH & gex.zero_gamma_strike:HIGH & news.latest_age_hours:LOW` (0/10)
- `dark_pool.n_prints:HIGH & liquidity_and_slippage.ask_size:LOW & macro_context.execution_hour:MID` (0/10)
- `dealer_greeks.net_vanna:LOW & liquidity_and_slippage.ask_size:MID & macro.sma20:HIGH` (0/10)
- `liquidity_and_slippage.ask:HIGH & liquidity_and_slippage.ask_size:MID & macro.spot:MID` (0/10)
- `dark_pool.n_prints:HIGH & liquidity_and_slippage.bid:HIGH & news.latest_age_hours:LOW` (0/10)
- `fundamentals.market_cap:HIGH & liquidity_and_slippage.ask_size:LOW & macro_context.execution_hour:MID` (0/10)
- `liquidity_and_slippage.ask_size:MID & macro.spot:HIGH & price_action.vwma_20:HIGH` (0/10)
- `fundamentals.market_cap:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:MID` (0/10)
- `liquidity_and_slippage.ask_size:MID & macro.spot:MID` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.closing_accel:HIGH & flow_persistence.net_directional_prem:HIGH` (0/10)
- `gex.zero_gamma_strike:HIGH & news.latest_age_hours:LOW` (0/10)
- `dealer_greeks.net_vanna:LOW & liquidity_and_slippage.ask_size:MID & price_action.vwma_20:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & macro.spot:HIGH & news.latest_age_hours:LOW` (0/10)
- `liquidity_and_slippage.ask_size:MID & macro.sma20:HIGH & macro.spot:HIGH` (0/10)
- `liquidity_and_slippage.ask_size:MID & macro.sma20:HIGH & price_action.vwma_20:HIGH` (0/10)
- `dark_pool.heaviest_node_price:MID & liquidity_and_slippage.ask_size:MID & macro.spot:MID` (0/10)
- `fundamentals.market_cap:HIGH & macro.spot:HIGH & macro_context.execution_hour:MID` (0/10)
- `liquidity_and_slippage.ask_size:MID & liquidity_and_slippage.bid:HIGH & macro.spot:MID` (0/10)
- `flow_aggression.total_flow_prem:HIGH & gex.zero_gamma_strike:HIGH & news.latest_age_hours:LOW` (0/10)
- `dealer_greeks.net_vanna:LOW & liquidity_and_slippage.ask_size:MID & liquidity_and_slippage.bid:HIGH` (0/10)
- `gex.zero_gamma_strike:HIGH & liquidity_and_slippage.ask_size:MID & macro.sma20:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:MID` (0/10)
- `dark_pool.n_prints:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:MID` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_dex:HIGH` (0/10)
- `fundamentals.market_cap:HIGH & liquidity_and_slippage.bid_size:LOW & macro_context.execution_hour:MID` (0/10)
- `dark_pool.n_prints:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:MID` (0/10)
- `dark_pool.n_prints:HIGH & liquidity_and_slippage.ask:HIGH & news.latest_age_hours:LOW` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dark_pool.n_prints:HIGH & news.latest_age_hours:LOW` (0/10)
- `gex.zero_gamma_strike:HIGH & liquidity_and_slippage.ask_size:MID & macro.spot:MID` (0/10)
- `fundamentals.market_cap:HIGH & liquidity_and_slippage.bid:HIGH & macro_context.execution_hour:MID` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `macro.sma20:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `dark_pool.heaviest_node_price:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `liquidity_and_slippage.ask:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `liquidity_and_slippage.bid_size:LOW & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `liquidity_and_slippage.bid:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `macro_context.execution_hour:LOW & news.latest_age_hours:LOW & price_action.vwma_20:HIGH` (0/10)
- `macro.spot:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & liquidity_and_slippage.bid_size:LOW & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & float_mechanics.float_shares:HIGH & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & float_mechanics.shares_short:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & float_mechanics.shares_short:HIGH & macro_context.execution_hour:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & dealer_greeks.net_charm:LOW & fundamentals.market_cap:HIGH` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & fundamentals.market_cap:HIGH & macro_context.day_of_week:LOW` (0/10)
- `macro_context.execution_hour:LOW & price_action.gap_pct:HIGH & relative_momentum.gap_pct:HIGH` (0/10)
- `macro.distance_to_sma20_pct:LOW & pemd.days_to_earnings:MID & price_action.dist_sma50:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW` (0/10)
- `macro_context.execution_hour:LOW & relative_momentum.rvol_20d:LOW & skew.call_iv_25d:HIGH` (0/10)
- `distance_to_zero_gamma_pct:LOW & fundamentals.short_ratio:LOW` (0/10)
- `flow_aggression.ask_sweep_prem:LOW & pemd.days_to_earnings:MID` (0/10)
- `regime_stack.sector_dist_pct:LOW & skew.skew_ratio:MID` (0/10)
- `fundamentals.market_cap:HIGH & macro_context.day_of_week:LOW & macro_context.execution_hour:LOW` (0/10)
- `fundamentals.market_cap:HIGH & liquidity_and_slippage.bid:HIGH & macro_context.execution_hour:LOW` (0/10)
- `macro_context.day_of_week:LOW & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `macro_context.execution_hour:LOW & skew.call_iv_25d:HIGH & technical.rvol_10min:LOW` (0/10)
- `flow_persistence.flow_persistence_pct:MID & regime_stack.sector_dist_pct:LOW & regime_stack.sector_vs_market_spread:LOW` (0/10)
- `fundamentals.short_ratio:LOW & gex.distance_to_zero_gamma_pct:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & liquidity_and_slippage.ask_size:LOW & macro_context.day_of_week:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & gex.zero_gamma_strike:HIGH & macro_context.day_of_week:LOW` (0/10)
- `dealer_greeks.delta_imbalance:MID & regime_stack.sector_vs_market_spread:LOW` (0/10)
- `fundamentals.short_ratio:LOW & macro_context.vix_level:HIGH` (0/10)
- `pemd.days_to_earnings:MID & price_action.dist_sma50:LOW & regime_stack.ticker_dist_pct:LOW` (0/10)
- `days_to_earnings:MID & flow_aggression.ask_sweep_prem:LOW & pemd.days_to_earnings:MID` (0/10)
- `dealer_greeks.delta_imbalance:MID & regime_stack.sector_dist_pct:LOW & regime_stack.sector_vs_market_spread:LOW` (0/10)
- `distance_to_zero_gamma_pct:LOW & fundamentals.short_ratio:LOW & gex.distance_to_zero_gamma_pct:LOW` (0/10)
- `macro_context.execution_hour:LOW & price_action.gap_pct:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & price_action.gap_pct:HIGH` (0/10)
- `macro_context.execution_hour:LOW & relative_momentum.gap_pct:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & macro_context.day_of_week:LOW & technical.atr:HIGH` (0/10)
- `days_to_earnings:MID & flow_aggression.ask_sweep_prem:LOW` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & macro_context.execution_hour:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.total_flow_prem:HIGH & flow_persistence.net_directional_prem:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & fundamentals.market_cap:HIGH & iv_term.iv_ratio:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & macro_context.day_of_week:LOW & technical.atr:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` (0/10)
- `macro_context.day_of_week:LOW & macro_context.iv_term_skew:MID & vrp.realized_vol_20d:MID` (0/10)
- `flow_aggression.total_flow_prem:HIGH & iv_term.iv_back:LOW & macro_context.day_of_week:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & regime_stack.market_spy_dist_pct:HIGH & skew.put_iv_25d:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & gex.zero_gamma_strike:HIGH & macro_context.day_of_week:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & flow_persistence.closing_accel:LOW & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & iv_term.iv_ratio:LOW & vrp.vrp:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro_context.day_of_week:LOW & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.total_flow_prem:HIGH & iv_term.iv_ratio:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & iv_term.iv_front:LOW & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & iv_term.iv_back:LOW & regime_stack.market_spy_dist_pct:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & regime_stack.market_spy_dist_pct:HIGH & skew.call_iv_25d:LOW` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & liquidity_and_slippage.ask_size:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & macro_context.execution_hour:LOW & vrp.front_iv:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.ask_sweep_prem:HIGH & flow_persistence.net_directional_prem:HIGH` (0/10)
- `float_mechanics.float_shares:HIGH & macro_context.day_of_week:LOW & technical.atr:HIGH` (0/10)
- `float_mechanics.shares_short:HIGH & liquidity_and_slippage.ask_size:LOW & macro_context.iv_term_skew:MID` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH & flow_persistence.net_directional_prem:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & flow_persistence.closing_accel:LOW & macro_context.execution_hour:LOW` (0/10)

Plain-English close: 1 finding(s) survived >= 8/10 angles; 135 mirage(s) were luck wearing a good week. The survivors list justifies keeping the Student on schedule.

---
run: 882.8s | rows 32281 | feature-bearing 11284 | trials 68402 | brain-side only, zero live changes