> SYNTHETIC FIXTURE - a deterministic demo showing the fully-populated machinery. NOT a real
> trading week (no live data has been labelled yet). The real weekly reports are `report_harvest_*.md`.

# V12 weekly edge report - harvest_20260704_2200

- snapshot: harvest_20260704_2200  |  live snapshot rows: {'candidates': 140, 'bid_path': 366, 'labels': 140}
- dataset rows: 122 (added +122 vs last run)  |  date range: ['2026-05-28 21:26:40.146000+00:00', '2026-06-02 19:50:43.675000+00:00']
- runtime: 0.1s  |  features: 4

## Rows by tier / outcome / executed
- tier: {'quota_cap': 46, 'prefilter': 43, 'topn': 17, 'random': 16}
- outcome: {'up': 52, 'down': 41, 'vertical': 29}
- executed: {'0': 71, '1': 51}

## Empirical EV thresholds (GATE 2)
- n=122
- empirical breakeven win-prob: 0.5992  CI95%: [0.5492, 0.6435]
- binary sanity floor (0.30/-0.50): 0.6534  <-- RED FLAG: empirical below floor
- empirical mu_win=0.4454 mu_loss=-0.6091 cost=0.0227
- expected shortfall (5% loss tail): -1.0000
- gap-through: {'down_below_-0.50_rate': 0.7073170731707317, 'down_tail_mean': -0.9310344827586207, 'up_beyond_+0.30_rate': 0.6538461538461539, 'up_tail_mean': 0.5823529411764705}

## Engine edge - executed trades
- n_executed=51
- hit rate: 0.5098  Wilson95: [0.3768, 0.6414]
- empirical hurdle: 0.5992  -> below hurdle
- expectancy (mean realized_return, executed): -0.0957

## Sequential edge test (SPRT)
- H0 win-rate=0.622 (hurdle+cost)  H1=0.672 (hurdle+0.05)  alpha=0.05 beta=0.2
- wins 26/51  LLR=-1.535  bounds[-1.558, 2.773]
- decision: **CONTINUE**

## Time-to-resolution (minutes)
- median=1440.0 p10=1440.0 p90=2880.0

## MFE / MAE profile
- MFE mean=0.2000 MAE mean=0.0000

## PBO / Deflated Sharpe (CPCV)
- N/A - CPCV needs >= 1000 rows (have 122). CPCV config: N=10 k=2 -> 45 splits, 9 paths.

## Verdict

INCONCLUSIVE