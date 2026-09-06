# NORTH_STAR — Goals & Aspirations

This is the charter. It says why the system exists, what winning means, and the principles that hold when everything else changes. It outranks persuasion — from any AI session, and from ourselves on a bad week. It changes rarely; see the amendment rule at the bottom.

Document grammar: git history and `reports/` hold the past. SYSTEM_ARCHITECTURE.md holds the present. ROADMAP.md holds the future. This file holds the timeless.

## Mission

Build a fully automated options trading system that earns a durable, statistically proven edge — and know, with evidence, whether that edge exists at all. Truth first; profit as its consequence. The system's deeper product is compounding knowledge: every decision it makes is recorded, graded, and learned from, so the system — and its owner — get permanently smarter regardless of any single trade's outcome.

### The owner's vision (2026-07-05)

This is an income engine, built to fund freedom — pursued with professional patience: small real capital first to prove survival, scaled only on evidence, aggressive once earned. One strategy, perfected, not a platform. The machinery outlives any strategy — if the current signals prove empty, the harness stays and hunts new ones. The owner is not a spectator: five-plus hours a week in the workshop, every event on his phone, learning the concepts as deeply as the system does. Power flows to the brain only as its track record justifies, and never by drift.

## What winning means

- **Operational mastery:** the system runs unattended, every decision recorded and graded, no silent failures. Every failure that does occur is loud, diagnosed, and closed with a test.
- **An answered question:** the Truth Harness delivers a verdict on whether the engine's edge is real — SPRT accept or reject, parameters fixed in advance. A clean NO is a success: it saves capital and redirects effort. An unanswered question is the only failure.
- **Proven, controlled returns:** calibrated positive expectancy on paper, across regimes, surviving the overfitting machinery — and only then, through the live-capital gate (ROADMAP item 14), real money at deliberate scale.
- **The aspiration:** a system that improves the way science does — every change evidence-gated through the harness, bad ideas killed cheaply, good ones promoted on proof. Always improving means always testing, never twiddling.

## Operating principles

- **Truth over comfort.** An honest ugly number beats a flattering false one, every time, because the flattering one becomes a real loss later.
- **Order of appeal:** the code wins over the docs; the harness wins over arguments; the data wins over intuition. Disputes end at the leakage test, not at the best rhetoric.
- **Executable prices only.** Entries at the ask, exits and labels on the bid, gap-throughs included. The mid is a fantasy and is never trusted anywhere.
- **Refusal is a feature.** Abstaining, gating, and sizing down are how the brain earns. A no-trade day is a valid output, not a malfunction.
- **Freeze the teacher while the student learns.** The rules engine's parameters stay fixed during data collection; every change to strategy goes through the harness first, never through live feel.
- **Fail open, fail loud.** If any intelligent layer dies, the system degrades to the frozen engine and keeps its records; and nothing is allowed to fail silently — every incident to date was quiet, so silence is treated as the primary enemy.
- **£0 first.** The cheapest effective solution, always; what we own before what we could buy; paid only if genuinely irreplaceable, and every saving flagged. Spending decisions are case-by-case: the math comes to the owner every time, and he decides.
- **Small, reversible steps.** Tags, backups, canaries, checkpoints. Nothing irreversible happens without a gate, and nothing is ever truly deleted.
- **Provenance on everything.** Versions, hashes, windows, timestamps — future-us must always be able to audit past-us.
- **Patience is a position.** The weeks of data before the brain, the shadow period before influence, the gates before capital — the pace is the design. Every shortcut through it is a way of paying to lie to ourselves.

## Risk constraints

- **Paper only** until the live-capital gate's written criteria all pass. No exceptions, no "small test" with real money.
- **Per-trade allocation stays capped at $800** until the EV machinery, on measured slippage, justifies a change in writing.
- **Sizing comes only from calibrated probability** through the Governor — never from conviction, streaks, or mood.
- **Automatic halt:** if live capital ever draws down **30%** from its high-water mark, the system stops entering and a human review is required before restart. Adopted together with the Stage-4 requirement that the probability of reaching this halt under the fitted return distribution at the chosen sizing is computed and reviewed by the owner before live capital; if that probability is uncomfortably high, sizing comes down before the halt moves up.
- **The daily brake runs in shadow during paper accumulation, not active.** On paper a stop-out is a completed, high-value data point, not a loss to prevent — halting after 3 stop-outs would discard the richest outcomes on the hardest days, which is the data we are here to collect. So the brake evaluates and logs its trigger (3 stop-outs, or a session loss ≥ 2× the $800 allocation) but does **not** suppress entries; the would-have-blocked trades are tagged and measured. It arms to **ACTIVE only at the live-capital gate (item 14)**, justified by that shadow measurement — not tied to brain ignition, which is a separate data-readiness clock. Its eventual live form may be a learned Governor rule rather than the fixed 3-count. This is a risk-control posture, not a signal or recipe change.
- **No strategy or parameter change during a drawdown** without harness evidence. The moment of maximum temptation is the moment of minimum trust in judgment.
- **Live-capital intent:** real money **is** the goal — £1,000–5,000 initial to prove survival in reality, scaling beyond that only on live evidence, no earlier than all of item 14's gates passing. Target pace: best case three months from 2026-07-06; dates may slip to evidence, gates never shrink to dates. This line exists so the ambition is stated calmly now, not decided emotionally later.
- **Sizing ambition (once edge is proven):** aggressive fractional Kelly (half-Kelly or above) is the owner's stated ambition — permitted only through the Governor, only on calibrated probabilities from the empirical (fat-tailed) distribution, and only after the P(halt) review above.

## Non-goals

Not high-frequency or latency games. Not price prophecy — the brain judges the engine's signals; it does not divine the market from nothing. Not feature maximalism — every sensor earns inclusion by out-of-fold value or stays a logged observer. Not impressive backtests — no number exists to be shown off. Not trading for its own sake — activity is a cost, not an achievement. Not a multi-strategy platform — one strategy, perfected. (The owner's separate swing system remains a separate world.)

## The decision record

The standing record of all owner decisions lives in ROADMAP.md's decision table. Only their charter-level essence is duplicated here; if the two ever disagree, this file wins on values, the table wins on configuration.

## When things conflict, in this order

Safety of capital and data > truth of the records > system uptime > returns > development speed. (This ordering is why we censor unknowable labels rather than guess, and why a lost day beats a poisoned week.)

## The owner's part

**Time:** 5+ hours per week, active co-development — the Monday checks, the weekly report, the checkpoint decisions, and learning the concepts as deeply as the system does. The system is built to need no more; giving it less than this is the one way to break it slowly.

Judge each week by adherence to process, and judge the four numbers — win rate, expectancy, equity curve, monthly P&L — only against their statistically expected bands in the weekly report, never against feel. Variance is loud; edge is quiet. What is in our control is the process — the recording, the gates, the patience; what is not in our control is any single outcome. We practice ruling the first and accepting the second.

## Amendment rule

This file changes rarely and deliberately. Any AI session may PROPOSE an amendment with reasoning; only Savvas applies one. Every amendment appends a line to the log below — date, change, why — and is committed alone, never bundled. CLAUDE.md carries one pointer: read NORTH_STAR.md before proposing anything that alters strategy, risk, or spend.

## Amendment log

- 2026-07-04 — v1.0 adopted. Charter created before the V12 brain build, so the machinery that generates persuasive numbers is judged by principles written in calm.
- 2026-07-05 — v1.1: [CONFIRM] items and owner's vision set via the twelve-question owner questionnaire. Halt 30% with P(halt) proviso; live capital £1–5k staged; 5+ hrs/week; multi-strategy added to non-goals.
- 2026-07-05 — v1.2: 21 further owner decisions integrated (engine, exits, risk, data, brain, ops, money). Freeze committed with two-tier scope; SPRT clock starts at full configuration. Promotion policy: eager within gates. Profits reinvested until amended. Spend: case-by-case with the math. Full record: ROADMAP.md standing-decisions table.
- 2026-07-08 — v1.3: daily brake set to SHADOW during paper accumulation (judgment + logging on, entry-suppression off); arms to ACTIVE only at the live-capital gate, proven by the shadow measurement, and not tied to brain ignition. Risk-posture clarification; no signal/recipe change.
- 2026-09-06 — v1.4: THE AMBITION LADDER (owner, five decisions in session). Ambition: a wealth engine — staged capital compounding toward a £100,000 pot within ~3 years of first real money; the £10k+/month income era is a decision taken at the pot, never assumed before it. Three-account architecture: Account 1 = discovery (the existing lab; pays tuition, never the scoreboard); Account 2 = PROOF — a fresh $5k paper account trading only court-promoted strategies at real size, its clean curve the owner's chart; Account 3 = reserve for the next promoted candidate or the pre-live dress rehearsal. Ladder: court promotion seats a strategy on Proof; 8 consecutive rising weeks there (curve above water at end, drawdown inside written bounds, capture ≥60% of backtest) plus the pre-registered live-gate items unlock the first real £1,000–5,000; thereafter one proven quarter at the current stake (profitable, drawdown in bounds, capture holding) doubles the deployment ceiling — £5k→£10k→£20k→£40k→£80k. No acceleration on streaks; demotion symmetry all the way up. Lifetime real-money loss cap: £2,500 across all stakes ever — breach returns everything to paper pending a written owner review; this is the harder line beneath the −30% halt. Honest-math clause: the pot is reached by returns earning the RIGHT for more owner capital at each rung, not by fantasy compounding. Dates may slip to evidence; gates never shrink to dates.
