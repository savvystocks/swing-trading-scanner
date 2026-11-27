# Paper lab - pre-registration (written 2026-11-27, before any lab trade; the commit that adds this file is the lock)

Owner, 2026-11-27: "just trade, all different strategies that you think work and log all the details, the set ups and everything". Of four offered books the owner picked two: the index dip-buy and the candle rule on seven new pairs. Code: scripts/paper_lab.py, run by .github/workflows/paper_lab.yml on the VPS tick (21:12 and 22:12 UTC Mon-Fri, 22:03 and 23:03 UTC Sun-Thu).

Account: OANDA practice 101-001-40973522-001 (fake money; a US-division account that lists currencies only), shared with the S26 book on EUR_USD and USD_JPY. Each book has its own instruments, so no two books ever hold the same instrument. No real money and no FTMO account are involved.

## Book S26X - the S26 candle rule on seven USD pairs
- Rule (unchanged code, scripts/fx_s26_alerts.py Market.signal and Market.update; fx_chart_screen_2026-11 v2 base rule): a daily pin bar or engulfing bar (17:00 New York close) whose low (long) or high (short) is within 0.25 daily ATR(14) of a swing low or high formed 3 to 60 days earlier, closing beyond that level; stop at the signal bar's extreme; entry at 18:00 New York; target 2 x the stop distance; exit after 10 trading days; one trade per pair.
- Pairs: GBP_USD, AUD_USD, NZD_USD, USD_CHF, USD_CAD, USD_NOK, USD_SEK. Counted from the 2026-11-27 daily close on (the first close after this lock); a signal while the pair still holds a trade is ignored, as in S26.
- Already seen: the big search's F6 family (pin bar and engulfing at a swing level, with its own stop and exit grid) on all nine USD pairs, 2005-2014 only; nothing in it passed. 2015-2026 on these seven pairs was never opened, so the forward record is fresh data. On EUR_USD and USD_JPY the same S26 rule made +0.001 R per trade on 2019-2026 (235 trades): expectation about 0 R per trade after costs.
- Model record: ask fills for longs, bid for shorts; stop exits pay max(0.5 pip, the pair's median H1 spread 2025-11 to 2026-11): GBP_USD 0.00019, AUD_USD 0.00013, NZD_USD 0.00015, USD_CHF 0.00015, USD_CAD 0.00018, USD_NOK 0.00397, USD_SEK 0.00368; R excludes commission and financing.
- Practice orders: 0.5% risk of the balance, broker stop at the fill, take-profit at 2R from the fill, closed by the job after 10 trading days; through scripts/fx_risk_engine.py on this book's own open trades (the dollar cluster allows one USD-short and one USD-long bet at a time) with the shared account's NAV for the day stop, pause and cushion; no order more than 2 hours after 18:00 New York; tag lab_s26x.
- JUDGED ONCE, at 100 closed model trades (about a year at the expected 8-9 a month): PASS only if the mean model R is above 0 with a plain t of at least 2.0. The practice-order record is reported beside it and never used to rescue a fail. The rule is not changed during the test; any change is a new book with a new record.

## Book DIP - the RSI(2) index dip-buy (model record only)
- Rule: idx_gold_2026-11 PROTOCOL.md section 4 R1, exactly: at the 16:00 New York close (the mid close of the H1 bar opening 15:00 New York; a day without that bar, with a stale one, or with fewer than 4 bars is carried, feeds the averages and never signals), buy when Wilder RSI(2) < 10 and the close is above its 200-day average; buy at the ask open of the bar opening 16:00 New York; sell at the bid open of the 16:00 bar on the first later day whose close is above its 5-day average; no stop, no time limit; one position per instrument; all signals.
- Port check: replaying scripts/paper_lab.py's Dip on the study's own data reproduced all 202 SPX500 and 209 NAS100 trades with identical entry and exit times.
- Instruments: SPX500_USD and NAS100_USD. Each trade records whether the other index was already held (a one-slot book would skip it).
- MODEL ONLY: this practice account cannot trade index CFDs, so no order is placed. Prices are OANDA practice bid/ask H1 bars; financing is estimated at the FTMO 2026-11-26 snapshot (US500 0.02446% and US100 0.02453% of price a night, Friday counted 3 nights); dividends are not credited; dollar figures at 25,000 USD notional per trade.
- Already seen: everything (the ETF twins and this CFD history 2003-2026). The study measured +0.25% per trade after FTMO costs, about 18 trades a year across both indices, and the rule was closed as an FTMO route on 2026-11-27 because it is too slow for the +10% target at safe sizes.
- Use: an implementation check of live quotes against the backtest only. No edge verdict comes from this record (a meaningful count would take well over a decade).

## Logging
Every setup, fill, skip and close goes to Telegram (setups with a chart), to reports/paper_lab/journal/<trade id>.md (plus the chart .png), and to reports/paper_lab/events.jsonl; reports/paper_lab/SCOREBOARD.md is rewritten on every run and a weekly summary is sent on Friday evening.

What this lab cannot show: FTMO's fills, swaps or rules; behaviour with real money; any edge before a book's judge count.
