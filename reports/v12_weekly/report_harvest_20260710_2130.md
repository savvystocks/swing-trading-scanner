# V12 weekly edge report - harvest_20260710_2130

- snapshot: harvest_20260710_2130  |  live snapshot rows: {'candidates': 9181, 'bid_path': 127112, 'labels': 9176}
- dataset rows: 8912 (added +8912 vs last run)  |  date range: ['2026-07-01 23:59:01.310000+00:00', '2026-07-10 19:12:20.816000+00:00']
- runtime: 4.4s  |  features: 119

## Data quality WARN

- 3 day(s) with zero random-tier rows: ['2026-07-01', '2026-07-02', '2026-07-03']

## Rows by tier / outcome / executed
- tier: {'none': 5769, 'topn': 2913, 'executed': 183, 'random': 47}
- outcome: {'vertical': 5312, 'down': 2194, 'up': 1406}
- executed: {'0': 8729, '1': 183}

## Empirical EV thresholds (GATE 2)
- n=8912
- empirical breakeven win-prob: 0.5482  CI95%: [0.5361, 0.5603]
- binary sanity floor (0.30/-0.50): 0.6704  <-- RED FLAG: empirical below floor
- empirical mu_win=0.3705 mu_loss=-0.3691 cost=0.0363
- expected shortfall (5% loss tail): -0.9523
- gap-through: {'down_below_-0.50_rate': 0.9867821330902461, 'down_tail_mean': -0.6595757154734411, 'up_beyond_+0.30_rate': 0.9950213371266002, 'up_tail_mean': 0.5295127512508935}

## Engine edge - executed trades
- n_executed=183
- hit rate: 0.0273  Wilson95: [0.0117, 0.0624]
- empirical hurdle: 0.5482  -> below hurdle
- expectancy (mean realized_return, executed): -0.6130

_stratified by source premium (reporting only; the SPRT object is the pooled executed stream):_
- source premium >=50k: n=162 hit=0.0247 Wilson95=[0.0096, 0.0618]
- source premium 25-50k: n=21 hit=0.0476 Wilson95=[0.0085, 0.2267]

## Engine edge by option expensiveness (IV rank at entry: cheap<33 / normal 33-67 / expensive>=67)  (reporting only; not a gate)
- cheap (IV rank <33): n=44 up-hit=0.0000 Wilson95=[0.0000, 0.0803] mean_return=-0.7163
- normal (33-67): n=94 up-hit=0.0426 Wilson95=[0.0167, 0.1044] mean_return=-0.5611
- expensive (>=67): n=45 up-hit=0.0222 Wilson95=[0.0039, 0.1157] mean_return=-0.6202

_Spread question REOPENED: prior tight-only reading was a synthetic-spread artifact; real executed-spread sample building since 2026-07-09 (n=70 so far)._

## Engine edge by spread width at entry (tight<2% / medium 2-8% / wide>=8%) - REAL spread, since 2026-07-09  (reporting only; not a gate)
- tight (<2%): n=0 - UNDERPOWERED
- medium (2-8%): n=7 - UNDERPOWERED
- wide (>=8%): n=63 up-hit=0.0476 Wilson95=[0.0163, 0.1309] mean_return=-0.5025

## Daily brake - SHADOW measurement (reporting only; in shadow the brake does NOT suppress entries) - UNDERPOWERED
- would-have-tripped on 3 day(s) of 5 needed; would-have-blocked 71 executed entries
- would-have-blocked (brake ACTIVE would remove these): n=71 hit=0.0423 Wilson95=[0.0145, 0.1170] mean_return=-0.5029 total_return=-35.70
- allowed (brake ACTIVE would keep these): n=112 hit=0.0179 Wilson95=[0.0049, 0.0628] mean_return=-0.6827 total_return=-76.47
_blocked worse than allowed -> the brake helps; blocked better -> it costs edge._

## Sequential edge test (SPRT)  [clock starts at the week-one Tier B drop]
- H0 win-rate=0.568 (breakeven+margin 0.02)  H1=0.618 (H0+0.05)  alpha=0.05 beta=0.2
- wins 5/183  LLR=-21.482  bounds[-1.558, 2.773]
- decision: **REJECT**

## Time-to-resolution (minutes)
- median=1608.3 p10=137.6 p90=5685.5

## MFE / MAE profile
- MFE mean=0.0207 MAE mean=-0.2975

## PBO / Deflated Sharpe (CPCV)
- CPCV ready (N=10 k=2 -> 45 splits, 9 paths); populated once a model (Stage 2) produces path performance.

## Verdict

NO-EDGE

## Ops self-test (watchdog)

- last stamp 2026-07-10T21:30:07Z | market_open=0 | inbox-commit age 97m | status **ok**