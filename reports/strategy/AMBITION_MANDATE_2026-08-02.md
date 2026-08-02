# THE AMBITION MANDATE — 2026-08-02 (owner order: minimum 2x the S&P annually; internet-only evidence; come back confident)

Clean-slate sweep of what the internet actually documents at 15-25%+ annual from options —
academic preprints, 13-year real-money blogs, 0DTE communities with thousands of members,
practitioner backtests. Verdict first: THE AMBITIOUS STRATEGY EXISTS, and it is not a new
signal — it is the SAME variance-risk-premium engine the evidence already crowned, with three
public, documented upgrades that turn ~7%/yr into 15-25%/yr: shorter tenor, further OTM,
VIX/Kelly-conditioned sizing at moderate leverage.

## The three independent evidence pillars (different authors, methods, eras — all agree)

1. THIRTEEN YEARS OF REAL MONEY (Early Retirement Now / "Big ERN", ex-Fed economist, massive
   FIRE-community audit trail): selling short-dated far-OTM SPX puts at ~2-2.5x leverage,
   2011→present, documented 13-17%/yr (one year ~20%; recent softer ~10%), no stop-losses,
   losses eaten through 2018 Volmageddon, 2020, 2022. The longest publicly documented
   real-money record in this family. ~1.5-2x the S&P's long-run return, live.
2. ACADEMIC, 2025, OPEN-ACCESS (arXiv 2508.16598, "Sizing the Risk: Kelly, VIX and Hybrid
   Approaches in Put-Writing on Index Options"): systematic SPXW 0-5 DTE put-writing with
   published sizing rules. In-sample 2018-2023: Kelly configs 20-25% annualized, information
   ratios 3-4. Out-of-sample 2024: Kelly 1DTE/5%-OTM 17.2% CAGR at 0.07% max drawdown;
   VIX-rank 5DTE/ATM 52.8% CAGR at 9.9% DD; hybrid 23.1% CAGR at 9.5% DD. The sizing
   methodology is fully published — free to implement.
3. LIVE 0DTE COMMUNITY RECORD (Tammy Chambless MEIC — Multiple-Entry Iron Condors; Quantum
   Options community, Option Omega academy, Theta Profits corroboration incl. a separate
   9,000-trade breakeven-IC record): live-traded since Aug-2022, 20.7% CAGR since Jan-2023,
   max drawdown 4.31%, DEFINED-RISK condors entered in 6 timed tranches/day. Record spans the
   Aug-5-2024 VIX spike and the Apr-2025 tariff crash. Self-reported but community-witnessed
   at scale, mechanics fully public.

Supporting: CBOE's own Bondarenko study (2019) — 125% notional PUT + bond collateral added
+4%/yr over PUT 1989-2018 (+6%/yr 2019-2021): leverage on the VRP is the documented lever.
Benchmark honesty: plain 2x S&P leverage did 23.7% CAGR 1977-2024 with a -79% drawdown — the
whole game is getting the return WITHOUT that drawdown, which is exactly what the three
pillars' sizing rules are for (their DDs: single digits).

## The strategy (named, concrete, ours)

THE LEVERED PREMIUM ENGINE — three books, one mechanism:
- BOOK A (core): short-dated (1-5 DTE) far-OTM (~5%) SPX/XSP put-writing, VIX-rank + fractional
  Kelly sizing per the arXiv methodology, ~1.25-2x notional ceiling (ERN zone), cash-secured
  accounting, VIX>=32 brake and drawdown ratchet as built. Target 15-25%/yr; modeled DD <10-15%.
- BOOK B (defined-risk sleeve): MEIC 0DTE multiple-entry iron condors — 6 timed tranches/day,
  defined risk per condor, per the published mechanics. Target ~20%/yr at low DD; the sleeve is
  structurally capped-loss, which the naked book is not.
- BOOK C (control): the plain monthly PUT-methodology put-write — the unlevered benchmark the
  ambitious books must BEAT to justify their leverage. (Ambition measured, not assumed.)
All free to implement: SPXW/XSP verified live on our Alpaca paper account; sizing rules public;
MEIC mechanics public; validation on QuantConnect's free SPX 2012+ minute data + our harness.

## Pre-registered honesty (the adversarial paragraph — one, then execution)

Sustained 2x-the-S&P is top-decile-fund territory; the three pillars are the best evidence on
the internet that 15-25% is achievable, and each has a hole: ERN is one man's account (audited
by community, not custodian); the arXiv OOS window is ONE bull year at $5M modeled fills; MEIC
is 3.5 years, self-reported, born in a mostly-rising regime. The failure mode of this family is
a fat left-tail week at leverage. Containment is non-negotiable: defined-risk sleeve first-class,
Kelly fractions capped, VIX brake, the 30% NORTH_STAR halt stays sovereign, paper first, £1-5k
initial live, and Book C as the leverage-justification control. Every book a counted trial with
pre-registered kills. If the ambitious books cannot beat the boring control after costs at their
own pre-set floors, the leverage comes off — that is the deal that makes the ambition honest.

## Plan (folds into the boundary as decision 15-AMBITION, amending decision 15)

1. TODAY: ratify the Levered Premium Engine as the core strategy family; Book C (control)
   activates in paper immediately; Book A activates at 1.25x notional floor sizing.
2. WEEK 1: QuantConnect replication of the arXiv configs (Kelly/VIX-rank, 1-5 DTE, 5% OTM) on
   SPX 2012-2026 — through 2018/2020/2022, which the paper's own window barely covers; MEIC
   backtest on our own captured chains + QC minute data. Parameter lock at the 08-09 boundary.
3. WEEKS 2-6: three-book paper tournament under pre-registered bars; fill ledger prices the
   0DTE frictions (the make-or-break for Book B at retail).
4. OCT: live gate per ROADMAP item 14 (£1-5k; IBKR UK parallel).
