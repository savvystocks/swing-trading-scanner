# ENGINE FEATURE MAP

This directory maps every working part of the trading system from the point of view of someone who
has to verify it: what it is, where it lives (file and function), how to exercise it for real, what a
healthy run prints, where its evidence lands, which regression checks guard it, and the traps that
have already bitten (from BREAKDOWNS.md). One file per subsystem. Read the file for a subsystem
BEFORE reviewing, changing or diagnosing it, then RUN its verification command rather than reasoning
from the code. This map is the maintained verification source for the engine; `scripts/feature_map_lint.py`
(MOT 6.18) fails the gate when a cited file or function no longer exists. Its healthy line is
`feature map lint: OK (N citations resolved)`; a failure names the file and the citation.

## Where the truth lives
- The live code is the VPS checkout: `ssh -i ~/.ssh/vultr_poller poller@64.176.178.15`, repo
  `~/swing-trading-scanner`, always at `origin/main`. The laptop checkout under OneDrive is weeks
  stale and must never be read for engine facts or edited.
- The engine itself runs on GitHub Actions (`.github/workflows/v10_lab.yml`) every 10 minutes,
  13:00-21:00 UTC on weekdays, from `main`. The VPS runs the poller, the watchdogs, the evidence
  chain and the court from cron.
- `fade_book_spec.json` is edited only on the VPS. `SYSTEM_ARCHITECTURE.md` is present tense,
  `ROADMAP.md` is future tense, `BREAKDOWNS.md` is append-only and every fix adds its entry.

## Baseline preconditions for any verification
- On the VPS, in the repo root, with `. ./.harvest_env` sourced when a job needs Alpaca or UW
  keys, and `./.venv/bin/python` for anything that imports sklearn or pandas.
- The market gate decides whether a cycle does anything; outside 13:30-20:00 UTC on a trading day
  a live cycle prints `market closed - no cycle` and exits. Use the drill and the MOT for
  out-of-hours verification; they fake every external.
- Nothing here places a real order: Alpaca paper only, keys in GitHub secrets and `.harvest_env`,
  never in chat.

## Subsystems
| file | subsystem | first-line verification |
|---|---|---|
| market-gate.md | is the session open | MOT 6.12 |
| candidate-scan.md | UW flow rows -> ticker candidates, pricey pool, student pool | MOT 6.17 pool checks |
| probe-roster.md | the seven-strategy probe loop, rotation, attempt budget | a cycle log's `probes:` line |
| student-seat.md | the pickers: pool, rank, select, budget, export | drill scenarios 6-7, MOT 6.11/6.17 |
| entry-path.md | enter_proactive_set: guards, legs, repricing, PENDING, routing | drill scenarios 1-4, MOT 6.14 |
| exit-engine.md | exits, backstops, VOID, autopsy | MOT dimension 3, 6.13 |
| reconcile.md | pending-intent and orphan roll-calls, stale orders, log integrity | MOT 6.14 (both) |
| persist-and-merge.md | the GHA persist step, resolver, union guard | `merge_logs.py --selftest` |
| harvest-transport.md | counterfactual harvest -> inbox -> VPS poller -> labels | `test_harvest_passivity.py` |
| evidence-and-court.md | corpora, tuner, glide, court, scoreboard, student research | Friday logs |
| vps-crons.md | every cron slot, its log, its freshness row | `scripts/freshness_sentinel.py` |
| telegram-and-watchdogs.md | notifications, owner commands, dead-man watchdogs, auto-rollback | watchdog logs |
| gate-and-ship.md | how a change is verified and shipped | `bash ~/vps_ship_grid.sh` |

## Conventions for the files
Every subsystem file has the same seven sections so an agent can find the same thing in the same
place: What, Where, Exercise, Healthy, Evidence, Checks, Traps. Citations are backticked
repo-relative paths, optionally followed by a colon and a function name; the lint resolves each
one against the checkout. Paths outside the repo (VPS logs under /home/poller) start with a slash
and are not checked. Quote log lines verbatim; they are what an
agent greps for. When a breakdown lands, add its trap here in the same commit as its fix.
