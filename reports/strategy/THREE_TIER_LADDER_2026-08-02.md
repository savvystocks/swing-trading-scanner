# THE THREE-TIER LADDER — 2026-08-02 (owner order: 3 accounts, ~2x SPX / ~50% / ~100%, one testable strategy each)

Evidence grade DEGRADES as the target climbs — stated per tier, pre-registered, so each account
tests exactly what its documentation supports. All three tiers harvest the same documented
mechanism (the index variance risk premium); the dial is tenor, moneyness, sizing, and Kelly
fraction. Nothing here requires paid software: rules are published; validation on QC free data;
execution on our Alpaca paper accounts (XSP/SPXW verified live 08-02).

## TIER 1 — target ~2x S&P (15-25%/yr) — account: premium-lane — grade: PROVEN
The Levered Premium Engine (AMBITION_MANDATE_2026-08-02.md): short-dated 5%-OTM SPX/XSP
put-writing, VIX-rank + fractional-Kelly sizing, 1.25-2x notional ceiling; MEIC defined-risk
sleeve; plain monthly put-write as in-account control. Pillars: ERN 13y real money 13-17%/yr at
2-2.5x; arXiv 2508.16598 Kelly configs 17-25% CAGR (IR 3-4); MEIC 20.7% CAGR live since 2023;
CBOE-published leverage study (+4-6%/yr at 125% notional).

## TIER 2 — target ~50%/yr — account: put-write — grade: DOCUMENTED (academic OOS, one year)
THE ARXIV VIX-RANK CONFIGURATION, run as published: SPXW 5-DTE AT-THE-MONEY put-writing, sized
by VIX9D percentile rank over a 21-day window (sell bigger when vol-rank high/premium rich,
stand down when poor), margin-modeled, no stops (per methodology).
- Documented: 52.77% CAGR out-of-sample 2024 at 21.6% vol, 9.9% max DD; in-sample 2018-2023
  framework 20-25%+ with the ATM configs at the aggressive end. Fully published sizing rules —
  the single best-documented ~50% options configuration found on the public internet.
- Honest holes: ONE out-of-sample year (a bull year); $5M modeled account; ATM short puts carry
  real left tail (the 9.9% DD is 2024's, not 2020's). Our week-1 QC replication runs it through
  2018/2020/2022 BEFORE activation — its 2020 number decides its true sizing.
- Kills (pre-registered): replication fails to beat Tier 1's config risk-adjusted on 2012-2026
  data -> demote to research; live paper premium-capture < 60% of backtest for 6 weeks -> halve
  sizing; NORTH_STAR 30% halt sovereign.

## TIER 3 — target ~100%/yr — account: v8.5 bot — grade: FRONTIER (backtest-only; NO audited
live 100%/yr record exists in public — stated plainly; Medallion-class is the only precedent
and it is closed)
AGGRESSIVE 0DTE DEFINED-RISK PREMIUM: maximum-documented-aggression multiple-entry 0DTE
structures (MEIC at full allocation / breakeven-IC / Skyline-class butterfly variants), ALL
capped-loss by construction — at 100% targets, naked anything = eventual gap death, so the
frontier book is defined-risk ONLY (ruin becomes slow measurable bleed, not overnight zero).
- Documented: Option Omega community backtests on 1-minute data reach triple-digit CAGRs at
  small size (e.g. $5k->$74k, ~300% CAGR, 2 contracts); Theta Profits' separate 9,000-trade
  0DTE record; academic support that 0DTE options are systematically overpriced (sellers earn
  premium) with known gamma/feedback tail. NONE of this is an audited live 100%/yr — the
  book's JOB is to test whether triple-digit backtest CAGR survives real fills and real weeks.
- Frictions are the make-or-break: 6 condors/day = 24 legs of spread crossings; the fill
  ledger prices this within weeks — the most likely honest outcome is "backtest 100%+, real
  fills 20-40%", and MEASURING that gap is the deliverable.
- Kills: premium capture <= 0 at 40 fills; capture < 50% of backtest for 4 consecutive weeks
  -> retire to research; weekly loss > 2x weekly target twice -> halve allocation.
- Prereq: V10 retires from EXECUTION at this boundary (verdict already REJECTED; scanner keeps
  harvesting passively at 0 cost) so the account is clean. Owner decision.

## The deal across the ladder
Each tier must BEAT THE TIER BELOW at its own pre-registered floors to keep its aggression;
each is a counted trial; all report premium-capture + day-clustered n_eff weekly; 30% halt
sovereign everywhere. Week 1: QC replication of Tiers 1-2 through 2012-2026 + Tier-3 config
sweep; parameter lock 08-09; paper live after lock, one tier per day.
