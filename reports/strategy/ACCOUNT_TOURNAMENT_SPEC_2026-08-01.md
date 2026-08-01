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

## Account map (one Alpaca login; separate titled paper accounts — owner decision 2026-08-01)

The Alpaca dashboard supports multiple paper accounts under the single existing login ("New Paper
Account" in the account switcher). Each paper account carries its own account ID, its own API key
pair, its own equity, and its own clean P&L — the same firewall the spec needs, with no extra
signups. All six books live under the one login.

| Acct | Paper account title | Method | Instrument | Cadence |
|---|---|---|---|---|
| 1 | v8.5 bot (existing) | V10 control, frozen | options, flow-triggered | ~10min cycles |
| 2 | premium-lane | Premium lane v2.2 | XSP/SPY put verticals, mleg | 1/day max |
| 3 | put-write | Pure index put-write | XSP ATM short put, cash-secured | monthly |
| 4 | school-gate | School-gated V10 | options, flow-triggered, gated | ~10min cycles |
| 5 | lessons-engine | Lessons Engine | options, flow-triggered, filtered | ~10min cycles |
| 6 | momentum | Momentum diversifier | shares, 12-1 momentum | monthly rebalance |

The owner creates each titled paper account in the dashboard, switches into it, generates that
account's API key pair, and hands it over via the established hidden-input terminal pattern; keys
never appear in chat. Each pair lands as its own GHA secret (ALPACA_KEY_N / ALPACA_SECRET_N) plus
VPS env entries where needed. Standard starting balance $100,000 per new account so the books are
comparable (covers put-write's ~$63k XSP collateral with margin to spare). If Alpaca caps the
number of paper accounts per login below six, the fallback is pre-decided: monthly-cadence books
consolidate first (put-write + momentum share one account — they never overlap in instrument
type, options vs shares, so reconcile separates them cleanly), then lessons-engine shares with
school-gate under record-namespace tags as the last resort.

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

1. Owner: create the 5 titled paper accounts under the existing login (dashboard → New Paper
   Account), generate each account's API keys; key handoff via terminal (hidden input, one at a
   time). Keys → GHA secrets.
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
6. Unknown unknowns (named): the per-login paper-account cap is unverified until the button is
   pressed (fallback consolidation order pre-decided in the account map); whether Alpaca's
   per-account rate limits are truly independent for paper accounts under one login is assumed,
   not proven — verified in step 2's off-state checks before any flag flips; five key pairs =
   five leak surfaces (mitigated: secrets only, never chat); operator attention is the real
   scarce resource — six accounts of alarms funnel into the existing Telegram channel with
   per-account prefixes.
