# RUNBOOK — operating the system

Plain-English operations. For WHAT the system is, read SYSTEM_ARCHITECTURE.md; for WHY, NORTH_STAR.md;
for the gates, LIVE_GATE.md. This file is HOW: the buttons, the alerts, the weekly rhythm, recovery.

## Your weekly rhythm (the 5 hours)

- **Monday:** glance at the weekend's brain reports (committed to `reports/`): the weekly edge report,
  discovery convergence, the Student verdict, the Council shadow, the Governor scoreboard, the
  Treasurer/brake shadow. Nothing needs action unless the Governor lists an organ "awaiting owner
  review" or a report flags AMBER/RED.
- **Any day:** the phone alerts fire on every buy, every sell, watchdog stalls, integrity failures,
  reconciliation divergence, and owner-command confirmations. Variance is loud; edge is quiet — judge
  the four numbers only against the weekly report's expected bands, never against a single day.
- **When an organ reaches ELIGIBLE_FOR_OWNER:** that is the only promotion you make. Read its track
  record, then, if you agree, set `owner_promoted: true` for that organ in `governor_registry.json`
  and commit. Nothing else can grant live authority.

## The controls (Telegram, from your phone)

Authenticated to your chat only; commands from any other chat are ignored and logged.

- `/halt` — pause NEW entries from the next cycle. Exits, backstops, and harvesting continue. Use if
  something looks wrong and you want to stop opening risk while you look.
- `/resume` — lift the halt (also clears a pending flatten).
- `/flatten` — arm a one-time close of every open paper position at the next open-market cycle. Also
  halts entries. Use `/cancelflatten` to abort before it fires.
- `/status` — report the current halt/flatten flags.

The command poller runs on the VPS every 15 minutes and writes the flag into the snapshots repo; the
engine reads it each cycle. Allow up to a cycle for a command to take effect.

## The alerts and what to do

- **Buy / sell alert:** informational. No action.
- **Watchdog stall (silent-death alarm):** the poller has not committed inbox data during market
  hours. Check the VPS is up (`ssh` per the access note) and that `poller.log` is advancing. The
  engine keeps trading regardless — the watchdog guards the DATA pipeline, not the trade path.
- **Integrity gate RED:** the nightly gate found a data fault (row loss, dup ids, null storm,
  out-of-session signals). The offending rows are quarantined; the brain will not train on them.
  Read `reports/ops` / the alert and decide whether a snapshot restore is warranted.
- **Reconciliation divergence changed:** the engine's open records and the broker's positions
  disagree by a NEW amount. Usually a dropped trade record from a rare push collision — check the
  positions vs `proactive_sandbox_logs.json`.
- **Nothing fired but you're unsure:** silence is the primary enemy by design, so the system is built
  to be loud. If it's quiet, it believes it's healthy — but the weekly report is the ground truth.

## Recovery

- **"Are the backups real?"** Run the restore drill:
  ```bash
  bash scripts/restore_drill.sh <path-to-snapshot-or-snapshots-dir>
  ```
  It rebuilds a working system in a clean directory from the off-box backup and prints PASS/FAIL. It
  proved 6/6 on 2026-07-23.
- **VPS access (read-only audits):** see the access note in memory; open the DB `mode=ro` only.
- **Old box / new box:** the poller runs on the new VPS. If it dies, the sparse GHA schedule is the
  engine's fallback heartbeat — the engine keeps trading; only harvesting pauses.
- **A bad day tempts a change:** don't. NORTH_STAR: no strategy or parameter change during a drawdown
  without harness evidence. The moment of maximum temptation is the moment of minimum trust in
  judgment. Parameters change only at a Sunday boundary, by the harness, committed alone.

## Promoting the school (the only way authority moves)

1. The Governor marks an organ ELIGIBLE_FOR_OWNER after 6 consecutive GREEN weeks.
2. You read its record and, if convinced, set `owner_promoted: true` in `governor_registry.json`.
3. To arm gate-mode, set `school_mode: gatekeeper` in the tunables — but only after LIVE_GATE.md's
   full ladder is satisfied (Student + Council promoted, backstop dependency resolved, off-state MOT
   green). A RED or a macro-brake day drops it back to `off` within one cycle.
4. `school_mode` stays `off` today. The frozen V10 engine trades alone, under the spread cap.

## The frozen engine is never "fixed"

The 24-hour take-profit hold is deliberate. Every-event phone alerts stay. The V10 rules engine's
parameters are frozen while the student learns. These are not bugs; leave them.
