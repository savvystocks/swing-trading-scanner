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
- Pools: generic probes take `candidates[:12]` (the top of the scan; until 2026-09-15 the fade book
  reserved the top two, decision 42); FOLLOW_CALLS and WINNER_PROFILE `_FULL_CANDS[:16]`; DIP_CONF_MILD
  `_PRICEY_CANDS[:14]`; FADE_WHALE `_WHALE_CANDS[:8]`.
- Rotation: the start index rotates by cycle so tail probes get lead slots; the attempt budget is
  10 sensor sweeps per cycle (`_att`) and `_PROBE_MAX_ATT = 4` per probe; two entries per cycle max.
- Live pre-quote: `sandbox_proactive_lab.py:_live_spread_pct` quotes the alert contract before any
  sweep; > 4% or no quote skips the name for the whole roster without spending an attempt.
- Regime gates: BULL_DIP needs BULL and DIP_CONF_MILD needs MILD (`fade_book.spy_regime`);
  DIP_CONVEXITY needs the PRIOR-CLOSE SPY below its 50-day and 20-day (`sandbox_proactive_lab.py:_dip_convexity_regime_ok`,
  spec `probe.dip_convexity.regime_gate`, fail-closed; the BEAR label until 2026-09-15); DIP_CONF_MILD keeps
  the hoisted intraday SPY-below-20d check; calls-only set `_CALLS_ONLY`.
- Held-name pre-filter: `sandbox_proactive_lab.py:_roster_open_sets` - a name with a record entered today
  is skipped for every probe; a name another strategy holds from an earlier day is skipped only for that
  strategy; the student seat also skips names any STUDENT_* record holds. `ticker_blocked` repeats the
  rule inside `enter_proactive_set`; `occ_collision` keeps one record per contract.
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
- 2026-09-15 THE PROBE FUNNEL (reports/research/probe_funnel_2026-09-15.md): the $1,000 slot confines every
  cell to the $4-9.90 band, where the archive shows no edge (all five cells flat or negative on own return;
  every one positive above $16). Loosening regime or dip conditions adds fills that lose; only the spread
  cap (3%), DIP_CONVEXITY's band (SPY below 50d) and the held-name rule were loosened (decision 41, MOT 6.23).
- 2026-09-15 (decision 42) the fade book's shape check inside `sandbox_proactive_lab.py:enter_proactive_set` runs
  AFTER `sandbox_proactive_lab.py:collect_metadata`, so the fade loop sweeps ~5.5 unheld names per cycle before
  rejecting them as not fade-shaped, for a book with no entry since 2026-08-20. Owner ruling (decision 43): the
  regime stand-down is hoisted before the sweep (`fade_book.py:stood_down`, MOT 6.25, drill scenario 9); the
  full shape check still runs on BEAR days. Two "inert" spec blocks have live readers (early_strength, momentum) and
  `entry.max_spy_dist_pct` is tuner-wired: do not delete them as dead weight.
