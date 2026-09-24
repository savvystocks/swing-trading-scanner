# What the system learns now (2026-09-24)

Owner question, verbatim: "what is it learning now because of the strategy we have, i feel like the student is finished now
because it's quite basic the strategy but how can we keep that in effect to gain a better edge. everything to do with data
from uw, what do we do with that now?"

Written Thursday 2026-09-24 ~22:30 UTC by the learning-architect pass. Read-only: nothing on the VPS was edited, no cron
touched, no order placed, no UW call made. Every claim below was checked against the live checkout at
`~/swing-trading-scanner` (HEAD 609f4088), the crontab, the logs under `/home/poller`, `data/cs_legs.db`,
`data/daily_bars.db`, `data/harvest.db`, `proof_logs.json` and `proof_logs_equity.jsonl`.

## 0. The blunt answer

1. Right now the system is learning almost nothing, and most of what it still runs is judging things that can never
   change again. The court re-reads a shadow ledger frozen at 2026-09-18 every night and prints "virgin days: 32"
   forever; the poller is finishing a cohort of dead directional candidates; the integrity gate certifies a frozen
   database; the watchdog measures a heartbeat that no longer exists; the digest has never reported an exit or a
   settlement; the morning analyst narrates the frozen court; the scoreboard prints "proof weeks 0/8" from a spec
   field that nothing writes.
2. The ONE live learning instrument for the ONE live strategy - the proof stint - has no judge. NORTH_STAR v1.4-v1.7
   and the 2026-09-06 build contract (item 6, "WEEK COUNTER") describe the 8-rising-week rule; `proof_account.rising_weeks`
   and `week_history` in the spec are written by nothing (the only reader is `scripts/trajectory_scoreboard.py:116`).
   Today the owner would learn that the stint passed or failed by opening `proof_logs.json` by hand.
3. The student is finished, and not because the strategy is basic. It was a meta-labeller for single-name option-flow
   candidates; its feed is gone, its walk-forward AUC was ~0.51, it made zero live picks under the cap, and it is
   switched off. A "student" for a weekly index credit spread is structurally starved: 52 decisions a year of which
   about four are losses. There is nothing to learn from that with a model.
4. "A better edge" does not come from tuning a $35-credit spread. Every tuning question worth asking has been asked
   (section 2); the ceiling of the structure is about $1,100 a year per contract and its loss tail is unobservable
   inside two years. The better edge is a SECOND, uncorrelated, evidenced stream: the two never-built share strategies
   (RSI(2) ETF dip-buy, 17 years out of sample; Faber 200-day switch, 33 years), which is exactly why
   `scripts/daily_bars_archive.py` exists since 2026-09-22.
5. The UW data is frozen history worth keeping (the option archive, 20 GB; `cs_legs.db`, the only evidence base of the
   only live strategy; `legs_multi.db`; the harvest). Its remaining uses are listed in section 3. Its remaining COSTS
   are the jobs that still pretend it is alive (section 1).

## 1. Inventory: every learning or evidence component still running or wired

Legend for "spread?": can this component produce anything at all for a weekly XSP index put credit spread.

### 1.1 The court - `scripts/sunday_boundary.py` (three crons)
- Runs as: Fri 22:35 UTC (the court, can PROMOTE and push), Wed 10:00 (report-only), Mon-Fri 22:00 (report-only,
  BOUNDARY_SEQ_APPLY=1 - it may still APPLY a sequential pass and git push the spec).
- Consumes: `reports/shadow_lab/ledger.jsonl` (last row 2026-09-18 22:39; its writers `scripts/fade_meta.py` and
  `scripts/shadow_lab.py` left the crontab 2026-09-21, so the ledger is frozen - the log says "virgin days: 32" every
  night and will forever), `challengers.json` (CH_STOP_m45, CH_STOP_m35), the nine hard-coded MENU challengers
  (V13_DEPTH, MILD_ONLY, BAND_WIDE, OPT_WINNER, EARLY_CUT, FADE_WHALE, BAND_50_400, EXIT_STOP40, SOFT_ROUTER),
  `proactive_sandbox_logs.json` (PROBE records for the six `probe.priority` names), `data/harvest.db` (the "fade-cohort
  labels 1391/500 ... META-MODEL THRESHOLD REACHED" line, a 2026-08-11 order for a student that no longer exists),
  `fade_book_spec.json`.
- Produces: verdict lines in `sunday_boundary.log` and `trajectory_nightly.log`, `reports/shadow_lab/sentinels.jsonl`
  and `trajectory.log` (eight synthetic SENTINEL books "accruing" on 21 days that never change), and it retains the
  authority to commit and push `fade_book_spec.json`.
- Spread?: NO, structurally. The weekly branch (`weekmeans`, line 355) judges CREDIT_SPREAD_W on ISO weeks SHARED with
  the control EXEC_BASELINE. The control has had no fill since Unusual Whales ended, so the shared count is frozen at
  5 - "PROBE CREDIT_SPREAD_W: 5/8 live virgin weeks vs control - HOLD" is now a permanent sentence. The five
  directional names and STUDENT_FAMILY on the docket can never accrue a day. All eleven challengers are directional.
- Recommendation: RETIRE the three cron lines now (daylight decision the ROADMAP asked for). Keep the file: a court
  needs a control that trades, and a future second strategy would need one built for its own cadence, not this one.
- Exact edits: crontab - remove the three `sunday_boundary.py` lines (`35 22 * * 5`, `0 10 * * 3`, `0 22 * * 1-5`);
  `scripts/freshness_sentinel.py` rows 77 ("nightly boundary (SEQ_APPLY)"), 78 ("friday court"), 91 ("challengers
  parses"); `scripts/morning_analyst.py:gather` drop the "LAST NIGHTLY BOUNDARY" block (it tails
  `trajectory_nightly.log`, which stops changing); `scripts/daily_digest.py` lines 88-96 drop the "The court: N
  evidence days" paragraph (reads the frozen ledger); `scripts/evening_persist.sh` stays (page_bundles still land
  there) but will commit nothing new from the court; `docs/feature_map/evidence-and-court.md` "What": dated
  retired line; `docs/feature_map/vps-crons.md`: remove the three rows; `SYSTEM_ARCHITECTURE.md`: present-tense
  note; `ROADMAP.md`: the QUEUED "court's docket is empty" item closes with the date; the six-name `probe.priority`
  list and `probe.tuning` block in the spec are the docket - clear them in the same commit so no reader believes a
  case is open. `probe.promotion_floor_week_mean` and `promoted` become inert.

### 1.2 Harvest poller + labels - `scripts/run_poller_vps.sh` -> `poller.py --once`, `data/harvest.db`
- Runs as: */15 13-21 UTC weekdays. Sentinel row 71 "harvest poller log".
- Consumes: the committed inbox (no new rows since 2026-09-22 - `harvest_logger.py:_flow_rows` is gated on
  `uw_scanner.enabled`), Alpaca quotes for the open candidates.
- Produces: barrier labels. State tonight: 86,060 candidates, 84,838 labels; 1,222 open of which 1,169 have a vertical
  barrier still ahead (latest 2026-09-25 20:00 UTC) and 53 sit past their barrier (39 flagged untradeable) and will
  censor. `data/harvest.db` is 455 MB; the off-box split backup is alive again since 2026-09-22.
- Spread?: NO. The cohort is single-name directional option candidates.
- Recommendation: KEEP through Friday 2026-09-25 and the first run of Monday 2026-09-28 (so the last barrier labels and
  the 53 stragglers censor), then RETIRE. The database becomes frozen history like the archive.
- Exact edits (after 2026-09-28): crontab - remove the `run_poller_vps.sh` line and the `watchdog_vps.sh` line (1.4);
  sentinel rows 71 ("harvest poller log") and, with 1.3, 80; `docs/feature_map/harvest-transport.md` and
  `vps-crons.md` dated retired lines. Passivity: removing a cron line touches no code; if `poller.py` or
  `harvest_logger.py` is edited for any reason, `test_harvest_passivity.py` runs (`bash scripts/verify_engine.sh`).
  ROADMAP items 4 and 4b (inbox pruning, NOT-NULL keys) close as REJECTED - there is no live harvest to protect.

### 1.3 Integrity gate - `scripts/integrity_gate.py`
- Runs as: 22:05 UTC Tue-Sat. Sentinel row 80.
- Consumes: `data/harvest.db`. Produces: "row continuity: OK (86060 -> 86060)" - green forever on a frozen file, and a
  quarantine table nothing trains on.
- Spread?: NO.
- Recommendation: RETIRE with the poller. Trap: `scripts/landing_watch.sh` greps today's date in `integrity_gate.log`
  (the 2026-09-19 false-alarm note) - if the gate stops and landing_watch keeps that check it will page nightly, so
  the landing_watch check comes out in the same commit.
- Exact edits: crontab line `5 22 * * 2-6 ... integrity_gate.py`; sentinel row 80; `landing_watch.sh` integrity check;
  `vps-crons.md` row.

### 1.4 VPS watchdog - `scripts/watchdog_vps.sh`
- Runs as: */15 13-22 weekdays. Liveness = age of the newest origin/main commit touching `data/harvest_inbox/`
  (line 26) - a premise that died with the feed (28 false pages in two days per this evening's review).
- Spread?: NO; the engine heartbeat that matters is `data/last_cycle_ok`, which `scripts/engine_watch.sh` (*/15 14-21)
  already watches with auto-rollback.
- Recommendation: RETIRE the cron line now; `engine_watch.sh` stays. Edits: crontab, sentinel has no row for it,
  `telegram-and-watchdogs.md` and `vps-crons.md` rows. The engine_watch window (14-21) leaves the 13:30-14:00 first
  cycle unwatched; widen it to 13-21 when the watchdog goes.

### 1.5 The student wiring - `probe.student` in the spec, `sandbox_proactive_lab.py:_student_rank/_student_select`,
`scripts/fade_meta.py`, `reports/fade_meta/student_*_2026-09-13.json`, `.github/workflows/brain_weekly.yml`
- State: `probe.student.enabled` = false (mode "live", STUDENT_A flagged live, C pulled); six dependency-free models
  dated 2026-09-13, stale at 200 days; `reports/shadow_lab/student_scores.jsonl` last row 2026-09-21 20:00;
  `fade_meta.py` is in no cron and is imported only by the MOT list (`v11_mot_harness.py:1069`); `brain_weekly.yml`
  schedule removed 2026-09-21 (dispatch only). STUDENT_FAMILY still sits in `probe.priority` with a `probe.tuning`
  clock and reads "0/8 live virgin days" in every court run and in `docs/performance_map/STUDENT_FAMILY.md`.
- Consumes: UW alert rows (none). Produces: nothing. Live record: zero fills.
- Spread?: NO. It scores single-name contracts on 15 flow/regime features; the spread offers it no candidate.
- Recommendation: RETIRE the docket presence and close the ROADMAP item; leave the engine code (MOT 6.11/6.17 pin it;
  deleting it is a larger engine change than this pass authorises and buys nothing).
- Exact edits: spec - remove STUDENT_FAMILY from `probe.priority`, delete `probe.tuning` (all six entries are student
  pickers); `docs/performance_map/STUDENT_FAMILY.md` to a retired header (the lint only requires ACTIVE names mapped,
  `scripts/performance_map_lint.py:38`); ROADMAP item 8 (Student, listed IN-FLIGHT in the text and QUEUED in the table)
  and 8b (discovery rig) close as REJECTED citing decision 47; `student-seat.md` dated line; `v10_lab.yml:100` may keep
  persisting `student_scores.jsonl` (harmless, it no longer grows).

### 1.6 Shadow lab and sentinel files - `reports/shadow_lab/*`
- `ledger.jsonl` frozen 2026-09-18 (writers retired); `breaker.jsonl` frozen 2026-09-18; `student_scores.jsonl`
  frozen 2026-09-21; `sentinels.jsonl` and `trajectory.log` appended nightly by the court on unchanging data;
  `page_bundles/` still written by `scripts/page_bundle.sh`.
- Spread?: NO. Recommendation: they stop growing when the court stops (1.1); keep the files (the MOT and the map lint
  reference them by name - `scripts/feature_map_lint.py:20-22`).

### 1.7 Returns ledger + performance map - `scripts/returns_ledger.py` (Fri 22:40, commits and pushes),
`scripts/returns_alarms.py` (22:24 weekdays), `docs/performance_map/`, MOT 6.19
- Consumes: `proactive_sandbox_logs.json` (the DISCOVERY book only) and `reports/research/probe_tuner_rows_v3.jsonl`
  (frozen corpus, last day 2026-09-09). It does not open `proof_logs.json`.
- Produces: `reports/performance/ledger.md` - CREDIT_SPREAD_W row today: 6 settled, +$256, 100% win, 5 shared weeks,
  t vs control -0.23 - and nightly alarms that are currently paging BIG_TRADE on the last exits of dead directional
  legs (AMD +700%, IBIT +139%, QQQ +508% this week).
- Spread?: YES, half. The discovery spread row is real; the book that decides anything (the proof stint) is invisible
  to it.
- Recommendation: REPOINT. Add a PROOF section read from `proof_logs.json` + `proof_logs_equity.jsonl` (settled weeks,
  $/traded week, worst week, drawdown from high-water, capture against the frozen denominator +$21.6/wk in
  `proof_account.seats[0].capture_denominator`); cut `active` to CREDIT_SPREAD_W so the lint and the alarms stop
  scoring corpses; scope BIG_TRADE/CONCENTRATION to active names. Exact edits: `returns_ledger.py:41` (STRATS list),
  a reader for the proof book, the `active` list the lint consumes; performance_map files for the retired names get a
  dated retired header.

### 1.8 Friday scoreboard - `scripts/trajectory_scoreboard.py` (Fri 22:25, telegram)
- Consumes: `proactive_sandbox_logs.json`, the spec (`proof_account.rising_weeks` -> "proof weeks 0/8", written by
  nothing), `proof_logs.json` (seat count), NORTH_STAR (version).
- Produces: PRIORITY / DISCOVERY / V10 legacy cumulative dollars and the North Star block. The line "Nearest
  commitment: October-gate pre-registration written before 2026-09-18" is a hard-coded string (line 129) and stale.
- Spread?: YES if repointed; today it cannot see a proof week.
- Recommendation: REPOINT it into the stint scoreboard (1.14): the 8-week ladder state, traded/paused weeks, drawdown
  from high-water, next settle date, the CP tail bound beside the streak. Drop the cohort dollars once the 11 legacy
  legs are closed (the discovery tuition, -$9.2k lifetime, is history).

### 1.9 Morning analyst - `scripts/morning_analyst.py` (08:10 weekdays, Gemini free tier)
- Consumes: `trajectory_nightly.log` (the frozen court), `freshness.log`, `trajectory_scoreboard.json`, yesterday's
  entries/closes from `proactive_sandbox_logs.json` (this one reads `closed_at` correctly). Never opens
  `proof_logs.json` or `proof_logs_equity.jsonl`.
- Produces: a daily brief (SENT 1,3xx chars) that will narrate "no upgrade passed its bars" every morning for the rest
  of time.
- Spread?: YES if repointed. Recommendation: REPOINT `gather()`: replace the court block with the proof block (open
  spread strikes vs the XSP close, distance to the short strike in %, days to expiry, yesterday's equity mark, the
  settle when it lands) and one line from `daily_bars.log`. Keep the sentinel block.

### 1.10 Daily digest - `scripts/daily_digest.py` (22:20 weekdays)
- Consumes: `proactive_sandbox_logs.json`, `fade_book.spy_regime`, the frozen ledger.
- Defect (confirmed in code and data): line 63 reads `le.get("exit_ts_utc")` but `leg_exits` rows carry `closed_at`;
  line 66 reads `s.get("ts")`/`settle_ts_utc` but `fivek_probes.py:195` writes `"at"` - so it has never reported a
  sell or a settlement, and all six settled spreads went unreported. Its "Still to run tonight: ... the student's
  training" is a hard-coded string. It also has no proof-book line.
- Spread?: YES once fixed. Recommendation: REPOINT: the two keys, add the proof book, drop the fade/court prose.
  BREAKDOWNS entry with the fix commit.

### 1.11 XSP quote log - `scripts/xsp_quote_log.py` (15:05 and 19:50 UTC weekdays), verdict ~2026-10-17
- Consumes: `fivek_probes._quote` (Alpaca indicative) for the would-be XSP and matched SPY legs. Produces
  `reports/research/xsp_quotes.jsonl` (9 rows incl. the seed; today's 19:50 row dropped as one-sided by the 09-22 fix).
- Spread?: YES - the one pre-registered test running on fresh data. Entry-window excess so far: -$4.0, +$3.0, +$0.5,
  -$0.5 (four snapshots, not four weeks; the rule counts weeks, median, after four weeks). Pointer, not evidence: the
  closing-quote study said mean $11.8 / median $6.0; the live entry window looks tighter.
- Recommendation: KEEP untouched; the two cron lines come out with the verdict (ROADMAP scheduled decision). DST ends
  2026-11-01, after the verdict.

### 1.12 `scripts/cs_live_fills.py` (Sat 12:00)
- Consumes: Alpaca closed orders for CREDIT_SPREAD_W records in the DISCOVERY book. Produces
  `reports/research/cs_live_fills.json` (6/6 records, mean fill vs quote +$2.5, paper).
- Spread?: YES for discovery; it CANNOT read the proof account - proof keys are never on the VPS by design
  (`proof_book.py` docstring). The proof record already carries `quoted` vs filled `prem` from
  `fivek_probes._confirm_fills` and `_closing_fills` (the 2026-09-20 fix), so the stint judge reads fills from the
  record, not the broker.
- Recommendation: KEEP as is (cheap, discovery only); no proof edit needed.

### 1.13 `scripts/cs_legs_measure.py` (on demand) and `data/cs_legs.db`
- Consumes: `data/cs_legs.db` - 740,820 contract-days, 24,937 names asked (XSP 18,857, SPY 6,080), days 2022-11-02 to
  2026-09-18, FROZEN (the puller was deleted 2026-09-21; the vendor floor rolls, so nothing in it can ever be
  re-pulled) - plus yfinance ^XSP, ^GSPC, SPY, ^VIX.
- Produces: the audited measurement (+$26.1/wk usable weeks, +$21.6 refilled; CP tail bound; 35-year refit).
- New since 2026-09-22/23 (asked by name in the last hours of the token): the 45-day monthly ladder (32 entries
  2023-10-31..2026-08-04, ~12 strikes each from ~1% to ~12% OTM, 293 of 299 with quotes); 1-DTE Mon->Tue (55 groups)
  and Wed->Thu (57 groups), six strikes each, 2025-07-28..2026-09-16, all quoted; Fri->Tue 4-day (5) and Fri->Thu 6-day
  (5) - too few to use; the 10-20% OTM crash wings for the 10 worst weeks 2024-12-16..2026-06-01 (73 of 100 quoted);
  and the exact Friday-entry legs (181 + 11) already spent on the Friday test.
- Spread?: YES - this is the pre-registration engine for everything in section 3.
- Recommendation: KEEP. Gap found: the off-box copies (`~/harvest-snapshots/cs_legs.db.gz` dated 2026-09-19 and the
  OneDrive `cs_legs_2026-09-22.db.gz`) predate the last pulls (newest `pulled_utc` 2026-09-23T00:17:57Z). Nothing
  refreshes the copy any more. One-off: stream a fresh `gzip -c` of `data/cs_legs.db` (94 MB) off-box now.

### 1.14 The proof stint judge - DOES NOT EXIST
- Where the rule lives: NORTH_STAR v1.4 (8 consecutive rising weeks, drawdown inside written bounds, capture >= 60%),
  v1.6 (failed stint returns to court), v1.7 (grammar: -30% from stint high-water on DAILY equity; a zero-trade week
  PAUSES; fail on DD breach or 3 non-rising traded weeks in any rolling 5; capture evaluable only at >= 20 closed
  trades); `reports/proof_account_build_contract_2026-09-06.md` item 6 ("WEEK COUNTER ... week_history ... FAILS
  CLOSED"); the spec carries `proof_account.rising_weeks: 0` and `week_history: []`.
- What writes them: nothing (`grep -rn rising_weeks --include=*.py` finds only the scoreboard's read).
- What exists: `proof_logs.json` (one OPEN record `p5k09211505`, credit $35, entered Mon 2026-09-21 ~15:05 UTC, expiry
  Fri 2026-09-25), `proof_logs_equity.jsonl` (5,000.00 / 5,000.00 / 5,017.89 / 5,024.89 / 5,000.89 for 20-24 Sep,
  sampled 13:31-13:36 UTC = the first cycle after the open, so the drawdown series carries yesterday's close), the
  settle by `fivek_probes._settle_one` on the first cycle after expiry against yfinance ^XSP (its series skipped
  2026-09-22; ^GSPC/10 is the exact fallback by definition), the milestone telegrams promised in v1.6 (every
  proof-week close) - not wired.
- Recommendation: BUILD, as a VPS evidence job off the trade path (no engine change): `scripts/proof_stint.py`,
  Fri 22:25 (in place of the scoreboard) and after Monday's first cycle, reading `proof_logs.json` and
  `proof_logs_equity.jsonl` from origin/main (both are in the persist list, `v10_lab.yml:96`). Rule, mechanical:
  a traded week is rising when its expiry week's `settle.pnl_usd` > 0; an ISO week with no record is PAUSED; FAIL on
  equity < 0.70 x running high-water or 3 non-rising traded weeks in any rolling 5; PASS at 8 rising traded weeks,
  extending to 20 closed trades for the capture test against +$21.6/wk. Output: `reports/proof/stint.json`, one
  telegram per week close, and the CP tail bound printed beside the streak. Equity sampling: either accept the lag and
  say so on the face of the output, or (engine change, MOT + gate) sample at the LAST cycle of the day and set
  sentinel row 70 to (19, 30); with the sampler as it is, row 70 should read (13, 0), not (14, 30), and it stops
  paging.

### 1.15 Daily bars archive - `scripts/daily_bars_archive.py` (22:15 weekdays)
- Consumes Alpaca daily bars; produces `data/daily_bars.db`: 46,471 rows, 30 ETFs, SPY from 2018-11-01 (eight years),
  the other 29 from 2020-07-27 (six years). XSP is an index - Alpaca serves no bars for it; ^XSP/^GSPC come from
  yfinance.
- Spread?: YES indirectly (SPY for the BEAR gate; index closes for the settle if stored). It is the forward feed for the
  two share strategies and the only thing the estate now captures.
- Recommendation: KEEP. Small edit: append a nightly yfinance ^GSPC and ^XSP close row so the VPS-side judge and any
  settle fallback have an index close on disk.

### 1.16 Legacy directional book, telegram commands, engine_watch
- 11 OPEN directional legs (FOLLOW_CALLS 3, DIP_CONF_MILD 2, DIP_CONVEXITY 2, WINNER_PROFILE 2, EXEC_BASELINE 2), no
  new entries, managed by the exit pass; the unmanaged SPY share position in the discovery account is untouched by
  owner order. `telegram_commands.py` and `engine_watch.sh` are controls, not learning: keep.
- Dead secrets: `v10_lab.yml:78`, `health-check.yml:21`, `archiver.yml:27`, `uw_probe.yml:25,35` still inject
  `UNUSUAL_WHALES_TOKEN`. `archiver.yml` and `uw_probe.yml` are UW-only workflows: disable both, remove the four lines,
  delete the secret in GitHub.

## 2. The tests ledger for the credit spread (asked, answered, where the evidence sits on the VPS)

| Question | Status | Result | Source on the VPS |
|---|---|---|---|
| 50% take-profit | KILLED 2026-09-17 | Level t 4.57 was a construction artefact; paired +$19.65/wk t 1.25 vs bar 2.83; on the 89 gate-traded weeks -$4.56/wk t -0.83; Wednesday exit +$1.6 t 0.09; stop-losses -$36.5/wk t -3.43 | `reports/research/kitchen_sink_2026-09-19.md` (Corrections + Closed list); ROADMAP decision 45 |
| Early management (21 DTE, 50%, day 5) | REJECTED 2026-09-19 | Negative in 20 of 24 paired cells on executable prices | kitchen sink family E, `~/research_data/research_2026-09-18/time_structure*` |
| Friday entry vs Monday | FAIL 2026-09-22 | Paired D +$8.76/wk, t 1.00 (NW 1.01); halves -5.24/+22.75; drop-best t 0.74; P4/P5 pass; Friday worst -$1,146; the 20 long-weekend weeks D -$40.65/wk | `~/research_data/friday_entry_2026-09-22/` (PROTOCOL.md sha 62ae5f6e, impl_A/B_results.json, attack_summary.json) |
| Other tickers (IWM QQQ GLD DIA SLV EEM DJX) | 0 of 7 pass, 2026-09-20 | Bar t >= 2.72 (Sidak), coverage >= 85%, refilled positive; DIA best at +$6.1/wk t 0.78; DJX 5% quote coverage; the S&P falls >2% in a week 11% of the time, the lowest of any liquid underlying | `~/research_data/legs_multi.db` (37 MB); the measuring script was deleted with the UW cleanup 2026-09-23 - the table survives in NORTH_STAR v1.9 and memory |
| Widths | measured 2026-09-19; decision cap-driven | 2/4 +$26.1 t 2.95 worst -$624; 2.5/4.5 +$24.1 t 6.65 worst -$238; 3/5 +$18.0 worst -$48; 2/3 (cap-fitting) +$7.7 t 0.94; 3/4 +$9.1; all negative at the max-loss tail bound; 35-yr refit 2/4 -$3.4/wk, 3/5 +$4.3, 2.5/4.5 +$5.2 | `scripts/cs_legs_measure.py` output; NORTH_STAR v1.8 (cap width) then v1.9 (cap lifted for proof) |
| Instrument XSP vs SPY | XSP stays; forward verdict pending 2026-10-17 | SPY tradeable +$26.7 vs XSP +$25.2 same weeks, SPY between the strikes 18 of 152 weeks (assignment); closing-quote excess friction mean $11.8 / median $6.0; live entry-window excess so far -4.0/+3.0/+0.5/-0.5 | `scripts/cs_legs_measure.py`; `reports/research/xsp_quotes.jsonl` |
| Directional trades as spreads | DEAD 2026-09-20 | Paired -24 to -32 pts/trade, t -7; spread wins 7-16%; the outright itself loses in the live band | `~/research_data/dir_paired_spread.json`, `dir_real_spread.json`, `dir_legs.db` |
| Kitchen sink (six families) | REJECTED 2026-09-19, ROADMAP item 18 | 13,841 configs, 12 search-bar passes, 0 survivors; holdout unspent | `reports/research/kitchen_sink_2026-09-19.md`; `~/research_data/research_2026-09-18/`; `~/kitchen_sink_2026-09-18.tgz` |
| The BEAR gate | in-sample; no out-of-sample verdict | 55% of the 152-week profit; ungated +$10.3/wk t 0.78; 35-yr gated +22.0 vs ungated +24.8 (trims drawdown, adds no EV) | `reports/research/regime_playbook_2026-08-25.md`; `cs_legs_measure.py` 35-yr block; audit 2026-09-20 |
| The tail bound | measured; cannot close | 122 traded weeks, 10 losses -> CP upper 13.5%; EV +$12.4 at realised loss, -$119.5 at max loss; one contract's 35-yr max drawdown $8.8k | `cs_legs_measure.py`; standing rule (premium tail bound) |
| Live-faithful expectation | audited 2026-09-20 | +$10 to +$22 per traded week, 95% range -$3 to +$40, P(true edge > 0) 35-40%; proving +$10/wk needs ~750 weeks | frozen in `proof_account.seats[0]` (spec); audit scripts were in /tmp (volatile) |
| Pooled weekend effect (Fri-Mon) | QUEUED, owner's word | Real mechanism (18 of 18 cells) but +$8-36 per weekend, thin; the "complete chain" precondition can no longer be met (UW cancelled; crash tails ~5,000 ticker-days repaired) | ROADMAP scheduled decision; kitchen sink |
| Live record | running | Discovery 6 settled, +$256 (credits $9, $14, $62, $33, $33, $105), 100% win; proof 0 settled, 1 open ($35 credit, settles 2026-09-25) | `proactive_sandbox_logs.json`, `proof_logs.json` |

Note the credit sizes: $9 and $14 credits against ~$1,500 of defined risk are 0.6-0.9% yields; at those weeks the
structure is negative at any tail bound. The kitchen sink already recorded that credits are decaying.

## 3. What can still be learned, and what cannot

### 3.1 What six live weeks cannot learn (say it first)
The weekly P&L has a standard deviation of about $180 (152-week sample). Six weeks give a standard error of ~$73/wk;
a true +$20/wk shows as t 0.27. The stint's streak rule is a coin flip on the win rate alone: at 92% weekly wins,
P(no loss in 8 traded weeks) is 0.92^8 = 51% whether the true edge is +$20 or zero. A pass means "no loss week yet";
a fail means "one ordinary loss week arrived" (8% per week). The stint is therefore a SURVIVAL and MECHANICS test
(fills, settlement, gate timing, drawdown behaviour, the owner's discipline), not an edge test, and its judge (1.14)
should print that beside the streak so a pass is never sold as proof.

### 3.2 Pre-registerable questions, ranked (mechanism, data, bar, what a pass changes)

1. A second stream: RSI(2) ETF dip-buy and the Faber 200-day switch (HIGH). Mechanism: diversification, not tuning -
   the dip-buy is long after a 2-3 day drop, i.e. exactly the weeks the spread stands down; Faber is flat in bear.
   Data: `data/daily_bars.db` forward (30 ETFs, six years; SPY eight) plus yfinance for the 2009-2026 history; the
   forward store from 2026-09-22 is a physical holdout nobody has seen. Bar (rules are published, no tuning): on the
   same 16 ETFs at next-open prices with 5 bps a side, reproduce the published out-of-sample statistics (dip-buy:
   pooled +0.33-0.36%/trade, 16 of 16 positive, maxDD -16.7%; Faber-2x: beats buy-and-hold CAGR with no deeper
   drawdown across all four decades), then measure the correlation of their weekly returns with the 152 spread weeks.
   A pass changes: a share-order entry path and a second PAPER seat in the reserve account "promotion 2"
   (`proof_account.reserve_account_id` = PA3TGRR06HJJ exists), never the proof account (one seat by design), sized
   five $1,000 slots. Cost: £0. This is the only item on the list that can move the account by more than $35 a week.
2. Monthly (45-DTE) tenor vs the weekly (HIGH as a question, LOW power). Mechanism: 12 entries a year instead of 52
   at ~$12 of XSP friction each (~$480/yr per contract saved), one quote crossing per six weeks of premium; against it,
   no weekly re-strike during a slide and a wider dollar width for the same delta. Data: the new ladder - 32 monthly
   entries with 12 strikes 1-12% OTM, 293/299 quoted, entry-day and expiry-day closing NBBO. Pre-registration: strikes
   delta-matched to the weekly (2% x sqrt(45/5) ~ 6% short, 12% long, or the ladder's nearest), BEAR gate on the entry
   day, sell short bid / buy long ask, hold to the monthly expiry, cash-settled on ^XSP; paired by calendar month
   against the sum of the weekly rule's settled P&L inside the same hold; bar paired t >= 2.0 on 32 pairs, both halves
   positive, drop-best t >= 1.5, CP bound at realised and max loss on the face. Honest power: only an effect above
   ~$60 a month can clear it; expect HOLD. A pass changes the seat's tenor only through a fresh-week stint, never
   mid-stint. Not independent evidence: the ladder was pulled after the weekly result was known, on the same market.
3. Width for real money: 3%/5% vs 2%/4%, paired (MEDIUM, cheap). Already measured as levels (3/5 +$18.0/wk, worst
   -$48; 35-yr +$4.3/wk, maxDD $4.7k, still positive at 0.7x credit) but never as the paired difference with a bar.
   Mechanism: the same premise at a lower yield with a third of the tail; the GBP 2,500 lifetime cap is ~$3,300 =
   two full-loss 2%/4% weeks. A pass changes the width at the FIRST REAL-MONEY RUNG only (the paper stint keeps 2/4 so
   its weeks stay like-for-like with the evidence). Data: `cs_legs.db`, one afternoon in `cs_legs_measure.py`.
4. The regime gate variants (MEDIUM, only as a forward ledger). The gate is 55% of the profit and in-sample; two
   years hold 17 gated weeks, so no variant can be separated on the archive. Pre-register three variants (current
   2%-below-50d; VIX > 25; price below the 200-day) and have the stint judge log each week's would-be decision under
   each, judged after 52 fresh weeks on the paired difference. The 35-year ^GSPC series is the only place a gate can be
   tested today and it says the gate trims drawdown and adds no EV. A pass changes the gate only at a seat
   re-registration.
5. Sizing by the tail (arithmetic, not a test). Max loss on the open spread is ~$1,565 (757/741); one contract is the
   only size at $5,000 and it is 31% of the account; the 35-year one-contract drawdown is $8.8k = 176% of the account.
   Nothing in our data shrinks that: 122 weeks / 10 losses give a 13.5% upper loss rate and each loss-free fresh
   week lowers it by ~0.1 point. What the crash wings CAN add: the price of 10-20% OTM protection in the 10 worst
   weeks (73 quoted contracts) - a price sample, not a P&L test - which only matters if a WIDER structure (e.g. 3%/10%)
   were ever proposed; it does nothing for the 2%/4%, whose long wing already caps the loss. Low priority; ten weeks
   cannot test anything.
6. Long-weekend / holiday-week behaviour of the Monday rule (LOW). The Friday test already showed the Friday arm dies
   on long weekends; for the live Monday rule the relevant subset is the 14 Tuesday-entry and 6 Thursday-expiry weeks -
   n = 20, unpaired, underpowered, and the Friday test's P4 already priced the gap tail over 35 years. The only
   defensible successor named in that verdict ("Friday entry except before long weekends") is a ~$9/wk question that
   needs a build and a fresh-week stint of its own. Park it.
7. The 1-DTE Mon->Tue / Wed->Thu structures (LOW). 112 one-day spreads with six strikes each, all quoted, 2025-07-28
   onward - the kitchen sink's family E already found Wed->Fri and mid-week short-DTE selling negative in all 18
   cells at executable prices. Test only if the owner wants the closed question re-opened with the XSP legs; expect
   the same answer.
8. Pooled weekend-effect run (owner's word already required; LOW). The precondition ("complete chain") cannot be met
   any more; it would run on the repaired archive with the refill rule, at XSP economics, and even a statistical pass
   fails $5k sizing by the search's own note.

Every question above is one row in one ledger, judged against a family bar for the number of questions asked of the
same 152 weeks (already: take-profit, Friday entry, seven tickers, five widths, the gate, and the kitchen sink's 11,502
index cells). The archive is exhausted for anything under about $40 a week; only fresh weeks and a second stream
change that.

### 3.3 What the frozen UW data is still for
- `data/cs_legs.db`: items 2, 3, 5, 7 above and any re-check of the live rule; irreplaceable (refresh the off-box copy).
- `data/uw_history.db` (20 GB, 762 sessions, crash tails partly repaired): a re-run of the six kitchen-sink families on
  the repaired chain (prior ~10% that anything passes, by the search's own estimate); the weekend pooled test; nothing
  for the live strategy. Keep, do not spend nights on it without a new mechanism.
- `data/harvest.db` and the corpora: the directional premise's tombstone; keep for provenance, never train on.
- `~/research_data/legs_multi.db`: the seven-ticker evidence; the measuring script is gone - recoverable from the
  session scratchpad if ever needed.

## 4. The student, answered directly

Is it finished? Yes. It was a gradient-boosted meta-labeller answering "is this option-flow signal real?" on
single-name contracts from 15 decision-time features (flow premium and side, ticker vs its 20-day, SPY vs 50-day and
20-day, ask, quoted spread, regime). Its honest walk-forward AUC was ~0.51 (0.487 for picker C); the 2026-09-20
winners-signature test hit the same ceiling (train 0.667, test 0.543, one seed and one +774% trade); STUDENT_A made
zero live picks under the cap; and on 2026-09-21 its feed ended. The model files are dated 2026-09-13 and expire at 200
days by their own rule. It cannot be "kept in effect": there is no candidate for it to score.

What would a student for this strategy even be? A model deciding each Monday whether to sell the spread, or at which
width, from features like VIX, term structure, distance to the 50-day, the prior week's return, the calendar. That
search has already been run: the kitchen sink's volatility family (864 configs) found premium pays LESS when IV is
high; nine conditions per index cell, and the conditioned sibling died every time; the one-feature student we do run,
the BEAR gate, is in-sample and worth zero EV over 35 years. And the sample is 152 decisions of which about 12 are
losses; a learner has nothing to fit. A student here would be a noise filter with a worse tail, which is the first
adversarial check failing before any code.

What replaces it: the ledger in section 2. One question at a time, protocol and pass mark written and hashed before
the number exists (the Friday test is the template: PROTOCOL.md + sha256, two independent builds, an attacker),
paired against the live rule, live gates applied, the CP tail bound at realised AND max loss on the face, dropped
weeks refilled at the unfavourable bound, and anything that touches the live rule judged on FRESH weeks after
pre-registration - never on the 152 it was found in. The learning is the ledger's closed rows, not a model's weights.
The court and the student were built for a strategy with 25 decisions a day; this strategy makes one a week, so the
machinery that fits it is a notebook with a judge, not a tribunal.

## 5. The six checks against this pass's own recommendations
1. Structural edge vs better noise filter: no recommendation here claims an edge; the one build (the stint judge)
   measures, and the one search worth running (item 1) reproduces published rules on a physical holdout.
2. Win-rate gains hiding fat tails: the stint's streak rule IS such a gain; the judge must print the tail bound beside
   the streak, and a pass is to be reported as survival, not proof.
3. Frictions: the monthly test charges closing-NBBO friction on both legs; the share tests charge next-open plus 5 bps;
   the live XSP friction verdict is pending and nothing above assumes it.
4. Data honesty: the monthly ladder and the 1-DTE legs were pulled after the weekly result was known, on the same
   market weeks - not independent; every new question on the 152 weeks is counted against a family bar.
5. Dead weight: the court (three crons), the poller and watchdog (after 2026-09-28), the integrity gate, the student
   docket, the UW secrets and the two UW-only workflows, the frozen shadow-lab writers.
6. Unknown unknowns found on the way: the settle path's yfinance dependency (^XSP skipped 2026-09-22), the equity
   series lag, no judge for the stint, the cs_legs off-box copy behind the last pulls, credits thinning to $9-14 on
   some weeks, and the discovery book still trading a second identical spread whose only remaining purpose is the
   returns ledger's row.

## 6. The to-do list from this pass (nothing executed; owner's word on each)
1. Build the stint judge (1.14) and repoint the scoreboard, digest and analyst to the proof book (1.7-1.10).
2. Retire the court's three crons and the student docket (1.1, 1.5); close ROADMAP items 8, 8b and the docket item.
3. After Monday 2026-09-28: retire the poller, watchdog and integrity gate (1.2-1.4), with landing_watch's check.
4. Stream a fresh off-box copy of `data/cs_legs.db`; add index closes to the daily-bars job (1.13, 1.15).
5. Remove the UW secret from the four workflow lines and disable `archiver.yml` / `uw_probe.yml` (1.16).
6. Decide whether item 1 of section 3.2 (the share strategies, reserve account) is the next build.
7. Optional, cheap: the paired 3%/5% vs 2%/4% width row (3.2 item 3); the monthly tenor row (3.2 item 2).
