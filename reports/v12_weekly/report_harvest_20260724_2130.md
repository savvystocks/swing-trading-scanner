# V12 weekly edge report - harvest_20260724_2130

- snapshot: harvest_20260724_2130  |  live snapshot rows: {'candidates': 24904, 'bid_path': 407558, 'labels': 24888}
- dataset rows: 24610 (added +24610 vs last run)  |  date range: ['2026-07-01 23:59:01.310000+00:00', '2026-07-24 19:52:46.534000+00:00']
- runtime: 9.0s  |  features: 119

## Data quality WARN

- 3 day(s) with zero random-tier rows: ['2026-07-01', '2026-07-02', '2026-07-03']

## Rows by tier / outcome / executed
- tier: {'none': 15957, 'topn': 8028, 'executed': 462, 'random': 163}
- outcome: {'vertical': 13585, 'down': 6703, 'up': 4322}
- executed: {'0': 24148, '1': 462}

## Empirical EV thresholds (GATE 2)
- n=24610
- empirical breakeven win-prob: 0.5643  CI95%: [0.5565, 0.5723]
- binary sanity floor (0.30/-0.50): 0.6718  <-- RED FLAG: empirical below floor
- empirical mu_win=0.3571 mu_loss=-0.3766 cost=0.0375
- expected shortfall (5% loss tail): -0.9370
- gap-through: {'down_below_-0.50_rate': 0.9849321199462927, 'down_tail_mean': -0.6519232699182066, 'up_beyond_+0.30_rate': 0.9942156409069876, 'up_tail_mean': 0.5232447044449615}

## Engine edge - executed trades
- n_executed=462
- hit rate: 0.0303  Wilson95: [0.0181, 0.0502]
- empirical hurdle: 0.5643  -> below hurdle
- expectancy (mean realized_return, executed): -0.5800

_stratified by source premium (reporting only; the SPRT object is the pooled executed stream):_
- source premium >=50k: n=386 hit=0.0285 Wilson95=[0.0160, 0.0503]
- source premium 25-50k: n=76 hit=0.0395 Wilson95=[0.0135, 0.1097]

## Engine edge by option expensiveness (IV rank at entry: cheap<33 / normal 33-67 / expensive>=67)  (reporting only; not a gate)
- cheap (IV rank <33): n=111 up-hit=0.0090 Wilson95=[0.0016, 0.0493] mean_return=-0.6779
- normal (33-67): n=252 up-hit=0.0357 Wilson95=[0.0189, 0.0665] mean_return=-0.5434
- expensive (>=67): n=99 up-hit=0.0404 Wilson95=[0.0158, 0.0993] mean_return=-0.5635

_Spread question REOPENED: prior tight-only reading was a synthetic-spread artifact; real executed-spread sample building since 2026-07-09 (n=349 so far)._

## Engine edge by spread width at entry (tight<2% / medium 2-8% / wide>=8%) - REAL spread, since 2026-07-09  (reporting only; not a gate)
- tight (<2%): n=8 - UNDERPOWERED
- medium (2-8%): n=52 up-hit=0.0385 Wilson95=[0.0106, 0.1298] mean_return=-0.5485
- wide (>=8%): n=289 up-hit=0.0346 Wilson95=[0.0189, 0.0625] mean_return=-0.5481

## Daily brake - SHADOW measurement (reporting only; in shadow the brake does NOT suppress entries)
- would-have-tripped on 12 day(s); would-have-blocked 349 executed entries
- would-have-blocked (brake ACTIVE would remove these): n=349 hit=0.0344 Wilson95=[0.0198, 0.0591] mean_return=-0.5460 total_return=-190.57
- allowed (brake ACTIVE would keep these): n=113 hit=0.0177 Wilson95=[0.0049, 0.0622] mean_return=-0.6849 total_return=-77.39
_blocked worse than allowed -> the brake helps; blocked better -> it costs edge._

## Sequential edge test (SPRT)  [clock starts at the week-one Tier B drop]
- H0 win-rate=0.584 (breakeven+margin 0.02)  H1=0.634 (H0+0.05)  alpha=0.05 beta=0.2
- wins 14/462  LLR=-56.268  bounds[-1.558, 2.773]
- decision: **REJECT**

## Time-to-resolution (minutes)
- median=1547.9 p10=107.2 p90=5558.5

## MFE / MAE profile
- MFE mean=0.0597 MAE mean=-0.3115

## PBO / Deflated Sharpe (CPCV)
- CPCV ready (N=10 k=2 -> 45 splits, 9 paths); populated once a model (Stage 2) produces path performance.

## Verdict

NO-EDGE

## Ops self-test (watchdog)

- last stamp 2026-07-24T21:30:04Z | market_open=0 | inbox-commit age 96m | status **ok**