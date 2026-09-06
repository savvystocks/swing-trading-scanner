# V12 weekly edge report - harvest_20260904_2130

- snapshot: harvest_20260904_2130  |  live snapshot rows: {'candidates': 70129, 'bid_path': 1263292, 'labels': 70073}
- dataset rows: 69781 (added +69781 vs last run)  |  date range: ['2026-07-01 23:59:01.310000+00:00', '2026-09-04 19:54:50.643000+00:00']
- runtime: 38.6s  |  features: 119

## Data quality WARN

- 3 day(s) with zero random-tier rows: ['2026-07-01', '2026-07-02', '2026-07-03']

## Rows by tier / outcome / executed
- tier: {'none': 44502, 'topn': 24269, 'random': 523, 'executed': 487}
- outcome: {'vertical': 38717, 'down': 18256, 'up': 12808}
- executed: {'0': 69294, '1': 487}

## Empirical EV thresholds (GATE 2)
- n=69781
- empirical breakeven win-prob: 0.5460  CI95%: [0.5418, 0.5506]
- binary sanity floor (0.30/-0.50): 0.6691  <-- RED FLAG: empirical below floor
- empirical mu_win=0.3630 mu_loss=-0.3590 cost=0.0353
- expected shortfall (5% loss tail): -0.9339
- gap-through: {'down_below_-0.50_rate': 0.981759421560035, 'down_tail_mean': -0.6539018310550689, 'up_beyond_+0.30_rate': 0.9942223610243598, 'up_tail_mean': 0.5202610410711481}

## Engine edge - executed trades
- n_executed=487
- hit rate: 0.0390  Wilson95: [0.0251, 0.0601]
- empirical hurdle: 0.5460  -> below hurdle
- expectancy (mean realized_return, executed): -0.5643

_stratified by source premium (reporting only; the SPRT object is the pooled executed stream):_
- source premium >=50k: n=403 hit=0.0347 Wilson95=[0.0208, 0.0575]
- source premium 25-50k: n=84 hit=0.0595 Wilson95=[0.0257, 0.1319]

## Engine edge by option expensiveness (IV rank at entry: cheap<33 / normal 33-67 / expensive>=67)  (reporting only; not a gate)
- cheap (IV rank <33): n=125 up-hit=0.0240 Wilson95=[0.0082, 0.0682] mean_return=-0.6391
- normal (33-67): n=261 up-hit=0.0421 Wilson95=[0.0237, 0.0739] mean_return=-0.5345
- expensive (>=67): n=101 up-hit=0.0495 Wilson95=[0.0213, 0.1107] mean_return=-0.5488

_Spread question REOPENED: prior tight-only reading was a synthetic-spread artifact; real executed-spread sample building since 2026-07-09 (n=374 so far)._

## Engine edge by spread width at entry (tight<2% / medium 2-8% / wide>=8%) - REAL spread, since 2026-07-09  (reporting only; not a gate)
- tight (<2%): n=16 up-hit=0.0000 Wilson95=[0.0000, 0.1936] mean_return=-0.4401
- medium (2-8%): n=69 up-hit=0.1014 Wilson95=[0.0500, 0.1949] mean_return=-0.4670
- wide (>=8%): n=289 up-hit=0.0346 Wilson95=[0.0189, 0.0625] mean_return=-0.5481

## Daily brake - SHADOW measurement (reporting only; in shadow the brake does NOT suppress entries)
- would-have-tripped on 15 day(s); would-have-blocked 354 executed entries
- would-have-blocked (brake ACTIVE would remove these): n=354 hit=0.0395 Wilson95=[0.0237, 0.0653] mean_return=-0.5417 total_return=-191.77
- allowed (brake ACTIVE would keep these): n=133 hit=0.0376 Wilson95=[0.0162, 0.0850] mean_return=-0.6243 total_return=-83.04
_blocked worse than allowed -> the brake helps; blocked better -> it costs edge._

## Sequential edge test (SPRT)  [clock starts at the week-one Tier B drop]
- H0 win-rate=0.566 (breakeven+margin 0.02)  H1=0.616 (H0+0.05)  alpha=0.05 beta=0.2
- wins 19/487  LLR=-55.678  bounds[-1.558, 2.773]
- decision: **REJECT**

## Time-to-resolution (minutes)
- median=1496.2 p10=87.9 p90=4685.6

## MFE / MAE profile
- MFE mean=0.0779 MAE mean=-0.3037

## PBO / Deflated Sharpe (CPCV)
- CPCV ready (N=10 k=2 -> 45 splits, 9 paths); populated once a model (Stage 2) produces path performance.

## Verdict

NO-EDGE

## Ops self-test (watchdog)

- last stamp 2026-09-04T21:30:05Z | market_open=0 | inbox-commit age 93m | status **ok**

## Ops telemetry (school 1f)

- alpaca EMPTY: 1 calls this week
- alpaca OK: 146475 calls this week
- fill ledger events ingested: 1095; measured entry fills by spread bucket tight/medium/wide: 175/204/316