# Probe funnel loosenings - review panel (2026-09-15, before the ship)

Two independent reviewers (model: Sonnet), each briefed with the feature map, the HEAD -> patched
diffs, the design (`reports/probe_loosening_design_2026-09-15.md`) and the evidence report
(`reports/research/probe_funnel_2026-09-15.md`). Lenses: (1) execution path and data honesty;
(2) operations, risk and the owner's six adversarial checks. Both returned SHIP-WITH-CHANGES.
Every CRITICAL and HIGH finding was applied before the ship; the rest are dispositioned below.

## Applied

| # | Severity | Finding | Fix |
|---|---|---|---|
| R2-1 | CRITICAL | The roster loop pre-filters candidate names through `_open_tk` (any probe record of any age, any book <= 5 days) BEFORE `enter_proactive_set`, so the `ticker_blocked` softening never saw the blocked names: Change 3 was dead on arrival for the roster loop and the student seat. | `sandbox_proactive_lab.py:_roster_open_sets` builds (same-day names, any book) and (name -> strategies holding it); the loop skips a name only if it is same-day or if THIS strategy holds it; the student seat skips same-day names and names any STUDENT_* record holds. MOT 6.23 tests the helper and asserts the loop and the seat use it. |
| R2-2 | CRITICAL | `_dip_convexity_regime_ok` read `fade_book.spy_dist50()` (today's bar) while the archive cell is prior-close (d1_close, CORPUS LEAK #3); the 20d confirmation sat on an intraday metadata reading. Live admission on a different basis than the evidence. | The helper now reads `fade_book.spy_prev_readings()` for BOTH the 50d and the 20d; the lambda's intraday 20d term is removed and the hoisted `_mkt20` check serves DIP_CONF_MILD only. MOT 6.23 and drill scenario 8 poke `dist50_prev`/`dist20_prev` and prove today's bar is ignored. |
| R1-1 | CRITICAL (framing) | The design cited the whole-cell +8.75/day for DIP_CONVEXITY without the report's own price-band caveat: in the $4-9.90 band the slot can buy, the cell is own -2.33/day (t 0.36). A court reader would be miscalibrated. | The caveat is now in the design, the performance map's Traps, and the report's verdict; the threshold's post-hoc nature is stated. |
| R1-2 | MEDIUM-HIGH | `ticker_blocked(probe=True, probe_name=None)` defaulted to the MOST permissive reading (only same-day records blocked). | A probe without a name keeps the full one-per-underlying rule (fail-closed); MOT 6.23 covers the no-name path. |
| R2-6 | MEDIUM | `DEFAULT_EXITS` mirrored only DIP_CONVEXITY though `PROBE_EXITS` also carries BULL_DIP_X: the class the BREAKDOWNS lesson names was patched by instance. | Both mirrored; MOT 6.23 compares every key of `PROBE_EXITS`. |
| R2-4 | MEDIUM-HIGH | The spread-cap evidence is on ALERT-time spread; the live cap gates a fresh quote at attempted entry. | Stated in the design and the report as directional, not a measurement of the live cap. |
| R1-3 | MEDIUM | The DIP_CONVEXITY threshold sweep lacked the post-hoc disclosure the price-band section carries. | Added to the report. |

## Verified by the reviewers, no defect

- `occ_collision` ("one record per contract, ever") reads the book fresh on every call and covers
  PENDING records, so no two strategies can land on one contract; same-cycle stacking is also
  stopped by the loop's own `_open_tk.add` after each success.
- `_ACTIVE_PROBE["name"]` is set immediately before every `enter_proactive_set(..., probe=True)`
  call, including the student seat, and reset in `finally`.
- `spy_regime()` and the `_REGIME` readings are written together in one successful branch, so the
  `spy_regime() is None` guard is a reliable staleness proxy.
- "Entered today (UTC)" is a safe boundary: the session (13:00-21:00 UTC) never straddles midnight.
- The spec keys nest correctly and the helper reads them.

## Dispositioned, not changed

| # | Severity | Finding | Disposition |
|---|---|---|---|
| R2-3 | HIGH | Concentration: up to one $1k slot per strategy on one name (seven books plus the student), same direction for the calls-only seats; correlated per-strategy evidence on shared-name days. | Accepted for paper (owner ruling), written into the design as a watch item; an owner-visible "N books on ticker" digest line is the cheap monitor and is owed before any live-capital conversation. |
| R2-5 | MEDIUM | Blast radius of `entry.max_spread_pct` not shown in the mirror. | Grepped on the VPS: the entry path (`enter_proactive_set`) is the only engine reader; the tuner lists it as a LIVE_WIRED key (it will treat the cap as changed on 2026-09-15 and cool its spread candidates for 14 days); two research scripts read it; the harvest does not. The ship grid runs the passivity suite regardless. |
| R2-7 | LOW-MEDIUM | Ship-chain ordering (`--update-map` before the performance-map lint) relies on the operator. | The ship script runs the ledger re-cut before `verify_engine.sh`; the lint would fail otherwise, which is the enforcement. |
| R1-4 | LOW-MEDIUM | Importing `returns_ledger` inside the MOT changes cwd/sys.path at import. | The MOT always runs from the repo root; noted, not changed. |
| R1-5 | LOW | `DEFAULT_EXITS` is a second literal rather than an import of `PROBE_EXITS`. | Pinned by MOT 6.23 across every key (the BREAKDOWNS lesson's second option); importing the engine into the ledger was judged heavier than the check. |
| R2-8 | LOW | The lambda kept an intraday 20d term. | Removed (see R2-2). |
| R2-9 | LOW | Research scripts carry the old cell. | Disclosed in the design; the ledger is the only source the map and the memory point to. |

## Verdict

SHIP after the fixes above, through the standard chain (feature-map lint, drill, MOT, suites, gate)
with the ledger re-cut run first. Both reviewers' full outputs are in the session transcript of
2026-09-15; this file carries what was acted on.
