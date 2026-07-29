# DAY'S LEDGER — 2026-07-29

Report only. Every claim sourced from today's committed record. No manufactured optimism.

## 1. What the system learned today

**About the MACHINE** (commits 8f3412a5, 29800638; canary record 8c5b2688907d):
- Cron runs dash, not bash: `. .harvest_env` never sourced — the integrity gate NEVER ran on
  schedule, and the kill-switch poller was dead in production since install. Both fixed, proven
  under cron-identical sh.
- The adoption logic strips the sign of any short (`abs(qty)`): every adopted short becomes a fake
  long whose "exit" doubles the short. Class bug, now a lane-activation blocker; fix proposed
  (SHORT_UNMANAGED quarantine), not yet built.
- The fail-open-silent degradation CLASS has four instances on record (dark-pool 35%, UW IP-block,
  yesterday's stale bake-off... and today's UW IV-term outage: 372 metadata skips, universe shrunk
  4× before the spread cap could act). Per-source success telemetry folds into Sunday's C2 spec.
- The canary exposed a structural asymmetry: broker stops trigger on TRADES; our exit logic reads
  BIDS. On thin options the cron exit will usually beat the resting stop intraday — the backstop's
  real value is OVERNIGHT GAP protection. Its stop rested at the broker for ~2 hours (verified
  live), then the cron closed FCEL at −50.0% and retired it first, exactly per design.
- Absence-blindness fixed as a class: landing_watch.sh pages on missing daily artifacts (drilled).

**About the MARKET** (ADVERSARIAL_FLAGS_2026-07-29.md; ledger events; canary/probe fills):
- Within-day correlation of option outcomes is tiny (ICC 0.012) — the daily common factor is mostly
  the constant cost drag. Real n_eff ≈ reported ÷ 2.2.
- VRP on OUR window: downgraded. The halves were 5 and 4 trading days; day-clustered, both bars fail
  (LB 0.41/0.24 vs 0.60). Strong point estimates, thin proof.
- The 19.6-year institutional record (^PUT): +7.1%/yr vs SPX +8.8%, maxDD −37% vs −57% — the
  premium's edge is DRAWDOWN SHAPE, not excess return, even in its best form.
- Exit friction has real tails: −51% to −63% vs a ≤15-min-old bid on stop-day illiquid names
  (instrument-limited; decision-mark enrichment now live for future exits).
- Short-side execution prices the SPREAD, not the legs: the probe filled at the displayed synthetic
  bid exactly (0.75 vs 0.94 mid) — selling cost ≈ 20% of credit vs mid, first datapoint.

**About the METHOD:** the adversarial directive caught what the prior process would not have. B1
(day-clustering) was never on any roadmap — it re-priced every number we own within hours of being
asked. B3 forced the existence-vs-harvestability distinction BEFORE the approval decision instead of
after 40 fills. And the F probe demonstrated that LIVE experiments expose what reviews cannot: no
audit of the reconcile code flagged the adoption path until a real spread got adopted.

## 2. What the checking saved (last 72 hours, honest costs)

- **Dead kill switch**: cost-if-undetected unquantifiable — the class (a safety control discovered
  dead at the moment of need) is NORTH_STAR's named primary enemy. It would have been found the
  first time you sent /halt in anger, which is the worst possible discovery time.
- **Integrity gate never running**: unquantifiable directly — the cost is whatever corruption would
  have entered the training pile unwatched between now and the next manual audit.
- **Naked-short generator**: quantifiable near-miss. Tomorrow ~13:30 UTC the exit pass would have
  sold the +36.7% wing and left a naked short F 18P. Bounded worst case on a put: ~$1,725
  (strike×100 − credit) on a probe designed to risk $25 — a 69× breach, plus a corrupted record. Cost
  of prevention: one status-flip commit.
- **Four fail-open sensors**: partially quantifiable — dark-pool starvation demonstrably capped our
  single strongest separator at 35% coverage for three weeks; today's IV outage silently removed the
  spread-cap's entire test population for a day (0 vetoes vs 115). The bias to downstream
  conclusions is real and not precisely computable.
- **Lane spec pressure test**: quantifiable. v1's "arithmetic $800 cap" was false — the pinned
  weekend path reached −$3,280/spread (8.2×), and the kill design would have let a tail-bad design
  survive a calm window ~99.6% of the time. Caught before a single order.
- **PBO instrument (72h window)**: certified pure noise as clean 100% of the time. Cost-if-undetected:
  eventually a false ACCEPT — real money on noise. Unquantifiable and the largest item on this list.

## 3. Where this leaves us on the path to a return — honestly

- **Is any proven edge in hand today? No.** Eight games closed, zero games open with positive
  expectancy demonstrated.
- **Best candidate**: VRP harvest via the premium lane. Honest status after B1+B3: the premium's
  existence is externally documented (20 years), but its best institutional form earned index-like
  risk-adjusted returns; our defined-risk, two-name, retail-cost form dilutes that three ways; our
  own window's confirmation is statistically thin (9 days); and the lane is now activation-blocked
  by the adoption bug on top of Sunday's approval. Even a full success is small in dollars at $450
  deployed — its real value is COST-TRUTH and a template for structural (non-predictive) games, not
  income. That must be said plainly.
- **What would have to be TRUE for a positive return** (testable conditions):
  1. Some signal or structure clears its own cost bar out-of-sample, twice consecutively, at
     day-clustered counts (M0–M1). — UNMET. Tests: D2–D4 this week, PEAD Saturday, accumulation
     feeds mid-August, weekly Student.
  2. OR the VRP capture survives real measured costs in our form. — UNTESTED. Test: the lane's
     40 fills (~2 weeks after activation) + a VIX>25 episode for the tail.
  3. Execution costs stay small enough on the traded set. — PARTIALLY MET: entry costs on
     SPY-class names are proven pennies; exit tails on illiquids are proven bad (so the traded set
     must exclude them — the friction gate exists for this).
  4. Enough regime coverage to trust any of the above. — UNMET by construction: ~4 weeks, one calm
     regime. Test: time; the archiver started the clock on our own option history 2026-07-28.
  5. The discipline holds (no gate ever shrinks to a wish). — MET so far, evidenced by this week's
     downgrades of our own results.

## 4. The honest progression claim

**Up case**: eight games eliminated at ~£0 redirects all future effort; the instruments are now
trustworthy (PBO fixed, day-clustering standard, real fill costs measured, lifetime trials feeding
the bar) so the NEXT positive result is far more likely to be real; three new data feeds opened; the
archiver is compounding the one dataset money can't buy us; and the one structural game is being
tested properly instead of romantically.

**Down case**: the two most-hoped paths both weakened this week — the flow edge is dead by every
reading, and our VRP confirmation thinned to 9 daily observations while the 20-year record capped
even the institutional form's upside at index-like Sharpe. The pond may be poisoned (untested). Our
effective sample sizes were overstated 2.2×. Nothing this week raised the probability that THIS
universe at THIS scale contains a large edge.

**Net, honestly**: the probability of finding a LARGE edge went slightly DOWN (the best candidates'
ceilings dropped). The probability that whatever verdict we eventually reach is TRUE went sharply UP.
For "eventually produces a modest positive return," the honest answer is: unchanged, and we don't
know yet — but the ground under the question is much firmer than it was on Monday.

## 5. What would change my mind

**Evidence this approach will NOT produce a return** (all testable, timeline ~7 weeks):
- The pivot clock completes: 6 consecutive REJECTED weekly verdicts with no discovery survivor
  (due ~Aug-30), AND
- the pond study (Fri) shows flow-flagged names are structurally bad terrain, AND
- D3 finds no magnitude-predictability either (Thu), AND
- the lane — if approved — dies its cost-bleed death at ≤40 fills (~mid-Aug), AND
- PEAD/congress/analyst all read null (Sat + mid-Aug).
If ALL of those land negative, the conclusion is that this universe/data/scale cannot pay, and the
honest pivot is to a different universe or a full stop — per the pre-registered rule, not mood.

**Evidence it WILL**: any single M0 candidate surviving two consecutive weeks at day-clustered
counts (weekly cadence, could happen any Sunday); or the lane showing positive net capture at 40
fills and then holding through a VIX>25 episode (weeks to months — the tail decides, not the calm);
or D3 revealing genuine magnitude-predictability that opens the vol-structure game with separation
above the bar (first read: tomorrow night).

We are not closer to a return than we were a week ago. We are much closer to knowing whether one
exists here. Those are different things, and only one of them was purchasable this week at £0.
