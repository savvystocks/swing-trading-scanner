# FORWARD PLAN — opportunity map to profitability — 2026-07-27

Planning report (Lane A, no code). The source question on the incumbent signal is closed — four
independent nulls. This maps the games NOT yet tested, ranks them by honest prior and
evidence-per-day, commits to dates on OUR work, and fixes the finish line. Anchor: NORTH_STAR.md
("the machinery outlives any strategy — if the current signals prove empty, the harness stays and
hunts new ones").

## 1. What we've proven — the foundation

The instrument works. In eight weeks it: built a 24,610-outcome labelled history with executable
prices; caught and fixed its own broken fluke-detector (PBO); killed four seductive false positives
in one weekend (low-IV spreads, the credit-fade artifact, lookahead persistence, the 3→54 mirage) —
each by verification, none by luck; and held pre-registration under temptation every time. That is a
proven edge-DETECTOR. What it has conclusively ruled out: **buying the options the flow buys loses
(~2–20% hit vs a 57% break-even bar); no reading of our 82 features rescues it (AUC 0.72 can't clear
costs); the flow does not predict the underlying stock (47–49% at 1–5d); 8-K events carry ~nothing at
3d (d 0.09); dark-pool accumulation is real but weaker than its own point-in-time reading (0.40 vs
0.58); and no exit rule, hold length, or spread structure rescues a signal-less long-option position
(all 14 structures negative, ~7–10% bleed at zero cost).** Ruled out is progress: six games are off
the board, cheaply, before real money touched any of them.

## 2. The untested frontier — ranked by promise × honesty

**F1. SELLING premium (volatility risk premium) — prior: the strongest.** We have only ever been a
BUYER, and we proved buyers of these options lose ~30% net pool-wide. Someone is on the other side of
that trade, structurally. Outside evidence is the best of any frontier: the variance risk premium is
the single most documented structural edge in options (implied systematically above realized; CBOE
put-write indices compounding for decades; it persists because it is payment for tail risk, not
mispricing). Honest caveats stated up front: our bake-off's credit-fade result (−$218/trade) does NOT
test this — it fades illiquid flow contracts at 1-day horizon crossing two wide spreads; real VRP
harvesting is systematic short DEFINED-RISK spreads on LIQUID underlyings at 30–45 DTE, where legs
cost pennies to cross. Untested by us in every respect. The tail-risk cost is real and must be priced
by the P(halt) machinery, not hand-waved.

**F2. Analyst-revision drift on multi-day stocks — prior: moderate, cheapest genuine test.** The old
sandbox prototyped UW analyst-upgrade feeds and never harvested them. Post-revision drift is a
well-documented multi-day anomaly (weakened in large caps, persistent in small/mid). We already pay
for UW (£0 incremental), the stock horizon carries no theta tax and bp-level costs, and if UW exposes
history, a backtest with thousands of independent events is days away — the 8-K rig from last night
is 90% reusable.

**F3. Insider clusters at 10–20 days — prior: weak-moderate.** Form 4's T+2 staleness killed it for
same-day options; it is irrelevant at a 2–4 week stock horizon, which is exactly where the academic
literature puts the (small, persistent) insider-cluster effect. The sandbox already built the
parsing (`backtest_alt_edges.py`, recoverable). Free via EDGAR; months of history fetchable.

**F4. Congress trades — prior: weak.** 45-day disclosure delay forces long horizons; literature
mixed. Worth one probe only because the feed may already be in our UW plan.

**F5. Earnings drift (PEAD) from sensors we already log — prior: weak-moderate.** The Tier-B
earnings-drift sensor has been logging since 07-07; PEAD is documented but heavily arbitraged. Nearly
free to test from owned data + yfinance.

**F6. Defined-risk spreads as execution — PARKED.** The weekend proved structure cannot rescue a
missing signal. Spreads re-enter only as the delivery vehicle for a signal that exists (e.g. F1's
short spreads), never as a fix on their own.

## 3. The fastest honest path

Ranked by evidence-per-day-of-effort:

| frontier | testable on owned/free data? | days to first honest read | why this rank |
|---|---|---|---|
| F2 analyst drift | UW history probe → yfinance outcomes | **2–3 days** if history exists | reuses last night's event-study rig wholesale |
| F5 PEAD | owned sensors + yfinance | 2–3 days (weekend slot) | nearly free, weak prior |
| F1 VRP existence | owned IV features + yfinance realized vol | 2 days for the EXISTENCE check | the edge itself needs a live paper lane for cost truth (~2 weeks of fills) |
| F3 insider 10–20d | EDGAR Form 4 fetch (like the 8-K fetch) | ~5 days | more parsing than 8-K; horizon needs longer outcome windows |
| F4 congress | UW probe | 1 day probe | long-delay feed, weakest prior |

**The single highest-leverage first move: probe UW's historical analyst + congress endpoints and, if
history exists, run the analyst-drift event study through the existing rig this week.** Zero new
cost, thousands of independent bets, the instrument unchanged, and a genuinely different information
stream — the exact profile of test the weekend taught us to value. F1's existence check runs in
parallel the same week because its payoff, if VRP is present on our universe, is the strongest
structural prior on the board.

## 4. Dated plan (dates bind OUR work; the market's verdict cannot be dated)

| milestone | target date |
|---|---|
| UW historical endpoints probed (analyst + congress); feasibility stated | **Tue 2026-07-28** |
| F1 VRP existence measurement (owned IV vs realized, per-ticker) — first read | **Wed 2026-07-29** |
| F2 analyst-drift event study built + first calendar-disjoint OOS read | **Thu 2026-07-30** |
| F5 PEAD study from owned sensors — first read | **Sat 2026-08-01** |
| F3 Form 4 fetch + 10–20d cluster study — first read | **Sun 2026-08-02** |
| Anything that beat its bar → pre-registered question + tripwire at the Sunday boundary | **Sun 2026-08-02** |
| If VRP exists on our universe: short-premium PAPER lane spec to owner (governed; measurement-tagged, firewalled, school grades it) | **Sun 2026-08-02** |
| Lane live on paper (if approved); poller extension deployed (if approved) | **w/c 2026-08-03** |
| Forward Run 2 on any surviving pre-registered question | **Sun 2026-08-09** |
| First cost-true read of the premium lane (~20 fills) | **~Sun 2026-08-16** |
| Incumbent pivot clock completes (weeks 2–6 verdicts) → owner pivot decision with this map on the table | **Sun 2026-08-30** |

Fallback stated now: if UW has no history for F2/F4, those flip to harvest-forward accumulation (new
sensor blocks, governed additive change at Aug-02) with first reads ~3–4 weeks later — the dates
above then bind the BUILD, not the read.

## 5. The milestone ladder to live money (fixed numbers; gates never shrink to dates)

- **M0 — candidate signal:** out-of-sample separation d > 0.68 (incumbent's own OOS + materiality),
  or for stock-horizon streams the pre-registered stock tripwire (weighted mean net 95% lower bound
  > 0 AND direction hit lower bound > 52%), on ≥ 300 independent bets, no vintage explosion.
- **M1 — survives repetition:** the same result on 2 consecutive weekly runs (the persistence lesson,
  now mandatory everywhere).
- **M2 — through the full gates on cost-true outcomes:** selection hit-rate 95% Wilson lower bound >
  that stream's OWN empirical break-even hurdle; PBO ≤ 0.20 (corrected CSCV); Deflated Sharpe > 0.5
  with every trial counted; beats the relevant incumbent baseline on identical purged splits;
  ≥ 8,000 graded rows or ≥ 2,000 independent bets, whichever its horizon makes binding.
- **M3 — Governor ladder:** 6 consecutive GREEN weeks → SHADOW_PROVEN; 6 more → ELIGIBLE_FOR_OWNER;
  owner promotion is the only path to LIVE. Drift (performance or population) blocks promotion.
- **M4 — the live-capital gate (ROADMAP 14 + NORTH_STAR):** calibrated positive expectancy on paper
  across regimes; P(−30% halt) computed on the fitted distribution at chosen sizing and reviewed —
  uncomfortable means size down; backstop lifecycle proven live; £1,000–5,000 initial, scaling only
  on live evidence. NORTH_STAR's stated pace — best case three months from 2026-07-06 — remains the
  ambition; dates slip to evidence, gates never shrink to dates.

## 6. Intention, honestly stated

This system exists to find and compound a real, statistically proven edge — and to KNOW, either way.
Its deeper product has been visible all weekend: every decision recorded, graded, and learned from,
so the system and its owner get permanently smarter regardless of any single outcome. The commitment
is not to make the flow work, or premium selling work, or any particular idea work — it is to hunt
fast, measure honestly, kill quickly, and refuse to pretend, until we find the game that genuinely
pays. Six games are already off the board at near-zero cost; five untested ones are now scheduled
within a week. A clean NO is a success; an unanswered question is the only failure; and the only
unforgivable outcome would be to bet real money on a story. Truth first — profit as its consequence.
