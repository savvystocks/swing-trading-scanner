# BULL VARIANT HEAD-TO-HEAD - 2026-09-09
corpus 73263 archive trades; exit -50/+50/0.20; paired on shared days.

| variant | trades | days | %/day | excess vs pool | t vs pool |
|---|---|---|---|---|---|
| BULL_DIP | 3784 | 206 | +9.36 | +4.87 | +2.37 |
| BULL_CALLS | 20994 | 206 | +10.13 | +5.64 | +3.73 |
| BULL_MOMO | 17207 | 206 | +10.41 | +5.92 | +3.68 |
| BULL_CONF | 163 | 8 | +18.84 | n/a | n/a |

## Does the dip filter earn its place? (each variant MINUS BULL_DIP, paired)

| variant vs BULL_DIP | shared days | mean diff | t | reading |
|---|---|---|---|---|
| BULL_CALLS | 206 | +0.77 | +0.42 | indistinguishable |
| BULL_MOMO | 206 | +1.05 | +0.49 | indistinguishable |
| BULL_CONF | 8 | - | - | too few shared days |

DECISION RULE (pre-registered here, before reading): drop the dip filter only if BULL_CALLS beats BULL_DIP at t>=+1.8 paired. Anything less is 'indistinguishable' and the live seat stays as it is - a filter is not removed on a hunch, and an indistinguishable variant is not an improvement, it is a coin flip with extra steps.

CAVEATS: bar-replay exits, one historical path, bull regimes only (~46% of days). BULL_DIP has ZERO live closed evidence, so nothing live is contradicted either way.
