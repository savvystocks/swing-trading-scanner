# DATA INTEGRITY AUDIT - 2026-08-31

## 1. Cross-source price alignment (UW closing quote vs Alpaca last hourly trade)
  sampled 800 contract-days | comparable 222 (no same-day bars: 578)
  inside bid-ask: 119 | near (<=10% of mid): 101 | OUTSIDE: 2
  ALIGNMENT: 99.1% -> PASS
  worst mismatches: [('SMCI251017C00045500', '2025-09-23', 3.9, 4.0, 3.55), ('IWM260618P00261000', '2026-04-23', 5.15, 5.25, 6.2)]

## 2. Date sanity (300 sampled contracts)
  bars predating archive window: 0 -> PASS
  weekend-dated bars: 0 -> PASS

## 3. OCC symbol parse round-trip (2,000 sampled)
  parse failures: 0 -> PASS
  expiry-before-trade-day: 0 -> PASS

## 4. Structural
  contracts_daily primary key (day, option_symbol): duplicates impossible by schema -> PASS
  flow_prints executed_at/day mismatches: 0 -> PASS
  orphan bars (no fetch record): 0 -> PASS

## Known, documented limits (not errors)
  - hourly bars exist only where a contract traded that hour (quiet hours = gaps)
  - UW quotes are end-of-day snapshots; intraday quote paths are not stored
  - exits in replays price near trade/mid, ~<=1pt optimistic vs bid on spr<=2 cohorts
  - coverage gate (47 tickers) trades breadth for era-consistency by design
