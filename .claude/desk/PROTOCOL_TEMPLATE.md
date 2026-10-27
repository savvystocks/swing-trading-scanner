# <study name> - protocol (locked before any outcome data is read)

## 1. Hypothesis
One sentence. What would be true if the idea works.

## 2. Prior tests
Every earlier test of this idea or a close relative found in docs/HYPOTHESIS_LEDGER.md, the memory notes and
reports/, with its verdict. "None found" only after searching all three; list the search terms used.

## 3. Data
Source, dates, symbols, frequency, adjustment, known gaps and coverage. EODHD does not exist. State what is NOT in
the data (dividends, delistings, missing quotes) and how each gap is handled. A missing value is never silently
skipped: say whether it is carried forward, counted as a loss, or excluded and counted.

## 4. Rules
Exact entry, exit, sizing and timing, so that two people writing code from this section alone get the same trades.
Signals use only information available before the trade; say which close or quote each decision uses. Always state:
how much is invested per position and whether fractional units are allowed; the warm-up (how much history before the
start feeds the signals); what is held on day one; and whether open positions are sold at the end (with costs).
In section 6, say whether the starting equity counts as the first peak for the drawdown.

## 5. Costs and constraints
Fill price (ask to buy, bid to sell for options; open or a stated minute for shares), slippage per side, commissions.
A $5,000 account; $1,000 per position unless a NORTH_STAR amendment says otherwise; no same-day sells.

## 6. Primary measure and pass bar
ONE primary measure and the bar it must clear, set now. Secondary measures are reported, never used to pass.

## 7. Tries and luck
Configurations this study tries (N). Project total from the ledger after adding N, and the luck bar
sqrt(2 ln total). A result below the luck bar is not evidence of an edge.

## 8. Holdout and splits
Which period or sample is held out, and the rule for using it once.

## 9. Crash and tail
Worst year, worst fall, largest possible single loss, each against the GBP 2,500 lifetime real-loss cap and the
25%-from-peak rule. For anything that sells premium: the Clopper-Pearson upper-bound expected value at realised
and at maximum loss.

## 10. Results file
The builder writes results.json with a "primary" object holding exactly the numbers in section 6, and a
"secondary" object for the rest. Every number in the verdict must come from a results file.

## 11. What a pass means
A pass means "worth a paper test". It never means trade it, and never means it beats simply holding the index
unless that comparison is the primary measure.

## 12. Run rules
One run. Any re-run, fix or deviation is written in RUNLOG.md with the reason before it happens, and a changed
rule is a new ledger row.
