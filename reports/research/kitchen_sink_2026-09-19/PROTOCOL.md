# RESEARCH PROTOCOL - pre-registered 2026-09-18 00:55 BST, before any search ran

Owner order: find a strategy with a profitable, RELIABLE edge, using everything we have. Five to six
months of searching have found none. Two false findings this week were manufactured by (a) a code
bug that skipped stop tests, (b) comparing a level t-statistic to a noise bar instead of the paired
difference. This protocol exists so that a "find" means something.

## THE BAR (fixed now; nothing below it will be presented to the owner)
A candidate PASSES only if ALL hold on the SEARCH period, then ALL hold again on the HOLDOUT:
1. Executable prices only: every SELL fills at the BID, every BUY at the ASK, entry and exit. Never mid.
2. Positive mean per period AND t > the PERMUTATION BAR computed on the exact grid you searched
   (sign-flip the period returns 500+ times, take the 95th percentile of the max |t| across the grid).
3. Clustered BOTH by day (or week) AND by ticker-week; take the decision on the more conservative.
4. Both halves of the search period positive. At least 8 of 10 quarters positive (or 6 of 7 if shorter).
5. Leave-one-period-out: still positive with t > 1.5 after removing the single best period.
6. If it modifies an existing live rule, report the PAIRED difference against that rule, with its own bar.
7. The live gates apply before scoring: the BEAR stand-down (SPY prior close > 2% below its 50d SMA)
   for anything that sells index premium; no same-calendar-day close; positions force-close at
   3 days to expiry if they route through the options exit engine (the fivek book does NOT).
8. Max loss per position <= $1,000 (defined-risk structures only; no naked shorts; no undefined risk).
   Judge against a $5,000 account with five $1,000 slots. Never the paper balance.
9. Tradeable: the engine can place it, or the build needed is named concretely in one paragraph.
10. Reproducible: your script runs end to end from /tmp/research/ and prints the numbers.

## DATA (read ONLY these; never touch data/uw_history.db or data/hourly_paths.db - another job is
## writing to it and any scan there will stall everyone)
- /tmp/research/search.db  table o(t, day, exp, cp, k, occ, vol, askv, bidv, prem, oi, bid, ask, iv, delta)
  Every option row (top-500-by-volume per ticker-day; far-OTM tails are thin on SPY/QQQ/NVDA/IWM/TSLA)
  for 34 liquid tickers, days 2024-09-03 .. 2026-03-13 ONLY. Indexed (t,day,exp,cp) and (t,exp,cp,k).
  bid/ask are the day's CLOSING NBBO. prem = total premium traded that day; askv/bidv = volume at ask/bid.
  iv populated ~70% of rows; delta always.
- /tmp/research/closes.json  {ticker: {day: [o,h,l,c,v]}} daily bars 2024-03-01 .. 2026-09-16 (Alpaca IEX).
  Use the CLOSE on expiry day for cash settlement (intrinsic); the 2%/4% live book settles this way.
- /tmp/research/regime.json  {day: {reg, sp, regime}} - reg = SPY prior close vs 50d SMA (%), sp = vs 20d,
  regime BEAR (<-2) / MILD / BULL (>+2). D-1 convention. This IS the live gate.
- HOLDOUT 2026-03-16 .. 2026-09-15 is NOT in search.db. You cannot read it. A separate verifier runs it
  once per surviving candidate. Do not try to reconstruct it from closes.json.

## CONVENTIONS
- Weekly structures enter on the first trading day of the ISO week at that day's CLOSE and use that
  week's Friday expiry unless you are explicitly testing a different tenor. Select strikes from the
  chain that EXISTS on the entry day; if the intended strike is missing, that week is DROPPED, not
  substituted (substitution silently widens spreads and flattered a result this week). Report drops.
- Spread P&L per contract = (credit or -debit at entry, executable) - (executable unwind or intrinsic at
  settlement), x100. Report $/period per ONE contract and the max loss per contract.
- Report for every candidate: n periods, total $, $/period, t(day), t(ticker-week), halves, quarters+,
  worst period, max drawdown, max loss, leave-one-out t, permutation bar, drops.
- Search honestly but not endlessly: a family grid of 50-200 configs is fine; report the grid size so
  the bar reflects it. Do not tune on the tail; do not add a parameter to rescue a near-miss.
- Time budget: several hours is fine. Write intermediate results as you go.

## OUTPUT
/tmp/research/<family>.py       your reproducible script (one file, runs end to end)
/tmp/research/<family>_results.json   {"family":..., "grid_size":..., "permutation_bar":...,
   "candidates":[{"name","spec"(every parameter, fully reproducible),"metrics"{...},"passes_search_bar":bool,
   "why_or_why_not":...}], "dead_ends":[...], "notes":...}
Your final message: the candidates that pass, the ones that nearly do and why they fail, and what you
learned about the family. A family with zero survivors is a valid, valuable result - say so plainly.
