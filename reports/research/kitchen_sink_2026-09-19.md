# The kitchen-sink strategy search: six families, 13,841 configurations, no survivor

Owner order 2026-09-18 00:49 BST: "find a strategy with a profitable edge ... throw the kitchen sink at
it and don't come back until you create a strategy that is profitable and reliable." Closed 2026-09-19.
Protocol, the six research scripts and the base-builder scripts are committed beside this report in
`reports/research/kitchen_sink_2026-09-19/`; the result files are archived on the VPS at
`~/kitchen_sink_2026-09-18.tgz` (35 MB of JSON and trade CSVs, not in git).

## Verdict

Nothing survives. Twelve configurations cleared their own pre-registered bar on the search period. One
was refuted by the researcher who found it; the other eleven were rebuilt from scratch by independent
adversarial verifiers and every one died before earning a run on the held-out six months. **The holdout
(2026-03-16 .. 2026-09-15) is unspent.** No number failed to reproduce - the arithmetic was right every
time. What failed was what the numbers were evidence of.

Honest value of the best of them: $0-$20 a week per contract against a $500-$1,000 loss roughly once in
20-40 weeks. On a $5,000 account with five slots, one ordinary bad week on any of them is $2,500-$4,960 -
most of the account and more than the GBP 2,500 lifetime cap in a single event. The data contains a
fortnight with two such weeks back to back (2025-W13/W14, both hidden behind the BEAR gate).

**Answer to "which strategy has a profitable edge": none is proven.** CREDIT_SPREAD_W remains the only
live positive (5 of 5 settled, +$151, 4 of 8 court weeks) and sits in the same position as everything
below: consistent, with a loss tail two years cannot measure.

## The bar, fixed before any search ran

`PROTOCOL.md`, written 2026-09-18 00:55 BST. A candidate passes only if ALL hold on the search period,
then ALL hold again on the holdout:

| # | Rule |
|---|---|
| 1 | Executable prices only: every sale at the BID, every purchase at the ASK, entry and exit. Never mid. |
| 2 | Positive, with t above a permutation bar computed on the exact grid searched (500+ sign-flip draws). |
| 3 | Clustered both by day/week AND by ticker-week; decide on the more conservative. |
| 4 | Both halves positive; 8 of 10 quarters positive. |
| 5 | Still positive at t > 1.5 with the single best period removed. |
| 6 | A change to a live rule is reported as the PAIRED difference against that rule, with its own bar. |
| 7 | The book's own live gates applied before scoring (BEAR stand-down, no same-day close). |
| 8 | Max loss per position <= $1,000; defined risk only; judged against $5,000 / five slots. |
| 9 | Tradeable by the engine, or the build named in one paragraph. |
| 10 | Reproducible end to end from one script. |

The holdout was made physically unreadable: researchers were given `search.db` (8.1M option rows, 34
liquid tickers, through 2026-03-13); `holdout.db` (2.1M rows) was a separate read-only file.

## What was searched

| Family | Configs | Cleared its bar | Survived | Finding |
|---|---|---|---|---|
| A. Index premium selling (put/call credit spreads, condors; SPY QQQ IWM TLT GLD; % and delta strikes; weekly / 2-week / monthly; nine regime, IV and prior-week conditions) | 11,502 | 4 | 0 | The structures earn nothing unconditioned (QQQ call spreads +$9-19/wk, t 0.45-0.88); each pass was one of nine conditions searched per cell - the sibling that escaped |
| B. Single-name premium selling filtered by daily flow (24 mega-caps) | 360 | 0 | 0 | Every configuration deeply negative, t -2.5 to -5. The unfiltered weekly put-spread pool lost $59,396 over 70 weeks. No flow aggregate rescues it |
| C. Volatility conditioning (IV rank 120/250d, IV minus realised, term structure) | 864 | 1 (+2 gated copies) | 0 | Premise false on this data: premium selling pays LESS when IV rank is high, because high IV marks weeks the index is already sliding. Its one pass was refuted by its own researcher as a coverage artefact |
| D. Price-triggered defined-risk directional (pullbacks, -3% days, breakouts, month-end, RSI, two down days; call debit vs put credit spreads) | 150 | 0 | 0 | Nothing beat regime-matched random entry (excess t -1.05 to +1.32). Call debit spreads negative on every tenor: paying the ask twice costs 4-8% of width per round trip |
| E. Time structure (calendars, diagonals, 1-2 DTE, 30-45 DTE managed at 21 DTE / 50% profit, roll timing, weekend cells) | 288 | 2 | 0 | Early management loses in 20 of 24 paired cells. The weekend effect is real but thin (below) |
| F. Wildcard (10/20/30-delta ETF spreads on nine ETFs, OI walls, IV skew, day-of-week, stand-down flags) | 677 | 5 | 0 | All five passes are 0.10-delta put spreads with >= 95% wins whose loss branch had not fired |
| **Total** | **13,841** | **12** | **0** | |

## The twelve passes and how each died

| Candidate | Claimed (search period) | How it died |
|---|---|---|
| C: index 10-delta $10-wide 2-week put spread | $57.6/wk, t 5.36 / 7.45, 7 of 7 quarters | Self-refuted. 130 of 257 ticker-weeks were dropped because the long leg was outside the top-500 extraction; the dropped half held 5 short-strike breaches. Refilled at the most favourable fill: t 3.57 < 4.33 bar; at neutral fills t 1.0-2.5 |
| E: IWM Friday-to-Monday 10-delta $5-wide | $10.2/wknd, t 7.07, 98.5% wins | The one cell of 24 that escaped a Monday gap for 20 months. Against the pooled 2% breach rate: +$8/weekend, t 1.89, with a $495 tail. 5 of 65 Mondays breached the short strike |
| E: SPY roll timing, Friday entry vs Monday (paired) | paired t 3.38 vs bar 3.22 | The single week where Friday entry took a -$466 full loss was dropped for a missing strike; with it back t 1.84. Against the LIVE 2%/4% rule the difference is +$3.42/wk, t 0.10 |
| A: QQQ call spread, 25-delta, 1% wide, after an up-week | $76.5/wk, t 6.16, n 26 | One -$400 rally week (P of zero in 26 about 0.5) drops t to 2.76. Same condition gives IWM nothing and SPY sub-bar |
| A: QQQ call spread, 25-delta, $7 wide, after an up-week | $85.9/wk, t 6.63, n 28 | Unconditioned: +$18.6/wk, t 0.77, nine near-max losses in 75 weeks. The filter's honest statistic is Welch t 2.31, family-wise p 0.14 |
| A: GLD put spread 1%/1%, next week, low IV | $55.7/wk, t 6.99, n 24 | The top-500 cap removed every GLD week down more than 2% (all 3). Refilled: $31.8/wk, t 1.92. A long-gold proxy inside a gold bull market |
| A: three-index call spread 2% / $7, BULL only | $41.3/wk, t 6.09, n 54 | 55 of 114 BULL weeks dropped for a missing far-OTM long, including breaches of -$567, -$261, -$257. Refilled t 3.49 / 2.64. -$20/wk in MILD |
| F: SMH 10-delta put spread, large width | $28/wk, t 19.84, 65 wins / 1 loss | The SPY gate removed the only two crash weeks (-$751, -$968 back to back); the DeepSeek -9.9% day landed ON the Monday entry day by luck (a Tuesday entry loses ~$351) |
| F: SMH 10-delta put spread, small width | $16.9/wk, t 12.69 | Break-even full-loss rate 3.49% vs realised 3.45%. Ungated t 0.31. Credits decayed to cents by 2026 |
| F: SLV 10-delta put spread, small width | t 12.86, max loss $97 | A $2.64 credit against $97 of risk. The one ungated SLV crash week (2026-W05, -23.5%) was removed by the coverage drop; refilled t 1.63 vs 3.95 |
| F: SLV 10-delta put spread, large width | t 10.14 | Both short-strike breaches were among the 30 dropped weeks; refilled at the most favourable fill t 2.19 vs 3.48 |
| F: six-ETF pooled 10-delta put spreads | $29.7/wk, t 4.92 / 4.36 | SMH is $1,851 of the $2,079 (ex-SMH t 0.53). A 5.4% loss rate on $997 already exceeds the $13.74 mean win, so the tail bound can never close |

## The two mechanisms behind every death

**1. Our own data cap deleted the crash weeks.** The archive kept the 500 busiest contracts per ticker
per day (no pagination - BREAKDOWNS 2026-09-17). The far-OTM long leg of a spread makes that cut mainly
on busy days, and the protocol rightly DROPS a week whose strike is missing. The dropped weeks were
systematically the bad ones. Any result on this corpus involving a strike more than ~5% OTM is
unmeasurable until the chain is complete; the re-pull is running (BREAKDOWNS 2026-09-19).

**2. The large loss had not happened yet.** A 0.10-delta weekly put spread collects about 2% of its
width, so it breaks even at a 2-3% full-loss rate. The pooled breach rate across 18 ETF cells is
6.6-7.3%, the delta-implied rate about 10%. Every passing cell was simply one whose loss branch had not
fired. The test the researchers skipped, applied to the nine verifiable passes:

| Candidate | n | losses | 95% upper loss rate | EV realised | EV at bound, realised loss | EV at bound, MAX loss | history needed |
|---|---|---|---|---|---|---|---|
| QQQ call spread 25d 1% | 26 | 3 | 27.2% | +$76.5 | +$48.9 | -$68.4 | 191 periods |
| QQQ call spread 25d $7 | 28 | 4 | 29.8% | +$85.9 | +$58.6 | -$105.7 | never |
| GLD put spread 1%/1% | 24 | 4 | 34.2% | +$55.7 | +$40.5 | -$49.2 | 374 |
| three-index call spread | 34 | 4 | 24.9% | +$35.6 | +$18.2 | -$135.6 | never |
| IWM weekend | 65 | 1 | 7.1% | +$10.2 | +$5.2 | -$24.3 | 1,070 |
| SPY roll timing | 48 | 9 | 30.4% | +$33.6 | +$25.6 | -$173.2 | never |
| index 10d $10 2-week | 64 | 3 | 11.7% | +$57.6 | +$21.7 | -$41.7 | 209 |
| same, IV-premium gate | 46 | 1 | 9.9% | +$54.9 | +$29.4 | -$40.6 | 106 |
| same, contango gate | 35 | 1 | 12.9% | +$49.1 | +$16.5 | -$74.3 | 185 |

Clopper-Pearson one-sided bound. Every one is positive if future losses look like past losses and
negative if a loss can run to maximum; none can close that gap inside two years. The sign-flip
permutation bar is the wrong null for a >90%-win structure - it cannot generate the unfired loss - which
is how 128 of 3,427 index-premium cells cleared a bar of 5.4 and zero-loss cells posted t of 17-35.

## What the search did establish

| Fact | Evidence |
|---|---|
| The weekend effect is real and small | Friday-close to Monday-close index put spreads earn the same credit as Thursday-to-Friday at the same delta and breach 1/2 to 1/6 as often, 18 of 18 cells (SPY 3.1% vs 10.1%, QQQ 1.6% vs 8.7%, IWM 1.5% vs 8.7%). Worth +$8-36 per contract per weekend at pooled t 1.5-2.5; the Monday gap arrived twice ungated in 20 months. A rough six-year pass on index closes did not find it before 2024 - unverified, see Limits |
| Premium selling pays less when IV is high | 864 configs; no IV gate lifted $/trade beyond noise; both surviving gates made the PAIRED difference negative (t -2.8 to -4.7) |
| Single-name premium selling loses | 360 configs, all negative at bid/ask fills |
| Early management loses on executable prices | 21-DTE and 50%-profit management negative in 20 of 24 paired cells; day-5 unwinds negative everywhere; Wed-Fri 1-2 DTE selling negative in all 18 cells |
| Price triggers are regime beta | 150 configs vs regime-matched random entry: excess t -1.05 to +1.32 |
| The SPY BEAR gate is the whole edge of every gated candidate, and protects nothing but SPY | Ungated: SMH large t 0.38, six-ETF t 0.25, QQQ call spreads t 0.77-0.88. The gate was open through SMH -9.3/-6.8/-8.4% weeks, GLD -6.3%, SLV -23.5%. Its entire in-sample benefit is one episode (April 2025) |
| Credits are decaying | SMH weekly credit ~$0.27 (2024) to $0.03-0.13 (late 2025); 9 of 11 weeks in 2026-Q1 had no positive credit at the closing NBBO |
| The week-wide noise floor | Across all 13,841 configs on the same ~70 weeks the approximate 95% max-t is 4.63; nothing at t 4.4 or below ever cleared the search that was actually run |

## Corrections to things said during the week

| Said | Truth |
|---|---|
| "XSP divides a SPY dollar edge by ten" (panel, repeated to the owner) | Wrong. XSP is SPX/10, the same price level as SPY (live legs 745/729; XSP 765 vs SPY 762). Same notional; what differs is quote width, now being logged (`scripts/xsp_quote_log.py`) |
| "Closing the credit spread at 50% of credit: +$45.9/wk, t 4.57" | t 4.57 was the LEVEL of the modified series. The paired difference against hold is +$19.65/wk, t 1.25; on the 89 weeks the live BEAR gate trades it is -$4.56/wk |
| "A debit spread beats the outright buy by +4.88 pts/day" | A stop test silently skipped on days the short leg had no quote. On the court's engine the spread loses, monotonically in the size of the credit |
| "The short leg has hourly bars 42.5% of the time" | 71.6% for the rule actually used; 42.5% belongs to a rule nobody uses |

## Limits of this result

- Every price is SPY/QQQ/IWM/ETF; the live book trades XSP (European, cash-settled). American physical
  settlement means an ITM short at expiry is assignment into $40-70k of stock on a $5,000 account -
  unmodelled here.
- Two years with one crash week (2025-04-04, SPY -9.54%). A rough first pass on SIX years of index closes
  (the free feed starts July 2020) suggests the live 2%/4% structure was negative over 2020-23 and that
  the weekend effect is absent before 2024 - at a fixed 2024-26 credit, which understates high-volatility
  years. It is a pointer, not a finding, and is parked.
- Closing NBBO from a truncated archive; IEX closes for settlement (measured effect on one study: $4).

## Closed - do not re-test without new data AND a new mechanism

10-delta ETF put spreads; conditioned index call spreads; single-name premium selling under any flow
filter; IV-rank gates on premium selling; price triggers on the underlying; early management of credit
spreads (21 DTE, 50% profit, day-5); mid-week short-DTE selling; debit spreads as a replacement for
outright buys; the take-profit on CREDIT_SPREAD_W.

## Still open, each needing the owner's word

| Item | What it is | Prior |
|---|---|---|
| Pooled weekend-effect test | The only mechanism found. Pre-register the six pooled Fri-Mon cells (bar ~2.5 for a 6-config grid) and run ONCE on the untouched holdout, on the complete chain, at XSP economics. Expect it to fail $5k sizing even if it passes statistically | modest |
| Re-run the six scripts on the complete chain | Only after the re-pull finishes (about 8 nights from 2026-09-19) | ~10% that any candidate passes |
| XSP quote-width verdict | `scripts/xsp_quote_log.py`, rule fixed in its docstring, due about 2026-10-17 | - |
| Earnings-week split for single names | Whether "single names lose" is earnings gaps plus flat, or uniformly negative | ~20% |

## Reproduce

`kitchen_sink_2026-09-19/extract.py` and `split.py` rebuild `search.db` / `holdout.db` from
`data/uw_history.db`; `closes.py` rebuilds the closes and the regime series; each family script runs end
to end from that directory (run them from a directory that holds no file named `inspect.py`);
`tailbound2.py` recomputes the table above from any family's results file.
