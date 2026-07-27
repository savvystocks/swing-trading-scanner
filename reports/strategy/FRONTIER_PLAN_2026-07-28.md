# AGGRESSIVE FRONTIER PLAN — maximise honest edge-discovery rate — 2026-07-28

Planning report + first study (executed tonight). Aggression = more games tested faster, each killed
fast on pre-registered conditions. Never daily tuning on noise; never winners-only reading. Anchor:
NORTH_STAR.md. All £0 unless flagged; EODHD excluded by standing rule everywhere.

## 3. THE FIRST STUDY — run tonight: insider purchases (NEW feed) — KILLED by pre-registration

Step zero passed: UW `/insider/transactions` paginates to real history (120k filings fetched,
2026-03-03→07-27; deeper exists) and carries BOTH `filing_date` (disclosure) and `transaction_date`
— entry was taken at the first close after **disclosure**, never trade time. Kill condition written
before any outcome: *dead if the mean-return lower bound ≤ 0 in both calendar halves OR the halves
disagree in sign.*

Seven-week readout (first pass): promising — solo-insider 10-day drift +2.05%/+0.71% across halves,
hit 61–65%, early half clearing both tripwire bars. Rather than waiting weeks for run 2, the fetch
was deepened to five months the same night. Result on 1,525 independent events (318 clusters, 1,207
solos, liquidity-floored, SPY-adjusted, winsorized means):

| cell | early half (Mar–mid-May) | late half (mid-May–Jul) |
|---|---|---|
| cluster, +10d | −0.53% (LB −1.58%), hit 54.0% | +2.19% (LB +0.72%), hit 64.3% |
| solo, +10d | **−0.86% (LB −1.48%)**, hit 43.8% | **+1.64% (LB +0.97%)**, hit 59.5% |
| both classes, +3d | negative | ~flat |

**The halves disagree in sign → KILLED on this window, exactly per the pre-registration.** The
7-week "promise" was the tail of a longer story that flips: insider buying marked falling knives in
March–April and marked winners in June–July. That is regime-dependence, not an edge — and
regime-conditioning two 2.5-month halves would be the overfitting trap wearing a lab coat. Knowledge
base entry #7. Cost: one evening, £0. This is the kill-fast discipline working at full speed —
the same vein would have consumed three weeks of harvest-forward hope without the deep fetch.

## 2. STEP ZERO RESULTS (the new feeds, measured tonight)

| feed | history | disclosure timestamp | verdict |
|---|---|---|---|
| insider `/insider/transactions` | 5+ months, paginates properly | `filing_date` ✓ | STUDIED → killed (above) |
| congress `/congress/recent-trades` | fixed 199-row window (~6 weeks) | `filed_at_date` ✓ (3-day lag visible) | thin; harvest-forward accumulation + weekly study once ≥300 events |
| analyst `/screener/analysts` | current window only (~4 days) | `timestamp` | harvest-forward only; sensor-block candidate |

## 1. THE PARALLEL QUEUE, DATED (work dates; the market's verdict is undateable)

| probe | hypothesis (pre-registered) | tripwire/kill | status + date |
|---|---|---|---|
| Insider drift (10d) | disclosure-time purchases carry drift | sign-consistent halves, LB>0 & hit LB>52% | **KILLED 07-28** (#7) |
| VRP existence | implied vol > subsequent realized on our universe | VRP present in ≥60% of tickers, both halves | **Wed 07-29** (owned IV features + yfinance) |
| Analyst-revision drift | upgrades carry multi-day stock drift | same bars as insider | harvest-forward: sensor block spec **Sun 08-02**, first read ~08-23 |
| Congress disclosure drift | disclosed congress buys drift at 10–20d | same bars; DISCLOSURE time only | accumulate (199/week window) → first read when ≥300 events, est. ~08-16 |
| PEAD 10–20d | post-earnings drift on owned sensors | same bars | **Sat 08-01** |
| Premium-selling paper lane | short defined-risk spreads harvest VRP after real costs | lane spec to owner **Sun 08-02** if Wed's existence check passes; first cost-true read ~20 fills (~08-16) | conditional |
| Debit/credit spreads on the pile | none — PARKED: structure cannot rescue a missing signal (proven 07-25) | reopens only with a live directional signal | parked |
| Multi-day stock horizon (general) | any surviving signal, replayed at 10–20d | inherits that signal's bars | needs only yfinance daily closes — **no EODHD**; the separate swing system's EODHD world stays separate per standing rule |

## 4. FASTEST EDGE-PER-DAY, next move

VRP existence (Wednesday) is now the highest-leverage open probe: strongest documented prior on the
board, data fully owned, two days to a read — and it feeds the only frontier that doesn't depend on
finding directional skill at all (selling time premium rather than buying direction).

## 5. DAILY LEARNING LAYER (accumulate daily, decide weekly, never tune daily)

Logged DAILY (already live): every graded outcome with its game tag (sample_tier/skip_reason), real
fill costs both ends (ledger), API health, spread-cap bite, reconcile state. Added by this plan:
congress + analyst snapshots appended daily to the feed store (VPS cron, append-only jsonl, £0) so
harvest-forward feeds accumulate history from today even before their studies exist.
Extracted WEEKLY (Sunday, unchanged): retrains, gates, discovery angles, drift checks, strategy
one-pager. No parameter moves outside Sunday boundaries; no daily reading of daily noise.

## 6. KILL-FAST DISCIPLINE (per live probe)

- VRP: dead if implied ≤ realized on ≥50% of universe in either half.
- Congress: dead if sign-inconsistent halves at first ≥300-event read (insider's lesson, same bars).
- Analyst: dead if first 3 accumulation weeks show hit LB < 50% at 5d.
- PEAD: dead if sign-inconsistent halves on the owned-sensor window.
- Premium lane (if approved): dead if 40 real fills show net premium capture ≤ 0 after measured costs.
Each kill is one evening's verdict, logged, and frees the slot for the next game.

## 7. KNOWLEDGE BASE (the ledger of CONCLUSIONS — 7 entries)

1. Buying flow-followed options: **dead** (hit 2–20% vs 57% bar; four independent reads).
2. Re-reading the same features (normalize/structural/persistence): **dead** (nothing beats incumbent OOS; persistence was a threshold mirage, 07-26).
3. Flow→stock direction, 1–5d: **dead** (47–49%, both runs).
4. 8-K events, 3d: **dead** (d≈0.09, calendar-disjoint OOS).
5. Dark-pool accumulation: **real but too weak** (stable 0.31–0.40 vs 0.68 bar, 5 vintages).
6. Structure-as-rescue (exits/holds/spreads on a signal-less long): **dead** (14 structures, all negative; ~7–10% bleed at zero cost).
7. Insider-purchase drift, 3d & 10d: **dead on this window** (sign flips between halves; regime artifact, 07-28).
Each entry carries its evidence file in reports/research/. This list IS the system's accumulated
knowledge: seven games eliminated at ~zero cost, zero real money burned on any of them.

## 8. FINISH LINE (unchanged, fixed 07-27 — gates never shrink to dates)

M0 candidate: OOS separation d>0.68 or stock tripwire (return LB>0 AND hit LB>52%) on ≥300
independent bets, sign-consistent halves, no vintage explosion → M1 twice consecutively → M2 full
gates on cost-true outcomes (Wilson LB > its own break-even, PBO ≤0.20 corrected-CSCV, DSR >0.5,
beats incumbent, all trials counted) → M3 Governor ladder (6 GREEN weeks per rung) → M4 owner switch
+ live-capital gate (P(halt) review, backstop proven, £1–5k first). NORTH_STAR pace ambition stands;
dates bind work, never verdicts.
