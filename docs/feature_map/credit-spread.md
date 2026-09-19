# Credit spread (CREDIT_SPREAD_W) and the $5k defined-risk probes

## What
The income seat's candidate: once a week, sell the 2%-OTM XSP put and buy the 4%-OTM put
(max loss = width minus credit, about $1,200 on XSP), European and cash-settled so no
sell-to-close order ever exists and it can never day-trade. Judged by the court on ISO weeks
(3 of 8 as of 2026-09-11; week four expired Friday 2026-09-11 and settles on Monday's first
cycle). The condor variant was killed by its backtest; PUT_DEBIT_W (bear-only) was retired in the
2026-09-10 cull. Unseatable on the proof account while its max loss exceeds the $1,000 cap
(NORTH_STAR v1.7); the v1.8 income-seat amendment lets a narrower width seat at the cap.

## Where
- `fivek_probes.py:cycle` - called every engine cycle from `sandbox_proactive_lab.py:run_scheduled_cycle`
  (`fivek_probes.cycle(creds, allow_entries=not (brake_active or halt_active))`), fail-open.
- `fivek_probes.py:_enter` - one entry per structure per ISO week, first cycle at or after 15:00
  UTC; the LONG wing is bought FIRST so a partial fill can never leave a naked short; broker
  idempotency check (`fivek_probes.py:_held`) before entering; limits from `fivek_probes.py:_quote`;
  orders via `fivek_probes.py:_order`; OCCs from `fivek_probes.py:_occ`.
- `fivek_probes.py:_settle_one` - after Friday expiry, settles each open record against the ^XSP
  close (`fivek_probes.py:_xsp_close_series`, yfinance) and books `settle.pnl_usd`.
- Config: `fivek_probes.py:_cfg` reads `probe.fivek` from `fade_book_spec.json`.
- Records: `book: PROBE`, `probe_strategy: CREDIT_SPREAD_W`, NO legs dict (the options exit engine
  ignores them), `occ` + `occ_more` so the orphan reconciler knows every leg.

## Exercise
- `./.venv/bin/python scripts/regime_drill.py | grep -n "PUT_DEBIT_W\|fivek"` (scenario 5: wings first).
- Live: `gh run view <id> --log | grep -in "fivek\|CREDIT_SPREAD\|settle"` on Monday's first cycle.
- Standing: `grep "CREDIT_SPREAD_W" /home/poller/sunday_boundary.log | tail -3`.

## Healthy
- `PROBE CREDIT_SPREAD_W: 3/8 live virgin weeks vs control - HOLD` in the Friday court.
- A settle line on the first cycle after expiry with a `pnl_usd`; `fivek probes skipped (fail-open): ...`
  means the module raised and did nothing - read the reason.

## Evidence
- Records with `settle`; the court's weekly unit (`scripts/sunday_boundary.py` `weekmeans`);
  the 2.5-year backtest in `scripts/fivek_backtests.py` (+$2.3k over 114 weeks, superseded-basis caveats apply).
- `scripts/xsp_quote_log.py` (2026-09-19, VPS cron, off the trade path): every backtest of this book priced SPY while the
  book trades XSP, so it logs bid/ask on the would-be XSP legs and the matched SPY legs at the same instant, through
  `fivek_probes.py:_quote` and `fivek_probes.py:_occ` (the engine's own INDICATIVE feed), into `reports/research/xsp_quotes.jsonl`.
  The decision rule is fixed in its docstring: median entry-window excess friction <= $5 a spread and the SPY backtests
  transfer; >= $20 and XSP's own spread consumes the edge. Four weeks, weeks as the unit of evidence.
- `scripts/cs_legs_pull.py` (2026-09-19, Saturday 12:00 UTC cron, off the trade path): the legs this rule could have traded,
  asked for BY NAME from the vendor's per-contract history (closing bid and ask, traded or not), every finished week since
  2023-10-23, strikes 1.0-6.0% below spot in 0.5% steps, XSP and SPY, into `data/cs_legs.db` (`scripts/cs_legs_pull.py:wanted`,
  `scripts/cs_legs_pull.py:mark_final`). Coverage of the live 2%/4% rule is 91% of weeks on XSP and 100% on SPY, against 54% from
  the capped chain archive. `scripts/cs_legs_pull.py:backup` leaves `cs_legs.db.gz` in the snapshot folder so the nightly
  off-box backup carries it: the vendor's floor rolls forward daily and the oldest weeks can never be pulled again.
- `scripts/cs_legs_measure.py` (on demand: `./.venv/bin/python scripts/cs_legs_measure.py`) measures the rule on that database -
  real XSP quotes, real ^XSP settlement, the BEAR stand-down applied, coverage and the Clopper-Pearson tail bound on every row.
  As of 2026-09-19 the live 2%/4% rule: 122 gated weeks, 92% win, +$26.1 a week, t 2.95, worst week -$624 against an average
  $44 credit and $1,187 max loss; +$10.3 a week (t 0.78) with no gate; negative at max loss on the tail bound. Tested as the
  instrument, SPY does not beat it once American exercise is respected (18 of 152 weeks finish between the strikes), so the
  book stays on XSP.
- `scripts/cs_live_fills.py` (same cron, read-only on the broker): quoted credit vs the credit the paper account actually
  filled, per record, into `reports/research/cs_live_fills.json` (`scripts/cs_live_fills.py:measure`). These are PAPER fills
  (the simulator fills at or inside the quote), so the figure bounds book-keeping error, not live-market slippage.

## Checks
- Drill scenario 5 (bear-only PUT_DEBIT_W, wings first); the court's weekly cadence branch.

## Traps
- Regime gate: `probe.fivek.credit_spread.regime_gate` (default true) stands the spread down in a
  BEAR week (the playbook on real SPY quotes: +$64/week in mild tape, bleeds in bear); an unknown
  regime allows the entry (fail-open, a missed income week beats a blocked settle path).
- 2026-08-11 FRIENDLY-FIRE ADOPTION class: bare-occ records must stay known to
  `sandbox_proactive_lab.py:reconcile_orphans` (they are: occ + occ_more).
- Settlement depends on yfinance returning ^XSP; a missing close leaves the record open until the
  next cycle that can fetch it. Check the Monday log if a week's settle line is missing.
- Never propose a sell-to-close for these; they are cash-settled by design.
