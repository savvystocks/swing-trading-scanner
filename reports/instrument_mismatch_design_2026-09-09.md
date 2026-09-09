# INSTRUMENT MISMATCH FIX - DESIGN DRAFT (2026-09-09, pre-panel)

Owner order after the capture study: close the gap between what the backtests measure and
what the live book buys, BEFORE the proof account seats anyone.

## The defect (measured, not suspected)
occ_source audit of all ~76 PROBE fills: ONE bought the trigger contract
(DIP_CONF_MILD, fixed 2026-09-01). Every other fill is `alpaca_resolved` - a contract the
engine SYNTHESIZED to a target delta/DTE. The archive corpus (probe_tuner_rows /
glide_fine_rows) is built per-OCC from real flow prints: it is the return of buying THE
CONTRACT THAT PRINTED. So FOLLOW_CALLS' +15.9%/day, CONSENSUS' cells, WINNER_PROFILE's
+6.3%/day and the bull/bear anchors' numbers describe an instrument the live book does not
buy. Their live results cannot confirm or refute those numbers.

Corroborating evidence from the same study: EXEC_BASELINE - whose archive comparator is the
unfiltered pool and which makes no instrument claim - CAPTURES (live median +5.70 vs archive
+4.67, gap +1.03). Execution friction is not the problem; instrument identity is.

## Proposed fix
1. NEW POOL `_TRIG_CANDS` - contract-identity rows built in scan_candidates beside
   `_PRICEY_CANDS`, using the SAME filters the archive corpus used:
   calls; per-alert premium 50k-1M (the archive band); ask-side aggressor (ask_vol > bid_vol);
   alert spread <= 2%; DTE >= 7; PLUS the live-only constraint ask <= $10 so one contract fits
   the $1,000 cap. Carries occ, expiry, strike, alert_ask - exactly the shape _PROBE_CONTRACT
   already consumes.
2. TRIGGER-PREFERRED ENTRY for the strategies whose evidence is trigger-based:
   FOLLOW_CALLS, CONSENSUS_CALLS, WINNER_PROFILE, WINNER_PROFILE_X, BULL_DIP, DIP_CONVEXITY.
   They draw from `_TRIG_CANDS` and set `_PROBE_CONTRACT` exactly as DIP_CONF_MILD does.
3. FALLBACK POLICY - the panel's question. Two options:
   (a) TRIGGER-ONLY: no contract identity, no trade. Cleanest evidence, costs throughput.
   (b) TRIGGER-PREFERRED with tagged fallback: synthesize when no identity exists, but the
       record keeps occ_source and the court scores trigger fills and synthesized fills as
       SEPARATE evidence streams. Preserves throughput, adds bookkeeping.
   Draft leans (b) but will not ship it if the panel finds the two-stream court is a
   verdict-laundering surface.
4. COMPARATOR HONESTY: the archive cohort these strategies are judged against must be
   restricted to the AFFORDABLE slice (ask <= $10 at the print), because the live book can
   never buy the rest. Every published cell for these strategies is re-derived on that slice
   or marked as not-live-comparable. This may move the headline numbers - that is the point.
5. EVIDENCE CLOCKS: this is an entry-path change for six strategies. Their virgin-day
   evidence restarts; none has 8 closed days, so nothing is lost.

## Coverage (ships in the same commits)
MOT: `_TRIG_CANDS` filter unit checks (band, aggressor, spread, DTE, ask cap); a trigger-path
fixture asserting the entered OCC equals the candidate's occ and occ_source is
uw_trigger_verbatim; a fallback fixture asserting the tag when identity is absent; the
existing occ-collision and live-repricing guards still fire on the trigger path.
Regime drill: one scenario per fallback branch. Sentinel: unchanged.

## Open questions for the panel
- Fallback (a) vs (b), and if (b), does a two-stream court launder verdicts?
- Does the ask<=$10 affordability cut bias the cohort (cheap contracts are not a random
  slice of flow - they are further OTM or nearer expiry)? If so, is the comparator fix
  sufficient or does the strategy definition itself need the constraint?
- The trigger contract is priced at the ALERT ask; live repricing then demands a live quote
  within band. What fraction of trigger candidates will die at the repricing gate, and does
  that reintroduce a selection difference the archive does not have?
- Do BULL_DIP / DIP_CONVEXITY belong in this change at all - their archive cells were
  measured on the same per-OCC corpus, but their live filters are md-level (regime, SMA
  distance) which the trigger pool does not carry.
