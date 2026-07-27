# PREMIUM LANE — measurement lane spec (DRAFT for the Sunday 2026-08-02 boundary)

STATUS: **DRAFT — NOT ACTIVE.** Nothing trades from this document. Activation requires the owner's
explicit yes at the Sunday boundary; if approved, the activation is logged as a counted trial and
the config flag flips in one commit. Anchor: NORTH_STAR.md; born from the VRP existence pass
(2026-07-28: median IV−RV +9.1pts, IV>RV on 79% of 866 ticker-days).

## What it is

A cost-measurement instrument for the one frontier that doesn't require directional skill: selling
richly-priced volatility with strictly defined risk. It answers a single question: **after real
measured costs, does any of the observed premium survive harvesting?** It is NOT an edge claim and
its results are FIREWALLED from Gate 1–4 evidence — capture/cost data only.

## The trade, exactly

- Structure: **short OTM put vertical (credit spread), mleg atomic order only** — both legs in one
  order, so no leg-in window exists in which the short is ever naked. If the mleg order doesn't fill
  as a unit, nothing fills. NAKED SHORTS ARE STRUCTURALLY IMPOSSIBLE IN THIS LANE.
- Underlyings: rule-built list, never hand-picked — the 6 tickers with the tightest mean option
  spread over the trailing 2 weeks of our own harvest with n≥100 quotes (today: SPY 1.11%, QQQ
  1.67%, TSLA, NVDA — equity-index names dominate, as they should). Refreshed only at Sunday
  boundaries.
- Tenor: 30–45 DTE at entry. Short strike: nearest to 5% OTM. Wing: the next strike at least $5
  lower (width $5 target), risk per spread = (width − credit) × 100 ≤ **$400 hard cap**.
- Cadence/size: max 1 new spread per day, max 2 concurrent, total lane risk ≤ **$800** (one engine
  leg's allocation — deliberately small; this buys data, not P&L).
- Entry accounting is WORST-CASE by pre-registration: credit booked at the bid of the short minus
  the ask of the wing (never mid). The fill ledger measures actuals on both ends.
- Exit: close at 50% of max profit, or at 21 DTE, or at 5 DTE whichever binds first (the 5-DTE rule
  exits before the pin/assignment window); mleg close, worst-case accounting again.
- Tagged `lane: MEASUREMENT_PREMIUM` on every record and ledger event; excluded from the scoreboard,
  SPRT, brake counts, and all acceptance-gate evidence.

## Tail clamps (the insurance IS the product — never optimize it away)

1. The long wing is mandatory and structural (atomic mleg). Any future proposal to widen width
   caps, skip wings "temporarily", or sell the call side too is a NEW organ requiring its own
   birth certificate — this spec does not authorize it.
2. Max book loss is arithmetic, not statistical: 2 spreads × $400 = **$800, full stop**. A gap to
   zero on both underlyings cannot exceed it.
3. Vol-spike behavior: if the macro brake reads BRAKE (VIX ≥ 30 or the pre-registered triggers), the
   lane opens NO new spreads; existing spreads ride their defined risk to the exit rules. No
   panic-close rule — the wing already bounds the damage, and closing into a spike pays the widest
   spreads of the cycle.
4. **A PASS in continued low-VIX is PROVISIONAL.** The lane's verdict cannot graduate beyond
   "provisional pass" until it has held positions through at least one episode of VIX > 25. Written
   here so a calm-month win cannot be talked into a full pass later. The premium is tail insurance
   sold; the seller's ledger is honest only after a tail.

## Pre-registered kill conditions (written before any fill exists)

- DEAD if cumulative net capture ≤ 0 after **40 real fills** (point estimate — see power note).
- DEAD EARLY if at any point from **20 fills** the 95% lower bound of mean capture < **−20% of
  risk-at-entry** (fast-bleed exit — 40 fills of hope is not owed to a bleeding design).
- PAUSED automatically by the macro brake as above; a pause does not reset fill counts.
- Power note (honest): with per-fill capture dispersion σ ≈ 0.35× risk, 40 fills give ~1.8σ
  resolution on the mean — enough to kill a genuinely negative design, NOT enough to certify a
  positive one. Certification needs the full gates on far more fills; this lane only decides
  whether the vein deserves that investment.

## Cost reality it must beat (from our own measurements)

Round-trip = 4 leg-crossings worst-case. On the SPY-class list (1.1–2.0% per-leg spreads), that is
roughly 4–8% of premium; target capture (50% of credit) clears it comfortably ON PAPER QUOTES. The
2026-07-27 ledger showed real fills land near the quoted side (not mid) — the same accounting this
spec pre-registers. If real leg-crossings on verticals run materially wider than the calm-month
quotes suggest, the 20-fill fast-bleed kill catches it within two weeks.

## Implementation shape (NOT built until approved)

`premium_lane.py`, called at the END of the engine cycle behind `premium_lane_enabled: false`
(default OFF; brake_mode pattern). Off-state byte-identity added to the MOT before the flag ever
flips. Fills flow through the existing fill ledger; grading through the existing harvester/labeler
with the MEASUREMENT tag. No school organ gains authority; no engine decision path is touched.

## The Sunday ask (one line)

**Approve the premium lane to start Monday 2026-08-03 — yes or no.** If yes: activation committed as
a counted trial, flag flips at the boundary, first fills that week, first kill-window read ~20 fills
in (~2 weeks), verdict summarised every Sunday alongside the existing cycle.
