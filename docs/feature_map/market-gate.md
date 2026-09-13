# Market gate

## What
Decides whether a scheduled cycle does anything. Closed means no orders, no exits, no harvest, no
inbox commit. It is the first thing a live cycle asks and the one bit that guards both entries and
exits, which is why it has a second opinion.

## Where
- `sandbox_proactive_lab.py:_market_is_open` - three retries against Alpaca `/v2/clock`, then the
  XNYS exchange calendar (`pandas_market_calendars`) decides; no creds -> closed; calendar
  unavailable -> closed.
- Called at the top of `sandbox_proactive_lab.py:run_scheduled_cycle` (`if live and not _market_is_open(creds)`).

## Exercise
- Offline: `./.venv/bin/python v11_mot_harness.py | grep "market gate"` (MOT 6.12 forces the clock
  call to raise and asserts the calendar's answer).
- Live: the first lines of any GHA run log (`gh run view <id> --log | grep -n "market"`).

## Healthy
- Closed: `market closed - no cycle: 0 orders, 0 exits, 0 harvest, no inbox commit`
- Clock down, calendar answering: `  market gate: clock API failing (HTTPError); calendar says OPEN ... - proceeding on the calendar`

## Evidence
- `data/last_cycle_ok` (UTC stamp + engine SHA) is written only by a successful cycle; the VPS
  watchdogs read it from `origin/main`.

## Checks
- MOT 6.12 "market gate: clock API failure -> exchange-calendar answer, not a blanket closed".

## Traps
- 2026-07-04 NO MARKET-OPEN GATE: a closed-market cycle could fire orders.
- 2026-09-11 (third entry) ENGINE BLIND FOR ~55 MINUTES: Alpaca clock returned 500, the fail-closed
  gate treated the session as closed, no exits ran. "Fail closed" must be read per consequence:
  closed-for-entries is safety, closed-for-exits is exposure.
