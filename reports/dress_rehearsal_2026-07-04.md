# Dress rehearsal — 2026-07-04 (Sat)

Weekend drill of the single-engine V10 system ahead of the Monday 6 July open. Prime rule held throughout: **the rehearsal was incapable of touching production** — every drill write went to scratch artifacts (copied DB, drill-prefixed files, a temp `_drill_alert.yml`) that were deleted, and the Alpaca orders endpoint was checked after every phase.

**Alpaca paper account was unchanged the whole time: 173 orders / 72 open positions at baseline and after every phase. Zero orders placed.** (Market closed all weekend; next open Mon 2026-07-06 09:30 ET.)

---

## Phase 1 — the real failure, triaged and fixed

**Symptom:** run `90a9e77` of `v10_lab.yml` failed with "No jobs were run" — a GitHub **startup_failure** (0s duration, reported against the `push` event because GitHub validates the workflow file on every push).

**Root cause:** the V9-retirement rename dropped the `ref: v10-research-sandbox` line from the checkout step but left a **childless `with:`** behind, making the workflow file invalid. (The file was also CRLF; GitHub tolerates that, but I normalized it to LF.)

**Fix:** removed the empty `with:`, LF-normalized — commit `862793d1`. **Proof:** dispatched the workflow (run `28717261651`) — jobs started and it exited **green**. A valid workflow with no `push` trigger produces no run on push, so the startup-failure runs stopped.

### The `on:` block, line by line (final)
```yaml
on:
  schedule:
    - cron: "*/10 13-21 * * 1-5"   # every 10 min, 13:00-21:59 UTC, Mon-Fri only
  workflow_dispatch:               # manual / API dispatch; carries the `flush` input
    inputs:
      flush:
        default: "false"           # flush=true => flush_positions instead of a cycle
  repository_dispatch:
    types: [run-sandbox]           # external cron (cron-job.org) can POST to drive exact cadence
```
- `schedule: */10 13-21 * * 1-5` — fires every 10 min, hours 13–21 **UTC**, **day-of-week 1-5 = Mon–Fri only**. In July (EDT, UTC−4) the session is 13:30–20:00 UTC, fully inside this band; the lab's own market-open gate trims the pre/post-open fires to the live session.
- **Why the "Saturday run" happened:** it was **not a scheduled fire** — the schedule is Mon–Fri and excludes Saturday. It was the startup-failure validation record created when I *pushed* on Saturday. Once the file was valid, no Saturday run appears.
- **Push trigger:** there is **none**, and there should be none — confirmed. The only triggers are schedule + manual dispatch + external repository_dispatch.

### Safety gap found and fixed (was not in the brief, but the prime rule demanded it)
`sandbox_proactive_lab.py` had **no market-open gate at all** — on a closed market a normal cycle or a flush could still fire paper orders (it relied only on UW returning no flow). Added `_market_is_open()` (Alpaca `/v2/clock`, **fail-closed** on no-creds/API-error). The cycle now no-ops cleanly when live+closed; flush converts to a dry statement. Commit `80e4ea5d`. MOT extended 73→**74** (+1 check: flush-on-closed-market is a dry no-op).

---

## Phase 4 — Monday 6 July timeline (BST · UTC · ET)

July = EDT (UTC−4); BST = UTC+1. Market open **14:30 BST / 13:30 UTC / 09:30 ET**, close **21:00 BST / 20:00 UTC / 16:00 ET**.

| BST | UTC | ET | Expected event | If it hasn't happened by… check |
|---|---|---|---|---|
| 14:00 | 13:00 | 09:00 | Pre-open GHA cycle + poller fires → **no-op** (market-closed gate) | (expected silence; not a fault) |
| **14:30** | **13:30** | **09:30** | **Market opens.** First real `v10_lab` cycle runs; first VPS poller poll (5-min buffer → polls from 13:25 UTC) | by **13:40 UTC**: `gh run list --workflow=v10_lab.yml` — is a cycle running? If not, check cron-job.org / dispatch manually |
| **14:30** | **13:30** | **09:30** | **Savvas dispatches the flush** (one-time, at the open): closes the 72 legacy positions | `gh run view <id> --log` shows "flushed …"; escalate: re-probe Alpaca positions |
| 14:40 | 13:40 | 09:40 | First inbox commit `candidates_20260706.jsonl` on main (if UW flow present) | by **14:00 UTC**: v10_lab run log — did `scan_candidates` return anything? UW reachable? |
| 14:45 | 13:45 | 09:45 | First VPS ingest: poller pulls main, ingests new candidates, writes first `bid_path` rows | by **14:15 UTC**: `tail data/poller.log` on VPS — pull ok? ingest count? |
| 14:30–15:00 | 13:30–14:00 | 09:30–10:00 | First **BUY alert** on Savvas's phone (when a cycle enters a trade) + the FLUSH alert | by **14:00 UTC**: was a trade entered (needs flow + gates)? Check Telegram secrets / `_notify` |
| 21:00 | 20:00 | 16:00 | Market close. Last in-session cycle + poll | — |
| 22:30 | 21:30 | 17:30 | Nightly off-box DB snapshot → private `harvest-snapshots` repo | by **22:00 BST**: `crontab -l` / `~/harvest-snapshots` on VPS |

**The flush command (run at 14:30 BST / 13:30 UTC / 09:30 ET):**
```
gh workflow run v10_lab.yml --ref main -f flush=true
```
Dispatch it right at the open — the ~1-min GHA spin-up means `flush_positions` executes just after `is_open` flips true, so the closes are real (not dry). Every order that day, including the flush closes, is attributable to a `v10_lab` run.

---

## Phase 5 — go / no-go

| Component | Result | Fix (commit) | Re-run / proof |
|---|---|---|---|
| Memory → single-engine | **PASS** | 3 memory files + MEMORY.md index | 0 stale two-branch rules |
| `v10_lab.yml` startup failure | **FIXED** | empty `with:` removed (`862793d1`) | dispatch `28717261651` green, jobs started |
| Trigger audit (`on:` block) | **PASS** | — (no push trigger; Mon–Fri cron correct) | shown above |
| Market-open gate (safety add) | **ADDED** | `_market_is_open` on cycle+flush (`80e4ea5d`) | battery + MOT 74/74 |
| `v10_lab` normal dispatch | **PASS** | — | run `28717261651`: deps install, secrets `***`, gate "market closed - no cycle", **0 orders, no junk commit** |
| `health-check` | **PASS** | EODHD injection dropped | run `28717329028` green, **EODHD=0 occurrences**, 11/11 schemas OK |
| Alert path (Telegram) | **SENT — awaiting your phone confirm** | temp `_drill_alert.yml` (now deleted) | run `28717465319`: `telegram_ok: True` via real `src.telegram.send_alert` |
| Flush plumbing (closed market) | **PASS** | dry-guard (`80e4ea5d`) | run `28717485553`: "DRILL/CLOSED: would flush 72 position(s), 0 orders sent" + list; **0 orders** |
| VPS plumbing | **PASS** | — | `run_poller_vps.sh` exit 0, pulled main, weekend no-op; both crons armed |
| VPS full-chain drill | **PASS** | `poller.py --drill` (`773dc17a`) | on a **copy**: ingest → **503 bid_path → 503 barrier evals → 503 labels**; real `harvest.db` byte-identical (mtime/size/counts unchanged); all drill artifacts deleted |
| Off-box snapshot | **PASS** | — | `harvest_20260703_2130.db.gz` pushed (`e66e685`) |
| Zero-orders safety (every phase) | **PASS** | — | 173 orders / 72 positions, unchanged throughout |

**One item is human-gated:** the alert path is server-side confirmed (`telegram_ok: True`) but only *passes* once Savvas confirms the drill message arrived on his phone.

### The honest remainder — Monday-only observables no weekend drill can reach
- **Live UW flow content.** The weekend UW call returns stale/empty flow; Monday's is live market-wide. *Healthy at the open:* `scan_candidates` returns real ranked candidates during RTH (visible in the v10_lab run log and the committed inbox).
- **Real order fills.** Paper orders only fill against a live book. *Healthy:* the flush closes fill (positions drop toward 0), and new cycle entries appear as Alpaca positions with BUY alerts.
- **Real quote-driven labels.** The drill used canned bids; live, the poller polls **real Alpaca option NBBO**. *Healthy:* `bid_path` rows carry real bids and the first up/down labels resolve as prices move (verticals resolve at the week's last session).
- **The gate flipping open.** *Healthy:* v10_lab cycles stop printing "market closed - no cycle" from 13:30 UTC onward and begin harvesting.

Commits this session: `862793d1` (YAML fix), `80e4ea5d` (market-open gate), `49129dc8` (temp drill workflow, since deleted), `773dc17a` (poller `--drill`). All pushed; battery green before every push (barrier 8/8, passivity 8/8, harvester 14/14, poller 8/8, MOT 74/74).
