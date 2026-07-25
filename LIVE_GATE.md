# LIVE_GATE — the pre-registered activation ladder

This file is the FINAL EXAM. It exists so that if a "yes" ever comes, it is exactly as unbendable as
every "no" before it. Every threshold below was written BEFORE the result it judges. Changing any
number here is a governed amendment at a Sunday boundary, committed alone, with the reason logged —
never a same-day reaction to a result. NORTH_STAR.md outranks this file; ROADMAP.md holds the
standing owner decisions it references.

Nothing in this file makes a gate easier to pass. Its only job is to pin the gates down.

## The one thing that is already live

The **spread cap** (`max_bid_ask_spread_pct`, real Alpaca spread at OCC resolution) is the single
owner-approved governed change and gates the frozen engine as of the Phase-1 merge. Everything else
below is dormant or shadow.

## Organ authority ladder (Governor-enforced)

Each school organ (Student, Council, each discovery survivor, Treasurer, macro brake) climbs only by
evidence and only through the Governor:

```
FROZEN → CANDIDATE → SHADOW_PROVEN → ELIGIBLE_FOR_OWNER → LIVE
```

- A rung is earned by **6 consecutive GREEN weekly verdicts** (`governor.PROMOTE_WEEKS`).
- Any **RED demotes one rung within one cycle** and zeroes the streak. Automatic, immediate.
- The Governor **never** writes the LIVE rung. `owner_promoted` in `governor_registry.json` is the
  owner's switch and the only path from ELIGIBLE_FOR_OWNER to LIVE.
- Performance drift or population drift caps a GREEN at AMBER — a drifting organ cannot be promoted.

## Gate-mode activation (addendum Section 1) — FLIP 1, gatekeeper

`school_mode` (tunable, default `off`). Moving it off→gatekeeper requires ALL of:

1. The **Student** has passed all four acceptance gates and is at ELIGIBLE_FOR_OWNER, owner-promoted.
2. The **Council** is at SHADOW_PROVEN or better (its TAKE selection Wilson lower bound has cleared
   the contract-bar median for the required consecutive weeks).
3. **Backstop dependency (flagged 2026-07-25):** fleet-wide backstop is enabled **and at least one
   live stop-fill has been reconciled** through the fill ledger, OR the owner explicitly records
   acceptance of the unproven stop leg. Gate-mode attaches a broker-side ratchet stop to every order;
   that leg must be proven before it is trusted fleet-wide.
4. The off-state byte-identity MOT check (`v12_school_mot`) is green on the shipping commit.
5. Every activation and de-activation is a Governor registry event; there is no silent arming.

**Demotion:** a RED verdict on the live organ, or a macro-brake day, drops `school_mode` back to
`off` (frozen engine) within one cycle.

## Gate-mode activation — FLIP 2, sourcing

`school_mode = sourcing` (school takes engine-SKIPPED candidates) is **HARD-BLOCKED** until:

- The fill ledger shows executed fills spanning the spread spectrum (tight / medium / wide buckets
  all populated), i.e. the Phase-1f coverage line reports no gap; AND
- Flip 1 has run live for its own evidence period (a separate trial in the counter, six consecutive
  GREEN); AND
- Owner promotion, as above.

## Fail-closed contract (addendum Section 2, canonical)

- **MISSING FEATURE** (stale past its `feature_ttl.json` TTL, or absent) → the model's native
  missing-data path. Never substituted, never a veto.
- **FAILED COMPONENT** (no calibrated probability, no quote, brake cannot evaluate, broker
  unreachable, latency budget exceeded) → absolute VETO for that cycle. Retries with backoff inside
  the latency budget; per-cycle, never a blacklist.
- Vetoes are counted by cause; the weekly report renders the false-veto rate. Loosening any veto is a
  governed Lane-B change past the pre-registered false-veto threshold below.

## Pre-registered constants (frozen; change = governed amendment)

| constant | value | meaning |
|---|---|---|
| Student gate: OOS Wilson lower bound | > empirical cost-inclusive hurdle | proof of edge |
| Student gate: PBO | ≤ 0.20 | not overfit |
| Student gate: Deflated Sharpe | > 0.5 | better than luck given the trials |
| Student gate: beats engine | net > engine net, same purged splits | worth more than the incumbent |
| feature-bearing gate | 8,000 rows | below this the verdict is WITHHELD/PROVISIONAL |
| Governor promotion | 6 consecutive GREEN weeks | one rung |
| Council disagreement band | member-prob std ≤ 0.18 | a split house does not trade |
| Council quorum | 3 of 5 members must score | else component-failure VETO |
| Treasurer Kelly ceiling | half-Kelly, 25% hard cap | sizing ambition, capped until proven |
| per-trade budget | $800 | until the EV machinery justifies otherwise in writing |
| liquidity cap | ≤ 10% of resting top-of-book | a recommendation that can actually fill |
| automatic halt | −30% from high-water | entries stop, human review required |
| P(halt) review | computed before any live sizing | if uncomfortably high, sizing comes down first |
| macro brake | VIX ≥ 32 or +20% spike, or index ≤ −4% vs 20d SMA | market-wide veto |
| false-veto threshold | > 5% of cycles, sustained | triggers a governed veto-loosening review |

## The pivot rule (draft — see ROADMAP)

The machinery outlives any single signal. The signal source is declared **mined out** only when, on
matured data (≥ 8,000 feature-bearing rows), the Student is REJECTED for **6 consecutive weekly
runs** AND no discovery survivor has reached SHADOW_PROVEN AND the stock-horizon escape route has
failed its tripwire for 2 consecutive runs. Meeting all three opens the owner pivot conversation —
different structures or a different signal source — with the harness kept intact. Nothing pivots
automatically; the rule exists so the decision is made on evidence, calmly, not abandoned on a bad
week.
