# STRATEGY STATE — 2026-07-25

Report-only (Lane A): no code path, parameter, or decision was touched to produce this. Every claim
carries an evidence reference — a committed report file, a commit hash, or the snapshot it was
computed on (`harvest_20260724_2130`). Anchor: NORTH_STAR.md. Where the record is silent, this says
"no evidence yet" rather than filling with prose.

## 1. The two layers, honestly

**The frozen engine (what actually trades).** It buys long options on the strongest Unusual-Whales
flow that clears its filters — one cluster per cycle, $800/leg, a 24-hour take-profit hold, exits on
a 30–50% velocity target, with a broker-side ratchet stop on the canary. Its measured result is a
decisive loser: on the real-spread era (since 2026-07-09), its executed graded picks are 8 up / 260
down / 81 vertical — a 2.3% up-hit rate (`harvest_20260724_2130`; Student report gate-4 line,
reports/student/student_harvest_20260724_2130.md). It is kept deliberately, for three reasons the
school depends on: it is an **unbiased probe** (it keeps sampling the signal space without the
school's opinions biasing what gets graded), the **incumbent baseline** every school gate must beat
(NORTH_STAR "beats the engine on the same purged splits"), and the **fill generator** whose real
microstructure the fill ledger now records (commit school-1c). Freezing the teacher while the student
learns is a NORTH_STAR principle, not an oversight.

**The school forming above it.** A meta-layer that judges the engine's signals rather than generating
new ones (NORTH_STAR non-goal: not price prophecy). Today it is entirely shadow or dormant: the
Council scores every candidate, the Governor tracks track-records, the Treasurer sizes on paper, the
macro brake watches — and `school_mode=off`, so the engine still decides alone
(v12_school_mot.py, 30/30, off-state byte-identity). The strategy it is forming is: **take the
engine's signal only when a diverse council agrees the specific contract is more likely than not to
pay after its own costs, size it by proven edge, and refuse everything else.**

## 2. The rulebook so far

| rule (one sentence) | evidence birth certificate | status |
|---|---|---|
| Reject contracts whose real bid-ask spread exceeds the cap at entry. | Monotone spread-bucket decay on `harvest_20260724_2130`: tight <2% hit 22.6%/net −0.04 → 2–8% 17.8%/−0.15 → 8–20% 15.6%/−0.30 → wide ≥20% 9.3%/−0.59 (this report §4 data); ROADMAP wide-spread question (prelim 2026-07-07). | **ACTIVE** (commit school-1def; the one owner-approved governed change) |
| Enter at the ask, grade/exit on the bid, gap-throughs included; never the mid. | NORTH_STAR "executable prices only"; label engine (test_harvest.py 8/8). | **ACTIVE** |
| A candidate must clear ITS OWN break-even bar, not a pool average. | Addendum flag 3; Council per-contract bar (reports/council/council_harvest_20260724_2130.md). | **ACTIVE (shadow)** |
| Take only when the calibrated win-probability beats that bar. | Student selection rule + four gates (reports/student/student_harvest_20260724_2130.md). | **ACTIVE (shadow)** |
| Require a quorum of diverse members to agree; a split house does not trade. | Council disagreement band std ≤ 0.18, quorum 3/5 (council report; test_brain council group). | **ACTIVE (shadow)** |
| Weight independent bets, not repeated themes (uniqueness weights). | The 0.099-weight pocket lesson (this report §3; pocket autopsy 2026-07-25). | **ACTIVE (shadow)** — applied in every school metric |
| Size by fractional Kelly on the empirical distribution, capped, liquidity-bounded, ratchet-reduced. | Treasurer (reports/treasurer/treasurer_harvest_20260724_2130.md; test_brain treasurer group). | **APPROVED-PENDING** (shadow; engine sizes fixed 1 until Treasurer promoted) |
| Halt entries market-wide on a VIX spike / trend break. | Macro brake (treasurer report; fired 0/8653 in this calm tape). | **APPROVED-PENDING** (shadow) |
| Stop entering at −30% drawdown from high-water; review before restart. | NORTH_STAR risk constraint; Treasurer ratchet zeroes at the halt. | **APPROVED-PENDING** (arms at the live-capital gate) |
| The daily brake logs but does not suppress during paper accumulation. | NORTH_STAR v1.3 amendment. | **ACTIVE (shadow by design)** |
| Prefer early-session signals (13:00–15:59 UTC concentration). | 25/26 pocket selections early-session; discovery early-hour flickers (idea_ledger.md 2026-07-25). | **HYPOTHESIS** (flicker, not confirmed) |

## 3. The hypothesis ledger

| vein | current belief | this week FOR | this week AGAINST | pre-registered tripwire | expected settle |
|---|---|---|---|---|---|
| The Student pocket | A razor-thin selectable pocket may exist. | First-ever gate-4 pass; blended OOF AUC 0.714 (council report). | Official verdict REJECTED; 26 selections collapse to ~4 themes (weight 0.099); the 3 most independent all lost (pocket autopsy 2026-07-25). | Student passes all four gates for the required run(s) at ≥8k rows (LIVE_GATE.md). | weeks, if ever |
| Cost avoidance (spread) | Wide spreads bleed edge; avoid them. | Monotone decay across 24k rows (§4); engine's real picks 49% in the worst bucket. | Executed-side cost unconfirmed until the fill ledger matures (ROADMAP wide-spread Q). | Fill-ledger spread-bucket coverage populated (LIVE_GATE §measurement lane). | 2–4 weeks of fills |
| Fixed-hold horizon | Unknown whether a 3/5-day hold labels better. | — | Not backfillable: stored paths cover 1.6%/0% at 3/5td (resolution stat 2026-07-25, ROADMAP Q). | OOS lift ≥1.5, PBO ≤0.20, 8/10 angles ×2 weeks (ROADMAP). | after poller extension (governed) |
| Stock-horizon escape | Does the flow predict the stock even where the option loses? | — | Run 1: hit 47–49% (below coin-flip), mean signed return negative at 1/3/5d (reports/discovery/stock_horizon_harvest_20260724_2130.md). | mean-return lower bound >0 AND hit lower bound >52%, ×2 weeks (ROADMAP). | run 2 = next Sunday |
| Early-session concentration | Signals may cluster/perform early. | 25/26 pocket early-session (idea_ledger). | Only a flicker in the rig; no convergence (idea_ledger). | 8/10 convergence ×2 weeks. | no evidence yet |
| Calibration step-cliff | Selection count will jump, not ramp. | Zero OOF mass within 10pts below the bar; plateaus at 0.778/0.824 (pocket autopsy). | Single observation; not yet a trend. | tracked, no tripwire set. | no evidence yet |

## 4. The trade we would take today

**From the latest shadow window (last 5 days): the school selects NOTHING.** The Council took 0 of
8,653 (best blend 0.508 vs a 0.520 bar, gap −0.012; council shadow CSV) and the Student took 0 in its
recent-days shadow window (reports/student/shadow_harvest_20260724_2130.csv, 2,756 rows, 0 TAKE). The
strategy in action today is refusal.

**What it selected when it last selected anything (full-OOF, the pocket):** 26 contracts across 6
tickers / 4 days — 13 SPY puts (2026-07-13), 7 PLTR, 3 NFLX, and TSM/ABT/UNH singles (pocket autopsy
2026-07-25; the26.csv). Uniqueness-weighted these collapse to ~4 independent bets.

**The three features that moved each probability: no evidence yet.** The committed shadow CSV records
`student_p / decision / reason / outcome` but not per-candidate feature attribution
(reports/student/shadow_harvest_20260724_2130.csv header). This is a recorded-evidence gap, not a
finding; adding attribution to the shadow table is a queued reporting enhancement, not a decision
change.

**Trades the school refused that the engine took, with graded outcomes** (real-spread era,
`harvest_20260724_2130` — the school would have vetoed all of these on spread and probability):

| ticker | real spread | outcome | net |
|---|---|---|---|
| FCEL | 25.5% | vertical | −0.35 |
| HYG | 44.4% | down | −0.76 |
| EFA | 121.6% | down | −0.67 |
| AA | 26.7% | vertical | −0.37 |
| UPST | 9.0% | vertical | −0.46 |

Engine executed, real-spread era: 8 up / 260 down / 81 vertical. The school vetoed the entire set.
This is the clearest picture of the forming strategy: it refuses exactly the wide-spread losers the
incumbent keeps buying.

## 5. Next intended change

**The single queued governed change: none is armed by this report.** The spread cap already shipped
(commit school-1def). The next governed decisions, in order, both awaiting a Sunday boundary and your
go:

1. **Poller extension** — keep polling past label resolution to signal+5 trading days, to make the
   fixed-hold question answerable (it is currently un-backfillable; resolution stat 2026-07-25). Cost:
   API budget from the existing adaptive cap. Evidence to justify arming: none required beyond your
   go; it is additive measurement.
2. **Measurement lane** (conditional, after #1) — 1–2 tagged paper trades/day across spread buckets,
   firewalled from the edge record, ONLY if fill-ledger coverage shows fills don't span the spectrum
   (LIVE_GATE.md §measurement lane). Not built; trigger not yet met.

Nothing else is queued. The spec freeze (ROADMAP) forbids new organs without a measured birth
certificate.

## 6. What would change our mind

**Kill criteria per vein:** the Student pocket dies if it is REJECTED for 6 consecutive weekly runs at
≥8k rows with no survivor reaching SHADOW_PROVEN (pivot rule, LIVE_GATE.md). Cost-avoidance dies if
the matured fill ledger shows wide-spread fills do NOT underperform after real executed costs.
Fixed-hold dies if, once measurable, no feature separates classes at the tripwire. Stock-horizon dies
if run 2 confirms run 1 (it is already failing). Early-session dies if it never reaches 8/10
convergence.

**Pivot clock: week 1 of 6.** The first official REJECTED verdict was 2026-07-24 (commit 0beafa4a).
The signal source is declared mined-out only at 6 consecutive REJECTED weeks AND no survivor AND the
stock-horizon route failed — all three, pre-registered before the outcome (ROADMAP pivot rule). One
week in; five to go before the pivot conversation opens. Nothing pivots automatically.
