# Treasurer + macro brake (Phase 4, SHADOW) - harvest_20260731_2130

Sizing is a recommendation only; the engine sizes a FIXED 1 contract until the Governor
promotes the Treasurer. All figures cost-inclusive and bid-side.

## Sizing of the Council's shadow TAKEs
- Council TAKEs sized this run: 0
- empirical mean win +0.506 / mean loss -0.459  (payoff ratio 1.10)
- recommended contracts (median / max): 0 / 0  [half-Kelly cap 0.5, hard cap 0.25, $800 budget, liquidity 10%]

## P(halt) - NORTH_STAR pre-live requirement
- probability of a -30% drawdown under the measured TAKE distribution: None  (UNDERPOWERED (0 TAKE returns; needs >= 20))
- UNDERPOWERED (0 TAKE returns; needs >= 20)

## Macro circuit brake
- rows where the macro brake WOULD have fired: 0 of 11284 (0.0%)  [VIX>= 32 or +20% spike]
- shadow only: records would-have-braked; arms live only through LIVE_GATE + Governor.

- trials counted (council pass): {'council_features_clustered_out': 30, 'council_rule_folds': 5, 'council_member_fits': 25, 'TOTAL': 60}

SHADOW ONLY - no order, size, or brake was changed. The frozen engine is untouched.