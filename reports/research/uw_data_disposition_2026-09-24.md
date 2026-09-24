# Unusual Whales data disposition - 2026-09-24 (Thu, ~22:30 UTC)

Data custodian pass. Every number below was measured on the LIVE box (poller@64.176.178.15, repo
~/swing-trading-scanner at origin/main 609f4088) or on the owner's laptop OneDrive tonight. Nothing was
edited, committed, ordered or killed; no key was read; Unusual Whales was not called.

Disk at the time of measurement: / 52 GB, 39 GB used, 9.9 GB free (80%; the watchdog pages at 85%).

## 0. The one-paragraph answer

Unusual Whales is gone and cannot be re-pulled (the token's 730-trading-day floor rolled forward daily and
the subscription ended 2026-09-22). Two stores are the live strategy's evidence and stay: data/cs_legs.db
(94 MB, off-box verified tonight) and the index/ETF fifth of data/uw_history.db. The single-name four
fifths of the archive (15.7 GB of the 20.5 GB file) served the flow-following premise that every study
rejected; it should leave the box as a cold copy on OneDrive (about 5-6 GB compressed, GBP 0) and be
rebuilt on the VPS as the index/ETF slice (about 4.8 GB). The counterfactual harvest (data/harvest.db)
labels its last candidate on Friday 2026-09-25 at the 20:00 UTC poll; after that the poller, the nightly
snapshot, the integrity gate, the archiver watch, one watchdog premise, five sentinel rows and about 160
lines of architecture/map text describe a machine that has no input. ~/research_data (855 MB, VPS-only,
irreplaceable) has never been backed up: one 209 MB tar.gz to OneDrive fixes that tonight.

## 1. Store by store

### 1.1 data/uw_history.db - the option archive

Size: 20,509,581,312 bytes (20.5 GB; 5,007,222 pages x 4 KB, freelist 0). Frozen: mtime 2026-09-23 01:30
UTC (the last-chance pull). Gitignored.

Contents (bookkeeping tables read; COUNT(*) on the big table avoided):
- contracts_daily: ~97.4M rows. The finisher log (~/uw_exit/finish.log) printed "97,152,272 contract-days
  stored" at 06:52 UTC 2026-09-22; the crash-tail pull that evening added 266,719 + the crash wings 4,630;
  the 00:10 UTC 23 Sep last-chance run added an unrecorded remainder. 762 sessions 2023-10-17..2026-09-21,
  260 tickers (pulled: 198,090 ticker-days). Per row ~210 bytes in the file.
- flow_prints: ~1.03M prints (prints_pulled: 441,196 contract-days, 507 days 2024-09-04..2026-09-11). A
  sample, not a tape (~2.3 prints per contract-day; reference_archive_truths). Directional-only.
- Bookkeeping: pulled, budget (33 days 2026-08-22..09-23, 731,212 calls), repaged (297 days, 9,709
  ticker-days), repaged_etf (SPY/QQQ/IWM: 1,530 ticker-days, +2,462,000 rows, REPAGE_LEFT=0), crash_repage
  (~5.5k ticker-days, ~2.5M rows), backfill_pulled (6,393 ticker-days, 3.17M rows), prints_pulled.

The split that matters:
- Index/ETF part: the 2026-09-22 slice was 47 chains / 19.8M rows (~20%; the OneDrive file). Counting
  every ETF-like symbol in the 260 (58 names incl. sector, levered, country, volatility ETFs) it is ~25%
  of rows. SPY, QQQ and IWM are COMPLETE past the old 500-row cap for all 510 archive days (repaged_etf);
  the other ETFs are complete only where the bonus re-page and the crash re-page reached.
- Single-name part: ~213 names, ~73-78M rows, ~15.5-16 GB of the file.

Readers NOW (grep of the live checkout and crontab):
- crontab: none. GitHub workflows: none. The engine never reads it.
- scripts/fade_meta.py:_vol_ivx_join (line 80, read-only URI) - no cron since 2026-09-21.
- scripts/probe_tuner.py:build_rows (line 108) - no cron.
- scripts/glide_sim.py:build_fine (line 79) - no cron.
- scripts/feature_map_lint.py ALLOW_MISSING (line 18) - tolerates its absence; the lint stays green if it goes.
- ~/research_data/research_2026-09-18/*.py (kitchen sink, finished) read it by path.

Useful for today: the index/ETF slice is the research base for defined-risk index structures (the regime
playbook, credit/debit spreads, condors, the kitchen-sink and time-structure families all ran on it). For
the LIVE rule itself, data/cs_legs.db supersedes it (legs asked by name: 91% week coverage vs 54% from the
capped chain). The single-name part was the input to the flow-following premise: no profitable directional
config (|t| 2.69 vs a 2.90 permutation bar), spreads 24-32 points worse per trade (t -7), no signature in
the winners, flow does not predict the stock. Nothing on the ROADMAP names it.

Off-box: OneDrive offbox_backup/uw_index_etf_2026-09-22.db.gz = 1,763,492,360 bytes gz (4,769,525,760
uncompressed, 2.7:1), built 2026-09-22 ~21:07 BST. It PREDATES the 22 Sep evening crash-tail pull (GLD,
SLV, TLT, IBIT, TQQQ, SOXL tails are in crash_repage) and the 23 Sep last-chance rows. The single-name
80% exists nowhere but this disk.

Compression measured tonight (two June-2025 weeks, indexed day range):
- single-name sample: 1,043,422 rows, 206.5 MB CSV -> 70.65 MB gz (2.92:1, 67.7 bytes/row)
- ETF sample: 308,224 rows, 60.5 MB CSV -> 20.5 MB gz (2.95:1)
- sqlite pages gz (the OneDrive slice): 2.7:1
So: single-name part ~5.0-5.3 GB as CSV.gz or ~5.8 GB as a gzipped sqlite slice; the WHOLE file
~7.6 GB as gzipped sqlite.

Options (all GBP 0):
(a) Keep whole on the VPS. Cost: 20.5 of 52 GB for data 80% of which no strategy can use; the box sits
    at 80% with a 5 GB cushion to the 85% alarm. Nothing lost.
(b) Prune the VPS to the index/ETF slice and cold-store the rest on OneDrive. Stream the whole file over
    ssh as gzip parts (~7.6 GB, ~1 GB parts, never materialised on the VPS - the 22 Sep lesson), verify
    sha256 of the reassembled stream on the laptop against the VPS file, then build the slice on the VPS
    (ATTACH + INSERT ... WHERE ticker IN (...), ~4.8 GB, needs ~5 GB free during the build; 9.9 GB is
    free), verify row counts per ticker against `pulled`, delete the 20.5 GB file. Saves ~15.7 GB on the
    VPS. The stale 1.76 GB slice on OneDrive is then superseded and can go. Lost: nothing; a single-name
    study would need the laptop and 20 GB of scratch (the laptop has 371 GB free).
(c) Delete the single-name part outright. Same VPS saving as (b); loses ~75M rows of by-day NBBO,
    greeks and OI on 213 names that can never be bought back under GBP 0.
RECOMMEND (b). Streaming the whole file rather than only the single-name rows means one hash to verify,
the bookkeeping tables travel with the data, and the stale 22 Sep slice is replaced by a current one.
Check the OneDrive quota first: the folder holds 8.7 GB now; a Microsoft 365 1 TB plan is fine, a 5 GB
free tier would not fit.

### 1.2 data/cs_legs.db - the credit spread's legs by name

Size: 94,072,832 bytes (94.1 MB). Frozen: mtime 2026-09-23 00:17 UTC. Gitignored. No writer exists any
more (scripts/cs_legs_pull.py deleted 07e31f07).

Contents: legs 740,820 rows (XSP 510,229; SPY 230,591; days 2022-11-02..2026-09-18: closing bid/ask,
volume, OI, IV, high, low, last per contract-day); asked 24,937 contracts (XSP 18,857 / SPY 6,080, entry
weeks 2023-10-20..2026-09-16, every one marked final).

Readers NOW:
- scripts/cs_legs_measure.py (module level, line 14, read-only URI) - on demand; the +$26.1/wk gated
  figure, the 35-year settlement check and the SPY-as-instrument rejection come from it.
- ~/research_data/friday_entry_2026-09-22/{attack.py, attack2-4.py, attack_fri.py, adv1/3/4.py,
  impl_A.py, impl_B_diag.py} - the pre-registered Friday-vs-Monday test (PROTOCOL.sha256), VERDICT
  PENDING. They open data/cs_legs.db by relative path from the repo root: do not move or rename the file.
- crontab: none (the Saturday 12:00 cs_live_fills.py reads the broker, not this database).

Useful for today: the entire evidence base of the only live strategy and the only source for any
pre-registered test on it.

Off-box: OneDrive offbox_backup/cs_legs_2026-09-24.db.gz (24,013,943 bytes, written 2026-09-24 23:15 BST).
Verified tonight: gzip -t ok; sha256 of the decompressed stream 0c39dbac15f042340371600a14e0dbdd
498314949143b6ce2d050c81728a0b8e = the VPS file byte for byte. cs_legs_2026-09-22.db.gz (21.6 MB) is the
older, superseded copy. The map's claim that the nightly backup carries it (docs/feature_map/credit-
spread.md:47, SYSTEM_ARCHITECTURE.md:309) is FALSE since the 22 Sep restore push: ~/harvest-snapshots/
.gitignore has `*.db.gz`, so ~/harvest-snapshots/cs_legs.db.gz (21.6 MB, 22 Sep 00:19, pre-final-pull)
is stale AND untracked.

RECOMMEND keep, whole. Review item (6) "nothing refreshes the off-box copy" closes by itself: the file can
never change again and the 24 Sep copy is final. Owed: fix the two doc lines; delete the stale gz in
~/harvest-snapshots (or leave it, 21 MB). Cost 0.

### 1.3 data/harvest.db, data/harvest_backups, ~/harvest-snapshots - the counterfactual harvest

Sizes: harvest.db 455,221,248 bytes (455 MB; +2.8 MB/day this week); harvest_backups 866 MB (two files,
harvest_20260923.db + harvest_20260924.db, poller.py:run_once line 152 `db.backup(keep=2)` at the 20:00
UTC run); ~/harvest-snapshots 4.4 GB = working files ~745 MB (five nightly gz 116-125 MB, KEEP=5, plus
the three 45 MB parts of tonight's) + archiver/ 19 MB + cs_legs.db.gz 21.6 MB + .git 4.2 GB (391 loose
objects 3.46 GiB, 494 MB of garbage tmp_pack, 67 commits since 2026-07-03). The GitHub repo
savvystocks/harvest-snapshots reports 2,622,236 KB (2.5 GB).

Contents: candidates 86,060 (2026-07-01..2026-09-22, ~1,500/day; executed 493; tiers topn 30,507 /
random 648 / none 54,412); labels 84,838 (up 15,705, down 22,212, vertical 46,616, censored 305);
bid_path 1,575,847 polls 2026-07-06..2026-09-24 20:00 UTC; fills 1,394 events 2026-07-27..2026-09-24
15:11; api_telemetry 1,123,269 Alpaca calls; integrity_quarantine 0.

Open cohort: 1,222 unlabelled. 53 are poll_tier 'none' (never polled, never labelled by design; barriers
already past). 1,169 are pollable (972 reduced + 197 standard), signals 2026-09-21 (513) and 2026-09-22
(656) - the last two harvest days before the feed switch - and EVERY one carries vertical_barrier_ts
2026-09-25 20:00:00 UTC. Today's last run: "open candidates: 1182 (1182 due) ... resolved up 5, down 7,
vertical 1, open 1169".

Readers NOW:
- poller.py:run_once via scripts/run_poller_vps.sh - crontab line 2, */15 13-21 UTC weekdays:
  harvest_db.ingest_inbox (0 new since 2026-09-22; harvest_db.ingest_fills still ingests fills_*.jsonl),
  poll, harvest_labeler.label_path, harvest_db.backup(keep=2), healthchecks.io ping.
- /home/poller/backup_snapshot.sh - crontab line 3, 21:30 weekdays: gz + split + push when the sha changes
  (it changed every day this week because of the polls).
- scripts/integrity_gate.py:run (module-level `import harvest_db`) - crontab line 6, 22:05 Tue-Sat: row
  continuity, schema, dups, null storms, MISSING rate; writes data/integrity_state.json.
- scripts/sunday_boundary.py:main line 181 - crontab lines 9-11 (Fri 22:35 court, Wed 10:00, nightly
  22:00): counts "fade-cohort labels n/500 toward the meta-model" (the selection brain, closed REJECTED).
  scripts/sunday_boundary.py:spawn_challengers line 69 launches scripts/variable_sweep.py:load_all
  (line 50, a 14,400-config grid over the harvest cohort) for the directional challengers.
- scripts/archiver_watch.sh (crontab line 13, 22:15) demands today's harvest_*.db.gz; scripts/landing_watch.sh
  (line 7, 22:45) demands a poller-log line and the snapshot file; scripts/watchdog_vps.sh (line 4)
  measures the age of the newest commit touching data/harvest_inbox/ (the premise that died - fills
  files still land occasionally, so it pages on every quiet half hour).
- scripts/freshness_sentinel.py rows: line 71 "harvest poller log", 80 "integrity gate", 82 "archiver
  watch", 84 "off-box backup", 89 "off-box snapshot repo".
- Engine side (GHA): sandbox_proactive_lab.py:3072-3073 calls harvest_logger.harvest_scan every cycle; it
  is a no-op now (harvest_logger.py:_flow_rows line 278 returns [] under uw_scanner.enabled=false;
  data/harvest_state.json for 2026-09-24 shows payload_count 0). fill_ledger.py still appends
  data/harvest_inbox/fills_YYYYMMDD.jsonl and v10_lab.yml line 102 commits them.
- Not scheduled: scripts/fade_meta.py, scripts/shadow_lab.py, src/brain/loader.py:latest_snapshot_gz
  (+ brain_weekly.yml, manual only), scripts/restore_drill.sh, the four test_harvest*.py gate suites.

Useful for today: it is the record of the dead premise - every scored flow candidate for 59 sessions,
with its feature payload and a triple-barrier label on executable bid paths. The student, the brain and
the fade meta-model were to learn from it; all three closed REJECTED. What survives as data: bid_path is
1.58M real Alpaca NBBO snapshots at 15-minute cadence on 86k single-name contracts (Jul-Sep 2026) - the
only intraday option-quote series the system holds - usable for single-name friction studies, which no
strategy needs. The 1,394 fill events are paper fills and bound book-keeping error only. 125 MB gz.

Off-box: harvest_20260924_2130 in three parts pushed tonight (de602e2); 22 and 23 Sep parts are in the
repo's history. The kill switch (/halt, /flatten via scripts/telegram_commands.py) publishes through this
SAME repo. At 2.5 GB and +125 MB per snapshot it reaches GitHub's 5 GB guidance in ~20 snapshots - the
failure class that silenced /halt for twelve days in September. Freezing the pile removes the growth.

RECOMMEND keep harvest.db (455 MB) as the record; prune around it: delete harvest_backups (866 MB) when the
poller stops; stop the nightly snapshot after the last label has been pushed; reclaim the 4.2 GB local .git
(a fresh shallow clone of the snapshots repo serves the kill switch; `git gc --prune=now` alone drops the
494 MB garbage). Nothing lost: the last snapshot is off-box and harvest.db stays on the VPS.

### 1.4 ~/research_data - the September research bases (VPS-ONLY, never backed up)

Size 855 MB. Readers now: none in the repo or crontab (grep research_data -> nothing); the friday_entry
scripts read data/cs_legs.db, not these.
- legs.db 687 MB: q(occ, day, b, a), 7,158,023 rows, 148,562 single-name contracts, 2024-09-03..
  2026-09-15 - by-name closing quotes for the directional-spread study (t -7, final). gz 200 MB.
- legs_multi.db 36 MB: 286,813 rows, 6,218 contracts, 2022-11-30..2026-09-18, same schema as cs_legs.db
  but a DISJOINT contract set (0 of its contracts and 0 of its rows are in cs_legs.db) - an earlier
  multi-strike ladder.
- dir_legs.db 14 MB (109,366 rows, 837 contracts); print_ts.jsonl 6.2 MB (83,734 first-print
  timestamps, the v3 corpus basis); spread_entries.jsonl 42 MB (83,734 directional spread entries);
  dir_paired_spread.json / dir_real_spread.json (the paired result).
- research_2026-09-18/ 71 MB: kitchen-sink code, results, feat.db 24 MB, PROTOCOL.md.
- friday_entry_2026-09-22/ 448 KB: the pre-registered test (PROTOCOL.sha256), verdict pending.
- crash_repage.log, last_chance.log, xsp_extras.log: the final pulls' logs.
Whole directory as one tar.gz: 208,774,050 bytes (209 MB).

RECOMMEND cold-store the whole directory as ONE tar.gz (209 MB) on OneDrive now, verify its sha256, then
delete legs.db, dir_legs.db, legs_multi.db, print_ts.jsonl and spread_entries.jsonl from the VPS (-785 MB)
and keep the small results, both PROTOCOL directories and the logs on the VPS as the record. Lost: nothing.

### 1.5 reports/research corpora (gitignored, 451 MB)

- glide_fine_rows_v3.jsonl 151 MB (90,405 rows; gz 6.3 MB) and probe_tuner_rows_v3.jsonl 28.8 MB
  (90,405 rows): the executable-basis corpora every directional verdict is denominated in. Readers now:
  scripts/returns_ledger.py (CORPUS, module level line 35, read at lines 152-154; crontab line 18 Fri 22:40,
  the ledger's ARCHIVE column for the retired cells), scripts/tuner_apply.py:main line 112 (no cron),
  scripts/probe_tuner.py and scripts/glide_sim.py (no cron), v11_mot_harness.py 6.10f/6.10g (name lints).
- superseded/ 158 MB (the entryday_regime variants, superseded 2026-09-11); historical_corpus_2026-08-13/
  58 MB; probe_tuner_rows.jsonl 15.6 MB (v1 - MOT 6.10f forbids reading it); entry_timing_v1.jsonl 16.7 MB
  and spread_trail_v1.jsonl 20.4 MB (the RETRACTED 09-16 spread study's rows); precise_partial.jsonl 6 MB;
  student_cohort_cache.npz 6.7 MB. Readers now: none.
- xsp_quotes.jsonl (live, 9 rows, +2/day; durable copy ~/xsp_quotes.jsonl) - not UW, stays.
RECOMMEND keep the two v3 corpora (180 MB; the ledger reads one and both are rebuildable only from the
single-name archive that is going cold); delete superseded/, historical_corpus_2026-08-13/, the v1 rows
and the retracted-study jsonls after adding them to the research_data tar (-275 MB).

### 1.6 data/cache_uw

Exists, EMPTY (4 KB; recreated 2026-09-21 20:15 by src/unusual_whales_api.py:32 CACHE_DIR at import).
Nothing reads it on the VPS (the engine runs on GHA). Delete the directory.

### 1.7 data/harvest_inbox

162 MB, 101 files tracked in git: 59 candidates_*.jsonl (last 2026-09-22) and 42 fills_*.jsonl (still
written by fill_ledger.py; last 2026-09-24 15:11). Already in both .git histories (VPS 265 MB, GitHub
276 MB). Keep; ROADMAP item 4 (inbox retention pruning) closes as REJECTED - the inbox is frozen.

### 1.8 Small UW-derived leftovers

~/harvest-snapshots/archiver/ 19 MB (seven days of UW chain snapshots 2026-07-28..08-05, tracked, already
off-box; archiver.yml is manual-only) - keep. ~/uw_exit/finish.log 1.6 KB (the finisher's record) -
keep. ~/kitchen_sink_2026-09-18.tgz 5.8 MB - keep (or fold into the research tar). ~/val2209 367 MB is a
throwaway validation checkout from 22 Sep, still being written by a gate run at 22:14 UTC tonight - not UW
data; delete when idle. /tmp research scratch ~60 MB (settle.jsonl, nostop.jsonl, spyputs.pkl, verify_*).

## 2. The harvest shutdown

When the last label lands: every pollable open candidate has vertical_barrier_ts 2026-09-25 20:00:00 UTC.
poller.py:_poll_now polls 'standard' every run and 'reduced' only in the first quarter-hour;
harvest_labeler.label_path (line 38) writes 'vertical' on the first poll whose ts >= the barrier. The cron
fires at 20:00 UTC on Friday 2026-09-25, inside poller._market_open_now's 5-minute buffer, and the poll
lands ~20:00:15 - so the last labels are written Friday 2026-09-25 at 20:00 UTC (21:00 BST). Fallback if
that run misses: the first session run on Monday 2026-09-28 (13:30 UTC). The 53 poll_tier 'none' rows
never label, by design. Confirmation query (Saturday):
  sqlite3 data/harvest.db "select count(*) from candidates c left join labels l on
  l.candidate_id=c.candidate_id where l.candidate_id is null and c.poll_tier!='none' and c.occ_symbol
  is not null"  -> 0
The 21:30 UTC Friday snapshot then carries the finished pile off-box.

Retire after that (exact lines; all crontab edits are the owner's/the ship gate's, not this pass):
Crontab (crontab -l numbering, HOME= is line 1):
- line 2  `*/15 13-21 * * 1-5 bash .../scripts/run_poller_vps.sh` - remove. Also pause or delete the
  healthchecks.io check it pings (HEALTHCHECK_URL in .harvest_env) or it emails on silence.
- line 3  `30 21 * * 1-5 bash /home/poller/backup_snapshot.sh` - remove AFTER the Friday 21:30 push
  (check data/snapshot.log for "snapshot 20260925_2130").
- line 6  `5 22 * * 2-6 ... scripts/integrity_gate.py` - remove (it audits a frozen table).
- line 13 `15 22 * * 1-5 bash .../scripts/archiver_watch.sh` - remove.
- line 4  `*/15 13-22 * * 1-5 bash .../scripts/watchdog_vps.sh` - NOT removed; rewrite its stall test
  (lines 27-29: `git log origin/main -1 --format=%ct -- data/harvest_inbox/`) to the engine heartbeat
  data/last_cycle_ok (which scripts/engine_watch.sh already reads); keep its disk alarm and the
  watchdog_status.json stamp.
- line 7  `45 22 * * 1-6 bash .../scripts/landing_watch.sh` - keep; delete the poller-log grep and the
  snapshot-file check (the two lines under "weekday market jobs") and the integrity-gate block.
- line 14 evening_persist.sh - keep (it persists the court's output).
Workflows:
- .github/workflows/v10_lab.yml line 78 `UNUSUAL_WHALES_TOKEN: ${{ secrets.UNUSUAL_WHALES_TOKEN }}` -
  remove; line 102 `git add -f data/harvest_inbox/*.jsonl data/harvest_state.json` - remove (fills files
  then stop travelling; fill_ledger.py stays passive on the runner).
- .github/workflows/health-check.yml line 21 `UNUSUAL_WHALES_TOKEN` - remove (schema_harness skips UW).
- The harvest_scan call at sandbox_proactive_lab.py:3072-3073: LEAVE IT. It is a fail-open no-op with the
  feed off; removing it is a trade-path edit that needs test_harvest_passivity.py, and CLAUDE.md lines
  15-16 (the standing rule) still name the four harvest suites - retiring the logger needs the owner to
  amend that rule first. The suites cost nothing while the path is dormant.
Sentinel rows (scripts/freshness_sentinel.py CHECKS):
- line 71 ("harvest poller log", 21:00 weekdays) - remove.
- line 80 ("integrity gate", 22:05 Tue-Sat) - remove.
- line 82 ("archiver watch", 22:15) - remove.
- line 84 ("off-box backup", data/snapshot.log 21:30) - remove.
- line 89 ("off-box snapshot repo", git_commit 21:30 weekdays) - this is also the /halt channel's
  liveness proxy; once snapshots stop it pages every morning. Replace with a check that the kill-switch
  repo is pushable (the Sunday health-check canary already clones it) or retire it.
- lines 74-75 (the emptied "harvest data" / "evidence stores" comment headers) - tidy.
Docs (present tense must stop describing the machine):
- SYSTEM_ARCHITECTURE.md lines 40-196: file-map rows 47-49, the fail-open hook 52-75, the transport loop
  76-106, the database layer 107-145, the barrier machine 146-167, the test suite 168-196 - rewrite as
  "frozen 2026-09-25; the pile is a record"; line 8, 11-12, 24 (overview still says it scans UW flow);
  lines 293-297 (stale: keep=14 is keep=2 in poller.py:152; retention 30 is KEEP=5 in backup_snapshot.sh);
  line 301 already says frozen; line 309 (the cs_legs.db.gz snapshot claim - false).
- docs/feature_map/README.md the `harvest-transport.md` table row; docs/feature_map/harvest-transport.md
  whole file -> a RETIRED banner with the date, keep the Traps; vps-crons.md rows at lines 14 (poller),
  15 (watchdog premise), 19 (backup_snapshot) plus the integrity and archiver_watch rows;
  credit-spread.md:47; telegram-and-watchdogs.md:18; persist-and-merge.md:4, 12, 17, 27 (inbox and
  harvest_state merge); market-gate.md:4-5, 20, 23 quote the engine's own "no harvest, no inbox commit"
  line - leave until the engine's print changes.
- ROADMAP.md: item 4 (inbox retention pruning, line 86), 4b (NOT-NULL PKs on the live harvest.db, line
  90), 12 (free orthogonal sensors into the harvest payload, line 101), table row 22 (adaptive harvest
  cap, line 306), the darkpool sensor retry note (~line 458) -> close REJECTED with "harvest frozen
  2026-09-25".
- MOT: v11_mot_harness.py 6.10 adaptive-cap checks (lines 991-1005), the spread-cap skip-reason check
  (1038), the 6.10d frozen-window list (1068), 6.34 (1779-1781) - keep while harvest_logger.py exists;
  they are unit checks and cost nothing.
- scripts/restore_drill.sh - keep as a manual drill or retire with the snapshot.

What the 86k labelled candidates are still good for: a record of the dead premise (the input, the
features, the executable-basis outcome, for 59 sessions), which is what BREAKDOWNS and the REJECTED
roadmap rows point at; the only research value beyond that is the bid_path quote series (1.58M
15-minute NBBO snapshots on 86k single-name contracts), which no live or planned strategy needs. Keep the
455 MB file, keep the last snapshot off-box, spend no more machinery on it.

## 3. Disk - what grows, and 90 days out

Growing today:
- ~/harvest-snapshots/.git: +~125 MB per nightly snapshot (one every day this week because the polls
  change harvest.db; after Friday only on days a fills event lands, i.e. the Monday entries -> ~125
  MB/week, ~1.6 GB per 90 days). The same growth lands on the 2.5 GB GitHub repo that carries /halt.
- data/harvest.db: +2.8 MB/day until Friday, then ~0. harvest_backups: constant 866 MB (rotating 2).
- swing-trading-scanner/.git: 265 MB, +1-2 MB/day of "sandbox lab data" commits (~+0.15 GB/90 days).
- /var/log: 1.9 GB root-owned (journal dir 1.5 GB on disk vs 148 MB journalctl reports - an old
  machine-id's files; btmp 187 MB of failed-login records; auth.log 47 MB). Needs root to vacuum; growth
  not measured, assume +0.2-0.5 GB/90 days.
- data/daily_bars.db 5.7 MB (+~6 KB/day); xsp_quotes.jsonl +2 rows/day. Negligible.
Projection without the prune: 39 GB -> ~41.5 GB used in 90 days = ~85% of the usable 48.9 GB - the
watchdog's alarm line, reached at the end of the window.
Projection with the recommended prune: -15.7 GB (uw single-name rebuilt out), -0.87 GB (harvest_backups),
-0.79 GB (research_data big files), -4.0 GB (snapshots .git re-cloned shallow), -0.37 GB (val2209),
-0.27 GB (superseded corpora) = about 17 GB used (35%), growing ~0.3-0.6 GB per 90 days once the nightly
snapshot stops (the largest remaining vector is /var/log, which is the OS's).

## 4. Order of work (all GBP 0; owner's go on each)

1. Tonight or tomorrow: research_data tar.gz (209 MB) -> OneDrive, sha256 verified. Irreplaceable, unbacked.
2. Saturday 2026-09-26 after the Friday 20:00 UTC labels and the 21:30 push: retire the poller, snapshot,
   integrity gate, archiver watch, the five sentinel rows, the two workflow lines; rewrite the watchdog's
   stall test; docs, map and ROADMAP in the same commit (gate green, passivity suite run).
3. Any evening outside 13:00-22:00 UTC: stream uw_history.db as gzip parts (~7.6 GB) to OneDrive, verify,
   build the index/ETF slice on the VPS, verify per-ticker counts, delete the 20.5 GB file, delete
   harvest_backups, re-clone ~/harvest-snapshots shallow, delete data/cache_uw, val2209 and the superseded
   corpora. Then delete the stale 1.76 GB slice from OneDrive.
4. Fix the two false cs_legs.db.gz claims (credit-spread.md:47, SYSTEM_ARCHITECTURE.md:309).

Nothing in this pass touches data/cs_legs.db, the two paper books, the crontab or the live repo.
