# V12 weekly edge report - harvest_20260731_2130

- snapshot: harvest_20260731_2130  |  live snapshot rows: {'candidates': 32581, 'bid_path': 526199, 'labels': 32559}
- dataset rows: 32281 (added +32281 vs last run)  |  date range: ['2026-07-01 23:59:01.310000+00:00', '2026-07-31 19:52:25.503000+00:00']
- runtime: 17.4s  |  features: 119

## Data quality WARN

- 3 day(s) with zero random-tier rows: ['2026-07-01', '2026-07-02', '2026-07-03']

## Rows by tier / outcome / executed
- tier: {'none': 20997, 'topn': 10589, 'executed': 477, 'random': 218}
- outcome: {'vertical': 17210, 'down': 9060, 'up': 6011}
- executed: {'0': 31804, '1': 477}

## Empirical EV thresholds (GATE 2)
- n=32281
- empirical breakeven win-prob: 0.5594  CI95%: [0.5526, 0.5658]
- binary sanity floor (0.30/-0.50): 0.6719  <-- RED FLAG: empirical below floor
- empirical mu_win=0.3695 mu_loss=-0.3838 cost=0.0375
- expected shortfall (5% loss tail): -0.9457
- gap-through: {'down_below_-0.50_rate': 0.9856512141280354, 'down_tail_mean': -0.656196158118701, 'up_beyond_+0.30_rate': 0.9940109798702379, 'up_tail_mean': 0.5324880813389121}

## Engine edge - executed trades
- n_executed=477
- hit rate: 0.0377  Wilson95: [0.0240, 0.0589]
- empirical hurdle: 0.5594  -> below hurdle
- expectancy (mean realized_return, executed): -0.5692

_stratified by source premium (reporting only; the SPRT object is the pooled executed stream):_
- source premium >=50k: n=394 hit=0.0330 Wilson95=[0.0194, 0.0556]
- source premium 25-50k: n=83 hit=0.0602 Wilson95=[0.0260, 0.1334]

## Engine edge by option expensiveness (IV rank at entry: cheap<33 / normal 33-67 / expensive>=67)  (reporting only; not a gate)
- cheap (IV rank <33): n=121 up-hit=0.0248 Wilson95=[0.0085, 0.0704] mean_return=-0.6445
- normal (33-67): n=256 up-hit=0.0391 Wilson95=[0.0214, 0.0704] mean_return=-0.5404
- expensive (>=67): n=100 up-hit=0.0500 Wilson95=[0.0215, 0.1118] mean_return=-0.5517

_Spread question REOPENED: prior tight-only reading was a synthetic-spread artifact; real executed-spread sample building since 2026-07-09 (n=364 so far)._

## Engine edge by spread width at entry (tight<2% / medium 2-8% / wide>=8%) - REAL spread, since 2026-07-09  (reporting only; not a gate)
- tight (<2%): n=10 - UNDERPOWERED
- medium (2-8%): n=65 up-hit=0.0923 Wilson95=[0.0430, 0.1871] mean_return=-0.4739
- wide (>=8%): n=289 up-hit=0.0346 Wilson95=[0.0189, 0.0625] mean_return=-0.5481

## Daily brake - SHADOW measurement (reporting only; in shadow the brake does NOT suppress entries)
- would-have-tripped on 14 day(s); would-have-blocked 352 executed entries
- would-have-blocked (brake ACTIVE would remove these): n=352 hit=0.0369 Wilson95=[0.0217, 0.0622] mean_return=-0.5439 total_return=-191.46
- allowed (brake ACTIVE would keep these): n=125 hit=0.0400 Wilson95=[0.0172, 0.0902] mean_return=-0.6404 total_return=-80.05
_blocked worse than allowed -> the brake helps; blocked better -> it costs edge._

## Sequential edge test (SPRT)  [clock starts at the week-one Tier B drop]
- H0 win-rate=0.579 (breakeven+margin 0.02)  H1=0.629 (H0+0.05)  alpha=0.05 beta=0.2
- wins 18/477  LLR=-56.594  bounds[-1.558, 2.773]
- decision: **REJECT**

## Time-to-resolution (minutes)
- median=1497.3 p10=93.5 p90=5487.9

## MFE / MAE profile
- MFE mean=0.0721 MAE mean=-0.3172

## PBO / Deflated Sharpe (CPCV)
- CPCV ready (N=10 k=2 -> 45 splits, 9 paths); populated once a model (Stage 2) produces path performance.

## Verdict

NO-EDGE

## Ops self-test (watchdog)

- last stamp 2026-07-31T21:30:04Z | market_open=0 | inbox-commit age 97m | status **ok**

## Ops telemetry (school 1f)

- alpaca OK: 115545 calls this week
- fill ledger events ingested: 761; measured entry fills by spread bucket tight/medium/wide: 131/107/285