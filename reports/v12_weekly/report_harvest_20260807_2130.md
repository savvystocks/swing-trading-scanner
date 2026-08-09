# V12 weekly edge report - harvest_20260807_2130

- snapshot: harvest_20260807_2130  |  live snapshot rows: {'candidates': 39430, 'bid_path': 645837, 'labels': 39402}
- dataset rows: 39124 (added +39124 vs last run)  |  date range: ['2026-07-01 23:59:01.310000+00:00', '2026-08-07 19:53:04.041000+00:00']
- runtime: 17.5s  |  features: 119

## Data quality WARN

- 3 day(s) with zero random-tier rows: ['2026-07-01', '2026-07-02', '2026-07-03']

## Rows by tier / outcome / executed
- tier: {'none': 25371, 'topn': 13011, 'executed': 481, 'random': 261}
- outcome: {'vertical': 20756, 'down': 11083, 'up': 7285}
- executed: {'0': 38643, '1': 481}

## Empirical EV thresholds (GATE 2)
- n=39124
- empirical breakeven win-prob: 0.5599  CI95%: [0.5542, 0.5657]
- binary sanity floor (0.30/-0.50): 0.6716  <-- RED FLAG: empirical below floor
- empirical mu_win=0.3689 mu_loss=-0.3846 cost=0.0373
- expected shortfall (5% loss tail): -0.9506
- gap-through: {'down_below_-0.50_rate': 0.9848416493729135, 'down_tail_mean': -0.6586249994502977, 'up_beyond_+0.30_rate': 0.9936856554564173, 'up_tail_mean': 0.5278757310401989}

## Engine edge - executed trades
- n_executed=481
- hit rate: 0.0395  Wilson95: [0.0254, 0.0609]
- empirical hurdle: 0.5599  -> below hurdle
- expectancy (mean realized_return, executed): -0.5674

_stratified by source premium (reporting only; the SPRT object is the pooled executed stream):_
- source premium >=50k: n=397 hit=0.0353 Wilson95=[0.0211, 0.0583]
- source premium 25-50k: n=84 hit=0.0595 Wilson95=[0.0257, 0.1319]

## Engine edge by option expensiveness (IV rank at entry: cheap<33 / normal 33-67 / expensive>=67)  (reporting only; not a gate)
- cheap (IV rank <33): n=122 up-hit=0.0246 Wilson95=[0.0084, 0.0698] mean_return=-0.6442
- normal (33-67): n=259 up-hit=0.0425 Wilson95=[0.0239, 0.0744] mean_return=-0.5373
- expensive (>=67): n=100 up-hit=0.0500 Wilson95=[0.0215, 0.1118] mean_return=-0.5517

_Spread question REOPENED: prior tight-only reading was a synthetic-spread artifact; real executed-spread sample building since 2026-07-09 (n=368 so far)._

## Engine edge by spread width at entry (tight<2% / medium 2-8% / wide>=8%) - REAL spread, since 2026-07-09  (reporting only; not a gate)
- tight (<2%): n=10 - UNDERPOWERED
- medium (2-8%): n=69 up-hit=0.1014 Wilson95=[0.0500, 0.1949] mean_return=-0.4670
- wide (>=8%): n=289 up-hit=0.0346 Wilson95=[0.0189, 0.0625] mean_return=-0.5481

## Daily brake - SHADOW measurement (reporting only; in shadow the brake does NOT suppress entries)
- would-have-tripped on 15 day(s); would-have-blocked 354 executed entries
- would-have-blocked (brake ACTIVE would remove these): n=354 hit=0.0395 Wilson95=[0.0237, 0.0653] mean_return=-0.5417 total_return=-191.77
- allowed (brake ACTIVE would keep these): n=127 hit=0.0394 Wilson95=[0.0169, 0.0889] mean_return=-0.6390 total_return=-81.16
_blocked worse than allowed -> the brake helps; blocked better -> it costs edge._

## Sequential edge test (SPRT)  [clock starts at the week-one Tier B drop]
- H0 win-rate=0.580 (breakeven+margin 0.02)  H1=0.630 (H0+0.05)  alpha=0.05 beta=0.2
- wins 19/481  LLR=-56.970  bounds[-1.558, 2.773]
- decision: **REJECT**

## Time-to-resolution (minutes)
- median=1476.2 p10=88.1 p90=5438.1

## MFE / MAE profile
- MFE mean=0.0729 MAE mean=-0.3183

## PBO / Deflated Sharpe (CPCV)
- CPCV ready (N=10 k=2 -> 45 splits, 9 paths); populated once a model (Stage 2) produces path performance.

## Verdict

NO-EDGE

## Ops self-test (watchdog)

- last stamp 2026-08-07T21:30:04Z | market_open=0 | inbox-commit age 96m | status **ok**

## Ops telemetry (school 1f)

- alpaca OK: 117098 calls this week
- fill ledger events ingested: 811; measured entry fills by spread bucket tight/medium/wide: 131/115/291