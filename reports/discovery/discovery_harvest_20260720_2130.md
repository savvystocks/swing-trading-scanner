# Discovery report - harvest_20260720_2130

## Plain-English close-out

Three best-looking findings (honesty numbers attached - OOS, PBO, trials, sample):
- `dealer_greeks.net_dex:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.6518 (n_eff 19.4, lift 4.76) | PBO 0.133 | trials 64862
- `dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.6421 (n_eff 34.2, lift 4.689) | PBO 0.133 | trials 64862
- `fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.6256 (n_eff 21.8, lift 4.568) | PBO 0.133 | trials 64862

Worst-confused features: 4 feature(s) too sparse to band (blind, not useless - sensor repair pending); the per-feature fill rates below separate blind from useless.
Today's data contains a HINT of an edge (survivors exist but have not cleared the promotion bar) - not yet defensible.
Zero live changes were made by this run: it reads the snapshot and writes this report only.

## Part 1 - Feature Verdict Table

- dataset: 16806 graded rows; feature-bearing 5998 (35.7% of the pile - the 'none' prefilter tier carries no feature vector and cannot be searched; that is a fill-rate fact, not a finding)
- cost-inclusive hurdle (empirical, THE bar - never the retired 62.5% figure): 0.5961 CI ['0.5806', '0.6105'] at mean cost 0.0519
- full per-band table: `verdict_harvest_20260720_2130.csv` (fill rate first, then weighted up-rate + CI, mean return, EV per band; thin bands say UNDERPOWERED)

Fill rate by feature block (lowest first - blind-vs-useless disambiguation):
```
block
brake_shadow                        0.038
days_to_earnings                    0.488
days_since_earnings                 0.661
post_earnings_iv_crush_flag         0.661
float_mechanics                     0.683
fundamentals                        0.685
skew                                0.791
iv_term                             0.791
vrp                                 0.791
distance_to_heaviest_dp_node_pct    0.976
price_action                        0.992
distance_to_zero_gamma_pct          0.995
gex                                 0.995
macro                               0.995
technical                           0.995
relative_momentum                   0.995
dealer_greeks                       0.999
flow_persistence_pct                0.999
liquidity_and_slippage              0.999
flow_aggression                     1.000
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
- `f.macro_context.day_of_week` MDA 0.0651 (fill 100%): genuinely moves OOS separation this week.
- `f.dealer_greeks.net_charm` MDA 0.0155 (fill 100%): genuinely moves OOS separation this week.
- `f.technical.atr` MDA 0.0138 (fill 99%): genuinely moves OOS separation this week.
- `f.dark_pool.n_prints` MDA 0.0101 (fill 100%): genuinely moves OOS separation this week.
- `f.dealer_greeks.net_dex` MDA 0.0076 (fill 100%): genuinely moves OOS separation this week.
Bottom five (no OOS contribution this week - dead weight or blind):
- `f.float_mechanics.float_shares` MDA -0.0036 (fill 68%): populated but useless so far.
- `f.alt_catalyst.insider_10d_buy_usd` MDA -0.0038 (fill 100%): populated but useless so far.
- `f.regime_stack.sector_dist_pct` MDA -0.0038 (fill 68%): populated but useless so far.
- `f.fundamentals.short_ratio` MDA -0.0042 (fill 68%): populated but useless so far.
- `f.regime_stack.market_spy_dist_pct` MDA -0.0067 (fill 100%): populated but useless so far.

## Part 2 - The Search (everything counted)

- model: gbm under purged+embargoed folds; OOS weighted AUC 0.696; top-quintile OOS up-rate 0.3366 vs pool 0.1369 (n_eff 392)
- calibration: isotonic, Brier sigmoid 0.157 / isotonic 0.270
- readable rules (depth <= 3), mined on train folds, graded OOS only:
  - `float_mechanics.float_shares:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.6920 (n_eff 11.9, lift 5.053) | PBO 0.133 | trials 64862
  - `dealer_greeks.net_dex:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.6518 (n_eff 19.4, lift 4.76) | PBO 0.133 | trials 64862
  - `dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.6421 (n_eff 34.2, lift 4.689) | PBO 0.133 | trials 64862
  - `fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.6256 (n_eff 21.8, lift 4.568) | PBO 0.133 | trials 64862
  - `dark_pool.n_prints:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4994 (n_eff 48.0, lift 3.647) | PBO 0.133 | trials 64862
  - `dark_pool.n_prints:HIGH & dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.4381 (n_eff 56.3, lift 3.199) | PBO 0.133 | trials 64862
  - `dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` OOS up-rate 0.4056 (n_eff 72.8, lift 2.962) | PBO 0.133 | trials 64862
  - `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & macro_context.execution_hour:LOW` OOS up-rate 0.3925 (n_eff 79.3, lift 2.866) | PBO 0.133 | trials 64862

### THE COUNTER (non-negotiable)

- trials this run, ALL angles aggregated: `{'model_fits': 127, 'verdict_bands': 234, 'rules_evaluated': 64276, 'thresholds': 198, 'angle_runs': 27, 'TOTAL': 64862}`
- PBO fed by the whole campaign: 0.133 
- Deflated Sharpe of the walk-forward champion: UNDERPOWERED (2 OOS windows; needs >= 4)

## Part 3 - The Honest Dated Replay (walk-forward)

- 2026-W28: train 0 -> test 2832 - UNDERPOWERED (train too thin)
- 2026-W29: train 3143 -> test 2702, champion `rule[dark_pool.n_prints:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW]`, takes 120 (n_eff 48.5), OOS up-rate 0.5338, OOS net ret -0.0056 
- 2026-W30: train 5897 -> test 101, champion `rule[dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH]`, takes 37 (n_eff 21.6), OOS up-rate 0.6997, OOS net ret 0.1763 

- trade-by-trade ledger (every test-week candidate, decision + stated reason + graded outcome + net P&L): `ledger_harvest_20260720_2130.csv`
- TRUE out-of-sample territory today: 2 scoreable week(s). That is THIN - verdict-grade replay needs months, not weeks; treat every number above accordingly.

Three lines, uniqueness-weighted, cost-inclusive (cumulative weighted net return):
- engine's actual picks: -41.596
- discovered strategy (OOS takes): 2.142
- pool baseline (every candidate): -358.100

## Part 4 - Standing process

- this rig re-runs with every Sunday brain cycle and appends here (reports/discovery/); the convergence matrix accretes in `convergence_state.json`.
- promotion rule (in ROADMAP): a SURVIVOR whose OOS lower CI clears the cost-inclusive hurdle with PBO <= 0.20 across consecutive runs becomes a SHADOW candidate for the Student pipeline - never a live deployment from this rig.
- nothing clears the promotion bar this run. What would change the odds: more graded weeks (the binding constraint), repaired sparse sensors (earnings/short-float/IV-term/skew/dark-pool blocks), or an owner-decided re-sourcing of the signal itself (the referenced adjudication file does not exist in this repo - flagged).

## Part 5 - The Ten Angles (Convergence Matrix)

Cells: confirmed / weak / absent / UNDERPOWERED. Judged by intersection, never selection.

| finding | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | confirmed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `model_top_quintile` | C | C | C | w | C | C | C | C | C | C | 9/10 |
| `dark_pool.n_prints:HIGH & dealer_greeks.net_vann` | C | w | w | C | w | C | C | w | C | w | 5/10 |
| `dealer_greeks.net_vanna:HIGH & macro_context.exe` | C | w | w | C | w | C | C | w | C | w | 5/10 |
| `dark_pool.n_prints:HIGH & fundamentals.market_ca` | C | w | w | C | w | C | C | w | C | w | 5/10 |
| `fundamentals.market_cap:HIGH & macro_context.exe` | C | w | w | C | w | C | w | w | w | w | 3/10 |
| `dealer_greeks.net_vanna:HIGH & flow_aggression.t` | U | - | - | U | - | U | - | - | U | - | 0/10 |
| `dealer_greeks.net_vanna:HIGH & news.latest_age_h` | U | w | - | U | w | U | - | - | U | - | 0/10 |
| `days_to_earnings:HIGH & dealer_greeks.net_vanna:` | U | w | - | U | w | U | - | - | - | - | 0/10 |
| `dealer_greeks.net_dex:HIGH & macro_context.execu` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `days_to_earnings:HIGH & float_mechanics.float_sh` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `dealer_greeks.net_dex:HIGH & fundamentals.market` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `float_mechanics.float_shares:HIGH & news.latest_` | w | w | w | w | w | w | w | w | w | w | 0/10 |
| `dealer_greeks.net_charm:LOW & dealer_greeks.net_` | U | - | - | U | - | U | - | - | - | - | 0/10 |

Angle sample notes: 1 seeds: 3/3 variants had sample; 2 time slices: 3/3 variants had sample; 3 bands: 3/3 variants had sample; 4 learner: 3/3 variants had sample; 5 weighting: 2/2 variants had sample; 6 costs: 2/2 variants had sample; 7 labels: 2/2 variants had sample; 8 population: 4/4 variants had sample; 9 target: 2/2 variants had sample; 10 regime: 3/3 variants had sample

SURVIVORS (>= 8/10; only shortlist eligible for the shadow path):
- `model_top_quintile` (9/10) SURVIVOR x1 run(s)

FLICKERS (4-7; watch, don't act):
- `dark_pool.n_prints:HIGH & dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW` (5/10)
- `dealer_greeks.net_vanna:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (5/10)
- `dark_pool.n_prints:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` (5/10)

MIRAGES (<= 3; named and buried - do not rediscover):
- `fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (3/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & news.latest_age_hours:LOW & pemd.days_to_earnings:HIGH` (0/10)
- `days_to_earnings:HIGH & dealer_greeks.net_vanna:HIGH & news.latest_age_hours:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `days_to_earnings:HIGH & float_mechanics.float_shares:HIGH & news.latest_age_hours:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.float_shares:HIGH & news.latest_age_hours:LOW & pemd.days_to_earnings:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & dealer_greeks.net_dex:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & pemd.days_to_earnings:HIGH` (0/10)
- `float_mechanics.float_shares:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `fundamentals.market_cap:HIGH & liquidity_and_slippage.bid_size:LOW & macro_context.execution_hour:MID` (0/10)
- `technical.atr:MID & technical.rvol_10min:LOW` (0/10)
- `fundamentals.market_cap:HIGH & macro.spot:HIGH & macro_context.execution_hour:MID` (0/10)
- `days_to_earnings:HIGH & fundamentals.market_cap:HIGH & macro_context.day_of_week:MID` (0/10)
- `relative_momentum.rvol_20d:LOW & technical.atr:MID & technical.rvol_10min:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:HIGH & macro.spot:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH & flow_persistence.net_directional_prem:MID` (0/10)
- `technical.rvol_10min:LOW & vrp.vrp:MID` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.closing_accel:HIGH & macro.spot:HIGH` (0/10)
- `fundamentals.market_cap:HIGH & macro.sma20:HIGH & macro_context.execution_hour:MID` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `fundamentals.market_cap:HIGH & liquidity_and_slippage.ask_size:LOW & macro_context.execution_hour:MID` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_persistence.closing_accel:HIGH & fundamentals.market_cap:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `flow_persistence.closing_accel:HIGH & gex.zero_gamma_strike:HIGH & news.latest_age_hours:LOW` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & fundamentals.market_cap:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.closing_accel:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.ask_sweep_prem:HIGH & fundamentals.market_cap:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH & fundamentals.market_cap:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & macro_context.day_of_week:MID` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `flow_persistence.closing_accel:HIGH & liquidity_and_slippage.ask:HIGH & news.latest_age_hours:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:HIGH & price_action.vwma_20:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.total_flow_prem:HIGH & flow_persistence.closing_accel:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:HIGH & macro.sma20:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro_context.sector_vs_spy:LOW` (0/10)
- `liquidity_and_slippage.ask_size:LOW & macro_context.day_of_week:MID & price_action.vwma_20:HIGH` (0/10)
- `dark_pool.heaviest_node_price:HIGH & dealer_greeks.net_dex:HIGH & flow_persistence.closing_accel:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & fundamentals.market_cap:HIGH & macro_context.sector_vs_spy:LOW` (0/10)
- `fundamentals.market_cap:HIGH & macro_context.day_of_week:MID & pemd.days_to_earnings:HIGH` (0/10)
- `flow_persistence.net_directional_prem:HIGH & technical.atr:MID` (0/10)
- `fundamentals.market_cap:HIGH & macro_context.execution_hour:MID & price_action.vwma_20:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & news.latest_age_hours:LOW & pemd.days_to_earnings:HIGH` (0/10)
- `relative_momentum.rvol_20d:LOW & technical.atr:MID` (0/10)
- `dealer_greeks.net_dex:HIGH & flow_persistence.net_directional_prem:HIGH & gex.zero_gamma_strike:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & liquidity_and_slippage.ask_size:LOW & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & macro.sma20:HIGH & news.latest_age_hours:LOW` (0/10)
- `flow_aggression.ask_sweep_prem:HIGH & macro.sma20:HIGH & news.latest_age_hours:LOW` (0/10)
- `dark_pool.heaviest_node_price:HIGH & flow_aggression.ask_sweep_prem:HIGH & news.latest_age_hours:LOW` (0/10)
- `macro.spot:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & liquidity_and_slippage.ask_size:LOW & macro_context.execution_hour:LOW` (0/10)
- `liquidity_and_slippage.bid:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & news.latest_age_hours:LOW & technical.atr:HIGH` (0/10)
- `days_to_earnings:HIGH & float_mechanics.float_shares:HIGH & float_mechanics.shares_short:HIGH` (0/10)
- `liquidity_and_slippage.ask_size:LOW & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `float_mechanics.float_shares:HIGH & float_mechanics.shares_short:HIGH & pemd.days_to_earnings:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro.sma20:HIGH & news.latest_age_hours:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `dark_pool.heaviest_node_price:HIGH & macro_context.execution_hour:LOW & news.latest_age_hours:LOW` (0/10)
- `dark_pool.n_prints:HIGH & float_mechanics.shares_short:HIGH & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & macro_context.execution_hour:LOW & technical.atr:HIGH` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & float_mechanics.float_shares:HIGH & news.latest_age_hours:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & float_mechanics.float_shares:HIGH & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & flow_aggression.total_flow_prem:HIGH & macro_context.vix_level:HIGH` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & float_mechanics.shares_short:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `float_mechanics.shares_short:HIGH & flow_aggression.ask_sweep_prem:HIGH & macro_context.vix_level:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & liquidity_and_slippage.ask_size:LOW & macro_context.day_of_week:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & float_mechanics.shares_short:HIGH & gex.net_gex:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & price_action.gap_pct:HIGH & relative_momentum.gap_pct:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & macro_context.day_of_week:LOW & macro_context.execution_hour:LOW` (0/10)
- `flow_aggression.ask_sweep_prem:HIGH & relative_momentum.rvol_20d:LOW` (0/10)
- `float_mechanics.float_shares:LOW & flow_persistence.n_ticks:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & gex.net_gex:HIGH` (0/10)
- `float_mechanics.short_pct_float:HIGH & fundamentals.market_cap:LOW & regime_stack.sector_dist_pct:LOW` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.day_of_week:MID & macro_context.execution_hour:LOW` (0/10)
- `flow_persistence.n_ticks:HIGH & regime_stack.sector_dist_pct:LOW & regime_stack.sector_vs_market_spread:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & price_action.gap_pct:HIGH` (0/10)
- `fundamentals.market_cap:LOW & fundamentals.short_pct_float:HIGH & regime_stack.sector_dist_pct:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & flow_aggression.total_flow_prem:HIGH & macro_context.day_of_week:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & fundamentals.market_cap:HIGH & macro_context.day_of_week:MID` (0/10)
- `dealer_greeks.net_vanna:HIGH & flow_aggression.total_flow_prem:HIGH & macro_context.day_of_week:MID` (0/10)
- `dealer_greeks.net_charm:LOW & dealer_greeks.net_dex:HIGH & gex.net_gex:HIGH` (0/10)
- `flow_persistence.n_ticks:HIGH & regime_stack.sector_vs_market_spread:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & gex.zero_gamma_strike:HIGH & macro_context.day_of_week:MID` (0/10)
- `dealer_greeks.net_charm:LOW & dealer_greeks.net_vanna:HIGH & gex.net_gex:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & macro_context.day_of_week:LOW & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & gex.zero_gamma_strike:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.day_of_week:LOW & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & relative_momentum.gap_pct:HIGH` (0/10)
- `dealer_greeks.net_dex:HIGH & dealer_greeks.net_vanna:HIGH & gex.net_gex:HIGH` (0/10)
- `news.latest_age_hours:LOW & relative_momentum.rvol_20d:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & fundamentals.short_pct_float:HIGH & skew.call_iv_25d:HIGH` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & macro_context.day_of_week:MID & macro_context.execution_hour:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & float_mechanics.short_pct_float:HIGH & skew.call_iv_25d:HIGH` (0/10)
- `dark_pool.distance_to_heaviest_dp_node_pct:MID & dark_pool.n_prints:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `dealer_greeks.net_vanna:HIGH & float_mechanics.float_shares:HIGH & relative_momentum.rvol_20d:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & relative_momentum.rvol_20d:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & fundamentals.market_cap:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_vanna:HIGH & float_mechanics.float_shares:HIGH & pemd.days_to_earnings:HIGH` (0/10)
- `dealer_greeks.net_charm:LOW & float_mechanics.float_shares:HIGH & pemd.days_to_earnings:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_charm:MID & dealer_greeks.net_dex:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `float_mechanics.shares_short:HIGH & flow_aggression.ask_sweep_prem:HIGH & flow_aggression.total_flow_prem:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & technical.rvol_10min:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & liquidity_and_slippage.bid_size:LOW & news.latest_age_hours:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & dealer_greeks.net_vanna:HIGH & fundamentals.market_cap:HIGH` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:MID & dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW & technical.rvol_10min:LOW` (0/10)
- `flow_persistence.net_directional_prem:HIGH & macro_context.execution_hour:LOW & skew.call_iv_25d:LOW` (0/10)
- `liquidity_and_slippage.ask_size:LOW & macro_context.day_of_week:LOW & news.latest_age_hours:LOW` (0/10)
- `dark_pool.n_prints:HIGH & iv_term.iv_front:LOW & liquidity_and_slippage.bid_size:LOW` (0/10)
- `float_mechanics.shares_short:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `flow_aggression.total_flow_prem:HIGH & liquidity_and_slippage.ask_size:LOW & skew.call_iv_25d:LOW` (0/10)
- `dealer_greeks.net_dex:HIGH & float_mechanics.shares_short:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `dark_pool.n_prints:HIGH & liquidity_and_slippage.bid_size:LOW & skew.call_iv_25d:LOW` (0/10)
- `liquidity_and_slippage.bid_size:LOW & skew.call_iv_25d:LOW & vrp.vrp:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & liquidity_and_slippage.ask_size:LOW & skew.put_iv_25d:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & dark_pool.n_prints:HIGH & liquidity_and_slippage.bid_size:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & iv_term.iv_front:LOW & liquidity_and_slippage.bid_size:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & iv_term.iv_front:LOW & liquidity_and_slippage.ask_size:LOW` (0/10)
- `dark_pool.n_prints:HIGH & liquidity_and_slippage.bid_size:LOW & vrp.front_iv:LOW` (0/10)
- `dark_pool.n_prints:HIGH & macro_context.execution_hour:LOW & relative_momentum.rvol_20d:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & fundamentals.market_cap:HIGH & macro_context.day_of_week:LOW` (0/10)
- `dealer_greeks.net_charm:LOW & macro_context.execution_hour:LOW & relative_momentum.rvol_20d:LOW` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & dealer_greeks.net_vanna:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)
- `alt_catalyst.reddit_mention_delta_pct:LOW & liquidity_and_slippage.bid_size:LOW & vrp.front_iv:LOW` (0/10)
- `flow_aggression.total_flow_prem:HIGH & liquidity_and_slippage.ask_size:LOW & vrp.front_iv:LOW` (0/10)
- `flow_persistence.net_directional_prem:HIGH & macro_context.execution_hour:LOW & skew.put_iv_25d:LOW` (0/10)
- `dark_pool.n_prints:HIGH & dealer_greeks.net_charm:LOW & macro_context.day_of_week:LOW` (0/10)
- `dealer_greeks.net_charm:MID & dealer_greeks.net_dex:HIGH & flow_aggression.ask_sweep_prem:HIGH` (0/10)

Plain-English close: 1 finding(s) survived >= 8/10 angles; 140 mirage(s) were luck wearing a good week. The survivors list justifies keeping the Student on schedule.

---
run: 1230.5s | rows 16806 | feature-bearing 5998 | trials 64862 | brain-side only, zero live changes