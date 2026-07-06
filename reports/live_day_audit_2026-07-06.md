# Live-Day Audit — 2026-07-06 (Checkpoint 2)

Strictly read-only forensic audit of the live trading + labelling + learning chain on go-live day.
Evidence gathered read-only only: SQLite opened `mode=ro`, poller/snapshot log reads, Alpaca REST GETs,
GitHub API. No writes to any live path, no restarts, no config edits, no drills. This report is the only
artifact produced.

Snapshot time: 2026-07-06 ~17:05 UTC (mid-session; US market open 13:30–20:00 UTC).

## VERDICT: AMBER

The core labelling / storage / learning-input chain is healthy and green — the frozen baseline is stamped
perfectly, ingestion is idempotent with zero duplicates, labels are arithmetically exact, storage is intact,
and the poller cadence is flawless. One real defect blocks a clean green: a double-triggered engine run
collided on `git push`, and the rebase dropped a filled trade's harvest row, so that executed trade
(`WULF260807C00024500`) is invisible to the learning chain. A single legacy position (`PFE`) also survived
the open-flush. Both are bug-fix-class. Recommend fixing the commit-collision data loss before the Tier B
go-ahead.

---

## 1. Ingestion chain (GitHub → VPS → DB) — GREEN

- Scan cycles today: 20 candidate-producing run_ids, 13:41:50Z → 16:51:31Z, ~10-min spacing, no gap > 12 min.
- v10_lab GHA runs today: 26 (13:01→17:01); the extra runs are pre-open no-ops, the flush cycle, and one
  double-fire (Finding 1).
- Inbox commits on main today: 22 sandbox commits, 21 touching today's inbox file.
- Inbox rows: **main (source of truth) 865 rows / 21 executed**; **VPS pulled copy 828 rows / 20 executed**.
  The 37-row / 1-executed gap is the 17:01 cycle committed to main but not yet pulled (next poller run
  ingests it) — expected lag, not loss.
- DB candidates today: **828**, across 20 run_ids, first 13:41:50Z, last 16:51:31Z.
- Reconciliation: DB 828 == VPS inbox 828; VPS inbox has 828 distinct candidate_ids (0 internal dups);
  DB has 0 duplicate candidate_ids. **Idempotency intact, no duplicates.**
- VPS pull health: last `git pull` 17:00:01Z (poller pulls every cycle); ingest lines idempotent
  (`46 new / 2383 present` → `71 new / 2429` → `44 new / 2500`).

## 2. The frozen baseline, live for the first time — GREEN

- params_hash today: **`82c5e6bf661f` × 828 — exactly one value. Nulls: 0.**
- Premium bands, harvested: `>=50k` 632, `25–50k` **196**, `<25k` 0.
- Premium bands, executed: `>=50k` 19, `25–50k` **1**.
- Volume push CONFIRMED live: 196 harvested and 1 executed in the new 25–50k source-premium band —
  impossible under the old 50k floor.

## 3. Sampling tiers — GREEN

- sample_tier today: topn 279, random **5**, executed 20, none 524 (total 828).
- Random 5 ≥ 5 threshold met. (The 10/day upgrade is Tier B and unmerged — its absence is not flagged.)
- Harvester dedup (topn/random): **0 violations** — no scanned contract has more than one full-payload row.
- Note: `SLV260807C00058000` has two executed rows (14:41 and 15:21). These are two real re-entries, i.e. the
  known absence of the one-per-underlying backstop (Tier B, unmerged) — not a dedup failure.

## 4. Trading reconciliation (read-only vs Alpaca) — AMBER

- Orders today: 93 (71 sell, 22 buy); 92 filled, 1 new (unfilled — `VZ`, below). All attributable to a V10
  run_id; no non-V10 orders.
- Flush: **71 sells in an 8-second burst 13:31:33–13:31:41Z** (at the open). Engine self-report:
  `FLUSH complete: 71/72 positions closed, cool-off cleared, log reset`. `FLUSH_PENDING` removed from main
  (commit d8d3f58). The flush cycle entered no trades (first buy 13:41, the following cycle). Correct.
- **Straggler (Finding 2):** `PFE260814C00025500` (13 @ $0.28, uPL −$182) was NOT in the flush's 71 closes
  and remains open. Current book = 21 positions = 20 today-entries + PFE. So the book is not strictly
  "today's only."
- Executed reconciliation vs main inbox (source of truth): **20 of 21 Alpaca buy fills have a harvest
  executed row.**
  - `VZ260807P00041000` — harvest-logged but unfilled on Alpaca (the 1 "new" order; the engine logs at
    submission, so a resting limit shows as executed in the harvest). Expected.
  - **`WULF260807C00024500` — filled on Alpaca (2 @ $3.10, 16:23:07Z) but has NO harvest row anywhere
    (Finding 1). This executed trade is invisible to the learning chain.**

## 5. Labelling engine (the poller, mid-flight) — GREEN

- Poller runs today: **17**, exact 15-min cadence 13:00:01Z → 17:00:01Z, no gaps.
- Errors / 429 / backoff / DB-lock in poller.log: **0**.
- Quote source: 100% Alpaca (last run 792/792 resolved via Alpaca), 0 UW fallback. Stale rate **5.38%**
  (266 / 4945).
- bid_path: 4945 rows, 2544 distinct candidates (full open cohort), most recent poll 17:00:04Z.
- Labels resolved today by outcome: vertical 1428, up 35, down 35 (backlog from last week resolving at the
  vertical barrier + intraday ±30% / −50% touches). All-time adds censored 262.
- Manual label verification — `DELL260710C00427500` (outcome down): entry_ref 16.85, down_level =
  16.85 × 0.50 = **8.425**. bid_path 15:00 $15.21 → 16:00 $10.51 → 17:00 $7.94. At 17:00, bid $7.94 ≤ 8.425
  → down touch. realized_return = (7.94 − 16.85) / 16.85 = **−0.5288**, stored −0.528783. **Exact.**

## 6. Storage and durability — GREEN

- `PRAGMA integrity_check`: **ok**.
- `PRAGMA journal_mode`: **wal**. No stray `-wal` / `-shm` between runs (clean checkpoints).
- Lock errors in either process log today: **0**.
- Local rolling backup: `data/harvest_backups/harvest_20260706.db` present (poller `db.backup()` each cycle,
  keep=14).
- Off-box snapshot: mechanism proven (Friday `harvest_20260703_2130.db.gz` pushed to harvest-snapshots),
  armed for tonight. Crontab: `*/15 13-21 * * 1-5` poller, `30 21 * * 1-5` snapshot push.

## 7. The learning chain — full-loop proof — PENDING (this evening)

Runs after tonight's off-box snapshot lands in harvest-snapshots (~21:30 UTC / 22:30 BST). Will manually
dispatch `brain_weekly` once (reads only the snapshot photocopy) and verify: dataset rows > 0 with today's
date range, populated tier/outcome tables, features > 0, report renders. UNDERPOWERED verdicts are correct
and expected at one day of data. Full-loop proof appended here once done.

## 8. Alerts — AMBER (partial)

- BUY: 20 entries logged (`ENTERED … | LIVE_PAPER`). `send_alert` is invoked on entry; transport proven live
  (brain_weekly send 2026-07-05 + MOT dim5). No telegram send errors in today's runs. But `send_alert` is
  silent-on-success and the chat can't be read read-only, so there is no independent per-alert delivery
  receipt — confirm on your phone.
- Flush closures: SILENT — no per-position SELL / autopsy alerts in the flush cycle (avoids 71-message spam).
- EOD digest: pending (fires after the 20:00 UTC close).

---

## Findings

**Finding 1 — MEDIUM (gates Tier B): double-trigger + git-rebase data loss.**
`v10_lab.yml` fires on both `schedule (*/10 13-21)` and `repository_dispatch` (cron-job.org). At 16:20 both
fired: schedule run 28806362961 (16:20:09) entered CRML and committed to main; dispatch run 28806400405
(16:20:45) entered WULF (real filled paper trade, 2 @ $3.10) and committed `[main b0bf262]`, but its push was
rejected and the rebase-retry hit `error: could not apply b0bf262` — the commit, and WULF's harvest row, was
dropped. The row never reached main (confirmed: main inbox has no WULF call). Net: one filled trade
permanently missing from the harvest. Recurs on any commit collision, so it also silently caps learning-chain
completeness. Proposed fixes (bug-fix-class):
- (a) Add `.gitattributes` with `data/harvest_inbox/*.jsonl merge=union` (and the state files) so concurrent
  appends union-merge instead of conflicting — no row is ever dropped, even on collision. Root fix.
- (b) Remove the redundant `schedule` trigger from v10_lab.yml (repository_dispatch is the reliable primary)
  so two runs never fire in one slot. Reduces collision frequency; hygiene.
- (c) Both (a) + (b).

**Finding 2 — LOW: flush straggler.** `PFE260814C00025500` was not in the flush's 71 closes ("71/72") and
remains open. The exit engine still tracks it. Fix: a verify-all-closed retry in the flush, or a one-off
manual close of PFE.

**Finding 3 — INFO:** the flush emits no alerts; the EOD digest and per-BUY Telegram delivery are not
verifiable read-only (confirm on phone). A one-line flush-summary alert would be a small enhancement.

---

*Section 7 (full-loop proof) to be appended this evening after the 22:30 BST off-box snapshot.*
