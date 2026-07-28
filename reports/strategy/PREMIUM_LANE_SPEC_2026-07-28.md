# PREMIUM LANE — measurement lane spec v2 (DRAFT for the Sunday 2026-08-02 boundary)

STATUS: **DRAFT — NOT ACTIVE.** Nothing trades from this document. Activation requires the owner's
explicit yes at the Sunday boundary; if approved, activation is a counted trial and the flag flips
in one commit. Anchor: NORTH_STAR.md; born from the VRP existence pass (2026-07-28: median IV−RV
+9.1pts, IV>RV on 79% of 866 ticker-days).

> **v2, 2026-07-28 ~01:00.** v1 was adversarially pressure-tested by three independent attackers the
> same night it was drafted. All three returned MATERIAL defects; every number below reflects the
> tightened design. The v1 defects are preserved in the pressure-test section — including the ones
> that made v1's headline safety claim false.

## What it is

A cost-measurement instrument for the one frontier that needs no directional skill: selling
richly-priced volatility with strictly defined risk. One question: **after real measured costs, does
any of the observed premium survive harvesting?** Results are FIREWALLED from Gate 1–4 evidence.

**Honest scope (from the kill-power attack):** the fill-count kill can detect COST-BLEED — a design
whose friction eats its premium (it kills that variant ~84% of the time). It CANNOT detect
TAIL-MISPRICING: a short-vol design that only loses in vol episodes survives any calm 40-fill window
~99.6% of the time, and no fill-count threshold fixes that. Tail-mispricing is adjudicated ONLY by
the VIX>25 clamp below. This lane measures costs; it cannot certify the strategy. Written here so
nobody — including its author — reads 40 calm fills as proof.

## The trade, exactly (v2)

- Structure: **short OTM put vertical, mleg atomic order only** — no leg-in window; a naked short
  cannot exist AT ENTRY. (Assignment can still un-pair the legs later — see the assignment rule.)
- Underlyings: rule-built — the 6 tickers with the tightest mean option spread over the trailing 2
  weeks of harvest (n≥100 quotes), refreshed only at Sunday boundaries — **then filtered by the two
  entry gates below, which on today's quotes effectively self-select SPY/QQQ and correctly block
  TSLA/NVDA-class friction.**
- Tenor: 30–45 DTE. Short strike nearest 5% OTM; wing at least $5 lower.
- **ENTRY GATE 1 — minimum credit:** worst-case booked credit ≥ $1.00 per $5 of width, enforced as a
  pre-order filter (no trade that day if unmet), not discovered at order time. (The cost attack
  showed 5%-OTM SPY/QQQ often yields $0.60–0.90 in calm vol — so this gate means NO-TRADE DAYS ARE
  NORMAL and logged; the lane does not chase credit by widening risk.)
- **ENTRY GATE 2 — friction:** (quoted spread of short leg + quoted spread of wing) ≤ 15% of
  worst-case booked credit, computed from the same quotes that book the trade. Today this passes SPY
  (~6%), is marginal on QQQ (~15%), and blocks TSLA (~23%+): the lane measures only trades that
  could plausibly survive their own costs.
- Size/cadence: 1 contract, max 1 new spread/day, max 2 concurrent.
- **Risk budget, restated honestly (the tail attack):** structural risk = width − credit ≤ $400 per
  spread; realized worst case includes exit crossing costs — **budget $450/spread, $900 book**. The
  v1 claim "a gap to zero cannot exceed $800, full stop" was FALSE for American physically-settled
  options and is withdrawn; with the assignment rule below, the bound is width − credit + crossing
  costs, and the budget above is the honest number.
- Execution: mleg limit at mid, improve one tick per 15 minutes, cancel unfilled at end of day (an
  unfilled day is tolerated and logged). LEDGER BOOKING stays worst-case (credit at short-bid minus
  wing-ask) regardless of the actual fill — conservative accounting is not negotiable.
- Exits (ladder fixed — v1's "5 DTE" line was dead code behind the 21-DTE rule):
  close at 50% of max profit, else at 21 DTE, as **marketable (cross-the-spread) mleg orders,
  retried every session if unfilled**; any spread still open at 2 DTE with the short strike within
  2% of spot **closes at market unconditionally**.
- **ASSIGNMENT RULE (new — the rule whose absence broke v1):** if a short leg is ever assigned, the
  paired wing is EXERCISED — never sold — the same trading day, and shares+wing are disposed as one
  unit. No leg of a broken spread is ever disposed unilaterally. This restores the width-bound up to
  fees; the v1 gap (shares liquidated at the open, orphan wing sold later) had unbounded
  path-dependence and produced 2.3× the cap in the attack's worked example.
- Tagged `lane: MEASUREMENT_PREMIUM` everywhere; excluded from scoreboard, SPRT, brake counts, and
  all acceptance-gate evidence.

## Tail clamps (unchanged in spirit, tightened in letter)

1. The wing is mandatory and structural. Widening caps, skipping wings, or adding the call side is a
   NEW organ needing its own birth certificate.
2. Book worst case: **$900** (2 × $450), arithmetic given the assignment rule; not "$800 full stop."
3. Vol spike: macro brake BRAKE → no new spreads; existing spreads follow the exit ladder (the 21-DTE
   marketable close applies even mid-spike — riding deep-ITM American shorts toward assignment is
   strictly worse than paying the spike's spread, per the attack's carry arithmetic).
4. **A PASS in continued low-VIX is PROVISIONAL until the lane has held through VIX > 25** — and
   (new) if pre-activation testing shows Alpaca paper does NOT simulate early assignment, the spec
   must state that the assignment tail is UNMEASURED in this venue, and the provisional label is
   permanent on paper regardless of VIX episodes.

## Pre-registered kill conditions (v2 — checkpointed, scoped)

- COST-BLEED KILL: dead if cumulative net capture ≤ 0 at the **40th fill**.
- FAST-BLEED KILL: checked ONLY at fills **20, 30, 40** (not every fill — v1's every-fill check was
  21 uncorrected tests that would false-kill 12–18% of genuinely good designs): dead if the
  one-sided 95% lower bound (z = 1.645) of mean capture < −20% of risk-at-entry at any checkpoint.
- PAUSE: macro brake, as above; pauses don't reset counts.
- SCOPE (restated): these kills adjudicate cost capture in the prevailing regime ONLY. Tail verdict
  = clamp 4, nothing else.

## Pre-activation tasks (before the flag can flip, if approved)

1. Test whether Alpaca paper simulates early assignment (open a deep-ITM short spread in a throwaway
   test, or confirm via docs/support); record the answer in this file. If NO → clamp 4's permanent-
   provisional wording applies, and the XSP alternative below gets priced.
2. Price the XSP alternative (European, cash-settled — deletes assignment and pin outright): if its
   measured friction gate reads ≤ 15%, prefer XSP over SPY despite wider quotes; record the numbers.
3. MOT check: `premium_lane_enabled: false` produces byte-identical engine behavior (brake pattern).

## Cost reality (corrected — the v1 "4–8% of premium" had a unit error)

Per-leg spread percentages are quoted against LEG premium (~$4); the vertical's credit is ~10×
smaller, so friction against CREDIT is what matters: on today's quotes, round-trip worst-case
friction ≈ 7–9% of credit on SPY (~$6 vs a ~$35 target), ~30% on QQQ, 31–62% on NVDA/TSLA. That is
14–46% of target profit across the raw list — the reason entry gate 2 exists. Stress exits (forced
21-DTE close in a spike, spreads 3–10× calm width) can consume the entire target on the frictionful
names — the reason they're blocked at entry rather than discovered in the ledger.

## The Sunday ask (one line, unchanged)

**Approve the premium lane (v2, as tightened above) to start Monday 2026-08-03 — yes or no.**
If yes: pre-activation tasks run first, activation is a counted trial, flag flips at the boundary,
first kill-window read ~2 weeks in, verdict summarised every Sunday.

## Pressure-test record (2026-07-28, three independent adversaries, all MATERIAL)

1. **Tail/gap:** v1's arithmetic-cap claim false on three paths — crash-day exit crossing ($430 vs
   $400 on the benign path), early assignment breaking the spread (worked example −$930 = 2.3× cap;
   assignment window is the whole trade life once deep ITM, NOT the last 5 days — v1's sentence was
   factually wrong), pin + failed exit (−$3,280 = 8.2× cap). Exit ladder had dead code (21 DTE
   always binds before 5). → assignment rule, marketable exits, 2-DTE unconditional close, honest
   budget, pre-activation venue test, XSP alternative.
2. **Kill power:** bad design survives 40 fills ~20% by luck even iid; with regime clustering, a
   calm window passes a tail-bad design 99.6% — no fill-count fixes it; v1 fast-bleed false-kills
   12–18% of good designs. → checkpointed kills, scope restated: cost-bleed only; tail = clamp 4.
3. **Cost:** unit error (spread % of leg premium vs credit); real friction 14–46% of target across
   the raw list; $400-cap + $5-width silently requires credit ≥ $1.00 which calm-vol SPY/QQQ often
   cannot yield — v1 would have been blocked on its tightest names and filled on its worst. →
   min-credit gate (no-trade days normal), friction gate, mid-then-improve execution.
