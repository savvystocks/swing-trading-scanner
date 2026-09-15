# Is the whole market better than the flow floor? Measured, and the answer is no.

Owner question, 2026-09-15 23:46 BST: *"how has the system zoned in to all the same tickers all the
time... this should be a whole market 0-1000 any contract any name system if all the right signals.
the flow scan should scan all flow signals not just that 50k premium... does that need to only be
look at 50k flow or any amount to be successful?"* Owner ruling: build the corpus, measure first.

Two datasets, two bases, one conclusion.

## What was built

`scripts/whole_market_build.py` -> `reports/research/whole_market_affordable_v1.jsonl` (gitignored,
46MB, rebuildable): 188,593 sampled contract-days over 508 sessions from
`data/uw_history.db:contracts_daily` (61M contract-days, every contract with volume, NO flow floor).
Entry at the day's NBBO ask, forward path at each later day's NBBO bid, the seat's BASE exit
(-50 / +50 / 0.20) at daily resolution, ask $0.30-$9.90, sampled 240/day either side of the $50,000
flow floor so both sides are measurable.

**Basis warning, carried in the file's own header.** This is CLOSE-TO-CLOSE. The v3 corpus enters at
the ask of a qualifying intraday print. The two are not comparable and no number here may be quoted
against a v3 cell; daily resolution also flatters stops. Every slice below shares the basis, so the
RELATIVE orderings are the result, not the levels. Section 4 re-tests every ordering on the v3 basis.

## 1. The $50,000 flow floor is one of the most protective rules we have

| Flow premium on the day | Mean per day | t | Win |
|---|---|---|---|
| under $5k | -23.66% | -34.58 | 17.6% |
| $5k-20k | -12.73% | -13.96 | 24.1% |
| $20k-50k | -7.48% | -5.44 | 26.4% |
| $50k-200k | -3.40% | -3.63 | 28.3% |
| $200k+ | +0.43% | +0.33 | 28.7% |
| **below the floor (invisible to us)** | **-18.53%** | **-28.33** | 20.6% |
| **at or above it (what we scan)** | **-1.82%** | **-1.84** | 28.5% |

Monotonic across five buckets and 188k rows. The floor was inherited without a justification on
file; it turns out to be doing heavy lifting. Answer to the owner's question: a $1,000 position does
NOT work on any flow size. Flow size is among the strongest single predictors in the dataset.

## 2. The "blue chip bias" is not a bias to correct

| Class | Whole market, per day | t |
|---|---|---|
| mega-cap | -3.46% | -3.36 |
| mid/small | -11.15% | -12.50 |
| ETF/index | -18.44% | -21.20 |

Crossed with the floor, exactly one cell is positive: **mega-cap with $50k+ flow, +3.96%/day, t
+3.03, both halves positive**. Mid/small at $50k+ is -2.08; ETFs at $50k+ are -11.80. The names the
ranking favours are the names that work. ETFs are the worst class in every cut and are about a third
of what we currently trade.

## 3. The premium-rank cut is roughly right

| Ticker's premium rank that day | Per day | t |
|---|---|---|
| 1-12 (the engine's generic pool) | -4.06% | -2.39 |
| 13-30 | -0.61% | -0.41 |
| 31-60 | -7.56% | -7.68 |
| 61+ | -15.02% | -23.55 |

Reaching deeper into the ranking - the fix the funnel report implied - reaches into progressively
worse names. Rank 13-30 is marginally better than the top 12 and is the only widening worth a test.

Also unambiguous on this basis: calls -1.87%/day vs puts -19.23%/day.

## 4. Re-tested on the v3 live basis, the orderings hold - and the affordable band kills all of them

| v3 basis | Own per day | vs pool | t |
|---|---|---|---|
| mega-cap, all contracts | -3.25 | +1.69 | +4.12 |
| mid/small | -4.56 | +0.35 | +0.33 |
| ETF/index | -6.72 | -1.76 | -2.77 |
| mega-cap CALLS | +0.82 | +5.76 | +5.26 |
| mid/small CALLS | +0.30 | +5.20 | +2.83 |
| ETF CALLS | -2.68 | +2.28 | +1.39 |

Same ordering as the whole market, independently derived. But inside the band a $1,000 slot can buy:

| v3, affordable calls ($0.30-9.90, spread <= 3%) | Own per day | vs pool | t |
|---|---|---|---|
| mega-cap | -6.62 | -1.88 | -1.09 |
| mid/small | -6.67 | -1.88 | -0.89 |
| ETF/index | -6.77 | -1.83 | -0.97 |

Identical to within a tenth of a point. **In the affordable band the name class stops mattering.**
Dropping ETFs from the affordable call pool makes it worse, not better (-7.98 vs -6.89; on the wide
exit -9.70 vs -8.42), so the obvious trade of "stop buying ETFs" is measured and rejected.

## 5. What this settles

1. **Do not lower the flow floor.** Below it is catastrophically worse and monotonic. The rule stands
   on evidence now rather than inheritance.
2. **Do not widen the ranking to reach mid-caps.** Rank 31+ is worse; mid/small is worse than mega-cap
   on both bases. The only widening with any support is rank 13-30, and it is small.
3. **Do not filter ETFs out** of the affordable pool - measured, it makes the pool worse.
4. **The $1,000 slot remains the whole constraint.** It was found on the flow-alert corpus, and it now
   survives a second, independent test across the entire options market: 188k contract-days, every
   name, every flow size, and no slice of the affordable band is positive anywhere.
5. The one separation that survives both bases and is already in the roster: **calls over puts, on
   mega-caps, with real flow behind them** - which is FOLLOW_CALLS' thesis, currently -61.9% a trade
   live on three trades, all of them in the affordable band.

## 6. Honesty notes

- Section 7 of the raw analysis searched 48 combinations; the winners there are search results, not
  evidence, and none of them is proposed for trading.
- The close-to-close basis is optimistic in absolute terms (the 2026-09-09 finding: bar-close entry
  flattered returns by 4-5 points a day). Only orderings are claimed.
- The cheap-versus-expensive ordering FLIPS between the two bases (cheap contracts are best within the
  mega-cap call cell close-to-close, worst on the intraday-print basis). That is an entry-timing
  effect, not a price effect, and it is the open question worth the next study - not a signal to trade.
- Sampling is 240/day per side of the floor; the file's header records it.
