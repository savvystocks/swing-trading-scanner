# Daily bar archive

## What
The first forward data capture after the Unusual Whales exit (2026-09-22). One Alpaca call per run stores split-
adjusted daily bars for the ETFs the two never-built-but-cleared strategies need - the published RSI(2) dip-buy on
ETF shares and Faber's 200-day switch - so research after the option archive froze is not limited to frozen history.
Free, off the trade path, and it never raises into a caller.

## Where
- `scripts/daily_bars_archive.py:run` - the whole job; `scripts/daily_bars_archive.py:fetch` pages Alpaca.
- `scripts/daily_bars_archive.py:open_db` - `data/daily_bars.db`, table bars(symbol, day, ohlcv, trade_count, vwap).

## Exercise
`cd ~/swing-trading-scanner && . ./.harvest_env && ./.venv/bin/python scripts/daily_bars_archive.py`

## Healthy
`daily bars: N rows written for M symbols; store now X rows over M symbols, FIRST .. LAST`

## Evidence
`data/daily_bars.db` on the VPS; the cron appends to ~/daily_bars.log (22:15 UTC weekdays).

## Checks
- MOT 6.38: writes, is idempotent for a repeated day, and fails open when the provider throws.
- Freshness sentinel row "daily bars archive" (EVIDENCE, 22:15 UTC weekdays).

## Traps
- 2026-09-22: it must stay off the trade path. It reads market data with the paper keys and writes only its own
  database; nothing in the engine reads it yet, and a strategy that wants it must say so in ROADMAP first.
- Alpaca's IEX feed is free but thinner than SIP; bars are split-adjusted, dividends are not - a total-return study
  must add them from elsewhere.
