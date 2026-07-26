# Flow persistence — head-to-head through the harness — 2026-07-26

## FINAL VERDICT: REJECTED — the run-1 pass was an artifact of the newest two days

> The head-to-head below passed all three pre-registered conditions on the 07-24 snapshot. A vintage
> sweep run immediately afterwards found the advantage exists in **exactly one snapshot out of five**
> — the newest — and is absent or reversed in every earlier vintage. The selection count across the
> nested sequence runs 0 → 4 → 1 → 3 → **54**, meaning one additional trading day took the strategy
> from three selections to fifty-four. That is a threshold sitting on the edge of a noisy probability
> distribution, not an effect. **Logged as measured-and-rejected.** Details in the vintage section.
>
> The run-1 result is left below, unedited, as the record of what a single snapshot said — and as a
> worked example of why the pre-registration demands two consecutive runs.

Research only (Lane A). Nothing deploys from this. Snapshot `harvest_20260724_2130`, 8,653 feature-bearing graded candidates. Same Student, same seed, same PurgedKFold splits; the only difference is nine causal persistence features.

> **Provenance.** An earlier non-causal version of these features (whole-day aggregates counting signals that arrive AFTER the decision point) scored 0.465 separation on 2026-07-25. That figure was lookahead-contaminated and is void. Everything below uses expanding-window features that see only what had already happened.

## The comparison

| metric | base (82 features) | + persistence | moved? |
|---|---|---|---|
| OOF weighted AUC | 0.7227 | 0.7226 | worse or flat |
| selections made | 26 | 54 | |
| independent bets (n_eff) | 12.0 | 7.0 | |
| selection hit rate | 0.5878 | 0.8023 | |
| **hit-rate 95% lower bound** | 0.3231 | 0.4358 | UP |
| **net return after costs** | -0.0792 | 0.1934 | UP |
| PBO | 0.2315 | 0.1300 | within 0.20 |
| deflated Sharpe | 0.0000 | 0.0000 | |

The bar every selection must clear is the empirical cost-inclusive hurdle: **0.5944**.

## Pre-registered tripwire (written before this was computed)

- (a) net return rises: **PASS** (-0.0792 → 0.1934)
- (b) hit-rate lower bound rises: **PASS** (0.3231 → 0.4358)
- (c) PBO stays within 0.20: **PASS** (0.1300)
- (d) all three repeat on a second consecutive weekly run: **not yet evaluable (run 1 of 2)**

### Run-1 verdict (superseded): **PROVISIONALLY MEETS (a)-(c); needs run 2**

## VINTAGE SWEEP — the test that killed it

The same head-to-head on five snapshots. **These are NESTED** (07-24 contains 07-23 plus one more
trading day), so this is not independent replication — it answers a narrower question: has the
advantage been present all along, or did it only appear in the newest rows?

| snapshot | rows | base net (n) | persistence net (n) | independent bets | holds? |
|---|---|---|---|---|---|
| 07-16 | 4,551 | — (0 selections) | — (0 selections) | 0 | no result |
| 07-20 | 5,998 | +0.3799 (3) | +0.3256 (4) | 2 | **persistence WORSE** |
| 07-22 | 6,281 | — (0 selections) | +0.4117 (1) | 1 | meaningless (1 trade) |
| 07-23 | 7,240 | −0.0908 (39) | −0.0245 (3) | 3 | better, but on 3 trades |
| **07-24** | 8,653 | −0.0792 (26) | **+0.1934 (54)** | 8 | **HOLDS** |

**HOLDS in 1 of 5 vintages.** The advantage exists only in the newest snapshot.

The selection-count sequence — **0, 4, 1, 3, 54** — is the damning number. Adding a single trading
day to 07-23 multiplied the strategy's trade count eighteen-fold. A real effect does not do that; a
calibrated probability sitting just under the hurdle, nudged over it by new data, does exactly that.

### A null test that must not be mistaken for evidence

A seed sweep (four seeds on the 07-24 snapshot) returned **identical results to four decimal places**
and was initially recorded as "4/4 HOLDS". It is worthless: `HistGradientBoostingClassifier` with
`early_stopping=False` and n < 200,000 performs no validation split and no binning subsample, so the
fit is fully deterministic and `random_state` is inert — verified directly (max probability
difference between seed 1 and seed 999: exactly 0.0). That sweep ran the same computation four times.
It is recorded here so the mistake is not repeated, not as support for anything.

Provisional only. A second consecutive weekly run must reproduce all three before this becomes a governed Student feature-set change at a Sunday boundary.

## Skeptical diagnostic (run because n_eff FELL while n rose)

Selections rose 26 → 54 but independent bets fell 12.0 → 7.0. That is the signature of a model
picking clustered repeats — mechanically what persistence features would cause, since they reward
tickers that keep reappearing. So the result was attacked before being believed.

The 54 selections are **8 ticker-days across 7 tickers**:

| ticker-day | selections | wins | mean net |
|---|---|---|---|
| PLTR 07-21 | 1 | 1 | +0.543 |
| SPY 07-13 | 13 | 12 | +0.419 |
| JNJ 07-20 | 1 | 1 | +0.339 |
| NVDA 07-07 | 11 | 8 | +0.155 |
| NFLX 07-21 | 3 | 2 | −0.043 |
| SPY 07-08 | 10 | 5 | −0.076 |
| SPCX 07-22 | 14 | 6 | −0.194 |
| NOW 07-07 | 1 | 0 | −1.041 |

**Robustness — leave-one-cluster-out:** the +0.193 weighted net stays positive with ANY single
ticker-day removed (8 of 8). Worst case, dropping the best cluster, is +0.111. So it is **not** one
lucky day — a genuine and better-than-expected result.

**But the sample is 8 independent bets that split 4 winners / 4 losers.** The positive mean comes
entirely from the winners being larger, not more numerous. Eight bets cannot distinguish a real edge
from luck at any useful confidence.

**And it would still be REJECTED by the Student's actual acceptance gates.** The tripwire tested
IMPROVEMENT, which it passed; the gates test SUFFICIENCY, which it fails:
- gate 1: hit-rate lower bound 0.4358 vs the 0.5944 hurdle — still far below;
- gate 3: deflated Sharpe 0.0000.
A better Student is not yet an acceptable Student.

**Live-constraint reality check:** the engine enforces one position per underlying, so the tradeable
version of this is ~**8 trades**, not 54 — the 80% headline hit rate is 54 contracts drawn from 8
decisions. On decisions, it is 4 from 8.

**AUC did not move** (0.7227 → 0.7226). Persistence did not make the model better at ranking; it
changed which candidates cross the threshold, concentrating them on repeat names.

## What the model did with them

- persistence features surviving correlation clustering into the model: **6** of 9 — `persist::n_prior_signals_3d`, `persist::hours_since_last_on_ticker`, `persist::is_repeat`, `persist::direction_agreement`, `persist::prior_signals_on_ticker_today`, `persist::premium_rank_so_far_today`
- dropped as redundant: `persist::n_prior_signals_1d`, `persist::same_direction_repeats_3d`, `persist::ticker_share_of_prior_day_premium`
- trials counted — base 396, persistence variant 399

## Honest limits

- ~3 weeks of one broadly calm regime; repeat-flow history per ticker is correspondingly thin.
- The outcome is the option's net return after executable costs, so a feature can carry real information about direction and still fail here if the move cannot clear the spread.
- Both arms share the same snapshot, seed and splits, so the comparison is like-for-like; what it cannot rule out is that a different model family would use these features better.
- Nothing here changes the engine, the Student in production, or any decision path.