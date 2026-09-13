# Exit engine

## What
Every cycle, before any entry, every OPEN record's legs are marked against the broker and the exit
rule decides HOLD, SCALE_OUT, CLOSE_STOP, CLOSE_TRAIL, CLOSE_EXPIRY or VOID. Broker-side backstop
stops sit under every position so a blind engine still has a floor. No same-day sells (owner rule
2026-08-12; `/flatten` exempt).

## Where
- `sandbox_proactive_lab.py:manage_open_positions` - the pass: excursion update per leg
  (`leg_path`: mfe_pct, mae_pct, stage, missing_cycles), the decision from
  `sandbox_proactive_lab.py:manage_exit` (FADE and V10 grammars: stop -50, trail arms +50,
  giveback 20% by default; probe-specific values via `_tuned`), closes via
  `sandbox_proactive_lab.py:_close_position`, the autopsy `sandbox_proactive_lab.py:run_trade_autopsy`.
- Untracked legs: a position that vanished after being tracked books worst-known; a record whose
  leg was NEVER tracked (no mfe_pct) after five position-less cycles is VOIDED
  (`action VOID_NEVER_FILLED`, return None, status VOID) - never a fake -100%.
- Backstops: `sandbox_proactive_lab.py:manage_backstops`, `_submit_backstop`, `_backstop_level`,
  `_capture_backstop_fill` (a filled stop is booked from the broker fill), `_retire_stop`
  (confirmed cancel before any engine close; MOT 6.12 confirmed-cancel).
- Parked corpses and expiry: CLOSE_EXPIRED_WORTHLESS books -100% only when the broker position is
  gone after expiry; PARKED records never block a ticker.

## Exercise
- `./.venv/bin/python v11_mot_harness.py | grep -n "Dimension 3\|VOID\|backstop\|stop cancel"`.
- Live: `gh run view <id> --log | grep -n "EXIT\|CLOSE_\|HOLD\|backstop\|SAFETY STOPS"`.

## Healthy
- `  SAFETY STOPS SET: 3 position(s)` telegram / log line after new fills.
- `CLOSE_STOP_LOSS` lines carry the reason `-53.7% <= -50% hard stop`.
- A `VOID: never filled` line for a limit that never became a position.

## Evidence
- `leg_exits` per record (occ, closed_at, return_pct, reason, action, closed_ok); the autopsy
  markdown (`proactive_autopsy_log.md`); the daily digest.

## Checks
- MOT dimension 3 (31 checks: state machine, autopsy); 6.12 confirmed-cancel; 6.13 superseded
  order ids; 6.13 VOID rule; 6.15 partial fills; the defensive `leg_path` read.

## Traps
- 2026-06-09 STOP BLEW THROUGH; 2026-07-02 NAKED 72-POSITION WEEKEND (no working exits) -> backstops.
- 2026-08-17 EXIT ENGINE CRASHED EVERY CYCLE; 2026-09-10 EXIT ENGINE DOWN 30 MINUTES (KeyError
  mfe_pct on a slow fill) -> defensive reads, `missing_cycles` reset.
- 2026-09-12 A NEVER-FILLED ORDER WAS BOOKED AS A -100% LOSS -> the VOID rule.
- A blind window (gate outage) means no exits; the backstops are the only floor then.
