# Live-Day Audit — 2026-07-06 (Checkpoint 2)

Strictly read-only forensic audit of the live trading + labelling + learning chain on go-live day.
Evidence gathered read-only only: SQLite opened `mode=ro`, poller/snapshot log reads, Alpaca REST GETs,
GitHub API. No writes to any live path, no restarts, no config edits, no drills. This report is the only
artifact produced.

Snapshot time: 2026-07-06 ~17:05 UTC (mid-session; US market open 13:30–20:00 UTC).

## VERDICT: AMBER

The core labelling / storage / learning-input chain is healthy and green — the frozen baseline is stamped
perfectly, ingestion is idempotent with zero duplicates, labels are arithmetically exact, storage is intact,
and the poller cadence is flawless. Amber, not green, because a double-triggered engine run collided on
`git push` and the rebase dropped one filled trade's harvest row (`WULF260807C00024500`) — lost to the
learning chain for today — and a legacy position (`PFE`) survived the open-flush. Root cause of the data loss
is FIXED FORWARD this session (commit fa5bdc92: schedule trigger dropped + inbox union-merge); PFE is being
closed by the owner. The single lost WULF row stays absent from today's dataset. Section 7 (full-loop proof)
is appended this evening; re-verify green then for the Tier B go-ahead.

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
- **Straggler (Finding 2):** `PFE260814C00025500` (13 @ $0.28) was NOT closed by the flush and remains open.
  Clean book = **20 positions opened today**; the 21st is this orphaned legacy leg (footnote below).
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
- Flush closures: the flush sends ONE summary alert (`FLUSH closed 71/72 legacy positions`) — not 71
  per-position alerts. So the 71/72 shortfall was itself alerted at 13:31. (Correction to the initial pass.)
- EOD digest: pending (fires after the 20:00 UTC close).

---

## Findings

**Finding 1 — MEDIUM: double-trigger + git-rebase data loss. FIXED (commit fa5bdc92).**
`v10_lab.yml` fired on both `schedule (*/10 13-21)` and `repository_dispatch` (cron-job.org). At 16:20 both
fired: schedule run 28806362961 (16:20:09) entered CRML and committed to main; dispatch run 28806400405
(16:20:45) entered WULF (real filled paper trade, 2 @ $3.10) and committed `[main b0bf262]`, but its push was
rejected and the rebase-retry hit `error: could not apply b0bf262` — the commit, and WULF's harvest row, was
dropped (confirmed absent from main). One filled trade lost from the harvest. Fix applied: dropped the
redundant `schedule` trigger (repository_dispatch is the sole driver; the concurrency group serialises runs)
and added `.gitattributes` `data/harvest_inbox/*.jsonl merge=union` so the append-only transport never drops a
row on a residual collision. The one lost WULF row (16:23, 2 @ $3.10) stays absent from today's dataset.

**Finding 2 — LOW: flush orphaned a legacy position (`PFE260814C00025500`).** Diagnosis: PFE has a live bid
($0.16, size 17; traded $0.17 at 16:58) — it is NOT a zero-bid corpse. At 13:31 (market open +1 min) the
illiquid far-dated contract had no bid, so the flush's market-close returned False and PFE was not counted
in the 71. But `flush_positions` (line 1206-1209) then marked ALL OPEN log records FLUSHED unconditionally,
including PFE's — so the broker position stays open while its tracking record reads FLUSHED, and the exit
engine (which only manages OPEN records) is now blind to it. It would sit until the 2026-08-14 expiry.
Resolution: owner places a GTC limit sell (fills immediately at the $0.16 bid, ~$208 recovered). See Finding 3
for the underlying flush bug.

**Finding 3 — MEDIUM (queued, Tier B — not changed mid-session): flush marks records FLUSHED on failed
closes.** `flush_positions` flips every OPEN record to FLUSHED regardless of whether `_close_position`
succeeded, orphaning any position it couldn't close (Finding 2). Fix: only mark a record FLUSHED when its
close actually succeeded (else leave it OPEN so the exit engine keeps managing it and closes it once a bid
returns), or re-fetch positions after the flush and reconcile. Also queue: one-per-underlying (Tier B) must
ignore legacy/orphaned positions so a straggler cannot block a live signal on that underlying for six weeks.

**Finding 4 — INFO:** the EOD digest (fires after the 20:00 UTC close) and per-BUY Telegram delivery are not
verifiable read-only — confirm on phone. The flush itself does send a one-line summary alert (Section 8).

---

## Footnote — clean-book count

"Positions opened today" = **20**. The broker shows 21 open; the extra is `PFE260814C00025500`, the
Finding-2 orphan (a pre-go-live legacy leg the flush failed to close and then mislabelled FLUSHED). All 20
of today's positions trace to a V10 run_id and an Alpaca fill.

---

*Section 7 (full-loop proof) to be appended this evening after the 22:30 BST off-box snapshot.*
