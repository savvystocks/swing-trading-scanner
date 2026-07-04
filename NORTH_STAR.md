# NORTH_STAR — Goals & Aspirations

This is the charter. It says why the system exists, what winning means, and the principles that hold when everything else changes. It outranks persuasion — from any AI session, and from ourselves on a bad week. It changes rarely; see the amendment rule at the bottom.

Document grammar: git history and `reports/` hold the past. SYSTEM_ARCHITECTURE.md holds the present. ROADMAP.md holds the future. This file holds the timeless.

## Mission

Build a fully automated options trading system that earns a durable, statistically proven edge — and know, with evidence, whether that edge exists at all. Truth first; profit as its consequence. The system's deeper product is compounding knowledge: every decision it makes is recorded, graded, and learned from, so the system — and its owner — get permanently smarter regardless of any single trade's outcome.

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
- **£0 first.** The cheapest effective solution, always; what we own before what we could buy; paid only if genuinely irreplaceable, and every saving flagged.
- **Small, reversible steps.** Tags, backups, canaries, checkpoints. Nothing irreversible happens without a gate, and nothing is ever truly deleted.
- **Provenance on everything.** Versions, hashes, windows, timestamps — future-us must always be able to audit past-us.
- **Patience is a position.** The weeks of data before the brain, the shadow period before influence, the gates before capital — the pace is the design. Every shortcut through it is a way of paying to lie to ourselves.

## Risk constraints

- **Paper only** until the live-capital gate's written criteria all pass. No exceptions, no "small test" with real money.
- **Per-trade allocation stays capped at $800** until the EV machinery, on measured slippage, justifies a change in writing.
- **Sizing comes only from calibrated probability** through the Governor — never from conviction, streaks, or mood.
- **[CONFIRM] Automatic halt:** if live capital ever draws down ____% from its high-water mark, the system stops entering and a human review is required before restart. (Proposed default: 20%.)
- **No strategy or parameter change during a drawdown** without harness evidence. The moment of maximum temptation is the moment of minimum trust in judgment.
- **[CONFIRM] Live-capital intent:** real money is / is not the goal, at roughly £____ initial, no earlier than ____ (only after item 14's gate). This line exists so the ambition is stated calmly now, not decided emotionally later.

## Non-goals

Not high-frequency or latency games. Not price prophecy — the brain judges the engine's signals; it does not divine the market from nothing. Not feature maximalism — every sensor earns inclusion by out-of-fold value or stays a logged observer. Not impressive backtests — no number exists to be shown off. Not trading for its own sake — activity is a cost, not an achievement.

## When things conflict, in this order

Safety of capital and data > truth of the records > system uptime > returns > development speed. (This ordering is why we censor unknowable labels rather than guess, and why a lost day beats a poisoned week.)

## The owner's part

**[CONFIRM] Time:** roughly ____ hours per week — the Monday checks, the weekly report, the checkpoint decisions. The system is built to need no more; giving it less than this is the one way to break it slowly.

Judge each week by adherence to process, not by P&L. Variance is loud; edge is quiet. What is in our control is the process — the recording, the gates, the patience; what is not in our control is any single outcome. We practice ruling the first and accepting the second.

## Amendment rule

This file changes rarely and deliberately. Any AI session may PROPOSE an amendment with reasoning; only Savvas applies one. Every amendment appends a line to the log below — date, change, why — and is committed alone, never bundled. CLAUDE.md carries one pointer: read NORTH_STAR.md before proposing anything that alters strategy, risk, or spend.

## Amendment log

- 2026-07-04 — v1.0 adopted. Charter created before the V12 brain build, so the machinery that generates persuasive numbers is judged by principles written in calm.
