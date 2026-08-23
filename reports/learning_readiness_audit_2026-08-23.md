# Learning-Readiness Audit — 2026-08-23 (executed in-repo)

Auditor: Claude (repo-resident session, direct artifact access). Question: can this lab LEARN —
convert data into correctly promoted, surviving changes — without gate-stacking itself into
never promoting anything?

## 1. Evidence checklist

| # | Artifact | Status | Where |
|---|---|---|---|
| 1 | Judge code verbatim | RECEIVED | scripts/sunday_boundary.py:82-96 (placebo 95th-pct, fallback 1.83), :311-366 (LLR ±2.94, ≥5d, mean>0, halves>0, nightly SEQ_APPLY) |
| 2 | Probation code | RECEIVED | :184-234 — demotion symmetry, 10-day recheck, auto_* markers, GLOBAL last_chg evidence filter, 14d key freeze |
| 3 | Adoption ledger | RECEIVED, EMPTY | git log "auto-boundary" = **0 commits ever**; trajectory.log has verdict lines only |
| 4 | Trials ledger | RECEIVED (approx) | 22 shadow books + 9 menu + 6 challengers + 12 probes; 12 dated in-code registrations |
| 5 | Placebo army, last 10 nights | PARTIAL | 4 army nights (8/17-8/21; 8/20 lost to a DB lock): placebo 95th ranged −10.3..+7.0, max +21.4; BASELINE crossed it once (+28.4 on 8/17) |
| 6 | Fill ledger / slippage | PARTIAL | fills/wk Aug: 4 → 20 → 76. Live-vs-replay capture ratio study still OWED (flagged since week-4 review) |
| 7 | Labels by regime | RECEIVED | live: 54,800 labeled candidates over ~40 days — **0 bear-regime days in the entire live window**. 2y corpus: 63 bear / 188 mild / 241 bull days |
| 8 | Standings | RECEIVED | CONSENSUS +$1,000/7; control +$566/3; FADE −$506/1; rest ≈ flat; promotions: 0 |
| 9 | Daily tuition | RECEIVED | probes since 8/10: avg **+$242/day** (positive — no tuition being paid), worst day −$517 |
| 10 | Priors (lab_audit_2026-08-19.md, both sim scripts) | **MISSING** | none of the three files exist in this repo — they are artifacts of an external session. Their headline numbers were checked by independent arithmetic below and are directionally CONFIRMED |

## 2. Scorecard L1-L7

| Metric | Value | Target | Evidence |
|---|---|---|---|
| L1 Data velocity | ~1,370 labels/day live; archive 11.68M rows; **fade evidence time = 0 days since Apr 2** (no bear regime) | report evidence in regime-days | item 7 |
| L2 Hypothesis quality | ~37 registered, mostly pre-registered; mined ones (SWEEP_*) labelled as mined; no cap | keep; cap not needed yet | item 4 |
| L3 Evidence velocity | **WORST METRIC.** Evidence clock resets on ANY spec change via global last_chg; spec changed 3× this week (v2.2/2.3/2.4) → all books' virgin days re-zeroed 3×. Median days before wipe ≈ 3-5 | per-key resets; batch changes weekly | item 2 |
| L4 Verdict fidelity | False-pass: 0 observed in 4 army nights; exact-by-permutation ~0.5-5%/look. **True-pass: UNMEASURED — no sentinels exist** | sentinel harness | items 1,5; A |
| L5 Adoption hit rate | **undefined — 0 adoptions ever** (machinery exists, ledger empty) | ≥1 completed probation by Oct | item 3 |
| L6 Decay detection | Disaster-kill fast (LLR −2.94 in days for a −20/day book). Interaction CONFIRMED: a spec change mid-probation wipes probation evidence too (same global filter) — zombie-life extender | per-key fix covers this | item 2 |
| L7 Transfer | Compounds: archive (permanent), regime router, corpus priors, memory, self-healing infra. One-offs: exit-dial variants | healthy | repo |

## 3. Failure-mode verdict

**Closer to F2 (learning nothing) for modest edges — with two correctives that soften it.**

Deciding numbers:
1. **Time-to-promotion for a true +2 pt/day (Sharpe~2) book at the dial AS CODED: ~300 virgin days.**
   The LLR binds hardest: llr = Σ2(x−1)/s²; at sd 15 (s²=225), E[llr]=2n/225 → 2.94 needs n≈331.
   The placebo-t leg needs t=2√n/15 ≥ 1.83 → n≈188. Joint, with nightly looks: single-digit %
   within a quarter. Independent arithmetic CONFIRMS the external priors table's direction.
2. **Adoptions ever: 0.** Nineteen days since v2.0, but see #3 —
3. **Evidence-clock resets this week alone: 3.** The court never had more than ~4 consecutive
   virgin days to judge. "Nothing promoted" is substantially self-inflicted clock damage plus
   0 bear days, not only bar height.

Correctives (why F2 is not as damning as the arithmetic looks):
- **At £5k scale, a +2 pt/day edge on $1k stakes ≈ $20/day — beneath tuition noise.** The court's
  insensitivity to Sharpe-1..2 trickles is nearly costless; the edges that matter here
  (consensus live ≈ +8-14/day when firing; fade-bear ≈ +24/day tradeable) clear the same gates
  in ~3-8 weeks of accrued regime-days. This court is built to promote monsters and ignore
  trickles — defensible for this account.
- Specificity genuinely works: the mega-sweep null bar (2.24) vs real best (5.17) proved the
  machinery separates signal from search-noise when the edge is big.

## 4. Dial recommendation (arithmetic shown)

Do NOT loosen the promotion quantile. At 95th-pct, per-look false-pass ≈5%; nightly correlated
looks ≈15-20% family-wise over a month if the LLR leg were dropped — the LLR is what collapses
joint false-pass to <1%. Loosening buys noise adoptions, the exact fade-era mistake.
Instead fix the two throughput killers that cost nothing in specificity:
- per-key evidence resets (stop wiping every book for one unrelated key change);
- batch spec changes to one weekly window (post-Friday review).
Expected effect: median virgin-window length rises from ~3-5 days to 20+ — a 4-6× evidence-velocity
gain, no false-pass increase. For the edges that matter (≥+8/day), expected promotion latency
drops from "never (clock keeps resetting)" to ~1 month of regime-days.

## 5. Top-3 builds

| Build | Metric | Effect | Hours | Kill criterion |
|---|---|---|---|---|
| SENTINEL harness: 8 hash-seeded shadow books (+1/+2/+3, −2 pt/day drift + 4 placebo twins) through the SAME judge nightly; publish time-to-promotion curves; machinery changes must re-pass | L4 true-pass | court gets measured + regression-tested | ~2 | if P2 never promotes in 90d at any sane dial → dial redesign forced |
| Per-key evidence clocks + weekly change window | L3 | 4-6× evidence velocity, zero specificity cost | ~1-2 | if a changed book retains stale evidence → revert |
| Regime-aware evidence odometer in Friday review ("fade: 0/10 bear-days accrued") | L1/F2 legibility | "no promotion" becomes diagnosable | ~1 | none (reporting only) |

## 6. Do-not-build

1. Loosening the placebo quantile to force promotions — 5%/look compounding nightly = noise adoptions.
2. A deeper/second student on live labels (n≈40 days) — the 2y archive already answered this at n=276k: AUC 0.5-0.6, edge is structural not pick-level.
3. More probe strategies (12→20) — bear-days, not breadth, are the binding constraint; more probes dilute per-strategy evidence and raise queue load.

## 7. The one number to watch weekly

**The evidence odometer: virgin evidence-days accrued this week minus evidence-days destroyed by
resets, per book.** If that number is ~0, the lab is not learning regardless of how good the
strategies are. (Secondary: the probe rung's "X/8 days vs control" counters.)

## 8. Open questions for the owner

1. Patience budget: how many weeks with zero promotions before you'd call the court broken?
2. False-adoption budget: how many wrong promotions per year are acceptable at paper stakes?
3. Tuition cap: max combined probe loss per day you'll fund (current run-rate is +$242/day, i.e. negative tuition)?
4. October gate: does real money require ≥1 completed promotion, or is settled credit-spread income sufficient?
5. Sep 8 UW verdict: what is the minimum evidence you want in hand to decide?
