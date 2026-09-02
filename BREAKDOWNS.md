# BREAKDOWNS - the complete incident log

Owner order 2026-09-01: every operational, data, or engine breakdown lives here, permanently,
with enough detail that any future session knows what happened and what fixed it.

STANDING RULE: when a breakdown is fixed, its entry is added to this file IN THE SAME COMMIT
as the fix - date, what broke, root cause, fix (with commit sha), and the lesson. Near-misses
caught in review before they fired count too. This file is append-only history; nothing is
ever deleted or rewritten.

Format per entry: WHAT BROKE / ROOT CAUSE / FIX / LESSON.

---

## V3.1/V4 scanner era (Apr-May 2026)

2026-04-10 - SILENT AUTO-PASS GATES. Three scan gates auto-passed on null/empty inputs
(peg null, float null, empty history), letting unqualified stocks through. Fix a93a255b +
8687ed6d. Lesson: nulls fail closed in scoring gates.

2026-04-21 - ALPACA-PY BREAKING CHANGE. OptionsSnapshot lost open_interest, IV moved levels;
scanner errored. Fix 37111a28. Lesson: providers drift; the weekly schema harness
(health-check.yml) exists because of this.

2026-04-28/30 - CRON DRIFT. intraday-rvol-check lacked permissions; daily-scan ran at the
wrong hour. Fix a770d0df, 3eb799b0.

2026-05-05 - SCAN CRASH. Sector overlay shadowed the datetime import; UnboundLocalError.
Fix 8efdd41a.

2026-05-11/14 - IMPORT-TIME CI CRASH. int() of empty GitHub secret at module import killed
the pipeline (MAX_CONCURRENT_LOTTERY, then ACCOUNT_SIZE_USD). Fix e9e47621, 23bcb9bc.
Lesson: empty secrets arrive as ""; guard every env parse.

2026-05-13 - WINDOWS UNICODE CRASH. Non-ASCII print on cp1252 console. Fix 148803d2.

2026-05-14 - GHA QUOTA EMERGENCY. 90% of free Actions minutes burned mid-month by new
30-min polls. Fix 367b333d (schedules halved/disabled, timeouts tightened, ~800 min/mo
saved). Lesson: every schedule costs quota; ancestor of the L0-incremental-cost rule.

2026-05-22 - WRONG FILE DEPLOYED. Stray root-level debug scripts made Streamlit Cloud
deploy the wrong entry file. Fix ea707336.

2026-05-29 - STUBBED MODULES + BUY-ON-SKIP. 28 modules found reduced to stubs (restored
58885a3e); weak-SKIP treated as bullish in signal math (25bc0b07); Jinja "?" leak in emails
(e7a19260).

## V8/V9 flow-scanner era (Jun 2026)

2026-06-03 - 90-MINUTE LIVE OUTAGE. KeyError in the ETF filter killed the intraday scan.
Root cause: parsers written against assumed UW payload shapes, not observed ones. Fix
1b958542 + 6114cdfe/08157f1e/178b7411 recalibrations. Lesson: calibrate to real payloads.

2026-06-09 - STOP BLEW THROUGH. TSLA put closed -52.2% vs a -50% stop. Root cause: exits
were poll-driven only; ZERO server-side stop orders existed (confirmed by the 07-02 audit:
0 OCO/stops in 169 all-time orders). Structural fix: Tier-B broker-side GTC backstops
(2026-07-06/07). Lesson: every position needs a resting broker-side order.

2026-06-10 - VERIFICATION SILENTLY OFF. LLM grader TypeError (str/float) graded 0 names;
nobody noticed. Lesson: silent degradation of a checking layer is worse than a crash.

2026-06-10 - VPS ROOT PASSWORD EXPOSED in chat. Later structural fix: key-only read-only
poller account. Lesson: rotate on exposure; least-privilege access.

2026-06-16 - SESSIONS PURGED (tooling). April working sessions hard-deleted by the 30-day
transcript cleanup. Recovery procedure in SESSION_RECOVERY_HANDOFF.md.

2026-06-22/23 - DEAD KEY + STALE REFERENCE. Live Alpaca key dead; the resolver swap left a
stale has_alpaca reference crashing _enrich. Fix 49cd7f05, 868f0f78, adf26eb4. Lesson:
sweep every call site when swapping credential resolvers.

2026-06-22 - PERSIST SILENTLY ABORTED. One bad pathspec killed the whole git add; scan
state and anti-spam state lost. Fix 1f858371 (split adds + rebase-retry).

## Counterfactual harvest / V10 cutover (Jul 2026)

2026-07-02 - HARVEST AUDIT RED, 3 CRITICALS. (1) Barriers hardcoded "Friday 16:00 ET"
landed on the Jul-3 holiday - ~1,700 candidates would mislabel; fix 62db4895 (XNYS
calendar). (2) The Windows Task Scheduler poller had NEVER run (Last Run 30/11/1999).
(3) The poller never git-pulled - the day's 1,656 candidates never reached the DB. Fix for
2+3: poller moved to the Vultr VPS with git-pull-first cron (2026-07-03). Lessons:
exchange calendars in all date math; labeling infra on an always-on box; transport
self-syncs. Report: reports/harvest_audit_2026-07-02.md.

2026-07-02 - NAKED 72-POSITION WEEKEND. 72 open paper positions, zero working exit orders,
52 records FLUSHED/orphaned so the exit engine never saw them (SNDK +99%, AAPL +183%,
PFE -100% unmanaged). Fix 3d166b54 (orphan adoption + close-on-failure), then Tier-B GTC
stops. Lesson: "logged" and "managed" must be the same set.

2026-07-02 - MANDATORY RANDOM SAMPLE EMPTY. The Bernoulli tier logged 0 rows (needed 5) -
sampled from an always-empty remainder. Fix d9be45b9. Lesson: verify mandatory samplers
actually emit.

2026-07-03 - CRLF PASS ZEROED A SCRIPT. run_poller_vps.sh emptied to 0 bytes by a
line-ending conversion. Fix 86a49f8c, 6ad42ff0. Lesson: never batch-convert endings blind.

2026-07-03 - DOCS DESCRIBED A DEAD SYSTEM. CLAUDE.md described the deleted EODHD scanner;
V9 and V10 both auto-firing into the same account; false safety docstrings. Fix: V9
retired 07-04, docs rebuilt; the present-tense/future-tense doc discipline exists because
of this. Report: REPO_FORENSIC_AUDIT_2026-07-03.md.

2026-07-04 - WORKFLOW STARTUP FAILURE. V9-retirement rename left a childless `with:` in
v10_lab.yml. Fix 862793d1.

2026-07-04 - NO MARKET-OPEN GATE. A closed-market cycle could still fire orders. Fix
80e4ea5d (_market_is_open via Alpaca clock, fail-closed) + MOT check.

2026-07-06 - GO-LIVE: HARVEST ROW LOST TO A TRIGGER RACE. Schedule + dispatch fired the
same minute; the loser's rebase dropped the commit carrying WULF's executed harvest row -
gone forever. Fix fa5bdc92 (single trigger + merge=union on the inbox). Lesson:
append-only transports get union merges; never dual-trigger a committing workflow.

2026-07-06 - FLUSH LIED ABOUT PFE. PFE's close failed at the open but flush marked ALL
records FLUSHED anyway - broker long, records blind. Fix: FLUSHED only on confirmed close;
PARK state added. Lesson: never record an exit that didn't confirm. (The residue of the
SAME position's option auto-exercise became the 1,300-share PFE ghost sold 2026-09-01.)

2026-07-08 - SILENT-DEATH ALARM OFF. No VPS watchdog cron, no Telegram creds on the box,
no dead-man ping - a silent death would have reached the owner as silence. Fixed same
evening (watchdog_vps.sh + creds + healthchecks ping, live-tested). Lesson: monitoring is
part of go-live; test the page end-to-end. Report: reports/diagnostic_2026-07-08.md.

2026-07-08 - SCOREBOARD DRIFT + FAKE SPREADS. 36 OPEN records vs 26 broker positions;
7 unconfirmed closes; executed rows before 07-09 carried a synthetic ~0.99% spread
(unusable for spread analysis); params_hash rotated on ops knobs. Fixes across 97cad722/
686c7c46/7a3c49fa. Lesson: reconcile continuously; hash only the recipe.

2026-07-10 - POLLER GIT RACES. "Cannot fast-forward" / "cannot lock ref" as the poller's
pull raced engine pushes. Fix da085494 (fetch --no-tags + reset --hard). Lesson: a
mirror-only box uses fetch+reset, not pull.

2026-07-16 - 61% OF TRAINING PILE FEATURELESS. Lean-tier rows stored labels with null
features; 10,646 "graded" rows were really ~4,104 trainable. Lesson: count trainable rows.

2026-07-22 - VPS DISK FILLED. keep=14 local DB backups held 14 full copies. Fix 68877ad8
(retention 2; off-box snapshots are the archive). Same day: cron scripts must be
dash/sh-compatible (29800638).

2026-07-25 - THE VALIDATOR WAS BROKEN. The PBO harness wasn't CSCV and certified pure
noise as clean. Fix 1f6fa787. Lesson: validate the validators.

2026-07-26 - LOOKAHEAD CONTAMINATION. Persistence features leaked the future. Fix
27f98c4b (rebuilt causal). Lesson: pre-register the leakage test before computing values.

2026-07-27/28 - 55 PHANTOM OPEN RECORDS. 101 OPEN records vs 49 broker positions -
cancelled entries never closed their records, blocking re-entry. Fix a3e68c88
(order-state-classified reconciliation, no guessed returns).

2026-07-28 - ARCHIVER CAPTURED THE WRONG DATA. Read-only key used for pushes (088ddde5),
bare OCC universe with no IV surface (1d1236b3), expiries spanning 1.5 weeks (18575f74).
Lesson: verify a new pipeline's first outputs field-by-field.

## Fade-book / $5k era (Aug 2026)

2026-08-04/05 - 24-HOUR SILENT ENTRY OUTAGE. iv_term failed in GHA only; a _safe wrapper
swallowed it; entries stopped fleet-wide for a day while digests looked normal. Fix
54f66645 + zero-entry market-day alarm. Lesson: alarm on absence of activity.

2026-08-05 - WATCHDOG CRON SILENTLY LOST. The snapshot-landing dead-man cron vanished;
nothing noticed for 20 days. Fix ff783604 (watchdog v2). Lesson: watchdogs need watchdogs.

2026-08-06 - LOST TRADING DAY (GHA incident). Unbounded IV retry+sleep vs the 8-min GHA
timeout; runs timed out, dispatches cancelled each other, the external dispatcher died,
and every alarm living inside GHA died with it. Fix ca7e3d6a (IV circuit breaker) +
engine_watch.sh on the VPS + engine_failover_exits.py (exit-only failover). Lessons:
circuit breakers not retries inside timeboxed runners; alarms live OUTSIDE the failure
domain; failover runs only the safety-critical half.

2026-08-07 - 8 FALSE "ENGINE DEAD" PAGES. The watchdog's own fetches bounced on a green
day and it declared death. Fix d1cd7371 (blind must confirm itself; blind never triggers
failover; page once per episode). Lesson: can't-see-it is not it's-down.

2026-08-11 - FRIENDLY-FIRE ADOPTION. The orphan reconciler, blind to legless PUTW records,
adopted our own short put as a long and covered it. Fix c76579f8. Lesson: every new
instrument class registers its occs with the reconciler BEFORE first trade.

2026-08-12 - RECORD VANISHED IN A PUSH RACE. File-level rebase conflict dropped the NVDA
record; same class risked a shares double-buy. Fix 236e7ae7 (record-level union resolver
by trade_set_id) + 8920c980 (idempotent entries vs broker truth). Lesson: merge trade logs
at record level.

2026-08-14 - DOUBLE-CLAIM DISEASE. Fresh fills were adopted before their entry record's
push propagated - daily duplicates; ledger appends clobbered full rows. Fix 44dddf5d
(45-min adoption grace), 24abdc4f (per-day ledger merge); extended to sell fills (2b9b8bce)
and pending orders (a36a9ef1). Lesson: adoption waits out propagation lag.

2026-08-17 - EXIT ENGINE CRASHED EVERY CYCLE. The no-same-day-sell deferred-HOLD dropped a
stage key; KeyError from the first same-day trigger onward. Fix a88dfb76. Lesson:
integration-test new owner rules against the exit state machine.

2026-08-18 - FIRST LIVE AUTO-ROLLBACK, WITH COLLATERAL. The rollback reverted the whole
tree: swept same-day code and carried stale data files that spawned 19 duplicate
adoptions. Fix 606f26ef (rollback commits CODE ONLY). Lesson: recovery actions get the
same blast-radius scrutiny as deploys.

2026-08-19 - PIP QUEUE CHURN. Dependency installs stretched runs; 24 runs lost plus the
overnight exit window. Fix 08eaef26 (pip cache, window 40 min). Same night: sqlite lock
contention wrote null ledger lines (0a2c2eb2 - 60s timeout + never-write-null).

2026-08-20 - FALSE AUTO-ROLLBACK. Twin schedulers 1 minute apart looked like a crash loop;
the watchdog rolled back healthy code and the rollback reverted its own fix. Fix 77c51096
(offset), 5ddc61f1 (no-op rollback = churn), 477060df (65m/3-tick thresholds). Lesson:
de-conflict schedulers; check what a rollback reverted.

2026-08-24 - MASS-ADOPTION / CORRUPT-LOG (worst data incident on record). A persist race
spliced two log versions into invalid JSON via rebase -X ours; the next run's
"unreadable = empty book" fallback adopted ALL 29 broker positions as duplicates, three
waves. Fix 41e6561b - _assert_log_integrity at cycle start (unreadable = restore newest
parseable from git or HALT loudly; "Never trade blind") + persist JSON-validation gate.
Lesson: fail closed on unreadable state; validate JSON before push.

2026-08-25 - SILENT-GAP AUDIT FALLOUT. Repo-wide hunt for the 08-24 pattern found six
fail-open gaps (corrupt spec masquerading as defaults; unreadable book = empty) and four
HIGH findings incl. spec trail keys the live engine NEVER READ (d16fb7e9). Same day: Ford
-87% - a leg through its stop exited on the expiry path instead (b8beac42, STOP OUTRANKS
EXPIRY); backstop Telegram spam 13-in-one-cycle (36b72390, batched); cron nested-quote
mangling killed sentinel emission (f65a67a9 - cron logic lives in script files). Lesson:
spec keys must be provably wired; audits hunt silent paths specifically.

2026-08-26 - REAL GHA OUTAGE EXERCISED THE FAILOVER. Gaps found live: failover didn't
stamp the good-cycle sentinel (false-rollback countdown) and didn't cover every tick. Fix
616916cd. Note: failover/rollback tested by real incidents only, 3-0 so far. Same day
(research): precise-replay OOM at 29.4k trades - bounded cache + checkpoint resume
(0b8fd4de).

2026-08-28 - PROMOTION TRACK EMPTY AND SILENT for 4 days after a demotion. Fix 9bc2f5fa +
0eb249f4 (an empty track announces itself). Lesson: empty-but-should-be-full is an alarm.

## September 2026

2026-09-02 - PROBE ENTRY DROUGHT, DAY ONE OF THE FIXED ROTATION (zero entries, zero
telegrams, cycles green). The 6-attempt budget (shipped 09-01 to stop the churn class) was
exhausted every cycle by DEGENERATE candidates: 5 of the scan's top 10 tickers had dead
metadata (no IV / non-optionable class), each costing a full failed sensor sweep in the
probe loop even though the fade loop had ALREADY discovered and skipped them the same
cycle. Compounding failure of visibility: probe-loop skips print nothing, so eight green
cycles produced zero entries in total silence - the owner noticed via missing telegrams.
Fix a6419e58: probes skip tickers the cycle already found metadata-dead or spread-dead
(free reuse of engine_skips), and a zero-entry probe cycle now prints its attempt count.
Lessons: (1) a budget shipped to bound one cost must not be exhaustible by an unrelated
waste class - audit what else spends the same currency; (2) zero-activity states must
announce themselves (the 08-04 absence-alarm lesson, relearned at probe scope); (3) the
same cycle must never pay twice for the same discovery.

2026-09-02 (root, found via the new visibility line) - THE WEDNESDAY BLIND SPOT. The
"degenerate" names weren't degenerate: CRWD/DELL/BIIB/KKR read iv=unavailable because the
front-IV probe window (10-15 DTE) spans only SIX days - the one window in the system
narrower than a week - so from a Wednesday it contains no Friday at all, and every
Friday-only-expiry equity failed metadata. Structural: the engine went blind for normal
stocks one weekday per week, since the window constants shipped. QQQ/SPY survived (daily
expiries), which disguised it as ticker flakiness. Live-verified same hour: CRWD front IV
None on 10-15d, 50.1 back - healthy on the widened window. Fix: iv_term_structure widens
once to 7-18d when the front window comes back empty (7+ days always spans a Friday);
suites+MOT green. Lessons: (1) any date-window constant must be >= 7 days wide or justify
why not; (2) when "bad data" clusters on a weekday, suspect calendar geometry before
provider flakiness; (3) the 08-04 lesson compounds - the absence-alarm that was missing
here (probe visibility line, shipped hours earlier) is what exposed a bug that predates it.

2026-08-31 - GRAND RETEST SCORED ZERO (transient). First run scored 0 trades; instrumented
rerun scored 33,386 with every funnel gate healthy; cause never reproduced. Lesson kept:
instrument the funnel BEFORE debugging by hypothesis - counters localized the problem
class in one run.

2026-09-01 - VENV DEPENDENCY DRIFT. vaderSentiment missing from the VPS venv failed the
MOT 127/128 (news sensor untouched by the diff under test). Reinstalled from
requirements-sandbox.txt; MOT 128/128. Lesson: a red MOT check names the failing
subsystem - check environment drift before suspecting the diff.

2026-09-01 - STALE WATCHDOG EXPECTATIONS (false alarms). landing_watch demanded a manifest
from the archiver workflow that died Aug 5 (replaced by snapshot pushes it also checks)
and grepped for a commit message wording ("student weekly report") that had evolved -
both alarmed nightly on healthy systems. Fixed in landing_watch.sh. Lesson: when a
monitored artifact is replaced, update every watchdog that expected the old one.

2026-09-01 - ROTATION SENSOR-COST BLOWUP (same-day regression of the grid deploy). From
17:40Z every engine run timed out and was cancelled by its successor - the 08-19/08-20
churn class - and no cycle completed for ~1.5h. Root cause: the new roster rotation walked
afternoon start indices into rare-filter probes; every candidate attempt runs a FULL sensor
sweep before its filter can reject, so pools of never-entering probes burned 10 attempts
each and cycle time blew past the dispatch interval. Head-first ordering had hidden this
cost for weeks (broad head probes entered within a few attempts and broke the loop).
Detected by the end-of-day status pull (cancelled-run pattern + stale good-cycle stamp);
morning runs were fast because morning start indices landed on broad probes. Fix same
evening: per-cycle attempt budget (6) restoring the pre-rotation cost envelope while
rotation keeps deciding who leads. Lesson: any reordering of a loop whose early exit
bounded a hidden cost must be shipped WITH an explicit budget on that cost - and a deploy
is not "verified" after its first green cycle when its behavior varies by hour.

2026-09-01 - NEAR-MISSES CAUGHT IN ADVERSARIAL REVIEW (never fired; the review gate is the
fix). Shipping the 3x3 grid, the 5-lens panel confirmed four defects pre-push:
(1) hour%14 rotation could never reach roster indices 7-12 - market hours span only 7-8
values (fix: day+hour seed); (2) the rotation cut the EXEC_BASELINE control from 5
fills/day to 1, quietly changing the promotion bar for all 8 tracked strategies (fix:
control keeps its head slot every cycle); (3) PUT_DEBIT_W's failed short leg left a filled
long put with NO record - infinite re-buy loop, reconciler-invisible (fix: wings-only
record logged); (4) a promoted weekly _W leg would trip the daily >=3/week throughput
floor forever (fix: weekly legs exempt). Separately, the live-band split test killed the
DIP_CONF_MILD design as shipped-from-backtest: its +11.3%/day edge sits in flow the scan
can't reach (cheap-band reality: +4.0 t0.7 noise); re-pointed at the whale pool
(+17.3/day t1.9 reachable). Lesson: backtest cohorts must be checked against the LIVE
FUNNEL's actual reach before a probe ships; adversarial review before push catches what
suites cannot.

2026-09-01 (evening) - INSTRUMENT-MISMATCH near-miss on the pricey pool (panel catch #5,
caught pre-push). The first pricey-pool build handed DIP_CONF_MILD ticker-level triggers,
but probes buy an engine-SYNTHESIZED cheap structure - so its live fills would have accrued
promotion evidence labeled with a +21.2/day t4.31 cell that was measured on the EXPENSIVE
TRIGGER CONTRACT itself (often landing in the same cheap band the split graded noise).
Pure data-honesty corruption: wrong instrument, wrong cohort filters (no aggressor, no
spread, calls+puts mixed), silently credited to the tested cell. Fix same night: the pool
keeps contract identity (occ, expiry, strike, alert ask; aggressor + spread + band filters
at alert level) and a _PROBE_CONTRACT override makes build_legs return THE trigger contract
(1 contract, live-quoted, spread-capped downstream like any leg). Lesson: a probe's
evidence must be earned on the instrument the backtest measured - "same ticker" is not
"same trade"; this gap exists latently for every synthesized-structure probe, so their
evidence blocks must never cite trigger-contract backtests as if equivalent.
