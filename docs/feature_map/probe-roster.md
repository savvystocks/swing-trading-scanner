# Probe roster

## What
The wide experimental net: every roster strategy trades live on paper every day, $1,000 a lot,
tagged `book: PROBE` and `probe_strategy: <name>`, judged by the Friday court against the control.
Owner decision 33 (2026-09-10) focused it to seven: EXEC_BASELINE (the control), FOLLOW_CALLS,
BULL_DIP, DIP_CONF_MILD, DIP_CONVEXITY, WINNER_PROFILE, CREDIT_SPREAD_W (the weekly XSP credit
spread, in `fivek_probes.py`), plus the STUDENT seat when `probe.student.enabled` is true.

## Where
- The roster tuple list and each strategy's filter lambda: search `("FOLLOW_CALLS", lambda md, c:`
  in `sandbox_proactive_lab.py:run_scheduled_cycle`; the loop that runs it starts at the
  `# PROBE ROSTER v3` comment in the same function.
- Rotation: the start index rotates by cycle so tail probes get lead slots; the attempt budget is
  10 sensor sweeps per cycle (`_att`) and `_PROBE_MAX_ATT = 4` per probe; two entries per cycle max.
- Live pre-quote: `sandbox_proactive_lab.py:_live_spread_pct` quotes the alert contract before any
  sweep; > 4% or no quote skips the name for the whole roster without spending an attempt.
- Regime gates: BULL_DIP needs BULL, DIP_CONVEXITY needs BEAR, DIP_CONF_MILD needs MILD
  (`fade_book.spy_regime`); calls-only set `_CALLS_ONLY`.
- Per-strategy tuning: `sandbox_proactive_lab.py:_tuned` reads `probe.tuning.<name>` from the spec
  (size_usd, struct, band); `probe.per_strategy_max_per_day` = 8.
- Trigger-contract override: `_PROBE_CONTRACT["c"]` makes `build_legs` return the alert's own
  contract (DIP_CONF_MILD, BULL_DIP_X, the student seat); `_ACTIVE_PROBE["name"]` stamps the record.
- Weekly structures: `fivek_probes.cycle` (CREDIT_SPREAD_W, self-settling).

## Exercise
- `gh run view <id> --log | grep -n "PROBE\[\|probe\[\|probes:"` on any session cycle.
- Offline: `./.venv/bin/python scripts/regime_drill.py` routes each regime's entry path with
  externals faked.

## Healthy
- `  PROBE[FOLLOW_CALLS] entered NBIS (hypothesis slot - not fade evidence)`
- `  probes: 0 entries this cycle - 6 of 10 attempts used, 3 name(s) pre-skipped on live spread, ...`
- `  probe[EXEC_BASELINE] skip NBIS: trigger_contract fail-closed: no live quote / crossed / spread>2% / ask outside 4.0-9.9`

## Evidence
- Records in `proactive_sandbox_logs.json` (`book: PROBE`, `probe_strategy`); day means in the
  Friday court (`scripts/sunday_boundary.py`), the scoreboard (`scripts/trajectory_scoreboard.py`).

## Checks
- MOT 6.10e roster focus; MOT dimension 2 routing; drill scenarios 1-5.

## Traps
- 2026-09-01 ROTATION SENSOR-COST BLOWUP: every attempt is a full sensor sweep; unbudgeted rotation
  blew the 8-minute GHA envelope and successive runs cancelled each other.
- 2026-09-09 CONTROL STARVED THE ROSTER: the control burned all attempts on spread-dead names.
- 2026-09-10 (third entry) ROSTER STARVATION, STRUCTURAL FIX: per-probe ceiling 4 + live pre-quote.
- The tuner's incumbent pool for every fixed strategy is `pricey_4_9`; the court's clock restarts
  on `probe.tuning.<name>.applied`.
