# Probe funnel loosenings - design for review (2026-09-15)

Owner ruling 2026-09-15 00:50 BST after `reports/research/probe_funnel_2026-09-15.md`: keep the
$1,000 slot; ship only the loosenings the archive supports. Three changes, one commit, ship before
the 14:30 BST open.

## Change 1 - spread cap 2% -> 3%
- `fade_book_spec.json` `entry.max_spread_pct`: 2.0 -> 3.0. Read by `fade_book.spread_cap`, applied
  in `sandbox_proactive_lab.py:enter_proactive_set` (step 9 of entry-path.md) to the real quote of
  the chosen contract. The live pre-quote's 4% liquidity proxy is unchanged. The student pool's
  alert-spread filter (`probe.student.pool.spread_max_pct` = 2, the archive-universe definition
  the pickers were trained on) is unchanged. The fade path shares the cap (near-dormant).
- Evidence: every cell's t vs pool at alert spread <= 3% is unchanged or higher (BULL_DIP 3.96 -> 3.97,
  DIP_CONF_MILD 1.79 -> 1.93, DIP_CONVEXITY 2.02 -> 2.19, FOLLOW_CALLS 3.84 -> 4.17). Caveat (panel):
  the corpus measures the ALERT-time spread; the live cap gates a fresh quote at attempted entry,
  minutes to hours later. Correlated, not identical; with the pool's p90 alert spread at 2.6% the
  3% real cap leaves little room either way. Readers of `entry.max_spread_pct`: the entry path only
  (`sandbox_proactive_lab.py:enter_proactive_set`), the tuner's LIVE_WIRED key list (it will see the
  key as changed on 2026-09-15 and cool its spread candidates for 14 days), and two research scripts.
  Nothing in the harvest reads it; the ship grid runs the passivity suite regardless.

## Change 2 - DIP_CONVEXITY market gate: BEAR label -> SPY below its 50-day
- New module-level helper `sandbox_proactive_lab.py:_dip_convexity_regime_ok`: True when
  `fade_book.spy_regime()` is not None and the PRIOR-CLOSE readings (`fade_book.spy_prev_readings`,
  the d1_close basis of the archive cell, CORPUS LEAK #3) satisfy 50d distance <
  `probe.dip_convexity.regime_gate.spy_50d_dist_max` (spec key, default 0.0) AND 20d distance < 0.
  Fail-closed on no reading. Panel-corrected: the first draft read `spy_dist50()` (today's bar) and
  left the 20d term on an intraday metadata reading; both now sit in the helper on the archive's basis.
- The filter lambda becomes `_dip_convexity_regime_ok() and calls`; the loop's `_rg_need` map drops
  DIP_CONVEXITY, a `_dip_convexity_regime_ok()` gate replaces it, and the hoisted `_mkt20` check now
  serves DIP_CONF_MILD only, so both call sites share one definition.
- The ledger (`scripts/returns_ledger.py`) re-cuts the archive cell to the live cell
  (calls, reg < 0, sp < 0) and snaps DIP_CONVEXITY's exit to the engine's hardcoded wide default
  (`PROBE_EXITS`, -70/+80/0.30) when no `probe.tuning` override exists. Until now the cell omitted the
  20d confirmation and ran the BASE exit (BREAKDOWNS 2026-09-15).
- Evidence (live cell, wide exit): < -2: own +19.2/day t 3.33 on 56 days; < 0: own +8.75 t 3.72 on
  103 days, halves +5.3/+12.2. On BASE: +8.4 t 2.34 -> +3.8 t 2.70.
- CAVEAT (panel 2026-09-15): those are whole-cell numbers. In the $4-9.90 band the $1,000 slot can buy,
  the same cell is own -2.33/day (t 0.36) at < 0 and +1.88 (t -0.03) at < -2. The loosening keeps the
  cell's edge; it does not make the executable slice positive. Expect roughly flat live days from this
  seat, not +8.75; the court decides on live days. The threshold was picked from a 4-point in-sample
  grid (post-hoc); t is flat 3.3-3.8 and both halves are positive at every cut, so a fluke is unlikely,
  but it is not a holdout.
- Also: `probe_name` absent -> a probe keeps the full one-per-underlying rule (fail-closed), MOT 6.23.

## Change 3 - probes freed from other strategies' older positions on the same name
- `sandbox_proactive_lab.py:ticker_blocked` gains `probe_name`; for a probe, a record blocks the
  underlying only if (a) it belongs to the same strategy (`probe_strategy`, else `book`), or (b) it
  was entered today (UTC), or (c) it is a pending entry order on the name (unchanged). Non-probe
  callers keep the old rule. The contract itself stays guarded downstream by the occ_collision
  rule ("one record per contract, ever"), which is what the old 5-day cross-book rule existed for.
- Call site passes `probe_name=_ACTIVE_PROBE.get("name")` (set by the roster loop before every
  probe attempt; the student seat sets it too).
- Panel-corrected: the roster loop ALSO pre-filtered names before `enter_proactive_set` through
  `_open_tk` (any probe record of any age, any book <= 5 days), which made the ticker_blocked change
  dead on arrival. `sandbox_proactive_lab.py:_roster_open_sets` now builds (same-day names, any
  book) and (name -> strategies holding it); the loop skips a name if it is same-day or if THIS
  strategy holds it; the student seat skips same-day names and any name a STUDENT_* record holds.
- Concentration watch item (panel): up to one $1k slot per strategy on a name; the court's
  per-strategy evidence becomes correlated on shared-name days. Paper-only; revisit before any
  live-capital conversation (an owner-visible "N books on ticker" digest line is the cheap monitor).
- Evidence: 71 of the day's candidate-name skips were "one-per-underlying" against other
  strategies' positions, the control's above all (QQQ 10, SPY 7, NVDA 7, SLV 7, IBIT 7).
- Risk accepted: up to one $1k slot per strategy on the same underlying (seven books) instead of
  one per underlying. Each probe's evidence is its own trades vs the control on the same days.

## Guards
- MOT 6.23: live spec cap is 3.0; the gate helper passes MILD/BEAR with SPY below its 50d, fails
  above it and on no reading; both call sites use the helper and the BEAR label is gone; the
  held-name rule (other strategy older -> not blocked; same strategy -> blocked; same-day PENDING ->
  blocked; non-probe -> old rule); the ledger cell equals the live cell and its exit equals
  `PROBE_EXITS`.
- Drill scenario 8: the helper under a patched regime cache (MILD below 50d passes, MILD above
  and BULL stand down).
- Verify chain: feature-map lint, drill, MOT, suites, gate; `returns_ledger.py --update-map`
  re-cuts the DIP_CONVEXITY tokens before the performance-map lint.

## Not in this change
The price band (owner's call, declined for now), the engine_watch cancelled-run row, the
three-minute fixed cost per run, research scripts that carry their own copy of the old cell
(`scripts/capture_ratio.py`, `scripts/masters_vs_seats_sim.py`, `scripts/agent_tests.py`).
