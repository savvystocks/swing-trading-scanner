# V12 weekly edge report - harvest_20260706_2130

- snapshot: harvest_20260706_2130  |  live snapshot rows: {'candidates': 3247, 'bid_path': 12069, 'labels': 1827}
- dataset rows: 1565 (added +1565 vs last run)  |  date range: ['2026-07-01 23:59:01.310000+00:00', '2026-07-06 19:42:08.341000+00:00']
- runtime: 0.8s  |  features: 115

## Data quality WARN

- 4 day(s) with zero random-tier rows: ['2026-07-01', '2026-07-02', '2026-07-03', '2026-07-06']

## Rows by tier / outcome / executed
- tier: {'none': 1123, 'topn': 395, 'executed': 47}
- outcome: {'vertical': 1436, 'down': 67, 'up': 62}
- executed: {'0': 1518, '1': 47}

## Empirical EV thresholds (GATE 2)
- n=1565
- empirical breakeven win-prob: 0.5960  CI95%: [0.5687, 0.6245]
- binary sanity floor (0.30/-0.50): 0.6660  <-- RED FLAG: empirical below floor
- empirical mu_win=0.2958 mu_loss=-0.3551 cost=0.0328
- expected shortfall (5% loss tail): -0.9644
- gap-through: {'down_below_-0.50_rate': 0.9552238805970149, 'down_tail_mean': -0.59042271875, 'up_beyond_+0.30_rate': 0.967741935483871, 'up_tail_mean': 0.42850493333333345}

## Engine edge - executed trades
- n_executed=47
- hit rate: 0.0213  Wilson95: [0.0038, 0.1111]
- empirical hurdle: 0.5960  -> below hurdle
- expectancy (mean realized_return, executed): -0.6831

_stratified by source premium (reporting only; the SPRT object is the pooled executed stream):_
- source premium >=50k: n=47 hit=0.0213 Wilson95=[0.0038, 0.1111]

## Sequential edge test (SPRT)  [clock starts at the week-one Tier B drop]
- H0 win-rate=0.616 (breakeven+margin 0.02)  H1=0.666 (H0+0.05)  alpha=0.05 beta=0.2
- wins 1/47  LLR=-6.339  bounds[-1.558, 2.773]
- decision: **REJECT**

## Time-to-resolution (minutes)
- median=5568.4 p10=5388.1 p90=5754.3

## MFE / MAE profile
- MFE mean=-0.1797 MAE mean=-0.2064

## PBO / Deflated Sharpe (CPCV)
- CPCV ready (N=10 k=2 -> 45 splits, 9 paths); populated once a model (Stage 2) produces path performance.

## Verdict

NO-EDGE