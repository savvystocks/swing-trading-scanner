# Winner stress test - 2026-08-23

Config: FADE / deep-bear (SPY < -3% vs 50d) / 50k-1M / spread<=3% / delta<0.30 /
stop -60 / trail trigger 80 / give 20%. Entry at ask, outcomes on bid.

Trades: 2521 across 47 trading days, in 2 distinct episodes.
Day-clustered mean +63.7%  t +4.63

## The honest unit: EPISODES (bear days cluster into corrections; they are not independent)

Episode count: 2   episode-mean +79.3%   episode-clustered t +0.00

  episode 1: 2025-03-04 .. 2025-04-23  (33d)  mean +40.6%
  episode 2: 2026-03-12 .. 2026-04-02  (14d)  mean +118.1%

## Concentration - the day ladder (top 8 and bottom 5)

  2025-04-21  +354.0%
  2026-03-30  +313.4%
  2026-04-01  +266.7%
  2025-04-22  +216.9%
  2026-03-27  +213.3%
  2026-03-31  +167.6%
  2026-04-02  +155.3%
  2025-04-23  +152.5%
  ...
  2025-03-11  -29.9%
  2025-03-06  -34.6%
  2025-03-04  -41.3%
  2025-03-14  -41.3%
  2025-03-07  -47.1%

## Jackknife

| removed | day-mean | t |
|---|---|---|
| top 0 day(s) | +63.7% | +4.63 |
| top 1 day(s) | +57.4% | +4.59 |
| top 2 day(s) | +51.7% | +4.54 |
| top 3 day(s) | +46.8% | +4.45 |
| top 5 day(s) | +38.8% | +4.16 |
| the entire best EPISODE (2026-03-12..2026-04-02) | +40.6% | +2.73 |

## At the LIVE spread cap (<=2.0) instead of 3.0

days 44, day-mean +57.6%, t +3.94

## Verdict

If the episode-clustered t collapses below ~2, or dropping the best episode kills it,
this is a handful of corrections - size it as a lottery, not an edge.
