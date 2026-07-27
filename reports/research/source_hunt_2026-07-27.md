# New-source signal hunt — 2026-07-27

Research only (Lane A). Nothing deploys. The question: does an alternative £0 source separate winners
from losers, before the trade, materially better than the flow's own out-of-sample baseline?

**The pre-registered bar:** the incumbent flow's best out-of-sample separation, |d| = **0.580**
(`dark_pool.n_prints`, measured 2026-07-25), plus a 0.10 materiality margin → a challenger needs
**OOS d > 0.68**. All comparisons like-for-like out-of-sample; in-sample numbers shown only to expose
decay.

## Verdict up front

**Honest null, twice.** Dark-pool accumulation is the most statistically solid feature family yet
measured — stable champion across five vintages, 1,400–2,500 independent bets — and still lands at
OOS d ≈ 0.33–0.40, well below the incumbent it was meant to beat. EDGAR 8-K item types, on ~7,000
independent stock events over eight weeks, separate at OOS d ≈ 0.03–0.12 — essentially nothing.
Neither source is worth building a strategy around. Combined with the 2026-07-25 hunt (normalized /
structural / persistence families) and the stock-horizon study, every alternative read now points the
same way: **the missing edge is a signal problem, not a sourcing, filtering, or machinery problem.**

## Step 1 — feasibility (all £0 confirmed; EODHD excluded by standing rule)

| source | dataset buildable? | rows / window | limits |
|---|---|---|---|
| dark-pool accumulation | YES from owned harvest (built tonight) | 4.5k–8.7k option-outcome rows, 5 vintages, 3 wks | raw block only 35% covered (sparse-payload budget); accumulation features reach 77–87% |
| EDGAR 8-K | YES, free SEC APIs (built tonight) | **8,030 filings, 3,799 tickers, 8 weeks**, 100% item codes | outcome must be the stock (no historical option quotes); ~zero-cost assumption on liquid names, UNRELIABLE means on micro-caps (see hygiene note) |
| Form 4 insider clusters | yes, but NOT built | months needed for enough cluster events | T+2 stale for same-day options; multi-day-stock horizon only — same class as 8-K with strictly fewer events; weak cousin already measured (`insider_cluster_flag`, d 0.38). Earns a study only if 8-K had shown life. It did not. |
| FRED / Trends / FINRA short interest | possible | — | too slow for any horizon we trade; short interest already a feature |

Repo archaeology: the "old scanner work" survives as archived v10-sandbox commits
(`prototype_alt_data.py`, `backtest_alt_edges.py`, edgartools Form-4 parsing — 94a52e29, 8eadc2dc,
b2985619, recoverable from the archive tag).

## Step 2a — TEST A: dark-pool accumulation (option outcomes, full vintage rigor)

Six causal expanding-window features (3-day print sums, print trend, prints vs own median, node-size
max, node-approach, days-with-prints). Champion chosen on the early half, measured on the late half,
per vintage:

| vintage | rows | champion | in-sample d | **OOS d** | independent bets |
|---|---|---|---|---|---|
| 07-16 | 4,551 | days_with_prints_5d | 0.376 | 0.334 | 1,425 |
| 07-20 | 5,998 | prints_3d_sum | 0.321 | 0.328 | 1,703 |
| 07-22 | 6,281 | prints_3d_sum | 0.322 | 0.305 | 1,778 |
| 07-23 | 7,240 | prints_3d_sum | 0.310 | 0.373 | 2,088 |
| 07-24 | 8,653 | prints_3d_sum | 0.283 | **0.398** | 2,500 |

Same champion in 4/5 vintages, no trade-count explosion, holds out-of-sample — **a real signal**, and
**a clear miss**: 0.398 vs the 0.68 requirement. Accumulation history adds nothing the point-in-time
print count doesn't already carry (the incumbent 0.580 IS a dark-pool feature). Would it clear the
Student's gates? Not remotely — the full 82-feature model containing the stronger version of this
signal already fails all three statistical gates. Trials: 30 (6 features × 5 vintages).

## Step 2b — TEST B: EDGAR 8-K event study (stock outcomes, calendar-disjoint OOS)

8,030 filings; entry at the first close AFTER the filing date (no same-day lookahead); 3-trading-day
forward return net of SPY over the identical window; champions chosen on JUNE, measured on JULY
(disjoint calendars, not nested); ~7,000 events with clean outcomes, nearly all distinct ticker-days.

| feature (top 5 of 15) | in-sample d (June) | **OOS d (July)** |
|---|---|---|
| item 3.02 (unregistered equity sales) | 0.097 | 0.085 |
| item 1.01 (material agreement) | 0.093 | 0.041 |
| item 2.02 (earnings) | 0.092 | 0.036 |
| n_items | 0.069 | 0.084 |
| item 5.07 (shareholder votes) | 0.055 | 0.125 |

Champion OOS d = **0.085**. The entire family sits between 0.02 and 0.13 — an order of magnitude
below the bar. Per-item win rates in the July half run 31–54% against a 50% base: 8-K item types
carry essentially no 3-day directional information. Would it clear any gate? No — there is nothing to
gate. Trials: 15.

**Data-hygiene note (self-critique, applies to means, not to the verdict):** the per-item MEAN
returns are contaminated by micro-cap outliers (item 5.03's July "mean" of +84% is a handful of
sub-$1 stocks multiplying; the all-events mean of +3.9% with a 50.0% win rate is the same tail). The
study should have winsorized or imposed a liquidity floor before printing means. The separation
statistics and win rates — the actual test — are robust to this (pooled-variance d shrinks, not
grows, under fat tails), but the means column of the drift table is not evidence of anything except
that unfiltered micro-caps are noisy.

## Machinery weaknesses this run exposed

1. **The sparse-payload budget starves our best signal family.** `dark_pool.*` is non-null on only
   35% of feature-bearing rows because alt-payloads are rationed. Our single strongest separator
   lives there. Widening dark-pool coverage in the harvest is a governed-change candidate with this
   line as its measured birth certificate (Sunday boundary; params clock noted). Fix class: governed.
2. **Retired feeds were retired whole.** The v10 sandbox's Form-4/8-K plumbing was archived rather
   than its DATA being folded into the harvest; tonight's 8-K result suggests that was the right call
   on value, but the pattern — prototype dies, feed dies with it — deserves a note. Fix class: none
   needed now (the feed measured null).
3. **My own study lacked a liquidity filter** (the micro-cap means above). Fix class: report-hygiene,
   fixed by noting here; any future event study gets a winsorize + ADV floor by default.
4. Positive pattern worth keeping: expanding-window aggregates lift effective coverage (35% → 77–87%)
   because they survive gaps — useful for any sparse block, independent of tonight's null.

## Cost + trials ledger

Stock outcomes assume ~zero transaction cost on liquid names (stated; false for micro-caps, see
hygiene note). Option outcomes use the standard executable-price cost model; costs synthetic before
07-09 as always. Trials tonight: 45 (30 + 15), on top of 256 in the 07-25 hunt — every additional
search raises the luck bar, which is why only out-of-sample numbers were read.

## Where this leaves the pivot conversation

Four independent reads now agree: the flow's own features (AUC 0.72, can't clear costs), alternative
readings of the same data (no family beats the incumbent), the stock horizon (below coin-flip), and
tonight's two external-leaning sources (0.40 and 0.09 vs a 0.68 requirement). The machinery keeps
proving it can measure; nothing measured contains enough signal to pay the spread. The pivot clock
(week 1 of 6) and its pre-registered conditions stand unchanged — but when that conversation opens,
this report is the inventory of what has already been honestly tried.
