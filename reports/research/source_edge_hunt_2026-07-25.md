# New-source edge hunt — 2026-07-25

Research only (Lane A). Nothing here is deployed or recommended. Snapshot `harvest_20260724_2130`, 8,653 feature-bearing graded candidates.

**The pre-registered bar, set before any new feature was computed** (flow baseline measured 2026-07-25): best single-feature separation |d| = **0.541**, median |d| = **0.084**. Cohen's d: 0.2 small, 0.5 medium, 0.8 large.

The honest test is the OUT-OF-SAMPLE column: the champion is chosen on the early period, then its separation is measured on the later period it never saw. Searching more features always raises the in-sample maximum — that is the trap, not the result.

| family | features tried | best in-sample \|d\| | **same feature, out-of-sample** | median \|d\| |
|---|---|---|---|---|
| A. FLOW (current source, the baseline) | 82 | 0.501 | **0.580** | 0.094 |
| B. NORMALIZED (rank/z of the same features) | 157 | 0.520 | **0.594** | 0.080 |
| C. STRUCTURAL (dte, moneyness, premium shape) | 7 | 0.310 | **0.400** | 0.279 |
| D. PERSISTENCE (repeat flow, clustering) | 9 | 0.495 | **0.465** | 0.309 |

### The champion of each family

- **A. FLOW (current source, the baseline)** → `f.dark_pool.n_prints` — in-sample 0.501, out-of-sample 0.58 (HELD)
- **B. NORMALIZED (rank/z of the same features)** → `rank_day::f.dark_pool.n_prints` — in-sample 0.520, out-of-sample 0.594 (HELD)
- **C. STRUCTURAL (dte, moneyness, premium shape)** → `struct::spread_over_premium` — in-sample 0.310, out-of-sample 0.4 (HELD)
- **D. PERSISTENCE (repeat flow, clustering)** → `persist::signals_on_ticker_that_day` — in-sample 0.495, out-of-sample 0.465 (HELD)

- total features tested (counted as trials): **256**
- PBO across family champions: **0.0** CSCV over 20 partitions

## Verdict

Incumbent flow, out-of-sample: **0.580** (`f.dark_pool.n_prints`). A challenger must clear this by at least 0.10 to count as materially better.

- **No alternative family beat the incumbent flow materially out-of-sample.** This honest null is the result of the study.
  - B. NORMALIZED (rank/z of the same features) edged ahead by +0.015 (0.594 vs 0.580) — inside the noise band, not a finding.

The deeper reading: the strongest separator in the entire pile is the same one either way — dark-pool print count — and it is ALREADY one of the 82 features the Student trains on. The Student reaches an out-of-sample AUC of ~0.72 with all of them together and still cannot clear the cost bar. So the constraint is not that we are reading the wrong source; it is that separation of this magnitude, however sourced, is too weak to overcome the spread and decay measured on 2026-07-25.

One genuine positive worth recording: the champion separator HOLDS out-of-sample (it strengthens rather than decays), and the PERSISTENCE family — repeat flow on a name, which the current read ignores entirely — scores comparably to the best existing features from only 9 engineered signals. Neither is a breakthrough; both are honest inputs for a future pre-registered question rather than a reason to change anything now.

## Sources inventoried but NOT built tonight, and why

- **Dark-pool print concentration, insider clusters, GEX, dealer gamma, skew** — already collected and already measured. `dark_pool.n_prints` IS the 0.541 baseline; `alt_catalyst.insider_cluster_flag` scores 0.383. Building these as 'new sources' would rediscover what the pile already says.
- **SEC EDGAR Form 4 / 8-K** — genuinely free and genuinely external (SEC JSON API, no key, 10 req/s limit). Not built tonight: Form 4 carries a statutory T+2 filing delay, so the insider signal is stale by construction relative to a same-day options decision, and an `insider_cluster_flag` derived from it is already in the feature set at |d| 0.383. Worth a dedicated study only if a slower-horizon strategy is on the table.
- **FRED macro series, Google Trends, FINRA short interest** — free, but slow-moving relative to a ~1-day option horizon; short interest is already present as `fundamentals.short_ratio`.
- **EODHD** — excluded by standing rule.

## Honest limits

- ~3 weeks of one broadly calm regime; per-ticker z-scores rest on thin history.
- Outcome is the option's net return after costs, so a feature can predict direction well and still fail here if the move is too small to clear the spread.
- Every feature tested is counted above; a family that tried more features had more chances at a high in-sample maximum, which is why only the out-of-sample column is read.
- Nothing here changes the engine, the Student's labels, or any decision path.