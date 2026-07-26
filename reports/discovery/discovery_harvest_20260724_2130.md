# Discovery report - harvest_20260724_2130

## Plain-English close-out

Three best-looking findings (honesty numbers attached - OOS, PBO, trials, sample):
- `dealer_greeks.net_vanna:HIGH & macro.spot:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.5021 (n_eff 66.9, lift 3.882) | PBO 0.000 | trials 65527
- `dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.4965 (n_eff 91.7, lift 3.839) | PBO 0.000 | trials 65527
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW` OOS up-rate 0.4725 (n_eff 66.5, lift 3.653) | PBO 0.000 | trials 65527

Worst-confused features: 4 feature(s) too sparse to band (blind, not useless - sensor repair pending); the per-feature fill rates below separate blind from useless.
Today's data contains a HINT of an edge (survivors exist but have not cleared the promotion bar) - not yet defensible.
Zero live changes were made by this run: it reads the snapshot and writes this report only.

## Part 1 - Feature Verdict Table

- dataset: 24610 graded rows; feature-bearing 8653 (35.2% of the pile - the 'none' prefilter tier carries no feature vector and cannot be searched; that is a fill-rate fact, not a finding)
- cost-inclusive hurdle (empirical, THE bar - never the retired 62.5% figure): 0.5944 CI ['0.5811', '0.6068'] at mean cost 0.0511
- full per-band table: `verdict_harvest_20260724_2130.csv` (fill rate first, then weighted up-rate + CI, mean return, EV per band; thin bands say UNDERPOWERED)

Fill rate by feature block (lowest first - blind-vs-useless disambiguation):
```
block
brake_shadow                        0.040
days_to_earnings                    0.540
days_since_earnings                 0.664
post_earnings_iv_crush_flag         0.664
fundamentals                        0.686
float_mechanics                     0.687
skew                                0.775
iv_term                             0.775
vrp                                 0.775
distance_to_heaviest_dp_node_pct    0.978
price_action                        0.989
distance_to_zero_gamma_pct          0.996
gex                                 0.996
macro                               0.996
technical                           0.996
relative_momentum                   0.996
dealer_greeks                       0.999
flow_persistence_pct                0.999
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
- `f.macro_context.day_of_week` MDA 0.0941 (fill 100%): genuinely moves OOS separation this week.
- `f.technical.atr` MDA 0.0164 (fill 100%): genuinely moves OOS separation this week.
- `f.dark_pool.n_prints` MDA 0.0076 (fill 100%): genuinely moves OOS separation this week.
- `f.dealer_greeks.net_vanna` MDA 0.0072 (fill 100%): genuinely moves OOS separation this week.
- `f.flow_persistence.flow_persistence_pct` MDA 0.0068 (fill 100%): genuinely moves OOS separation this week.
Bottom five (no OOS contribution this week - dead weight or blind):
- `f.macro_context.sector_vs_spy` MDA -0.0018 (fill 69%): populated but useless so far.
- `f.fundamentals.short_ratio` MDA -0.0020 (fill 69%): populated but useless so far.
- `f.iv_term.iv_ratio` MDA -0.0021 (fill 78%): populated but useless so far.
- `f.macro_context.iv_term_skew` MDA -0.0027 (fill 78%): populated but useless so far.
- `f.pemd.days_to_earnings` MDA -0.0043 (fill 54%): populated but useless so far.

## Part 2 - The Search (everything counted)

- model: gbm under purged+embargoed folds; OOS weighted AUC 0.719; top-quintile OOS up-rate 0.3276 vs pool 0.1293 (n_eff 554)
- calibration: isotonic, Brier sigmoid 0.152 / isotonic 0.150
- readable rules (depth <= 3), mined on train folds, graded OOS only:
  - `dealer_greeks.net_vanna:HIGH & macro.spot:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.5021 (n_eff 66.9, lift 3.882) | PBO 0.000 | trials 65527
  - `dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.4965 (n_eff 91.7, lift 3.839) | PBO 0.000 | trials 65527
  - `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW` OOS up-rate 0.4725 (n_eff 66.5, lift 3.653) | PBO 0.000 | trials 65527
  - `dark_pool.n_prints:HIGH & dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4560 (n_eff 99.4, lift 3.526) | PBO 0.000 | trials 65527
  - `dealer_greeks.net_vanna:HIGH & liquidity_and_slippage.bid:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4517 (n_eff 65.5, lift 3.492) | PBO 0.000 | trials 65527
  - `dealer_greeks.net_charm:LOW & macro.spot:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4455 (n_eff 72.6, lift 3.444) | PBO 0.000 | trials 65527
  - `dark_pool.n_prints:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4261 (n_eff 68.7, lift 3.294) | PBO 0.000 | trials 65527
  - `dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.4212 (n_eff 57.7, lift 3.257) | PBO 0.000 | trials 65527

### THE COUNTER (non-negotiable)

- trials this run, ALL angles aggregated: `{'model_fits': 130, 'verdict_bands': 234, 'rules_evaluated': 64937, 'thresholds': 199, 'angle_runs': 27, 'TOTAL': 65527}`
- PBO fed by the whole campaign: 0.000 CSCV over 4000 partitions, sampled 4000 of C(15,7)
- Deflated Sharpe of the walk-forward champion: UNDERPOWERED (1 OOS windows; needs >= 4)

## Part 3 - The Honest Dated Replay (walk-forward)

- 2026-W28: train 0 -> test 2832 - UNDERPOWERED (train too thin)
- 2026-W29: train 3143 -> test 2702, champion `gbm@p>=0.40`, takes 364 (n_eff 110.3), OOS up-rate 0.3299, OOS net ret -0.2757 
- 2026-W30: train 5897 -> test 2756, champion `gbm@p>=0.50`, takes 0 (n_eff 0.0), OOS up-rate N/A, OOS net ret N/A UNDERPOWERED (takes too thin)

- trade-by-trade ledger (every test-week candidate, decision + stated reason + graded outcome + net P&L): `ledger_harvest_20260724_2130.csv`
- TRUE out-of-sample territory today: 2 scoreable week(s). That is THIN - verdict-grade replay needs months, not weeks; treat every number above accordingly.

Three lines, uniqueness-weighted, cost-inclusive (cumulative weighted net return):
- engine's actual picks: -67.723
- discovered strategy (OOS takes): -9.285
- pool baseline (every candidate): -694.238

## Part 4 - Standing process

- this rig re-runs with every Sunday brain cycle and appends here (reports/discovery/); the convergence matrix accretes in `convergence_state.json`.
- promotion rule (in ROADMAP): a SURVIVOR whose OOS lower CI clears the cost-inclusive hurdle with PBO <= 0.20 across consecutive runs becomes a SHADOW candidate for the Student pipeline - never a live deployment from this rig.
- nothing clears the promotion bar this run. What would change the odds: more graded weeks (the binding constraint), repaired sparse sensors (earnings/short-float/IV-term/skew/dark-pool blocks), or an owner-decided re-sourcing of the signal itself (the referenced adjudication file does not exist in this repo - flagged).

## Part 5 - The Ten Angles (Convergence Matrix)

Cells: confirmed / weak / absent / UNDERPOWERED. Judged by intersection, never selection.

| finding | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | confirmed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `model_top_quintile` | C | C | C | w | C | C | C | C | C | C | 9/10 |
| `dark_pool.n_prints:HIGH & fundamentals.market_ca` | C | w | w | C | w | C | C | w | C | w | 5/10 |
| `dark_pool.n_prints:HIGH & dealer_greeks.net_vann` | C | w | w | C | w | C | C | w | C | w | 5/10 |
| `dealer_greeks.net_vanna:HIGH & gex.zero_gamma_st` | C | w | w | C | w | C | w | w | w | w | 3/10 |
| `dealer_greeks.net_vanna:HIGH & macro.spot:HIGH &` | C | w | w | C | w | C | w | w | w | w | 3/10 |
| `dealer_greeks.net_vanna:HIGH & liquidity_and_sli` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `dark_pool.heaviest_node_price:HIGH & dealer_gree` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `dark_pool.n_prints:HIGH & gex.zero_gamma_strike:` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `dealer_greeks.net_charm:LOW & macro_context.exec` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `dealer_greeks.net_charm:LOW & dealer_greeks.net_` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `fundamentals.market_cap:HIGH & liquidity_and_sli` | U | - | - | U | - | U | - | - | U | - | 0/10 |
| `dealer_greeks.net_charm:LOW & macro.spot:HIGH & ` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `fundamentals.market_cap:HIGH & liquidity_and_sli` | U | - | - | U | - | U | - | - | - | - | 0/10 |
| `fundamentals.market_cap:HIGH & macro_context.exe` | w | w | w | w | w | w | w | w | w | w | 0/10 |

Angle sample notes: 1 seeds: 3/3 variants had sample; 2 time slices: 3/3 variants had sample; 3 bands: 3/3 variants had sample; 4 learner: 3/3 variants had sample; 5 weighting: 2/2 variants had sample; 6 costs: 2/2 variants had sample; 7 labels: 2/2 variants had sample; 8 population: 4/4 variants had sample; 9 target: 2/2 variants had sample; 10 regime: 3/3 variants had sample

SURVIVORS (>= 8/10; only shortlist eligible for the shadow path):
- `model_top_quintile` (9/10) SURVIVOR x2 run(s)

FLICKERS (4-7; watch, don't act):
- `dark_pool.n_prints:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` (5/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW` (5/10)

MIRAGES (<= 3; named and buried - do not rediscover):
- `dealer_greeks.net_vanna:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (3/10)
- `dealer_greeks.net_vanna:HIGH & macro.spot:HIGH & macro_context.execution_hour:LOW` (3/10)
- `dealer_greeks.net_vanna:HIGH & liquidity_and_slippage.bid:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & dealer_greeks.net_dex:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `fundamentals.market_cap:HIGH & liquidity_and_slippage.ask_size:LOW & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & macro.spot:HIGH & macro_context.execution_hour:LOW` (0/10)
- `fundamentals.market_cap:HIGH & liquidity_and_slippage.bid_size:LOW & macro_context.execution_hour:LOW` (0/10)
- `fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `macro_context.execution_hour:LOW & skew.skew_ratio:MID & technical.atr:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW & skew.skew_ratio:MID` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:MID` (0/10)
- `flow_persistence.net_directional_prem:HIGH & fundamentals.market_cap:HIGH & macro.sma20:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & news.latest_age_hours:MID` (0/10)
- `flow_persistence.closing_accel:HIGH & gex.zero_gamma_strike:HIGH & macro.spot:HIGH` (0/10)
- `flow_persistence.net_directional_prem:HIGH & fundamentals.market_cap:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.closing_accel:HIGH & macro.spot:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & gex.zero_gamma_strike:HIGH & news.latest_age_hours:LOW` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:MID` (0/10)
- `flow_aggression.ask_sweep_prem:HIGH & fundamentals.market_cap:HIGH & pemd.days_to_earnings:MID` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_dex:HIGH & flow_persistence.closing_accel:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & flow_persistence.net_directional_prem:HIGH & macro.spot:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.closing_accel:HIGH & flow_persistence.net_directional_prem:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.closing_accel:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `days_to_earnings:MID & fundamentals.market_cap:HIGH` (0/10)
- `flow_persistence.closing_accel:HIGH & gex.zero_gamma_strike:HIGH & liquidity_and_slippage.ask:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & fundamentals.market_cap:HIGH` (0/10)
- `flow_aggression.ask_sweep_prem:MID & flow_persistence.closing_accel:HIGH` (0/10)
- `fundamentals.market_cap:HIGH & pemd.days_to_earnings:MID` (0/10)
- `dark_pool.n_prints:HIGH & flow_persistence.net_directional_prem:HIGH & news.latest_age_hours:LOW` (0/10)
- `flow_persistence.net_directional_prem:HIGH & fundamentals.market_cap:HIGH & price_action.vwma_20:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:HIGH & liquidity_and_slippage.ask_size:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH & flow_persistence.net_directional_prem:MID` (0/10)
- `flow_persistence.net_directional_prem:HIGH & macro.sma20:HIGH & news.latest_age_hours:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:MID & macro.spot:HIGH` (0/10)
- `flow_persistence.net_directional_prem:HIGH & fundamentals.market_cap:HIGH & news.latest_age_hours:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & fundamentals.market_cap:HIGH & pemd.days_to_earnings:MID` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:MID & liquidity_and_slippage.ask:HIGH` (0/10)
- `flow_persistence.closing_accel:HIGH & gex.zero_gamma_strike:HIGH & liquidity_and_slippage.bid_size:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:MID & macro.sma20:HIGH` (0/10)
- `dark_pool.heaviest_node_price:HIGH & flow_persistence.closing_accel:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `flow_persistence.net_directional_prem:HIGH & news.latest_age_hours:LOW & price_action.vwma_20:HIGH` (0/10)
- `flow_persistence.net_directional_prem:HIGH & fundamentals.market_cap:HIGH & liquidity_and_slippage.bid:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH & relative_momentum.rvol_20d:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.closing_accel:HIGH & liquidity_and_slippage.bid:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & flow_persistence.closing_accel:HIGH & liquidity_and_slippage.ask:HIGH` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dark_pool.n_prints:HIGH & news.latest_age_hours:LOW` (0/10)
- `dark_pool.n_prints:HIGH & macro.spot:HIGH & news.latest_age_hours:LOW` (0/10)
- `flow_aggression.ask_sweep_prem:HIGH & liquidity_and_slippage.ask:HIGH & news.latest_age_hours:LOW` (0/10)
- `dark_pool.heaviest_node_price:HIGH & flow_aggression.total_flow_prem:HIGH & news.latest_age_hours:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro.sma20:HIGH & news.latest_age_hours:LOW` (0/10)
- `flow_aggression.ask_sweep_prem:HIGH & liquidity_and_slippage.bid:HIGH & news.latest_age_hours:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & news.latest_age_hours:LOW & technical.atr:HIGH` (0/10)
- `dark_pool.heaviest_node_price:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `dark_pool.node_size:MID & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dark_pool.node_size:MID & liquidity_and_slippage.bid:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.node_size:MID & macro_context.execution_hour:LOW & price_action.vwma_20:HIGH` (0/10)
- `dark_pool.node_size:MID & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `liquidity_and_slippage.ask:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `dark_pool.heaviest_node_price:HIGH & flow_aggression.ask_sweep_prem:HIGH & news.latest_age_hours:LOW` (0/10)
- `dark_pool.n_prints:HIGH & macro.sma20:HIGH & news.latest_age_hours:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro.spot:HIGH & news.latest_age_hours:LOW` (0/10)
- `macro.spot:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `dark_pool.node_size:MID & flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & float_mechanics.shares_short:HIGH & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & liquidity_and_slippage.bid:HIGH & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & float_mechanics.float_shares:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & liquidity_and_slippage.ask_size:LOW & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW` (0/10)
- `macro_context.execution_hour:LOW & relative_momentum.gap_pct:HIGH` (0/10)
- `news.vader_compound:HIGH & pemd.days_to_earnings:MID` (0/10)
- `dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW` (0/10)
- `news_sentiment_score:HIGH & pemd.days_to_earnings:MID & price_action.dist_sma50:LOW` (0/10)
- `macro_context.execution_hour:LOW & skew.call_iv_25d:HIGH & technical.rvol_10min:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & fundamentals.market_cap:HIGH & macro_context.day_of_week:MID` (0/10)
- `days_to_earnings:MID & news.vader_compound:HIGH & price_action.dist_sma50:LOW` (0/10)
- `days_to_earnings:MID & flow_aggression.ask_sweep_prem:LOW` (0/10)
- `days_to_earnings:MID & news.vader_compound:HIGH` (0/10)
- `days_to_earnings:MID & news_sentiment_score:HIGH & price_action.dist_sma50:LOW` (0/10)
- `days_to_earnings:MID & flow_aggression.ask_sweep_prem:LOW & pemd.days_to_earnings:MID` (0/10)
- `days_to_earnings:MID & news_sentiment_score:HIGH` (0/10)
- `news_sentiment_score:HIGH & pemd.days_to_earnings:MID` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & gex.zero_gamma_strike:HIGH & macro_context.day_of_week:MID` (0/10)
- `news.vader_compound:HIGH & pemd.days_to_earnings:MID & price_action.dist_sma50:LOW` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & skew.skew_ratio:MID` (0/10)
- `flow_aggression.total_flow_prem:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `flow_persistence.n_ticks:HIGH & pemd.days_to_earnings:MID` (0/10)
- `dealer_greeks.net_dex:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `macro_context.execution_hour:LOW & relative_momentum.rvol_20d:LOW & skew.call_iv_25d:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.ask_sweep_prem:HIGH & macro.spot:HIGH` (0/10)
- `macro_context.execution_hour:LOW & price_action.gap_pct:HIGH & relative_momentum.gap_pct:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.day_of_week:MID & macro_context.execution_hour:LOW` (0/10)
- `fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW & skew.skew_ratio:MID` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `flow_aggression.ask_sweep_prem:LOW & pemd.days_to_earnings:MID` (0/10)
- `dealer_greeks.net_vanna:HIGH & liquidity_and_slippage.ask:HIGH & macro_context.execution_hour:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & macro_context.day_of_week:MID & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & macro_context.execution_hour:LOW` (0/10)
- `macro_context.execution_hour:LOW & price_action.gap_pct:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.total_flow_prem:HIGH & macro_context.day_of_week:MID` (0/10)
- `dealer_greeks.net_charm:LOW & price_action.gap_pct:HIGH` (0/10)
- `days_to_earnings:MID & news.vader_compound:HIGH & pemd.days_to_earnings:MID` (0/10)
- `dealer_greeks.net_charm:LOW & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & news.latest_age_hours:LOW & skew.put_iv_25d:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & news.latest_age_hours:LOW & skew.put_iv_25d:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_persistence.net_directional_prem:HIGH & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & dealer_greeks.net_vanna:HIGH & technical.atr:HIGH` (0/10)
- `gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW & skew.skew_ratio:MID` (0/10)
- `liquidity_and_slippage.bid:HIGH & liquidity_and_slippage.bid_size:LOW & news.latest_age_hours:LOW` (0/10)
- `iv_term.iv_front:LOW & news.latest_age_hours:LOW & price_action.vwma_20:HIGH` (0/10)
- `fundamentals.market_cap:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & liquidity_and_slippage.ask:HIGH & macro_context.day_of_week:LOW` (0/10)
- `gex.zero_gamma_strike:HIGH & iv_term.iv_front:LOW & news.latest_age_hours:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & float_mechanics.float_shares:HIGH & liquidity_and_slippage.bid_size:LOW` (0/10)
- `dark_pool.heaviest_node_price:HIGH & liquidity_and_slippage.bid_size:LOW & news.latest_age_hours:LOW` (0/10)
- `liquidity_and_slippage.bid_size:LOW & news.latest_age_hours:LOW & price_action.vwma_20:HIGH` (0/10)
- `float_mechanics.shares_short:HIGH & pemd.iv_rank_1y:HIGH & technical.atr:HIGH` (0/10)
- `liquidity_and_slippage.bid_size:LOW & news.latest_age_hours:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & liquidity_and_slippage.bid_size:LOW & news.latest_age_hours:LOW` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.day_of_week:MID & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.ask_sweep_prem:HIGH & flow_persistence.net_directional_prem:HIGH` (0/10)
- `liquidity_and_slippage.bid_size:LOW & macro.sma20:HIGH & news.latest_age_hours:LOW` (0/10)
- `dark_pool.n_prints:HIGH & float_mechanics.shares_short:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.total_flow_prem:HIGH & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & dealer_greeks.net_vanna:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.total_flow_prem:HIGH & flow_persistence.net_directional_prem:HIGH` (0/10)
- `float_mechanics.float_shares:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & flow_aggression.ask_sweep_prem:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & liquidity_and_slippage.ask:HIGH & macro_context.day_of_week:LOW` (0/10)
- `dark_pool.n_prints:HIGH & flow_aggression.ask_sweep_prem:HIGH & macro_context.day_of_week:MID` (0/10)
- `dark_pool.heaviest_node_price:HIGH & macro_context.execution_hour:LOW & skew.skew_ratio:MID` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.day_of_week:LOW & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_vanna:HIGH & macro_context.day_of_week:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & pemd.iv_rank_1y:HIGH & technical.atr:HIGH` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_charm:LOW & macro_context.day_of_week:LOW` (0/10)
- `gex.zero_gamma_strike:HIGH & news.latest_age_hours:LOW & vrp.front_iv:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & pemd.iv_rank_1y:HIGH & technical.atr:HIGH` (0/10)

Plain-English close: 1 finding(s) survived >= 8/10 angles; 154 mirage(s) were luck wearing a good week. The survivors list justifies keeping the Student on schedule.

---
run: 609.7s | rows 24610 | feature-bearing 8653 | trials 65527 | brain-side only, zero live changes