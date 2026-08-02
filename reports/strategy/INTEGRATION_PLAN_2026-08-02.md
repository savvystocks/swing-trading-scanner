# INTEGRATION PLAN — the three-tier ladder into our system (2026-08-02)

Companion to THREE_TIER_LADDER / AMBITION_MANDATE / CORE_STRATEGY. Exact mechanics per tier,
engine changes, order plumbing, validation protocol, and build order. The engine/harness/
governance stack is unchanged — each tier is a BOOK: config block + entry module + exit module
+ per-book ledger namespace, routed to its account's keys.

## TIER 1 — Levered Premium Engine (premium-lane acct, target 15-25%/yr)

RULES (from ERN's published practice + arXiv Kelly configs + CBOE leverage study):
- Sell XSP puts 3x/week (Mon/Wed/Fri cycle), 1-5 DTE, strike ~5% OTM (delta roughly 2-10).
- Sizing: fractional Kelly (quarter-to-half) from the Treasurer's fill-ledger distribution,
  scaled by VIX-rank multiplier; notional ceiling starts 1.25x, may step to 2x only by Governor
  promotion after its pre-registered window. Cash-secured accounting at all times.
- Exits: HOLD TO EXPIRY (cash-settled; no assignment). No stops (ERN/spintwig evidence). The
  VIX>=32 macro brake blocks NEW entries only.
- MEIC sleeve (defined-risk) at 25% of book, rules as Tier 3 but conservative deltas.
- In-account control: 1 plain monthly ATM XSP put (PUT methodology) — the leverage must beat it.
ENGINE WORK: new `book_tier1` module — strike picker (pct-OTM from spot), VIX-rank fetch
(yfinance ^VIX9D free), Kelly fraction from treasurer.py (exists), single-leg order at
worst-case limit (sell at bid, improve ladder), expiry settlement reconciler (cash settlement
posts overnight — reconcile expects position to VANISH, not close; new case for reconcile).
DATA: nothing new — Alpaca quotes (tested), yfinance VIX. £0.

## TIER 2 — arXiv VIX-rank configuration (put-write acct, target ~50%/yr)

RULES (as published, arXiv 2508.16598):
- Sell SPXW/XSP puts at 5 DTE, AT-THE-MONEY, weekly cycle.
- Sizing: VIX9D percentile rank over trailing 21 sessions -> position fraction (rank-scaled:
  high rank = rich premium = larger size; low rank = smaller/stand aside). Margin-modeled
  (IBKR-style approximated with cash-secured cap in paper).
- NO stops; hold to expiry; cash-settled.
- 2020-CONDITION (pre-registered): the week-1 QC replication through 2018/2020/2022 sets the
  Kelly cap so the modeled worst historical drawdown <= 25% (inside the NORTH_STAR 30% halt).
  If no cap achieves that while preserving >=35% CAGR on 2012-2026, the tier's target drops to
  what the cap allows — printed at the 08-09 boundary, not negotiated after.
ENGINE WORK: same module family as Tier 1 with different strike/tenor/sizing params — one
code path, two configs (anti-overengineering). Settlement reconciler shared.
DATA: same. £0.

## TIER 3 — Frontier 0DTE defined-risk (v8.5 bot acct, target: measure whether ~100% survives)

RULES (MEIC as published + community variants):
- Each trading day: 6 iron-condor tranches on XSP/SPX 0DTE, entered at fixed clock times
  ~30-45min apart starting 15:00 UTC; short strikes at premium target (~$1.50-2.50 credit per
  side at 10-25 delta), wings $5-10.
- Per-side stop: close a side when its loss = total credit received (the MEIC breakeven rule);
  winning side runs to expiry. Defined-risk ALWAYS (wings mandatory).
- Allocation ladder: start 1 condor/tranche; scale only by Governor promotion.
- FRICTION TRUTH: 6 tranches x 4 legs = the fill ledger's hardest test; premium-capture vs
  backtest is THE metric. Expect the honest outcome "backtest 100%+, real 20-40%".
ENGINE WORK (the real build): intraday cadence. Our GHA cycle (~10min) handles timed ENTRIES
well (6 fixed times), but MEIC stops are intra-minute events. Phase A: stop-checks at 10-min
cycle granularity, slippage explicitly measured as a cost line (honest degradation, logged).
Phase B (only if Phase A capture-gap demands): move Tier-3 loop onto the VPS (24/7 box, no GHA
latency) — a build task, not a spend. Alpaca mleg atomic condors: supported (tested pattern
from the lane). PREREQ: V10 execution retirement (boundary decision; scanner keeps harvesting).
DATA: intraday quotes via existing Alpaca stream/polling. £0.

## SHARED PLUMBING (all tiers)
- Per-book config blocks ship OFF; MOT off-state proof before any flag; activation one book/day.
- Fill ledger: every entry/exit stamps decision_mark -> slip_vs_decision (exists; A2).
- Weekly scoreboard: premium-capture %, day-clustered n_eff, book-vs-control delta, DD vs
  modeled — auto-rendered Sunday (strategy_state extends).
- Kills: as pre-registered in THREE_TIER_LADDER (capture floors, beat-the-tier-below, 30% halt).
- Trials: 3 book activations + every replication config counted into lifetime_trials.json.

## VALIDATION PROTOCOL (week 1, all free)
1. Owner: QuantConnect + optionsDX signups (~5 min each). Keys handoff for the 2 new accounts.
2. QC replications on SPX 2012-2026 (incl. 2018/2020/2022): Tier-1 config grid (1-5DTE x
   3-7% OTM x quarter/half Kelly x 1.25/1.5/2x), Tier-2 as published + capped variants,
   Tier-3 MEIC daily loop (QC minute data supports it).
3. Cross-check the winning configs through OUR harness on optionsDX files (two engines agree
   or we investigate).
4. 08-09 boundary: parameter lock, activation order, Tier-2 cap printed, Tier-3 Phase A go.

## OPEN QUESTIONS THE REPLICATION MUST ANSWER (registered now)
Q1 Tier-2 modeled max-DD through Mar-2020 at published sizing (the number that sets its cap).
Q2 Tier-1: does 2x notional beat 1.25x risk-adjusted across 2012-2026, or is ERN's 2-2.5x
   period-specific?
Q3 Tier-3: backtested capture at $0.05-wide XSP quotes vs SPX $0.50 — which index the condors
   should trade (XSP liquidity vs SPX size).
Q4 All: does hold-to-expiry beat 50%-profit-take on OUR windows (spintwig says yes; verify).
