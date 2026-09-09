# REGIME MASTERS - DESIGN DRAFT v1 (owner order 2026-09-09, pre-panel)

Owner's architecture: three master strategies - BULL, MILD, BEAR - that trade only their
regime, and promotion transfers INFORMATION (proven indicators/conditions) into the master
rather than seating new strategies. The masters become uniformly well-rounded accumulations
of everything every probe has proven. Precedent already live: EXIT_STOP40 promoted a knob,
not a strategy; the 3x3 grid anchors are condition-sets born from probes.

## 1. Spec structure
fade_book_spec.json gains masters.{BULL,MILD,BEAR}, each:
  conditions: ordered list of DATA predicates, e.g.
    {"path": "candidate.total_premium", "op": ">", "value": 100000}
    {"path": "md.macro.distance_to_sma20_pct", "op": "<", "value": 0}
    {"path": "candidate.flow_type", "op": "==", "value": "call"}
  exits: via existing probe.tuning (glide rule applies unchanged)
  merge_history: [{date, source_probe, condition, evidence, prev_conditions}]
  evidence_clock: restarts on every merge (anti-churn law)
Predicates use a WHITELISTED path vocabulary and ops (>, <, ==, abs<) interpreted by a
small evaluator in the engine - merges are data commits, never code edits.

## 2. Engine
Three roster entries MASTER_BULL/MASTER_MILD/MASTER_BEAR: filter = regime match AND all
spec conditions true. Seeded at migration with their regime anchor's CURRENT conditions
(BULL_DIP, DIP_CONF_MILD, DIP_CONVEXITY) so day one changes no behavior. Anchors then
retire from the roster (their identities live on inside the masters' merge_history).
All-regime strategies (FOLLOW_CALLS) and structural books (CREDIT_SPREAD_W) are NOT
per-regime and keep the classic seat path. WINNER_PROFILE/X stay frozen controls forever -
benchmarks are never merged.

## 3. Two promotion paths (sunday_boundary)
SEAT path (unchanged): structural/all-regime strategies promote as themselves.
MERGE path (new): an indicator-probe passing the standard bar (>=8 virgin days, trimmed
t>=1.8 vs control, both halves, floor) generates a MERGE PROPOSAL: its defining condition
into its regime's master. Owner-ACK telegram required. On ACK: spec commit appends the
condition (AND semantics; OR-shaped ideas must arrive as their own probe), evidence clock
restarts, 14d cooldown, merge logged. Cadence cap: max 1 merge per master per month.

## 4. Court treatment of masters
Masters are judged like any probe vs EXEC_BASELINE. A merge that degrades the master
triggers auto-rollback of the LAST merge only (demotion symmetry over merge_history -
revert to prev_conditions, same machinery class as auto_* rollback). Interaction honesty:
a merged condition-set is a NEW cohort; nothing inherits the source probe's t-stats - the
master re-earns from its restarted clock.

## 5. Proof-account interplay
Masters are natural proof-seat candidates (the NORTH_STAR v1.5 regime portfolio). Rule:
a master holding a proof seat is TEACHER-FROZEN - merges queue until the stint concludes
(pass or fail). A queued merge applied after a passed stint restarts the next stint's clock.

## 6. Coverage (registry rule - ships in the same commits)
MOT: predicate-evaluator unit checks (each op, unknown-path rejection, empty-conditions
refuses to trade); roster presence; seed-equivalence check (master seeded == anchor
behavior on fixtures). Regime drill: one scenario per master. Sentinel: masters block
parses + merge_history monotone. Odometer: every merge logs a trial entry.

## 7. Migration order
Build AFTER proof Phases B/C and the gate pre-registration (owner priority 2026-09-09).
Step 1 evaluator + seeded masters (behavior-identical); step 2 anchors retire; step 3
merge path in the boundary. Each step through full gates.

## Open questions for the panel
- AND-only merge semantics: too restrictive? (Each AND narrows the funnel - throughput.)
- Should master exits also merge from source probes, or stay glide-tuned only?
- Does the master subsume its seed anchor's virgin-day history or start at zero? (Draft: zero.)
- Interaction between master cooldowns and the tuner's Friday exit passes on the same spec keys.
