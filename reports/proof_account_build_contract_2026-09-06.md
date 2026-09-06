# PROOF ACCOUNT — BUILD CONTRACT (2026-09-06)

Panel verdict: BUILD-WITH-CHANGES (4 adversarial lenses + judge, 83 code reads). This document
is the binding contract for the build; every item below ships or the build does not arm.
Owner rulings of 2026-09-06 are law (NORTH_STAR v1.7): per-trade cap $1,000; CREDIT_SPREAD_W
unseatable on Proof until a rung's stake holds its $1,200 max loss; proof drawdown bound -30%
from stint high-water on DAILY samples; zero-trade weeks PAUSE the streak (8 rising TRADED
weeks); stint fails on DD breach or 3 non-rising traded weeks in rolling 5 -> back to court;
capture>=60% evaluable only at >=20 closed proof trades (stint extends); capture denominator
frozen in writing at seating.

## Required BEFORE BUILD (panel, verified against code)

1. ISOLATION LAYER — a BookContext (creds, log path, cooloff path, brake scope, reconciler
   scope, telegram tag) threaded explicitly through route_to_alpaca_paper (today reads
   os.environ directly, no creds param), manage_open_positions, manage_backstops,
   reconcile_orphans, record_close, _append_log. No os.environ mutation for account switching;
   no bare _paper_creds() below the routing decision. ALPACA_PROOF_* permanently excluded from
   src/alpaca_creds._pairs() (its working_creds() probes an account-agnostic market-data
   endpoint and cannot tell accounts apart). Account identity pinned: every armed cycle asserts
   proof creds resolve to the spec-pinned account_id AND discovery creds resolve to a different id.
2. PROOF-NATIVE STRUCTURE HANDLING — defined-risk structures enter as ONE atomic mleg order
   (pattern exists in the exec path); proof settlement reads broker positions/fills, never the
   synthetic close series; weekly entry gates keyed per account. (Moot for seat one after the
   CREDIT_SPREAD_W ruling, but built into the design so a later seating needs no redesign.)
3. NO 25%-OF-EQUITY CLAUSE — flat $1,000 cap with skip-with-logged-reason. (Superseded by v1.7.)
4. proof_logs.json WIRED INTO THE FULL PERSIST STACK in its creation commit — its own
   validation clause in v10_lab.yml, a MERGERS entry in merge_logs.py keyed by trade_set_id
   plus selftest, explicit git add in the persist step, broker-vs-record reconciliation at
   cycle start, pinned in engine_watch.sh's rollback data-pin list. MOT: a proof record
   survives a simulated -X theirs conflict.
5. SEATING fires EXCLUSIVELY in the probe-court PROMOTE branch (never auto_*/MENU exit
   upgrades); only promotions after arming seat; the pre-2026-08-31 probe.promoted backlog is
   grandfathered as live legs, not seats. FIRST PROMOTION is an owner-ACK gate, not a
   notification.
6. WEEK COUNTER measures settled, executable truth — settlements attributed to their expiry
   week; open positions valued at conservative executable basis (bid for longs, cost-to-close
   ask for shorts), never raw mid-marks; daily equity series via Alpaca portfolio/history into
   week_history; FAILS CLOSED (week uncounted + loud page) on missing/partial data.
7. AUTH != EMPTY — proof helpers propagate auth errors instead of swallowing into []; a typo'd
   secret pages loudly instead of reading as a flat healthy account fabricating
   CLOSE_UNTRACKED bookings.
8. UNSEAT MACHINERY ships with the build — remove from seats, flatten that strategy's proof
   positions next day (no-same-day honored), zero rising_weeks, immutable seat_history record,
   demotion telegram, fresh court case required to re-seat.
9. /flatten AND FAILOVER iterate an explicit account roster — sentinel cleared only after ALL
   accounts flush; failover gains a proof exit pass with proof_logs.json in its commit list;
   missing-keys alarm rate-limited per episode; regime-drill scenario killing the process
   between account flushes.
10. PROOF PASSIVITY as a house invariant — proof placement strictly AFTER all discovery work,
    own order/retry budget behind a hard try/except wall; proof positions excluded from every
    discovery budget, concurrency count and throughput metric. MOT: a cycle with proof creds
    broken produces byte-identical discovery decisions to a proof-disabled cycle; a proof exit
    leaves sandbox_ticker_cooloff.json byte-identical.
11. SPEC-AWARE SENTINEL ROWS in the build commit — vacuously fresh while disarmed/unseated,
    arming automatically at the spec flip; expired_open + ghost_open duplicated against
    proof_logs.json; week_history content check; broker-vs-record divergence check.

## Required BEFORE ARMING

- Owner rulings v1.7: DONE 2026-09-06 (cap, spread seat, DD bound, streak grammar, stint
  failure, capture floor).
- Proof credentials provisioned by the OWNER in GitHub Actions secrets AND VPS .harvest_env
  (never through chat); proof account_id pinned in the spec; failover --check asserts proof
  readability when enabled; both proof secrets in health-check.yml's Sunday canary; dual
  identity assertion green (catches a wrong-slot paste of two valid keys).
- Full suites + MOT green including every new check above; regime drill extended.

## Phases

- A (today): creds threading through the submit/entry path with discovery defaults +
  _pairs() exclusion guard + MOT no-bare-creds check. Pure refactor, behavior-identical.
- B: BookContext through the exit machinery (log/cooloff/brake/reconciler scopes) + MOT
  byte-identity checks.
- C: proof route (seat gate, sizing, proof_logs.json + persist stack wiring, week counter,
  sentinel rows, unseat, flatten/failover roster) — lands enabled:false.
- D: owner creates paper account #2 + adds secrets; arming checklist run; spec flip on
  owner's word.

## Owner action items (whenever ready this week)

1. Create the second Alpaca paper account in the dashboard, reset its equity to $5,000.
2. Add its keys yourself as GitHub Actions secrets ALPACA_PROOF_API_KEY /
   ALPACA_PROOF_SECRET_KEY, and append the same two lines to /home/poller/.harvest_env on the
   VPS. Keys never pass through chat.
3. Say "arm proof" when done — the arming checklist runs, and the account waits for its first
   seat.
