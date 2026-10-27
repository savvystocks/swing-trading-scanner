# Hypothesis ledger

Every idea this project has tested, in one place, with how many configurations it tried and how it ended. It exists so
that a good-looking result is never judged on its own: the more ideas have been tried, the better the best one looks
by luck alone.

## The luck bar
With N independent tries and no real edge anywhere, the best t-statistic expected from noise alone is about
sqrt(2 ln N): 3.0 at 100 tries, 3.7 at 1,000, 4.4 at 14,000. Tries that share data are not fully independent, so a
permutation bar computed on the exact grid (as the 2026-09-17 search did: |t| 2.90 for 60 combinations) beats this
rule of thumb whenever it can be run. Recorded configurations to date: at least 14,700, plus engine and probe variants
that were never counted, so the project-wide luck bar is about 4.4 and rising.

## How a row is added
1. Before any data is read: date, the hypothesis in one sentence, where its protocol lives (path and sha256 when
   locked), and the number of configurations it will try.
2. After the run: the verdict, the key number, and where the result is kept.
3. Before calling any idea new, search this ledger and the memory notes for an earlier test of it.

## Tested
| Date | Hypothesis | Configurations | Verdict | Record |
|---|---|---|---|---|
| 2026-06 to 08 | V10: follow large Unusual Whales option flow into directional paper trades | engine variants, not counted | REJECTED: 3.8% hit rate, SPRT reject, conviction inverted | ROADMAP; BREAKDOWNS |
| 2026-08-05 to 08-23 | Fade book: take the side against the flow when trend and SPY oppose it | live book + corpus, not counted | REJECTED on real triggers: pure sweeps -14.3% t -4.33 | memory: real-trigger pivot |
| 2026-08 | Live paper probes (EXEC_BASELINE, FADE_UNROUTED, CONSENSUS, DP_HEAVY, QUIET_TAPE, FADE_DP, OPT_WINNER, EARLY_STRENGTH, OVERNIGHT, TURN_OF_MONTH, condor and others) | about 15 strategies | none promoted; culled; the condor killed by backtest | fade_book_spec.json history |
| 2026-08-23 | Archive edge mine: follow the aggressor / consensus in calls | mined grid, size not recorded, 9 survivors | not tradeable: likely bull-market beta; failed the 2026-09-17 search | memory: real-trigger pivot |
| 2026-09-09 | Every earlier backtest re-scored on executable prices | all | earlier results superseded (-4 to -5.5 points a day) | reports/instrument_mismatch_design_2026-09-09.md |
| 2026-09-16 | Directional trades as credit spreads (+4.88) | 1 | RETRACTED: a missing-quote skip in the study code | memory: spread finding retracted |
| 2026-09-17 | Any profitable directional configuration on the court engine at $1,600 | 720 (6 cells x 12 exits x 5 bands x outright/spread); permutation bar 2.90 | REJECTED: best t 2.69 with a negative second half | memory: no profitable directional config |
| 2026-09-17 | Close the weekly credit spread at 50% of its credit | a few | KILLED: paired -$4.56 a week on the weeks the BEAR gate trades | memory: credit spread take-profit |
| 2026-09-18 | Kitchen sink, six families (index premium, single-name premium, volatility conditioning, price-triggered defined risk, time structure, wildcard) | 13,841 | ZERO survivors after the search bar, halves and a physical holdout | memory: kitchen-sink search; /tmp/research/PROTOCOL.md (VPS, ephemeral) |
| 2026-09-19 | The weekly XSP 2%/4% credit spread on its true instrument, 152 weeks | 1 plus gates | +$26 a week gated, not significant; seated by owner ruling anyway | memory: credit spread true instrument |
| 2026-09-19 | Published rules on ETF shares: Connors RSI(2) dip-buy (8 variants x 16 ETFs) | 128 | POSITIVE out of sample since publication (16 of 16 ETFs), small: about 5.6% a year | memory: shares and tail program |
| 2026-09-19 | Faber 10-month, GTAA-5, dual momentum, turn-of-month, overnight-only SPY | 5 | Faber halves the drawdown but trails SPY; dual momentum underperforms; turn-of-month weak; overnight 9.9% a year gross (t 6.1) dies at 1 bp a side | memory: shares and tail program |
| 2026-09-20 | The 2%/4% weekly spread on IWM, QQQ, GLD, DIA, SLV, EEM, DJX | 7 | 0 of 7 pass | memory: no other ticker works |
| 2026-09-20 | Directional trades as spreads, both legs priced by name | about 4 | REJECTED: 24-32 points a trade worse than the outright (t -7) | memory: directional spreads dead |
| 2026-09-20 | A signature in the winners (gradient boosting on 90,405 trades) | 10 seeds plus split dates | REJECTED: one seed and one cut; dies on concentration, seeds, affordability and every other split | memory: winners signature |
| 2026-09-20 | Faber 200-day switch on 2x SPY | a handful | 12.9% vs 10.8% a year with a smaller drawdown (research only, never seated) | memory: beat buy-and-hold |
| 2026-09-22 | Friday instead of Monday entry for the XSP spread | 1, pre-registered | FAIL (both independent implementations) | VPS ~/research_data/friday_entry_2026-09-22, PROTOCOL sha256 62ae5f6e |
| 2026-09 | The student model (gradient-boosted entry filter) | not counted | switched off (spec probe.student false, MOT 6.33) | SYSTEM_ARCHITECTURE |
| 2026-10-05 to 10-17 | Second-go program: five pre-registered primaries | 5 | all five FAIL | memory: second-go due diligence |
| 2026-10-17 | XSP vs SPY quote width from the passive log | 1 | VOID: Alpaca's free quotes are randomized | ROADMAP 2026-10-17 |
| 2026-10-21 to 10-25 | Crash test: the live spread replayed on SPY options 2008-2025 | 1, pre-registered | FAIL: worst fall -$4,856 a contract vs the $3,300 cap (2018); the book was wound down | swing_research/crash_test_2026-10, PROTOCOL_EOD.md sha256 0dc799a0 |
| 2026-10-25 to 10-26 | Index with a crash filter: (A) Faber 10-month rule on SPY; (B) half A, half Connors RSI(2) on 26 ETFs; each against a same-risk SPY/cash mix, 2007-2026 | 2 arms, pre-registered, one run | A FAIL (worst fall -25.9% vs the 25% limit); B PASS (4.80% a year, worst fall -14.7%, beats its same-risk mix 2.39% at p 0.0065; SPY made 10.86% with a -55.2% fall) | swing_research/trend_filter_2026-10, PROTOCOL.md sha256 661ed4be, VERDICT.md |
| 2026-10-26 | Do the stock picks saved from Instagram beat SPY? Every dated pick, next open to 23 Oct 2026 | 1 (266 picks, 37 creators), rules written first | NO: average pick -8.9% vs SPY +9.4% over the same days; 29% beat SPY, 63% lost money | swing_research/influencer_scorecard_2026-10, PROTOCOL.md sha256 128718ac, SUMMARY.md |
| 2026-10-27 | Pre-seat checks for strategy B's paper book: (0a) Alpaca IEX vs Yahoo signal parity 2024-2026; (0b) fills at 09:40 New York instead of the open; (0c) paper dividends | 2 measurements, no parameters, locked first | 0a FAIL: buy days agree 95.1% (need 97%), sells 99.1%, month-end trend 34 of 34, so a build takes its signals from Yahoo; 0b PASS: 09:40 fills cost 0.004 points a trade (+0.400% vs +0.396%), 6.2% of trades had no minute data; 0c: Alpaca paper pays no dividends (its documentation) | swing_research/trend_filter_2026-10/PRESEAT_RESULTS.md; protocol PRESEAT_CHECKS.md sha256 de97a7f7 |

## Locked, not yet run
None.

## Proposed, not tested (from the Instagram review, 2026-10-26; each needs the owner's go and a locked protocol)
Insider cluster buying (SEC Form 4); recession filters on FRED (yield curve, credit spreads, LEI, CPI above 4%); the
RSP/SPY breadth trend; CFTC leveraged-fund positioning in S&P futures. See
swing_research/instagram_2026-10/all/SYNTHESIS.md.
