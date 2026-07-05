# Swing Trading — Project Memory

SYSTEM_ARCHITECTURE.md is the single source of truth for how this system works. Read it before doing any work in this repo. This file holds only the standing rules and deliberately carries no architecture description and no file lists — those live in SYSTEM_ARCHITECTURE.md and only there, so this file cannot drift.

Doc discipline: SYSTEM_ARCHITECTURE.md is strictly present-tense (what the code does now; the code wins; no future intent). ROADMAP.md is strictly future-tense (every item has a one-line acceptance criterion and a status: QUEUED / IN-FLIGHT / SHIPPED / REJECTED; it never claims something already exists). Graduation: when an item ships and its tests pass, the same commit flips it to SHIPPED in ROADMAP.md and writes its reality into SYSTEM_ARCHITECTURE.md; no item is ever silently deleted — it closes as SHIPPED or REJECTED with a one-line reason.

NORTH_STAR.md is the charter (mission, principles, risk constraints); it outranks persuasion and changes only by Savvas's amendment. Read it before proposing anything that alters strategy, risk, or spend. Standing owner decisions live in ROADMAP.md; do not re-litigate them without a NORTH_STAR amendment proposal.

Single engine: V10, on `main`, as of 2026-07-04. V9 was retired that day — the old Unusual-Whales-flow → Alpaca live engine and its workflows are gone. There is one branch, `main`; there is no separate sandbox branch anymore. Anything removed is recoverable from the `pre-v9-retire-*` and `archive/v10-research-sandbox-final` tags.

Standing rules (non-negotiable):
- £0 incremental cost — existing VPS, GitHub, Unusual Whales, and Alpaca only.
- EODHD does not exist for any purpose. Do not add, call, or reference it.
- Labels are bid-only and executable-price-only (entry_ref = ask at signal, never mid).
- Harvest passivity is inviolable: logging must never alter or crash the trade path. Re-run `test_harvest_passivity.py` after ANY change touching the harvest logger or path.
- Full suites + MOT green before any push: barrier labeler, passivity, harvester, poller, then the MOT.
- Never force-push. Never delete branches.

Date discipline (costs real money if wrong): before any time-sensitive call (CPI/FOMC/earnings/expiry/position), confirm the real date with `date` first.

Working with Savvas: he is not a coder and gave full coding control. Plain text, clickable multiple-choice over open questions, no markdown header/bold walls, no emojis, no unprompted comments/docstrings/tests. Flag disagreements with 2-4 alternatives, then execute his choice. Load the savvas-coding-style skill at session start.
