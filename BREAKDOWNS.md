# BREAKDOWNS - the complete incident log

Owner order 2026-09-01: every operational, data, or engine breakdown lives here, permanently,
with enough detail that any future session knows what happened and what fixed it.

STANDING RULE: when a breakdown is fixed, its entry is added to this file IN THE SAME COMMIT
as the fix - date, what broke, root cause, fix (with commit sha), and the lesson. Near-misses
caught in review before they fired count too. This file is append-only history; nothing is
ever deleted or rewritten.

Format per entry: WHAT BROKE / ROOT CAUSE / FIX / LESSON.

COVERAGE RULE (owner order 2026-09-07, "the MOT must be well taught from all the
breakdowns"): every new entry also names the REGRESSION CHECK that would catch its
return (MOT check, suite test, sentinel row, drill scenario, watchdog) - or states
NONE-POSSIBLE with the reason. The standing coverage matrix lives at
reports/mot_coverage_2026-09-07.md and is re-audited when it drifts.

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

2026-09-03 - THE BULL-DAY AFFORDABILITY DROUGHT (zero buy signals all day; owner caught it
again by silence). First BULL-regime day since the grid shipped: flow concentrated in
mega-cap names (AVGO, DELL, SOXL, QQQ), and every probe's SYNTHESIZED contract (4%-OTM /
35-DTE on $300-500 underlyings) priced $12-20 - over the $1k budget's $10 ceiling - so all
six attempts died premium_too_rich, cycle after cycle. Structural mismatch, visible only on
big-cap days: the scan's affordability filter vets the TRIGGER contract ($0.30-4.00), then
the engine discards that identity and builds a contract the budget cannot buy. The affordable
contract existed on every one of those candidates all day. Fix: affordability identity kept
per side at scan (cheapest in-band contract's occ/ask/expiry, DTE>=7), and when a probe's
synthesized legs fail the budget it buys THE trigger contract through the panel-hardened
verbatim path (resolution skip, fail-closed live repricing with a widened 0.30 floor via
band_lo, occ-collision guard, nickel limits). Lessons: (1) when a filter vets object A and
the engine then trades object B, every property the filter guaranteed silently stops being
true - trade what you vetted; (2) each regime's first live day IS a test day - MILD's first
day found the sensor drought, BULL's first day found this; BEAR's first day will find its
own, plan to watch it; (3) the visibility line paid again - diagnosis took minutes, not hours.

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

2026-09-02 (evening) - PUSHED ON A RED MOT (process breakdown, self-inflicted, corrected
within the hour). The throughput-trio commit went to main while the MOT was FAILING: the
push command piped the suite script through tail, so the shell chain read tail's exit code
(0) instead of the script's (1) - the gate ran, failed, and was overridden by plumbing. A
second slip compounded it: the previous background suite run's result was never checked
before editing further. The failures themselves proved to be the new ONE-RECORD-PER-
CONTRACT invariant working correctly against harness fixtures that reused a mock contract
across sequential entries (plus one stale stub signature); engine code was sound, fixtures
were updated, and the invariant is now itself a certified MOT check (dim 6, 129/129).
Lessons: (1) NEVER pipe the gate - run the suite, check ITS exit code, THEN commit;
(2) a background gate run must be read before the next edit lands on top of it; (3) when a
new invariant breaks old tests, suspect the tests are asserting the old world - but only
after proving it, never as the first assumption.

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

2026-09-04 - FROZEN ARCHIVE WINDOW: the UW history puller's END date was HARDCODED at
2026-08-21, so the archive (contracts_daily, flow_prints) silently stopped advancing on
Aug 20 while the nightly crons kept burning the full 30k-call budget backfilling ever-older
ticker-days inside the frozen window. Every corpus downstream - probe_tuner rows, the glide
fine grid, tuner_apply's evidence - was two weeks stale, which means tonight's "first
automatic tuning pass" would have judged strategies on zero new data and the Friday chain
would have HOLD-spammed forever. A second interacting defect hid it: pull sessions crossing
UTC midnight kept spending into the NEW day's budget (used_today() re-reads date.today()
per iteration), so the history puller's 22:30 session alternately ate two days' budgets and
left its next session 0 calls - the log's repeating "0 calls / budget 30000/30000" blocks
read like normal budget discipline instead of a starvation symptom. Found 2026-09-04 21:20
while verifying why the Friday tuner refresh left no trace. Fix (same commit): END is now
computed at runtime as yesterday; both pullers stop at the UTC day roll so a session can
never spend the next day's budget; cron budgets partitioned (prints 12k at 00:15, history
up to 30k at 22:30) so both stages progress every day; one-shot catch-up chain Saturday
03:30 UTC re-pulls Aug 22-Sep 4 recent-first then reruns probe_tuner + glide build +
tuner_apply on the fresh corpus. Lesson: a dataset with a rolling purpose must have a
rolling window - and monitors must alert on DATA FRESHNESS (max(day) vs today), not on
process exit codes; every process here exited 0 every night while the data quietly died.

2026-09-04 (evening) - FRIDAY CHAIN TRIPPED ON AN UNCOMMITTED SCRIPT: the 21:45 UTC tuning
chain died at step one because hourly_library.py was added to the cron line while the script
itself existed only in the local working tree - never committed, so the VPS checkout had
nothing to run, and the && chain silently skipped the glide build and tuner_apply with it.
Caught within minutes because the relaunched chain was being watched live; fixed same night
(script committed after a green gate, chain relaunched manually). Lesson: a cron edit and
every script it references land in the SAME push - a cron line is a promise the repo has to
keep. The freshness sentinel (shipped tonight) now alarms on the missing-artifact symptom
(tuner_apply.log absent after a Friday), and the registry rule in its docstring makes the
pairing explicit: any new cron or data store ships with its sentinel row in the same commit.

2026-09-04 (late) - NIGHTLY BOUNDARY SILENT 3 NIGHTS (Sep 2-4): trajectory_nightly.log froze
at Sep 1 22:14; the 22:00 SEQ_APPLY court simply did not run. Root cause found only after two
same-night near-repeats: research crons (probe_tuner, glide_sim build) APPEND to tracked
corpus jsonl files without committing, and interactive sessions scp files in - either way the
worktree carries modified tracked files, and every pull-first cron (git pull --rebase refuses
a dirty tree) dies silently at its first command with no log line, because the log redirect
sits on the python step the chain never reaches. The archive freeze hid inside the same
silence. Fix, three layers: (1) c114215b untracks + gitignores probe_tuner_rows.jsonl and
glide_fine_rows.jsonl (VPS-local rebuildable research data - a growing file must never be
tracked on a box where crons pull); (2) --autostash added to every cron git pull, because the
BOUNDARY COURT ITSELF legitimately dirties tracked court files (sentinels.jsonl,
trajectory.log) at 22:00 that evening_persist only commits at 22:45 - the design depends on
pulls tolerating that 45-minute window, and plain --rebase never did; (3) pull-retry on the
cron lines plus session discipline: staged work is committed or reverted before any :00 cron
boundary. Proven same night: the 22:00 boundary ran clean for the first time since Sep 1 and
the 22:10 student pulled through the dirty court window on autostash. Lesson: on a pull-first
box one dirty tracked file silently kills EVERY downstream cron; the freshness sentinel's
schedule checks now catch the symptom class within one night instead of three.

2026-09-07 - THE WATCHDOG'S MESSENGER FAILED SILENTLY: the freshness sentinel ran at 08:00,
found 2 stale items, and the owner received nothing - the Telegram send was one attempt with
a bare except that swallowed any failure, and a missing-env path skipped the send with zero
trace. The owner detected it (again) before the machinery did, on a day when Labor Day
silence made a missing report invisible. The sentinel existed precisely because processes
were failing quietly - and its own mouth could fail quietly. Fix (pushed 2026-09-07): three
send attempts with backoff, every failure path printed loudly to the sentinel log (failed
attempts, gave-up, missing env), verified by a live delivery. Also fixed: the trajectory
scoreboard sentinel row false-alarmed because its log file does not exist until the first
Friday run - touched into existence. Lesson: every alerting path needs retries and a written
trace of its own failure; a monitor that cannot prove it spoke is presumed silent - and the
Sunday heartbeat exists for exactly this, so a missing Sunday message must be treated as an
incident, never as quiet.


2026-09-07 - FROZEN TUNER CORPUS (active data loss, caught by the coverage audit before any
symptom): scripts/probe_tuner.py fetched its daily-close window with a HARDCODED end of
2026-08-31, so every archive day after Aug 31 was silently discarded from the tuning corpus -
regime features came back None and build_rows skipped the day. The Friday chain would have
"refreshed" forever on a corpus frozen at Aug 31 while both corpus sentinel rows (mtime-based)
stayed green, and tuner_apply's HOLD verdicts on frozen evidence are indistinguishable from
the designed holding-is-normal behavior. The same grammar sat in fade_meta.py (end=2026-12-31,
a New Year's Day time bomb for the nightly student). This is the 2026-09-04 frozen-archive
breakdown reproduced one layer downstream, five days later, by the same hand. Fix (same
commit): both end dates computed at runtime; two CONTENT-day sentinel rows on the corpus files
(newest row day <= 11 trading days); tuner_apply now REFUSES to judge and pages when the
corpus is >10 trading days stale instead of printing HOLD. REGRESSION CHECKS: sentinel rows
"tuner corpus content day" + "glide corpus content day"; tuner_apply's frozen-corpus refusal.
LESSON: the lesson of 09-04 was written but not generalized - after any breakdown, grep for
the CLASS (here: hardcoded date literals in data windows), not just the instance; and a
verdict that cannot distinguish "no change needed" from "cannot see" must fail loud.

2026-09-07 (second entry) - FROZEN-WINDOW CLASS SWEPT: the owner's challenge ("you've found
old corpus things twice now") prompted a class-wide sweep of every recurring script for
hardcoded end-date literals. THIRD live instance found: historical_corpus.py, the monthly
first-Saturday corpus refresh, had END = 2026-08-01 and a bars URL ending 2026-08-12 - every
monthly "refresh" since August has added nothing while exiting green. Fixed to rolling
(through the last complete month). The one legitimate frozen window (fivek_backtests.py, a
published one-off study whose evidence must stay reproducible) is now explicitly marked
FROZEN-BY-DESIGN. REGRESSION CHECK: MOT 6.10d frozen-window lint - scans all 22 recurring
scripts for end-date literal patterns and fails the gate on any unmarked hit, so the class
cannot re-enter the codebase through any future edit. LESSON: when the same disease appears
twice, the third instance is already there - sweep the class the same day, and make the
gate reject the pattern itself, not just today's instances.

2026-09-07 (third entry) - CHECKPOINT-FROZEN BARS: the frozen-window class in checkpoint
clothing. hourly_library marked each contract DONE at first fetch, so a contract fetched
mid-window (e.g. Aug 27 build) never received its later bars - September trigger days were
silently unreplayable ("0 fetched this run" in a green log) even after every date literal was
unfrozen, because the staleness lived in a checkpoint table, not a constant. Found chasing
why the corpus backfill ingested nothing past Aug 31. Fix (same commit): a top-up pass every
run extends any occ whose stored bars end before its 70-day window does. REGRESSION CHECK:
the sentinel's "tuner corpus content day" full-file row now trips when ingestion stalls
(>11 sessions), whatever the mechanism; the library prints its top-up count every run.
LESSON: a rolling window is not enough - anything CHECKPOINTED against a growing dataset
needs a completion condition, not a fetched-once flag; and "0 fetched" on a day when data
grew is itself an anomaly worth a printed count.

2026-09-09 - CONTROL STARVED THE ROSTER: with the attempt budget raised to 10, EXEC_BASELINE
(which has no candidate filter and always holds the head rotation slot) burned every attempt
re-testing tickers that were spread-dead or unaffordable, so the rotation never reached the
tail probes - including the two WINNER_PROFILE controls shipped hours earlier. Root cause: the
2026-09-02 free-skip fix propagated only the FADE loop's discoveries into engine_skips; a
probe's OWN quality discovery (spread_cap / metadata_unavailable / premium_too_rich) was
never recorded, so probe 2..N paid full sensor sweeps to relearn what probe 1 already knew.
Visible in the 19:07Z cycle: 8 of 10 attempts spent by the control on spread caps, "0 entries
this cycle". A second defect in the same line: the starved-cycle message still printed "of 6"
after the budget rose to 10 - a monitoring line that lies about its own limit. Fix (same
commit): quality skips propagate into engine_skips for the whole cycle (one probe pays, the
rest skip free); message prints the true cap. REGRESSION CHECK: the starved-cycle line prints
the attempt count and cap every zero-entry cycle - a control monopolising the budget is now
legible in one glance; MOT dim-6 probe budget checks cover the loop. LESSON: a fix that
teaches the system "don't relearn dead facts" must cover EVERY learner, not just the one that
found the bug - and any monitoring string carrying a constant must read that constant, never
repeat it.

2026-09-09 (second entry) - THREE EVIDENCE-INTEGRITY DEFECTS FOUND BY THE REGIME-MASTERS
PANEL (none caused by the design under review; all live and costing integrity daily).
(1) INVISIBLE GLIDES: tuner_apply wrote Friday exit changes into probe.tuning.* but never an
auto_* marker, and the probe court had NO evidence clock at all - so every strategy kept
accruing verdicts across a config change that happened under it, the exact laundering the
anti-cube law was written to stop (it protected only the MENU books). Fix: the tuner writes
an auto_<date> marker carrying keys+prev, and the probe court excludes days on or before a
strategy's tuning "applied" date, printing what it excluded. NOTE a near-miss caught during
the fix: the marker's first draft carried "demoted": "n/a", and the clock does
max(date, demoted) - any non-date string sorts above every real date and would have silently
excluded ALL evidence for the touched keys. Markers now carry "tuner": true instead, and the
demotion loop skips them by that flag.
(2) THE DEMOTION RATCHET HAD A SINGLE POINT OF FAILURE: the revert did sect, key =
path.split(".") (a two-level unpack) inside ONE blanket try/except wrapping the entire
demotion loop AND its commit - so a single malformed or nested path raised, discarded every
revert computed in that pass, and permanently disabled demotion for every promoted key, with
the sole symptom one line reading "demotion check skipped: ValueError". Fix: per-record
try/except with a LOUD skip line, and arbitrary-depth path support.
(3) SPEC WRITES COULD VANISH AND STILL REPORT SUCCESS: every spec writer pushes with
git pull --rebase -X ours, where under rebase "ours" is the UPSTREAM side - a conflicting
hunk silently discards the local edit, -q hides it, and the script then telegrams that the
glide/demotion was applied. Fix: verify-after-push in both writers - re-read the spec from
disk and assert the exact values survived BEFORE claiming success; on loss the telegram says
WRITE LOST and names the keys. REGRESSION CHECKS: the tuning-clock exclusion line prints on
every affected court run; the demotion skip line names the failing record instead of the
pass; the WRITE LOST telegram replaces a false success. LESSON: a law is only as wide as the
paths it is wired into - the anti-cube clock existed for a year and never covered the court
that judges promotions; and any "success" message not derived from re-reading the artifact is
a guess wearing a fact's clothes.

2026-09-09 (third entry) - EVERY BACKTEST NUMBER WAS OPTIMISTIC BY ~4-5 POINTS/DAY: the
corpus entry basis was not executable. probe_tuner (and glide_sim, grand_retest, the mild_conf
studies) entered each replayed trade at the CLOSE OF THE FIRST HOURLY BAR AFTER the print -
an Alpaca OPRA TRADE aggregate roughly 60-120 minutes after the signal, i.e. a last-sale
price, not an ask. Three compounding faults: (1) that price violates the house rule that
entry_ref is the ASK at signal - we were buying at a number no buyer could transact; (2) the
SAME entry bar was fed to the peak/trail loop, so the trail could arm and the peak could be
set on a high that occurred BEFORE entry - one-directional look-ahead; (3) exits returned the
exact theoretical level (`return fl`, `return stop`), never a bid, never gapping through.
Found by the instrument-mismatch panel (2026-09-09), which was convened for a different and
lesser defect. The correct input had been banked all along and thrown away: uw_flow_prints
stores nbbo_bid/nbbo_ask AT each print - its own docstring says the point was "entry at the
TRUE trigger time and TRUE ask" - and every consumer took only min(executed_at) and discarded
the quote. MEASURED COST (reports/research/basis_diff_2026-09-09.md): POOL +6.03 -> +1.67,
FOLLOW_CALLS +9.06 -> +4.49, BULL_DIP +9.36 -> +4.70, DIP_CONF_MILD +11.06 -> +5.59,
DIP_CONVEXITY +18.44 -> +14.49, WINNER_PROFILE_X +6.33 -> +1.95. Every cell degraded by more
than the +3/day promotion floor, so under the panel's pre-registered rule EVERY v1-derived
figure is SUPERSEDED. The edges survive relative to the pool (excess over pool is largely
unchanged, ~+2.8 to +12.8) - the bias was systematic, not strategy-specific - but the
ABSOLUTE numbers that promotion floors are denominated in were inflated roughly two-fold.
Fix (same commit): entry = the banked ask at the print, contracts with no print ask DROPPED
rather than faked from the daily quote, the entry bar excluded from the peak loop, and every
exit haircut to the bid side with gap-through filling at the bar low. Corpus rebuilt to a
VERSIONED file (probe_tuner_rows_v2.jsonl, 79,045 rows) so the two bases can never be silently
mixed, and every row now stamps basis/entry/spread_frac. REGRESSION CHECK: rows carry a
"basis" field, the sentinel watches the v2 file, and the basis-diff report is committed so
any future reader sees what the correction cost. LESSON: a backtest is a claim about a price
you could have paid - if the entry is not a quote you could have lifted at the moment you
decided, the whole edge is a measurement artifact; and when the honest input is already in
the database, the defect is not missing data but a consumer that never asked for it.

2026-09-10 - FOLLOW-UP to the 2026-09-09 corpus-basis entry: the fix had covered the GENERATOR
only. Nine consumers still read the superseded v1 files - including the whole Friday chain
(glide_sim build at 21:45 UTC and tuner_apply behind it), which would have applied exit glides
on the optimistic basis the very next day. glide_sim ported to the executable basis (reads v2
rows' banked ask + spread, entry bar out of the peak loop, bid-side fills, versioned output
glide_fine_rows_v2.jsonl, single-writer lock); tuner_apply repointed and its INCUMBENT_POOL
moved to the $4-9.90 band the live gate actually buys (BULL_DIP/DIP_CONVEXITY had been tuning on
a band entirely below the live floor); every research consumer and the sentinel repointed.
REGRESSION CHECK: MOT 6.10f corpus-basis lint fails if any script names a v1 corpus file.
LESSON: a data-basis fix is not done at the writer - sweep every reader in the same session,
and lint the old name so it cannot creep back.

2026-09-10 - EXIT ENGINE DOWN 30 MINUTES (KeyError mfe_pct, three consecutive cycles 18:50-19:10
UTC, owner paged by GHA + Telegram). WHAT BROKE: manage_open_positions crashed before managing
any position; the run's data persist and cycle-complete marker were skipped. Broker-side GTC
backstops were the only protection during the gap. ROOT CAUSE: two writers create leg_path
entries of different shapes. NKE's limit order (18:17) sat unfilled 32 minutes; for three
cycles the record was OPEN with no broker position, so the untracked-leg counter did
setdefault(leg, {}) and stored only missing_cycles. When the fill landed at 18:49, the
excursion update's setdefault found that bare dict and indexed path["mfe_pct"] directly.
FIX: excursion keys read with .get(key, ret_pct) (a missing excursion means "start tracking
now"), and missing_cycles is cleared when the position is tracked again (a stale count from a
slow fill could otherwise add to a later transient gap and book a false CLOSE_UNTRACKED). The
crash fix shipped alone first (live outage, market open); this entry and the counter reset
followed in the next commit. REGRESSION CHECK: MOT 6.10g lints the update line for direct
indexing and requires the counter reset. LESSON: when two code paths write the same record
slot, one bare setdefault is a time bomb - and any exception inside position management must
skip the record, not the cycle (the loop still lacks a per-record guard; queued).

2026-09-10 (second entry) - EVIDENCE CHAIN EFFECTIVELY FROZEN AT AUG 31 WHILE EVERY CHECK
PASSED (owner: "why can't the system stay updated with the newest and right data"). WHAT BROKE:
the tuner corpus held 14 September rows against ~1,650 in a normal month; tomorrow's Friday
tuning pass would have judged on an August corpus. ROOT CAUSES (two): (1) the prints puller
runs at 00:15 UTC and Unusual Whales publishes a day's prints with a lag - it received EMPTY
lists for Sep 1 (219 of 253 contract-days), Sep 2 (all 201), Sep 3 (all 352) and Sep 8 (all
390), and "insert or replace into prints_pulled ... 0" marked every one of them done forever;
(2) the hourly bar library topped up only in the Friday chain, so the corpus could never be
fresher than a week. WHY NO ALARM: every freshness check on these stores tested the NEWEST DAY
(max(day), newest content day, newest file) - and the newest day was fine. A hole behind the
newest day, or a day at 1% of normal volume, is invisible to a newest-day check; the 43-row
sentinel was green all week. FIX: both pullers defer an empty result inside the last 7 days
(retried next session, never marked); a nightly corpus chain (01:45 UTC Tue-Sat: bar top-up,
tuner rows build-only, fine-grid build) replaces Friday-only; the sentinel gains session-hole
and day-density rows for the archive, prints, bars and both corpora (v1.3), and tuner_apply
refuses to judge when recent days are thin or missing. One-off repair: recent zero marks
deleted and re-pulled. Also corrected in the same session: an initial misread claimed Sep 5
was a missing day - it was a Saturday (date discipline). REGRESSION CHECK: MOT 6.10h asserts
the defer guard in both pullers, the density rows in the sentinel, and the density refusal in
the tuner; the density rows themselves page the next morning if the class returns. LESSON:
"fresh" must mean complete AND dense, not merely recent - a freshness registry that only asks
"what is the newest day" is a registry of last-seen dates, not of data health.

2026-09-10 (third entry) - ROSTER STARVATION, STRUCTURAL FIX. WHAT BROKE: 23 of 36 cycles spent
all 10 attempts with zero entries; the control (first in rotation, no filter) burned 108 attempts
in a day - 78 on spread-cap rejections each discovered only AFTER a full sensor sweep - and the
tail strategies received 1-4 attempts all day. Half of all orders the engine did place never
filled. ROOT CAUSE: the attempt budget bounds SWEEPS (cycle time), but a rejection at the 2%
live spread cap was only learnable after the sweep, and nothing stopped one probe from consuming
the whole budget. FIX: (1) LIVE PRE-QUOTE - before any sweep, one cheap indicative quote of the
whale's own alert contract (cached per ticker per cycle); no usable quote or spread over 4% ->
skip without spending an attempt, and mark the ticker dead for the rest of the roster this cycle
(the 2% gate on the actual contract is unchanged); (2) PER-PROBE CEILING of 4 attempts per cycle
so at least three probes are reached every cycle. REGRESSION CHECK: MOT 6.10i asserts both; the
starved-cycle line now prints pre-skips beside attempts so the split is legible daily. LESSON:
a budget that protects cycle time must be spent on the expensive step only - every cheap
rejection moved in front of the expensive step is a free attempt returned to the roster.

2026-09-11 - PUSHES BLOCKED BY A 131 MB CORPUS IN A NIGHTLY COMMIT. WHAT BROKE: the 22:10 UTC
student job's commit ("fade meta weekly") swept reports/research/glide_fine_rows_v2.jsonl
(131 MB) into its commit; GitHub refuses files over 100 MB, so that commit and everything on
top of it could not be pushed - the first symptom was a research commit failing to land at
23:16 UTC. ROOT CAUSE: the 2026-09-09 corpus rebuild introduced NEW filenames (v2) and only the
old v1 names were in .gitignore; a broad "git add" in a nightly job did the rest. FIX: local
unpushed history rewritten with a soft reset to origin (no force push, origin untouched), the
file unstaged, both v2 corpora and the cohort cache gitignored, one clean commit pushed.
REGRESSION CHECK: MOT 6.10j asserts the growing corpora are gitignored. LESSON: renaming a
growing artifact is a change to .gitignore first - and a nightly job that adds a whole
directory will find every file you forgot.

2026-09-11 - CORPUS ENTRY LEAK #2: FIRST-PRINT ENTRY ON A DAY-QUALIFIED ROW (found by the
student formula search). WHAT BROKE: the v2 corpus entered every contract-day at the ask of
the day's FIRST print, but a row qualifies on the day's TOTAL premium (>= 50k) - an alert would
only exist once cumulative premium crossed that floor. For cheap short-dated calls the crossing
came a median 86 minutes after the first print at an ask 24% higher on average (29% of cases
>25% higher); for the engine's $4+ band the ratio was exactly 1.0 with zero lag. A picker
trained on v2 found and harvested exactly that: +131%/trade, 94% wins, "+276%/trade on the
holdout" - and its picked-trade profile ($0.37 entry, 4 DTE, day volume 25x the cohort) was
the tell. FIX: corpus v3 - entry at the QUALIFYING print (cumulative premium first >= 50k) plus
a 10-minute cycle delay before any bar counts; trail exits fill at the bar CLOSE once the floor
is crossed (an intrabar spike on a cheap contract is not a fill); rows without a qualifying
print are excluded (69,666 rows vs 79,045). Every consumer repointed; MOT 6.10f now forbids v1
AND v2 names; v3 corpora gitignored. Same search on v3: the pre-registered winner is
+33%/trade on the search window and +12%/trade, 62% wins, weekly t +1.45 on the untouched
holdout (random 95th pct +0.55). REGRESSION CHECK: MOT 6.10f (basis lint) + the rows' basis
tag "ask_at_qualifying_print" required by glide_sim; the holdout discipline itself is the
standing check on any future "too good" number. LESSON: a picker is the sharpest leak detector
there is - when a model's best trades share a profile no trader would recognise, the profile is
the bug; and a row that qualifies on a whole day's total must not be entered before that total
existed.

2026-09-11 (second entry) - CORPUS LEAK #3: REGIME COLUMNS FROM THE ENTRY-DAY CLOSE (found by the
student-wiring panel, 02:30). WHAT BROKE: the corpus's three regime readings - SPY vs its 50d
(reg), SPY vs its 20d (sp), ticker vs its 20d (smd) - were computed from a window that INCLUDED
the entry day's close, i.e. post-entry information, and keyed on the entry day. Entry is the
ask at the qualifying print; the same-day close move sits inside every label the model was
trained against and inside every regime cell any strategy was measured on. In the student's
first models these were the #1, #2 and #5 most-split features (27% of splits); the archive
showed the tell-tale sign of a leak, a side-flipping correlation (calls positive, puts negative
in the same tercile). Live, the engine fed intraday running values instead - a different
quantity, so the leaked part could never transfer. FIX: the corpus computes all three at the
PRIOR close (smad shifted by one day; rows stamp regime_basis "d1_close"; glide_sim refuses rows
without it); the live side computes the same prior-close readings (fade_book.spy_prev_readings,
macro distance_to_sma20_prev_pct) and the student uses ONLY those; corpora v3 rebuilt
(70,976 rows), fine grid, as-of features and the formula search re-run on the honest columns.
Also fixed in the same session from the same panel: five student features that could not
exist live (dropped; 15 remain), thresholds now calibrated on the walk-forward stream never
in-sample, the export refuses while a case is open and asserts evaluator parity, the roster
runs ONE student seat ranking best-first (six seats would have reversed the 2026-09-10
throughput fix), a NameError on the trade path (an unbound record-book name) caught before it
ran, and the regime stand-down now treats an UNKNOWN regime as a stand-down. REGRESSION
CHECK: MOT 6.11 (15 features, live/archive vector parity, prior-close helper, one-seat wiring,
no stale hooks, corpus regime_basis, model files with walk-forward AUC and parity); regime
drill scenario 6 (no model, budget spent, unknown readings). LESSON: every fixed-strategy
archive number before 2026-09-11 also carried this leak; the corpus is now on its fourth
honest correction in three days, each found by a harder question than the last - the panels
are the machinery that finds them, and the leak that matters most is always the one hiding
inside the "obvious" columns.

2026-09-11 (third entry) - ENGINE BLIND FOR ~55 MINUTES MID-SESSION: ALPACA CLOCK 500 + FAIL-CLOSED
GATE (16:10-17:04 UTC; owner paged by the VPS watchdog "no inbox commit for 50m during market
hours"). WHAT BROKE: every cycle printed "market closed - no cycle: 0 orders, 0 exits, 0 harvest"
while the market was open; no position was managed, no candidate was scored, no inbox row was
committed. The runs reported SUCCESS, so the workflow's failure alarm and the crash detector
stayed quiet; only the inbox-staleness watchdog saw it (it did, correctly, every 15 minutes).
ROOT CAUSE: Alpaca's paper /v2/clock endpoint returned "Internal Server Error" intermittently
(the data quote endpoint 504'd in the same window); _market_is_open() made ONE call and treated
any exception as "closed" - a deliberate fail-closed rule written so a clock blip could never fire
an order into a closed market, which in this failure mode disabled the exit engine instead.
Broker-side GTC backstops were the only protection. FIX: the gate retries the clock three times
with backoff, then decides from the XNYS exchange calendar (holiday and early-close aware) with
a loud line; no credentials still means closed; calendar unavailable still means closed. Shipped
alone first (live outage); this entry and the regression check followed. REGRESSION CHECK: MOT
6.12 forces the clock call to raise and asserts the gate returns the calendar's answer instead of
False. LESSON: "fail closed" must be read per consequence - closed-for-ENTRIES is safety,
closed-for-EXITS is exposure; a gate that guards both with one bit needs a second opinion the
moment its only source fails. And the watchdog that paged is the one that watches the DATA, not
the exit codes: the 2026-09-04 lesson, vindicated.

2026-09-12 - A NEVER-FILLED ORDER WAS BOOKED AS A -100% LOSS. WHAT BROKE: ORCL (WINNER_PROFILE_X,
entered 2026-09-10 19:59 UTC) never filled - the limit was cancelled unfilled and the broker
never held the position - yet after five position-less cycles the untracked-leg counter booked
CLOSE_UNTRACKED at "worst-known" = -100%, inventing a $111 loss on a trade that never existed
and a losing day for a strategy's record. ROOT CAUSE: the counter (audit finding #10) was
written for positions that VANISHED (expired worthless, manually closed) and used -100% as the
conservative default; it could not tell "vanished" from "never arrived". The tell was in the
record all along: a leg that never had an excursion tracked (no mfe_pct) was never a position.
FIX: a leg with no tracked excursion after five position-less cycles is VOIDED - return None,
status VOID, action VOID_NEVER_FILLED, excluded from every court and ledger - and the ORCL record
corrected the same way. A vanished position (excursion once tracked) still books worst-known.
ALSO FOUND the same morning: NBIS260918C00240000 bought 2026-09-11 19:51 UTC exists at the
broker with NO record in the book (the panel's item 8 window, submitted-but-unlogged); the
orphan reconcile adopts it on Monday's first cycle with a backstop; the PENDING-intent record
before routing is promoted to the next build. REGRESSION CHECK: MOT 6.13 asserts the VOID branch
and its never-tracked condition. LESSON: "conservative default" is only conservative in one
direction - a fake loss corrupts the evidence exactly as a fake win would.

2026-09-12 (second entry) - A FILLED TRADE'S RECORD WAS LOST TO A PUSH RACE. WHAT BROKE: the
19:40 UTC cycle of 2026-09-11 entered NBIS260918C00240000 for FOLLOW_CALLS at 19:51:13, wrote
the record and pushed it (commit f654da2e carries it). The next cycle checked out main 34
seconds after that push landed and still received the previous commit (982fa024): it ran its
whole cycle on a book without NBIS (its orphan roll-call saw the fill and held it in the
45-minute grace window), then its own push was rejected, the rebase conflicted on the log, and
the record-level resolver ABORTED because data/last_cycle_ok - a two-line heartbeat committed by
every run since 2026-08-17 - was not in its table. The workflow's fallback is a FILE-LEVEL
`git pull --rebase -X theirs`, which resolved the conflicted hunk with the stale run's copy:
commit 526f5182 removed the NBIS record. A filled paper position sat at the broker with no
record, no backstop and no strategy attribution. ROOT CAUSE: three links, each survivable on
its own - (1) a stale checkout (GitHub-side propagation, not controllable); (2) a resolver that
treated one unknown conflicted file as a reason to give up on ALL of them (latent since
2026-08-17, fired on every push race since); (3) a fallback that resolves at file level and so
drops records. The panel's "submitted-but-unlogged" window (instrument-mismatch panel item 9,
2026-09-09) is a fourth, separate route to the same orphan and was still open. FIX (one commit):
PENDING-INTENT RECORD - enter_proactive_set writes the record as PENDING with a client_order_id
per leg BEFORE routing, flips it to OPEN after the fill response, and reconcile_pending() at
cycle start settles any PENDING left behind against the broker by order name (exists -> OPEN
with the order attached; ended unfilled or absent after 15 minutes -> VOID, return None); every
exposure guard (one-per-underlying, one-record-per-contract, roster, fade concurrency) counts
PENDING as open. RESOLVER - merge_logs merges data/last_cycle_ok (later heartbeat wins) and, for
any other unknown conflicted file, takes the run's own version and continues; the record-level
merge never aborts. UNION GUARD - inside the push-retry loop the workflow runs
merge_logs --guard origin/main after every rebase path: any trade record present on origin and
missing locally is restored before the push. The NBIS record itself is restored from f654da2e
in the data commit that follows this one. REGRESSION CHECK: MOT 6.14 - the entry path writes
PENDING before routing; the payload carries client_order_id; the pending roll-call precedes the
orphan roll-call; the guards see PENDING; a functional roll-call (broker has the order -> OPEN;
404 after grace -> VOID with return None); resolver and guard wiring; the merge_logs selftest.
LESSON: a record store merged by git needs a merge that understands records on EVERY path,
including the fallback - a fallback allowed to lose data will eventually lose the one record
that mattered. And the intent belongs on disk before the order is on the wire.

2026-09-12 (third entry) - A DRILL WROTE FIXTURE ROWS INTO THE LIVE SCORE LOG. WHAT BROKE: the
regime drill's student scenario (scripts/regime_drill.py, scenario 6) scores a fixture
candidate "XYZ" through the real _student_rank, whose passive logger appends to
reports/shadow_lab/student_scores.jsonl - the calibration audit the engine commits every
cycle. Seven XYZ rows landed in the VPS working copy at 06:53 UTC; the fade-meta cron's
`git add reports` would have pushed them into the committed audit on Monday. ROOT CAUSE: the
drill fakes the book (append/save/load), the broker and the router, but not the score-log
path, and the engine's logger is deliberately silent (never raises) - so nothing said a word.
FIX: the drill points STUDENT_SCORES_LOG at a temp file and neutralises _rewrite_last before
any scenario runs (the entry path now rewrites the book after routing); the MOT does the same
for itself; the seven rows were discarded from the VPS copy (never committed). REGRESSION
CHECK: MOT 6.15 - source order in the drill, and the MOT asserts the real score log is
byte-for-byte unchanged across its own run. LESSON: a passive logger that never raises is
exactly the writer a harness forgets to fake - every fail-open sink needs a redirect in every
harness that exercises the code around it.

2026-09-12 (fourth entry) - THE STUDENT SEAT SCORED THE WRONG SLICE. WHAT BROKE: the STUDENT roster
seat (landed 2026-09-11) ranked the dip strategies' side-pool - calls only, ask $4.00-9.00, premium
50-400k, DTE >= 7 - because it was the only contract-level pool the engine had. Picker A's evidence
lives elsewhere: its cap-fitting edge is in sub-$1 contracts on BOTH sides (spread study 2026-09-12:
search +24.7%/trade t 1.19, holdout +52.1%/trade t 1.46, ~1.5 trades a week), and the $4-9.90 band
is exactly where it loses (-10.9%/trade, the Thursday test). Had A gone live on Thursday's wiring it
would have traded the losing band; the passive score log for one session measured that band and
nothing else. No trade was affected (zero live pickers). ROOT CAUSE: "affordable" meant three
different bands in three places - the scan's $0.30-4.00, the pricey pool's $4-9, the AFFORD cohort's
$4-9.90 - and none of them was the evidence's universe; the seat inherited the universe of the pool
it read. FIX (same commit): a contract-level STUDENT pool under the archive filters the pickers were
trained on (both sides, premium 50k-1M, ask-side aggressor, alert spread <= 2%, ask >= 0.30 with no
ceiling, DTE >= 1, top 30 by premium); the seat executes only picks whose LIVE ask is under
exec_max_ask ($10 = the $1,000 cap) at engine sizing, and an unaffordable pick spends one weekly
budget unit once per contract-day, as the study did; the trigger leg builds either side and sizes
student picks to the budget (the dip strategies' one-contract call is byte-identical); the export
judges the auto-pull rule on the EXECUTED slice; A's threshold cohort is ALL. REGRESSION CHECK: MOT
6.17 (seat pool source, pool filters, select helper, budget dedup, sized LONG_PUT leg, dip leg
unchanged, export executed slice, spec keys) and regime drill scenario 7 (pricey call unaffordable,
cheap put enters as a 25-lot LONG_PUT through the dry-run entry path). LESSON: before a picker is
wired to a pool, write down the universe its evidence was measured on and diff it against the pool's
filters - a seat cannot find an edge in a band the evidence never contained.

2026-09-13 - PUSHED WITHOUT THE GATE ON A STALE GREEN SENTINEL (process breakdown, self-inflicted,
the 2026-09-02 class). WHAT BROKE: the returns-map ship chain ran the new performance-map lint,
which FAILED on an illustrative token in docs/performance_map/README.md; the `&&` chain stopped
before scripts/verify_engine.sh, so the drill and the MOT never ran - and the commit step then
tested `[ -f /tmp/gate_green ]`, found the sentinel left by the PREVIOUS green run, and pushed
ce90f120 to main. The MOT's new 6.19 check would have failed on that tree. ROOT CAUSE: a
green-sentinel that only asserts "a gate passed once" instead of "the gate passed on THIS tree";
every chain since 2026-09-01 has carried the same flaw and the 2026-09-02 entry fixed the habit,
not the mechanism. FIX (same night): scripts/gate_fresh.sh - verify_engine.sh stamps
/tmp/verify_green with the HEAD sha plus a hash of the working tree's status and diff, only on ALL
GREEN, and ship chains gate the commit on `bash scripts/gate_fresh.sh` (exit 0 only when the
sentinel describes the tree as it is now; any edit, new file or commit makes it stale). The README
example token was rewritten so the lint cannot match it, and the offending tree was re-verified
in full before the corrective commit. REGRESSION CHECK: MOT 6.20 asserts verify_engine.sh stamps
through gate_fresh.sh and that gate_fresh.sh reports STALE after a change to the tree; the map's
gate-and-ship.md carries the trap. LESSON: "the gate is green" must be a statement about a tree,
not about a file; a sentinel without an identity is a lie waiting for the next `&&` to break.

2026-09-14 - THE ONE-LOT SCALE-OUT WALL: A +369% WINNER SAT BEHIND A -50% STOP (found in the
pre-open diagnosis). WHAT BROKE: HOOD260918C00100000 (adopted 2026-08-20, one contract) peaked at
+369% and gave back to +145% with its trail never armed and its broker backstop still at the
initial -50% level; AAPL260918C00325000 (one contract) peaked at +515% and sat at +350% the same
way. ROOT CAUSE: the V10 exit grammar's first tier is SCALE_OUT_50, "sell half"; on a ONE-contract
position the broker cannot sell half, the close is rejected (HOOD: close_fails 2), the stage stays
"initial" so the scale-out is retried instead of the trail arming, and the backstop ratchet, which
mirrors the stage, never moves off the -50% level. Every one-contract position under that grammar
(every trigger-contract probe buy, the control's pricey fills) has the same wall. FIX (same night):
in the exit pass, a SCALE_OUT_50 decision on a one-contract leg arms the trail instead (stage ->
trailing, close_fails reset, one log line) and the trail rule is re-evaluated in the same cycle, so
a runner past its give-back closes at once and the backstop ratchets to the peak-based level.
REGRESSION CHECK: MOT 6.21 asserts the one-lot branch exists in the exit pass ahead of the scale-out
sale and re-evaluates the rule at stage trailing; a functional exit-pass fixture for a one-contract
runner is owed. LESSON: a rule written for a $4,000 book with multi-lot positions has a tier that a
$1,000 one-lot book can never execute; every grammar tier needs a "what if the quantity is one" case.

2026-09-14 (second entry) - RETIRING A PROBE SWITCHED OFF ITS SETTLE SWEEP: FIVE EXPIRED XSP
RECORDS OPEN FOR 26 DAYS. WHAT BROKE: three VRP_DAILY and two PUTW cash-settled short puts that
expired 2026-08-19/20/21 stayed status OPEN; the freshness sentinel printed "expired legs still open
... settle/exit machinery broken" and "ghost open records" every morning from 2026-09-08 and nobody
acted. ROOT CAUSE (two): (1) vrp_probe.cycle and putw_leg.weekly_cycle return immediately when the
probe is not enabled in the spec, and both probes were retired by disabling them, so the settle
loop that runs before the entry gate never ran again; (2) both settle paths, and the credit
spread's, price expiry from a yfinance ^XSP series with period="10d", so any record not settled
within ten days of expiry becomes unsettleable forever. Also found: the VPS venv lacked yfinance
(the 2026-09-01 dependency-drift class). FIX (same night): the enabled flag now gates ENTRIES only,
settles run for any open record regardless; the ^XSP window is 120 days in all three modules;
yfinance installed in the venv. The five ghosts settle on Monday's first cycle. REGRESSION CHECK:
MOT 6.21 asserts neither settle sweep is gated on enabled and no module uses the ten-day window;
the sentinel's "expired legs still open" row is the live alarm. LESSON: retire a strategy's ENTRIES,
never its bookkeeping; a probe's records outlive the probe.

2026-09-14 (third entry) - THE EIGHT-MINUTE WALL: A QUARTER OF ENGINE CYCLES CANCELLED SINCE 9 SEP.
WHAT BROKE: the engine job carries timeout-minutes 8; cycles were taking 6-9 minutes and the slow
ones were cancelled part-way: 4 of 51 on Mon 8 Sep, 17 of 51 on Tue 9, 15 of 52 on Wed 10, 11 of 52
on Thu 11, 7 of 24 by 17:45 BST on Mon 14 (four in a row 15:10-15:40 BST, so no completed exit pass
for about 40 minutes of the first hour). A cancelled cycle skips whatever it had not reached, usually
the later exit checks, the backstop pass and the student scoring; records survived because the
persist step runs on `always()`, and no lost money was found. Nobody was told: the run is cancelled,
not failed, the cycle sentinel is only stamped on success but a successful run always followed within
the heartbeat window, so engine_watch stayed "ok" throughout; the Saturday 12 Sep pre-open diagnosis
checked that the last runs were green and missed the rate. ROOT CAUSE: the earnings sensor
(`sandbox_v11_sensors.py:post_earnings_drift`) asked Yahoo for earnings dates for every candidate
ticker on every cycle with no cache (the profile sensor beside it has had one since it was built),
so the same ticker was fetched once per contract; for funds (SOXX, SOXL, IBIT, IWM, EWZ, LQD, URA,
TQQQ, SMH, ARKK...) Yahoo has nothing and yfinance retried for 10-84 seconds per call, 2-4 minutes of
every cycle. FIX (same day, shipped after the close): funds never reach Yahoo (a symbol list plus the
cached profile: source yfinance with no sector, industry or market cap), and one lookup per ticker
per cycle is cached; the sensor's answer is unchanged (null, fail-open, the 3-day earnings blackout
never blocked on a fund before and does not now). NOT DONE HERE, owed: an engine_watch row that counts
cancelled runs per hour so a cycle that dies at the cap pages instead of hiding behind the heartbeat.
REGRESSION CHECK: MOT 6.22 asserts a fund symbol never calls Yahoo and that a second call for the same
ticker in a cycle is served from the cache unchanged. LESSON: "cancelled" is not "failed" to GitHub,
so it is not "failed" to any alarm that reads the sentinel; count the runs that never finished, not
just the ones that broke.

2026-09-15 - THE LEDGER'S DIP_CONVEXITY CELL WAS NOT THE LIVE CELL. WHAT BROKE: the returns ledger
(the one source every performance number is supposed to come from) scored DIP_CONVEXITY's archive
cell as "calls, SPY 50d < -2" on the BASE exit (-50/+50/0.20): +8.1/day, t 2.07, 63 days. The seat
actually trades calls with SPY below its 50d AND below its 20d (the tuner's 2026-09-01 confirmation),
and runs the engine's hardcoded wide exit (-70/+80/0.30, `PROBE_EXITS`): +19.2/day, t 3.33, 56 days.
Found while testing the owner's loosening request on the archive. ROOT CAUSE: `ARCHIVE_FILTER` was
written from the seat's NAME, not its filter lambda, and `exit_idx` only knew `probe.tuning.<name>.exit`
- the spec never had that key for this seat, so the map's own line "the ledger snaps to what the
spec says" described a key that did not exist. FIX (same commit as the loosenings): the cell is
re-cut to the live cell (and to the new SPY-below-50d band, decision 41); `DEFAULT_EXITS` mirrors
`PROBE_EXITS`. REGRESSION CHECK: MOT 6.23 asserts the ledger's DIP_CONVEXITY predicate equals the live
cell and its exit equals `sandbox_proactive_lab.PROBE_EXITS`. LESSON: a cell must mirror the live filter
AND the exit the seat runs; both live in the engine, so the ledger must read them from the engine or
be pinned to it by a check.

2026-09-15 - THE RESERVED CONTRACT: THREE POSITIONS COULD NOT BE CLOSED, ONE EXPIRING IN THREE DAYS.
WHAT BROKE: ON260918P00075000 (QUIET_TAPE, expires 2026-09-18) was decided CLOSE_EXPIRY by the exit
engine on every cycle from 17:47Z and never closed. The broker had no record of the attempts at all
(zero orders on the symbol today) and the position showed qty_available 0. QQQ261016C00730000 and
SPY260925P00740000 were in the same state. The failure counter climbed to 4, reset at 5 because a
bid existed, and looped: never closed, never parked, nothing printed, no alert. Found in the Tuesday
evening department review, not by any alarm. ROOT CAUSE (two): (1) `sandbox_proactive_lab.py:_retire_stop`
returned True immediately when the RECORD said `backstop.retired` - a claim about the broker, taken
as the broker's state. All three records claimed retired while their stop still rested (status
pending_new since 2026-08-25 on ON), so the cancel was skipped, the resting stop kept the only
contract reserved, and `_close_position` was rejected before it ever reached an order id. (2)
`_note_close_failure` knows only one failure mode, the zero-bid corpse; a rejection with a live bid
reset the counter, which is what made it silent and infinite. FIX (same evening): _retire_stop now
sweeps the BROKER for any resting sell on the contract (the recorded id, a superseded one, or an
orphan), cancels each, re-confirms none survive, and returns False on unknown state - the record's
flag can no longer authorise a close; _note_close_failure gets a reserved-contract branch that prints
every cycle and sends ONE telegram.

WHAT THE BROKER ACTUALLY SHOWED (checked contract by contract the same night, all 17 resting sells vs
their records): 14 healthy positions matched their record's order id exactly. The three stuck ones
diverged in TWO different ways, and the fix covers both. (a) QQQ261016C00730000: the record's id WAS
the resting order and the record said retired=True - the flag lied about the very order it named.
(b) SPY260925P00740000 and ON260918P00075000: the record named one id (1798669e, da341230) while a
DIFFERENT order rested (fd15045c, 9cac7cbd), and the resting id was not in prior_order_ids either -
an orphan stop the record knew nothing about. Sweeping by contract, not by remembered id, is the only
thing that catches (b). LIKELY MECHANISM, and a latent defect of the same class left for a separate
fix: `_cancel_order` returns True on HTTP 204, which means the cancel was ACCEPTED, not completed -
proved tonight, when cancelling these three with the market shut left all three in `pending_cancel`
and still resting, to complete only at the next open. `manage_backstops` treats that True as "the old
stop is gone" and submits a replacement, which is how one contract ends up with a stop the record does
not name. OWED: make the ratchet's cancel confirm terminal the way _retire_stop now does.

The three stale stops were cancelled by hand the same night; with the market shut they sit in
pending_cancel and complete at the 2026-09-16 open, after which the first cycle can close them.

PANEL, BEFORE THE SHIP (two reviewers, one DO-NOT-SHIP, both applied): the first draft of this fix
reproduced the very class it closes, three ways. (1) _retire_stop now BLOCKS the close before
_close_position is reached, so _note_close_failure - the only path that alerts - became unreachable
for exactly this incident: a stop that will not die printed to the cycle log and paged nobody, and a
degraded orders endpoint was silent entirely. Both call sites now route a blocked close through
_note_close_failure, so it counts and alerts like a rejected one. (2) _qty_available returns None on
any failure and `None == 0` is False, so a failed broker read fell through to the zero-bid branch that
resets the counter - the silent loop again. Unknown is now treated as blocked. (3) the alert was once
per record for its LIFETIME (the ON stop had rested three weeks); it is now once per record per day,
and always when expiry is within a day, because a physically settled option left open through Friday
is ASSIGNED into shares and this engine manages OCC-keyed legs only, never a stock position. Also
caught: MOT 6.26 as first written called the real _notify and the real _order_state, so the ship gate
would have paged the owner and hit Alpaca on every run. REGRESSION CHECK: MOT 6.26 (a retired flag with a live resting order
cancels it and refuses the close; a clean contract proceeds; a reserved contract is flagged and
alerted, never parked). LESSON: our record of the broker is a claim, not the broker. Any step that
can collide with live broker state must read the broker, and a failure mode with only one branch will
one day be the wrong branch.

2026-09-15 (second entry) - THE CONTRACT CAP KEPT THE HELD-NAME LOOSENING FROM WORKING. WHAT BROKE:
STUDENT_A produced its first eligible live pick since going live (XLE 66 call, score 34.69 vs
threshold 14.58, ask $0.49) and did not enter: "student[STUDENT_A] skip XLE: ticker cap: 5 held + 5
pending on XLE >= 3". WINNER_PROFILE was refused the same name the same cycle. ROOT CAUSE: the
subordinated `max_contracts_per_ticker` (3) in `sandbox_proactive_lab.py:ticker_blocked` counts
contracts across the WHOLE account, so EXEC_BASELINE's 5-lot XLE put from 09-14 plus its own resting
5-lot stop made 10 on a cap of 3 for every other strategy - the exact block the 2026-09-15 held-name
loosening (decision 41) was meant to remove, one layer below it. Two gates, one intent: loosening the
first without the second bought nothing for the seats that most needed it. FIX: for a named probe the
cap counts only that strategy's own contracts (its own OPEN/PENDING records' OCCs); every other caller
keeps the account-wide count. REGRESSION CHECK: MOT 6.26 (another strategy's 5+5 does not block a
different probe; the owning strategy and non-probe callers still capped). LESSON: when a rule exists
in two places, change both or neither; a "subordinated belt-and-braces" cap is still a cap.

2026-09-17 - TWO YEARS OF ARCHIVE WERE SILENTLY TRUNCATED AT 500 CONTRACTS A DAY. WHAT BROKE: the
option archive that every backtest, corpus and court verdict is built on holds only the 500
busiest contracts per ticker per day. 111,320 of 138,030 ticker-days (80.6%) sit at exactly 500
rows and no ticker-day anywhere in the 61,006,588-row table exceeds 500. Because the feed returns
volume-descending, the missing rows are the low-volume far-OTM tail - on 2026-09-10 any SPY
contract trading under 1,262 lots is simply absent (QQQ 819, NVDA 293, IWM 209, TSLA 178, AAPL 152,
META 123). For SPY expiring 2026-09-18 with spot ~758 we hold 31 call strikes topping out at 790:
nothing above +4.2% exists. That is precisely the strike a debit spread sells, so every
spread-access study ran against a chain that could not contain its own short leg. ROOT CAUSE:
scripts/uw_history_pull.py line ~125 (and the same in scripts/uw_flow_prints.py) requested
"?date={dd}&limit=500" and no pagination existed anywhere in the repo - no page, offset, cursor or
page_token. Nothing logged or flagged a day that came back exactly at the cap, so it never
surfaced in two years. Verified live 2026-09-17: limit is a hard SERVER cap (limit=1000 and 2000
both return 500) and `offset`/`skip` are ignored, but `&page=2` returns a genuinely different 500
rows reaching down to volume 200. The data was always there and always paid for; we asked for one
page. SECOND FINDING, same audit: START was 2024-09-03 while the UW token's floor is a ROLLING
730-TRADING-day window - a live 403 returned "The earliest date currently available to this token
is 2023-10-17". About 230 trading days we are entitled to had never been pulled and expire
permanently at one day per day; 2023-10-17 itself rolled off during the audit. FIX: pagination
added to the puller, capped at UW_MAX_PAGES (5) and entered only while a page came back FULL and
its tail still had volume, so we fetch the real missing tail and not zero-volume chain padding on
all 260 names; START moved to 2023-10-17 (reversed(days) already pulls recent days first, so the
backfill only ever spends leftover budget); a 3 GiB disk guard added because pagination grows the
archive. 3,916 ticker-days already recovered by an out-of-band run were adopted into the puller's
checkpoint so the cron does not repay for them. REGRESSION CHECK: the puller now counts ticker-days
that hit the page cap while their tail still has volume and prints "TRUNCATION WARNING: N
ticker-days hit the N-page cap with volume still in the tail" at session end; silence is the
healthy state and the nightly log carries it. NOT CLOSED BY THIS FIX: the 510 days already stored
keep their truncated chains, because the `pulled` checkpoint marks them done - re-paging days whose
stored row count is exactly 500 is a separate job and is owed. LESSON: a cap that is also a
plausible answer is invisible. Any paged endpoint must either page to exhaustion or record that it
stopped early, and "the vendor gives us two years" is a claim to test against the vendor, not to
inherit from a comment.

2026-09-18 - THE ARCHIVE PULLER DIED ON A LOCKED DATABASE, ONE NIGHT AFTER IT WAS FIXED. WHAT BROKE:
the nightly `scripts/uw_history_pull.py` session of Friday 2026-09-18 ended at 22:38:42 UTC with
`sqlite3.OperationalError: database is locked` after 900 of roughly 18,000 calls, so a night of
backfill into a ROLLING window (entitled history expires at one trading day per day) recovered one
day instead of about fifty. Found on 2026-09-19 by a full-system diagnosis, not by any alarm: the
traceback sat in `uw_pull.log` and nothing reads that log. ROOT CAUSE: the archive is a rollback-
journal SQLite file with one writer and several readers. `fade_meta.py` starts at 22:10 on weekdays,
runs about thirty minutes and reads `data/uw_history.db` throughout; its log closed at 22:39, one
minute after the crash. A reader's shared lock blocks the writer's exclusive lock at COMMIT, the
connection's timeout was 60 seconds, and the commit was not wrapped - so the first long overlap was
fatal. Thursday's run survived the same overlap only by timing. FIX: `commit_retry` waits a lock out
(ten attempts, thirty seconds apart, logged as LOCK RETRY) and re-raises anything that is not a lock;
the connection timeout is 300 seconds; every commit in the session uses it. Same change: the page cap
default moves 5 -> 12, because the truncation sentinel shipped on 2026-09-17 fired on its first night
(91 ticker-days still had volume in the tail at page five). REGRESSION CHECK: MOT 6.27 (a connection
whose commit raises `database is locked` twice is retried to success with two waits; a different
OperationalError still raises). NOT CLOSED BY THIS FIX: a crashed nightly puller still pages nobody -
the freshness sentinel only notices days later when the newest day goes stale. LESSON: a job that
writes a shared archive must assume a reader is always there. The 2026-09-17 fix was verified against
the API and never against its neighbours in the crontab.

2026-09-21 - A QUIET MARKET OR A DEAD TOKEN WOULD HAVE STOPPED THE ONLY LIVE STRATEGY. Found while checking
whether the owner could end the Unusual Whales subscription. WHAT BROKE (latent, never fired on a Monday entry):
sandbox_proactive_lab.run_scheduled_cycle asked the UW flow scanner for candidates and, if it got none, left the
cycle - skipping EVERYTHING after it: the weekly credit spread, the proof book ("promotion 1"), the put-write and VRP
settles, the share probes and the arming of the owner's /flatten. scan_candidates is correctly fail-open (a missing
or dead token gives an empty list), so ending UW would have stopped both live spreads entering AND settling, silently,
with a DEGRADED page every ten minutes. It also bit on any quiet cycle, and the 2026-09-20 first-session entry gate
made that worse: a Monday with no flow candidates meant a skipped week. ROOT CAUSE: self-contained probes were added
below a guard written for the directional entries, and nothing asked whether they needed the flow. FIX: the early exit
is gone; with no candidates the directional loops iterate nothing and every probe still runs. uw_scanner.enabled in
the spec skips the scanner and its page together, so ending UW is a config change - set false tonight with the owner's
"credit spread only" ruling, and the Sunday schema harness skips UW on the same switch. ALSO: the first ship attempt
aborted on its own safety check, which searched for the text "return None" and matched it in the comment explaining
the fix; nothing was pushed. REGRESSION CHECK: MOT 6.32 reads code lines only (no comment can fool it): no return
between the scanner and the credit spread; the proof book and the self-settling probes all sit after the scanner; the
switch skips the page. LESSON: a guard placed for one family of entries silently governs everything written below it;
and a safety check that matches text can be fooled by the comment that documents it - check code, not prose.

2026-09-21 (second entry) - SWITCHING THE SHARE PROBES OFF WOULD HAVE STRANDED THEIR POSITIONS. Found while
carrying out the owner's "credit spread only" ruling. WHAT BROKE (latent - no share position was open): shares_probes.cycle
returned on `not cfg.get("enabled")` BEFORE its exit logic, so disabling the probe stopped the sells along with the buys;
an open OVERNIGHT or TURN_OF_MONTH position would never have been closed. This is exactly the 2026-09-14 class
(retiring a probe switched off its settle sweep) - that fix covered vrp_probe, putw_leg and fivek_probes and missed
this one. FIX: `enabled` now folds into the existing allow_entries flag, which already ran exits and blocked entries;
the early return fires only on missing credentials. REGRESSION CHECK: MOT 6.33 - no `enabled` early exit in the
cycle, and the entries gate sits ahead of the first close call. LESSON (again): retire a strategy's ENTRIES, never its
bookkeeping - and when a lesson is learned on three modules, sweep for the fourth.

2026-09-20 - THE WEEKLY SPREAD TRUSTED ITS OWN QUOTES AND ITS OWN CALENDAR. An eight-agent
audit of the credit spread's numbers (four lenses, each independently refuted) found three defects in
the live book, none of which had cost money yet. WHAT BROKE: (1) the BEAR stand-down sat inside the
per-cycle entry block, so the week's decision was retaken every ten minutes - a week that opened BEAR
entered anyway once the label flipped (5 of the 17 bear weeks in three years would have), a Friday
flip opened next week's spread while the once-a-week test only looks back to Monday so Monday opened a
second one, and a Monday that merely failed to quote retried all week; the evidence base prices a
first-session entry held to expiry and nothing else. (2) _enter booked the INDICATIVE QUOTE as the
premium and marked the record OPEN without ever asking the broker what filled; in four of the first
six spreads the short leg rested 2-17 minutes at its limit, and a short that never filled would have
left the book claiming a credit it never received while holding only the long wing. (3) On
2026-08-25 13:38 UTC the orphan reconciler, reading the empty book left by the previous day's
corrupt-log incident (see 2026-08-24), adopted both legs of the 2026-08-28 spread as its own and the
exit engine stopped them out at 13:33 for a realised +$29; the record never noticed, stayed OPEN and
booked +$62 at expiry six days later. The adoption route is already fixed (41e6561b, fail-closed on an
unreadable book) and the reconciler has known bare-occ legs since 3ee328c3; what was unfixed is that
the record has no way to notice a leg closed behind its back. ROOT CAUSE, all three: the book believed
its own intentions instead of asking the broker, and it re-decided a weekly question on a ten-minute
clock. FIX (one commit): fivek_probes._first_session gates entries to the exchange week's first
session (holiday-aware, Monday-only when the calendar is unreadable) ahead of the regime gate;
_order_state + _confirm_fills rewrite each leg's prem to its filled_avg_price, keep the quote as
`quoted`, mark a dead leg filled:false and drop it from net_credit; _closing_fills + _settle_one price
any leg closed at the broker from its realised fill instead of expiry intrinsic, annotate the record
and page the owner, because a European cash-settled spread must never be closed by a sweep. The six
records already in the book carry no order ids and are left untouched. NOT CORRECTED IN PLACE: the
2026-08-28 record still reads +$62; the realised figure was +$29 and the court's weekly unit used the
+$62 - a rewrite of a settled record is a bigger risk than the $33, so it is recorded here instead.
REGRESSION CHECK: MOT 6.30, six checks on the real entry and settle code - the first-session guard
stands ahead of the regime gate; a filled leg is booked at the broker's price with the quote kept; a
dead short is wings-only and never priced at expiry; legs closed at the broker are booked realised and
page the owner; an untouched week still settles at exactly +$62 with the ordinary telegram; a legacy
record without order ids is left byte-identical. LESSON: a book that records what it MEANT to do
diverges from the broker silently, and it diverges most on the days that matter; ask the broker.

2026-09-19 - THE LANDING WATCH PAGED A FALSE ALARM EVERY NIGHT. WHAT BROKE: at 22:45 UTC on at least three
nights running (16, 17 and 18 September) the owner's phone received "LANDING WATCH: integrity gate: no run logged
today (22:05 job)" while the gate had run at 22:05 and printed INTEGRITY GATE GREEN each night. Found by
a full-system diagnosis; nobody had questioned the page. ROOT CAUSE: `scripts/landing_watch.sh` proved
the gate ran by grepping today's date in `tail -5` of the gate's log. The gate gained checks until its
dated header sat seven lines from the end, outside the window - so a healthy job read as absent. FIX:
the window is 40 lines. REGRESSION CHECK: MOT 6.28 (the window is parsed out of the script and must be
at least 20). LESSON: an alarm that is wrong every night teaches its reader to ignore it, which is worse
than no alarm. A watch must key on something the watched job promises - a dated final line or a state
file - never on how many lines it happens to print.

2026-09-19 (second entry) - THE FLOW-PRINT TAPE WAS BEING CAPTURED BY LUCK, AND A MISSED TAPE IS GONE FOR
GOOD. WHAT BROKE: `flow_prints` holds a real print tape on 2 of its 475 days (2026-09-04 and 09-11, ~130
prints per contract-day); every other day holds about two. The diagnosis of 2026-09-19 asked the vendor
again for the puller's own cohort: contract-days stored with 149, 484, 278 and 452 prints on 09-11 now
return 9, 3, 7 and 2, days 09-15 to 09-17 return nothing at all, and 09-14 returns 1-9. Unusual Whales
publishes a day late, serves it in full for a short while, then THINS it. ROOT CAUSE: the puller marked a
contract-day done on its first non-empty answer, whatever its size, and spent the rest of its budget on a
two-year backlog the vendor had already thinned; whether a day was caught full depended on which night
the first non-empty answer arrived. FIX: `is_final` keeps every contract-day inside a 12-day window open -
it is asked again each night, `insert or ignore` keeps the fullest tape ever seen, `prints_pulled.n` keeps
the maximum - and each session logs one `window` line per day (asked / returned tonight / held) so the
vendor's real clock can be read off a week of logs and the window tightened. Same change: both archive
pullers write a session-state file on a clean end and on a crash, and the landing watch pages when either
is stale for 26 hours or marked crashed - closing the gap left open by the 2026-09-18 entry; and the
history puller re-pages, with leftover budget, the ~41,800 stored ticker-days that were genuinely cut at
the old 500-row cap, skipping tails that trade 10 lots or fewer (owner ruling 2026-09-19, the free route:
the disk cannot hold every tail). REGRESSION CHECK: MOT 6.29 (no answer is final inside the window; a
crashed session leaves a readable mark) and the re-page rule check beside it. NOT RECOVERABLE: the full
tapes of the 473 thin days. LESSON: some data can be collected exactly once. For any vendor feed, ask
what happens to yesterday's answer next week BEFORE designing the checkpoint - a "done" flag is a bet
that the answer will never get better or worse.

2026-09-22 - THE KILL SWITCH WAS DEAD FOR TWELVE DAYS (found in the post-exit health check, never fired in anger).
WHAT BROKE: `/halt` and `/flatten` would have failed. `scripts/telegram_commands.py:_write_flag` publishes halt.json
through the ~/harvest-snapshots repo and returns True only when the push confirms; every push to that repo since
2026-09-10 was rejected by GitHub's 100 MB file limit, because the nightly harvest snapshots had grown to 122 MB.
The same rejection meant the off-box database backup had been stale for twelve days.
ROOT CAUSE: one repo carried two unrelated jobs - a 120-byte control flag and a 122 MB nightly database - so the
backup's growth curve silently disabled the owner's emergency stop. The nightly alarm DID fire, eight times
("BACKUP ALARM ... FAILED TO PUSH"), and nobody triaged it: an alarm nobody acts on is not a control.
FIX (this commit + VPS-side, 2026-09-22): the snapshots repo no longer tracks *.db.gz (the unpushed commits were
reset, not force-pushed, and the push confirmed); ~/backup_snapshot.sh now takes a snapshot only when harvest.db's
content hash changes, SPLITS the gz into 90 MB parts, which is what travels off-box, and keeps 5 local copies
instead of 30; the irreplaceable data went off-box by a second route the same night (OneDrive).
LESSON: never let a control path share a transport with bulk data. And an alarm that fires nightly without a
triage step is noise - the sentinel's "off-box snapshot repo" row is the check that must page, not the email.
REGRESSION CHECK: the sentinel's existing `git_commit` row on ~/harvest-snapshots (TRADE criticality) plus
MOT 6.12's kill-switch publish test; the new split keeps every pushed file under the limit that broke it.

2026-09-22 - THE HARVEST KEPT CALLING A VENDOR WE WERE CANCELLING (near-miss, caught in the same audit).
WHAT BROKE: nothing yet. a6967d48 switched the Unusual Whales scanner off in the spec, but that switch guarded
`sandbox_proactive_lab.py:scan_candidates` only. `harvest_logger.py:_flow_rows` kept calling the vendor on every
open-market cycle (about 1,000-1,500 calls a day), so the day the token died the harvest would have gone silently
empty, and the engine would have kept paying calls into the owner's last allowance while the final archive pull
needed it.
ROOT CAUSE: a feature switch named for a subsystem ("uw_scanner") that only one of the subsystem's two call sites
consulted. The map and the MOT both described the switch as "the engine no longer calls UW", which was untrue.
FIX (this commit): `_flow_rows` reads the same switch and returns [] without calling out.
LESSON: when a switch is named after a dependency, find every call site of that dependency, not every caller of the
function you are editing. The proof is a grep for the vendor, not a reading of the switch.
REGRESSION CHECK: MOT 6.34 (the harvest feed must be gated on the same switch as the scanner).

2026-09-24 - THE EVENING DIGEST NEVER REPORTED A SALE OR A SETTLE (found by the performance review; fatal to its purpose).
WHAT BROKE: `scripts/daily_digest.py` (22:20 UTC, the owner's one plain-English page of the day) has said "Sold today:
nothing" and shown no settlement on every evening since it was written on 2026-08-25 - through 64 directional exits on
2026-09-18..24 and the credit spread's +$105 settle booked on 2026-09-21.
ROOT CAUSE: it read `le.get("exit_ts_utc")` from `leg_exits` rows that carry `closed_at`, and `s.get("ts")` /
`settle_ts_utc` from settle dicts that carry `at`. Neither key has ever existed on a record, so both branches were dead
from the first run, and the fallback sentences ("nothing ... that's normal, not broken") read as healthy.
FIX (this commit): `scripts/daily_digest.py:trade_lines` reads `closed_at` and `at` (the old names stay as fallbacks),
reads `proof_logs.json` beside the discovery book so the proof stint's settles appear, and `main(today=None)` can be
replayed for a past day. Replayed for 2026-09-21..24 it lists the exits and the 2026-09-21 settle.
LESSON: a report that prints a reassuring sentence when it finds nothing must be proven against a day when something
happened; a digest that has never once said "sold" is broken, not quiet. Read a record's keys from a record, never from
memory.
REGRESSION CHECK: MOT 6.39 (a fixture record with a `closed_at` exit and an `at` settle must appear in the digest text
for their day and not for another).

2026-09-24 (second entry) - THE INBOX WATCHDOG PAGED 28 TIMES IN TWO DAYS ON A DEAD PREMISE.
WHAT BROKE: `scripts/watchdog_vps.sh` measured engine liveness as the age of the newest commit touching
`data/harvest_inbox/` on origin/main. Unusual Whales ended on 2026-09-22 and the harvest feed went quiet with it
(2026-09-22 second entry), so the inbox stopped receiving commits while the engine completed every cycle; the watchdog
paged "stalled" every quarter-hour of two sessions and wrote 28 page bundles.
ROOT CAUSE: a liveness signal borrowed from a subsystem that could be switched off independently of the thing it
measured. The 2026-09-11 trap ("it watches the DATA, not exit codes") was right about the value of an independent
signal and silent about the day the data would legitimately stop.
FIX (this commit): the watchdog reads the stamp inside `origin/main:data/last_cycle_ok` (written only by a cycle that
finished, committed by every persist) and pages when it is older than 30 minutes during the session; the alarm
semantics, the page bundle and the status stamp are unchanged (`last_cycle_ok_age_min` replaces
`last_inbox_commit_age_min`). An empty stamp counts as no evidence, not as midnight.
LESSON: when a dependency is switched off, grep every watchdog and sentinel for the artefacts that dependency produced;
a dead-man switch keyed to a feed dies with the feed, loudly.
REGRESSION CHECK: MOT 6.40 (no code line of the watchdog references `data/harvest_inbox`; the liveness line reads
`data/last_cycle_ok` on origin/main).

2026-09-24 (third entry) - THE PROOF-EQUITY SENTINEL ROW WAS SET TWICE WITHOUT READING THE WRITER.
WHAT BROKE: the freshness row "proof book equity samples" expected 19:30 UTC when it was created (2026-09-20), then
14:30 after the 2026-09-22 fix. `proof_book.py:sample_equity` wrote once per UTC day on the first open-market cycle
(13:31-13:36), and the VPS copy's mtime - what a `schedule` row actually compares - is the poller's quarter-hour reset
that lands the change, 13:45. Both settings paged [TRADE] every weekday (freshness.log: "last update Tue 22 13:45,
expected a run Tue 22 14:30"). Sampling at the open also meant the stint's drawdown series lagged a session.
ROOT CAUSE: the 2026-09-22 fix was made without checking when the sampler writes, and neither setting accounted for
the pull that gives the file its timestamp on the box that runs the sentinel.
FIX (this commit): `proof_book.py:sample_equity` keeps one row per UTC day and rewrites it on every open-market cycle
(atomic replace, never raises), so the stored value is the session's last mark (~19:52 UTC in summer time), and the
row expects (19, 30, WEEKDAYS): the last change lands with the 20:00 reset in summer and the 21:00 reset in winter, so
19:30 holds in both clock regimes. The 20:30 first proposed for this fix would have paged every summer day for exactly
the reason above.
LESSON: a schedule row's time is read from the writer's timestamp, never assumed - and on the VPS the timestamp is the
pull that lands the file, quantised to the poller's quarter-hour, in both clock regimes.
REGRESSION CHECK: MOT 6.41 (two samples on one day leave one row holding the later mark; a sample that throws leaves
the file byte-identical) and the row itself, which pages again if the writer moves.

