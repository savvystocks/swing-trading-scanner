# Multi-account strategy tournament — spec, 2026-08-01 (staged for the 2026-08-02 boundary)

Owner directive (2026-08-01, verbatim intent): run all viable methods on separate Alpaca paper
accounts "to see which actually performs." This document is the spec. Nothing in it is active;
every activation requires the owner's explicit yes at a Sunday boundary and is logged as a counted
trial. The winners-only learning rule remains red-flagged and is not part of this tournament.

## The one rule that makes the tournament honest (pre-registered before any account trades)

"See which performs" is a multiple-testing machine: with six accounts running, one will lead the
leaderboard by luck within weeks. Therefore:

- WINNER DEFINITION IS FIXED NOW: a method "performs" only when its pre-registered success
  criterion (below, per method) is met at its own minimum sample, using day-clustered effective
  counts and net-of-friction returns. Leaderboard position at any earlier moment is noise and
  decides nothing.
- ALL SIX ACCOUNTS ARE TRIALS: on activation day, +6 entries go into lifetime_trials.json; every
  weekly evaluation pass counts its comparisons. The Governor's deflated-Sharpe machinery prices
  the fact that we ran six at once.
- NO MID-TOURNAMENT TINKERING: each method's spec freezes at activation. A change to any method's
  rules = that method's record resets to zero (it becomes a new counted trial). The control (V10)
  changes for no reason whatsoever.
- NO CROSS-CONTAMINATION: no method reads another account's positions, fills, or P&L. The school's
  gate evidence firewall (adoption-exclusion) applies tournament-wide.

## Account map — FINAL (per-login cap CONFIRMED at 3, 2026-08-01)

The Alpaca dashboard allows multiple paper accounts under the one existing login, and the cap is
three: after v8.5 bot + two new accounts (premium-lane, put-write, both created 2026-08-01 at
$100,000) the "New Paper Account" button disappeared. Six methods therefore consolidate into
three accounts — grouped by RISK TYPE, not cadence, which is stronger than the earlier fallback:
every short-premium/assignment surface lives in ONE account, so an assignment or adoption mishap
(the ADOPT abs(qty) class) can never tangle with the long books. The control stays alone.

| Paper account (dashboard) | Account ID | Books hosted | In-account separation |
|---|---|---|---|
| v8.5 bot (existing) | PA3Y8L8ZA493 | V10 control ONLY, frozen | none needed |
| premium-lane | PA3DWS0CCP91 | premium lane + pure put-write ("short-premium") | OCC + mleg-vs-single + record namespace |
| put-write | PA3IZ4697HP4 | school-gate + lessons-engine + momentum ("flow-lab") | shares vs options; OCC + record namespace between the two options books |

Method specs below keep their original numbering as BOOK ids (books 2–6). Secret naming follows
the dashboard titles even though each account hosts more than its title suggests — this table is
authoritative: ALPACA_KEY_2/ALPACA_SECRET_2 = the premium-lane account; ALPACA_KEY_3/
ALPACA_SECRET_3 = the put-write account. Keys are handed over via the established hidden-input
terminal pattern (never chat) and land as GHA secrets.

Consolidation rules (pre-registered before any book trades):
- Per-method P&L comes from per-record fill ledgers under book namespaces, NEVER from account
  equity — books share accounts, so equity is only a sanity cross-check.
- Same-OCC collision, school-gate vs lessons-engine: school-gate has priority; lessons-engine
  skips and logs the skip (the harvest still measures the counterfactual). Expected rare — the
  gate refuses most entries.
- Same-OCC collision, lane vertical leg vs put-write ATM XSP short: put-write (monthly,
  first-mover) holds; the lane skips that day, logged. Different strikes make this rare.
- Reconcile is per-account and namespace-scoped: an unmatched broker position is QUARANTINED
  (MEASUREMENT_PROBE pattern), never blind-adopted — the abs(qty) adoption class stays closed
  tournament-wide.
- Equity allocation inside flow-lab: momentum book $40,000 notional (20 names × $2,000); the two
  options books share the remainder. Inside short-premium: put-write collateral (~$63k for one
  ATM XSP) + the lane's $900 risk book fit inside $100k with margin to spare.

## Per-method specs (success + kill, pre-registered)

ACCT 2 — PREMIUM LANE. Spec unchanged: PREMIUM_LANE_SPEC_2026-07-28.md v2.2 governs (entry gates,
$900 book, correlation clusters, assignment rule, kills at 20/30/40 fills z=1.645 on cost-bleed,
VIX>25 provisional clause). The only amendment: its book moves from a quarantine tag inside
account 1 to its own account — which closes the adoption-bug exposure class by architecture
instead of by exclusion lists. Honest frame stands: cost-measurement instrument first.

ACCT 3 — PURE INDEX PUT-WRITE (the undiluted documented form). Rules: on the first trading day
after monthly expiry, sell one XSP at-the-money put, nearest monthly expiry, fully
cash-collateralized within the account's cap; hold to expiry or assignment; if assigned, dispose
next session at market open. No other trades, ever. External evidence: the 19.6-year index record
(+7.1%/yr, 17% vol, −37% max DD vs SPX −57%). Success criterion: implementation fidelity — after
10 fills, mean friction (fill vs mid at submission) ≤ 15% of premium collected; P&L verdict is
explicitly OUT OF SCOPE inside the tournament window (monthly cadence = ~12 observations/year;
any P&L claim before ~2 years is noise and will not be made). Kill: friction > 25% of premium
over the first 6 fills, or any naked/unintended exposure detected by reconcile. VIX > 25:
provisional clause identical to the lane's.

ACCT 4 — SCHOOL-GATED V10. Rules: identical signal stream to account 1; every proposal passes
through the Student/Council gate (school_mode=gatekeeper, this account only); entries only when
calibrated blended probability clears that contract's empirical cost-inclusive hurdle; exits
identical to V10. Success criterion: after ≥ 40 gated decisions with day-clustered n_eff ≥ 15,
the gated book's uniqueness-weighted net return beats account 1's on the SAME signal days with a
95% lower bound above zero on the difference. Also measured (not a success bar): refusal rate —
expected high; a near-zero refusal rate is itself a fault flag. Kill: any gate bypass or
cross-account read detected; or the school's weekly verdict machinery goes stale (no fresh
verdict for 2 weeks).

ACCT 5 — LESSONS ENGINE. Rules: V10's signal stream with every OOS-validated lesson hard-wired at
birth — max spread 2% (not 5%), liquid-universe floor (price ≥ 5, mcap ≥ 250M), trail-dominant
exit config, one position per correlation cluster, earnings blackout enforced. No ML, no new
signals — the same engine minus the measured leaks. Success criterion: after ≥ 40 fills with
day-clustered n_eff ≥ 15, uniqueness-weighted net return beats account 1 with the 95% LB of the
difference above zero (expected outcome per the evidence: loses less; flat = important result).
Kill: any fill violating its own hard-wired rules (spec violation = instrument broken), or
friction telemetry shows its tighter spread cap is unfillable (> 60% of attempts expire unfilled
over 2 weeks).

ACCT 6 — MOMENTUM DIVERSIFIER. Rules: monthly, on the first trading day: rank the S&P 500
membership by 12-month-minus-1-month total return (yfinance closes, computed locally, no new data
source); buy the top 20 equal-weight as shares; hold one month; rebalance. No leverage, no
options. Honest horizon statement, pre-registered: academic momentum pays across YEARS with
crash months along the way — this account CANNOT produce a verdict inside the tournament window
and is run as a slow diversifier + implementation exercise. First honest read: 12 months. Kill:
implementation faults only (missed rebalance, wrong universe, unintended position).

## Evaluation protocol

- Weekly: one per-account line in the Sunday strategy section (fills, day-clustered n_eff,
  uniqueness-weighted net, friction telemetry, spec-violation count). Rendered from committed
  artifacts, no hand numbers.
- Verdicts: ONLY when a method hits its own pre-registered sample floor. The weekly line prints
  "n=X of floor Y — no verdict" until then.
- The tournament never picks a winner by ranking. Each method passes or fails its OWN bar; two
  methods can both pass; all can fail.
- Every activation, kill, and verdict goes in the day's ledger and the lifetime trials file.

## Architecture (fetch once, route many — £0 audit)

- One engine cycle serves accounts 1/2/4/5: the existing cron-job.org-dispatched run fetches the
  UW scan ONCE; each method consumes the same in-memory scan and routes orders with its own
  account's keys. Zero marginal UW quota; seconds of marginal GHA time; no new workflows for the
  high-frequency accounts.
- Accounts 3 and 6 are monthly: two tiny scheduled workflows (~2–3 GHA-minutes each per MONTH).
- Alpaca rate limits are per-account (~200 req/min each) — splitting methods across accounts
  spreads load; no shared bottleneck.
- yfinance load: momentum needs ~500 tickers once a month (batched, cached) — well inside the
  existing pattern; per-source health telemetry (C2 spec) covers degradation.
- Per-account state: each account gets its own records file / fill ledger namespace and its own
  reconcile pass; landing checks (archiver_watch pattern) extend to every scheduled job so
  absence pages.
- Incremental cost: £0. Paper accounts are free; GHA stays inside the free tier via the
  consolidated cycle; no new data sources.

## Build order (post-approval; nothing before the yes)

1. Owner: DONE 2026-08-01 — premium-lane and put-write created in the dashboard. Remaining:
   generate each account's API keys; key handoff via terminal (hidden input, one at a time).
   Two pairs → GHA secrets (ALPACA_KEY_2/SECRET_2, ALPACA_KEY_3/SECRET_3).
2. Multi-account routing layer in the cycle (config-OFF per account; MOT off-state proof per
   account before any flag flips).
3. Accounts activate one at a time, each activation a counted trial: lane first (already
   pressure-tested), then put-write (simplest), then lessons, then school-gate, momentum last.
   One activation per day maximum so faults are attributable.
4. Passivity battery after ANY change touching the shared cycle (standing rule); full suites +
   MOT green before every push.

## Adversarial six-check on the tournament itself

1. Edge vs noise-filter: only acct 3 rests on external evidence of edge; 2 is a cost instrument;
   4/5 are A/B instruments; 6 is a diversifier. The tournament measures — it does not assume.
2. Win-rate vs fat-tail: put-write's left tail is the documented −37% DD shape; verticals cap
   acct 2; 4/5 inherit V10's defined-risk longs; 6 is unlevered long shares. No naked exposure
   anywhere; reconcile + adoption-exclusion enforced per account.
3. Frictions: every method logs fill-vs-decision (A2 machinery); acct 3/5 have explicit friction
   kill bars; paper-fill optimism is named — paper fills flatter, so friction numbers are floors.
4. Data honesty: +6 lifetime trials at activation; pre-registered bars; day-clustered n_eff
   everywhere; no winner-by-ranking; frozen specs.
5. Dead weight: the tournament adds a routing layer and two tiny workflows; anything killed is
   deactivated the same week, not left running.
6. Unknown unknowns: the per-login cap RESOLVED at 3 (2026-08-01) — consolidation map above is
   final. Still open and named: whether Alpaca's rate limits are truly independent per paper
   account under one login is assumed, not proven — verified in step 2's off-state checks before
   any flag flips; same-OCC cross-book collisions are handled by the pre-registered priority
   rules but the exit engine's namespace scoping must be MOT-proven before activation (two books
   holding the same OCC would otherwise fight over one aggregated broker position); two new key
   pairs = two leak surfaces (mitigated: secrets only, never chat); operator attention is the
   real scarce resource — all books' alarms funnel into the existing Telegram channel with
   per-book prefixes.
