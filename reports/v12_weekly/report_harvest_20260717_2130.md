# V12 weekly edge report - harvest_20260717_2130

- snapshot: harvest_20260717_2130  |  live snapshot rows: {'candidates': 16944, 'bid_path': 266724, 'labels': 16928}
- dataset rows: 16655 (added +16655 vs last run)  |  date range: ['2026-07-01 23:59:01.310000+00:00', '2026-07-17 19:51:55.342000+00:00']
- runtime: 8.2s  |  features: 119

## Data quality WARN

- 3 day(s) with zero random-tier rows: ['2026-07-01', '2026-07-02', '2026-07-03']

## Rows by tier / outcome / executed
- tier: {'none': 10758, 'topn': 5459, 'executed': 330, 'random': 108}
- outcome: {'vertical': 9280, 'down': 4378, 'up': 2997}
- executed: {'0': 16325, '1': 330}

## Empirical EV thresholds (GATE 2)
- n=16655
- empirical breakeven win-prob: 0.5623  CI95%: [0.5529, 0.5715]
- binary sanity floor (0.30/-0.50): 0.6722  <-- RED FLAG: empirical below floor
- empirical mu_win=0.3562 mu_loss=-0.3713 cost=0.0378
- expected shortfall (5% loss tail): -0.9331
- gap-through: {'down_below_-0.50_rate': 0.9878940155322065, 'down_tail_mean': -0.6501145012716764, 'up_beyond_+0.30_rate': 0.9946613279946613, 'up_tail_mean': 0.508341419657833}

## Engine edge - executed trades
- n_executed=330
- hit rate: 0.0303  Wilson95: [0.0165, 0.0549]
- empirical hurdle: 0.5623  -> below hurdle
- expectancy (mean realized_return, executed): -0.5943

_stratified by source premium (reporting only; the SPRT object is the pooled executed stream):_
- source premium >=50k: n=284 hit=0.0282 Wilson95=[0.0143, 0.0546]
- source premium 25-50k: n=46 hit=0.0435 Wilson95=[0.0120, 0.1453]

## Engine edge by option expensiveness (IV rank at entry: cheap<33 / normal 33-67 / expensive>=67)  (reporting only; not a gate)
- cheap (IV rank <33): n=85 up-hit=0.0000 Wilson95=[0.0000, 0.0432] mean_return=-0.7080
- normal (33-67): n=168 up-hit=0.0417 Wilson95=[0.0203, 0.0835] mean_return=-0.5445
- expensive (>=67): n=77 up-hit=0.0390 Wilson95=[0.0133, 0.1084] mean_return=-0.5776

_Spread question REOPENED: prior tight-only reading was a synthetic-spread artifact; real executed-spread sample building since 2026-07-09 (n=217 so far)._

## Engine edge by spread width at entry (tight<2% / medium 2-8% / wide>=8%) - REAL spread, since 2026-07-09  (reporting only; not a gate)
- tight (<2%): n=4 - UNDERPOWERED
- medium (2-8%): n=18 up-hit=0.0000 Wilson95=[0.0000, 0.1759] mean_return=-0.5538
- wide (>=8%): n=195 up-hit=0.0410 Wilson95=[0.0209, 0.0789] mean_return=-0.5481

## Daily brake - SHADOW measurement (reporting only; in shadow the brake does NOT suppress entries)
- would-have-tripped on 8 day(s); would-have-blocked 217 executed entries
- would-have-blocked (brake ACTIVE would remove these): n=217 hit=0.0369 Wilson95=[0.0188, 0.0710] mean_return=-0.5472 total_return=-118.74
- allowed (brake ACTIVE would keep these): n=113 hit=0.0177 Wilson95=[0.0049, 0.0622] mean_return=-0.6849 total_return=-77.39
_blocked worse than allowed -> the brake helps; blocked better -> it costs edge._

## Sequential edge test (SPRT)  [clock starts at the week-one Tier B drop]
- H0 win-rate=0.582 (breakeven+margin 0.02)  H1=0.632 (H0+0.05)  alpha=0.05 beta=0.2
- wins 10/330  LLR=-39.977  bounds[-1.558, 2.773]
- decision: **REJECT**

## Time-to-resolution (minutes)
- median=1557.5 p10=107.4 p90=5627.4

## MFE / MAE profile
- MFE mean=0.0504 MAE mean=-0.3042

## PBO / Deflated Sharpe (CPCV)
- CPCV ready (N=10 k=2 -> 45 splits, 9 paths); populated once a model (Stage 2) produces path performance.

## Verdict

NO-EDGE

## Ops self-test (watchdog)

- last stamp 2026-07-17T21:30:05Z | market_open=0 | inbox-commit age 97m | status **ok**