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
- 2026-09-14 THE ONE-LOT SCALE-OUT WALL: the V10 grammar's SCALE_OUT_50 cannot sell half of one
  contract; the stage stayed initial, the trail never armed, the backstop stayed at -50% while HOOD
  gave back +369 -> +145. A one-contract leg now arms the trail instead and the rule is re-evaluated
  in the same cycle. Grep `1-lot scale-out impossible` in a cycle log to see it fire.
- 2026-09-14 (second entry) RETIRING A PROBE SWITCHED OFF ITS SETTLE SWEEP: `vrp_probe.py:cycle` and
  `putw_leg.py:weekly_cycle` returned early when disabled, and the ^XSP window was ten days. Settles
  now run regardless of enabled with a 120-day window; the sentinel's "expired legs still open" row
  is the alarm.
- 2026-09-15 THE RESERVED CONTRACT: `sandbox_proactive_lab.py:_retire_stop` trusted the record's
  `backstop.retired` flag, so a stop that was still resting kept the contract reserved
  (qty_available 0) and every close was rejected before it reached an order id - three positions,
  one expiring in three days, looping silently for hours. The sweep now reads the broker
  (`sandbox_proactive_lab.py:_resting_sells`) and a reserved contract alerts once
  (`sandbox_proactive_lab.py:_note_close_failure`, `sandbox_proactive_lab.py:_qty_available`). MOT 6.26.
- A close that fails has THREE modes, not one: no bid (park the corpse), reserved contract (cancel the
  resting order and retry), and UNKNOWN because a broker read failed. Unknown is treated as blocked -
  the first draft of the 2026-09-15 fix let a failed `_qty_available` fall through to the bid branch,
  which is the silent loop it was written to kill (panel finding, caught before the ship).
- Alerts on a blocked close are once per record per DAY, and always when expiry is <= 1 day away: a
  physically settled option left open through Friday is ASSIGNED into shares, which this engine does
  not manage (`_record_leg_occs` is OCC-keyed and would never see the stock position).
