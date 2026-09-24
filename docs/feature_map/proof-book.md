# The proof book ("promotion 1"): the $5,000 account judged on its own

## What
A SECOND Alpaca paper account, $5,000, holding ONE strategy so its record is unambiguous. Seated
2026-09-20 by owner ruling (NORTH_STAR v1.9) without the probe court, which stood at 4 of 8 HOLD:
the weekly XSP put credit spread, short 2% OTM / long 4% OTM, one contract, European cash-settled.
The owner lifted the $1,000 per-trade cap for this book in the same ruling, so it trades the same
width as discovery and its weeks are like-for-like with the evidence; worst case is about $1,490 a
contract, roughly 30% of the account. The edge is NOT proven - the audit of 2026-09-20 puts the
honest expectation at +$10 to +$22 a traded week with a 95% range of -$3 to +$40 - so this stint is
the validation, not a victory lap.

## Where
- `proof_book.py:creds` - reads ALPACA_PROOF_API_KEY / ALPACA_PROOF_SECRET_KEY (GitHub Actions
  secrets only, never the VPS) and caches one verdict per process.
- `proof_book.py:verify` - refuses unless the keys exist, differ from the discovery keys, and open
  EXACTLY `proof_account.account_id`. A wrong-slot paste of two valid keys is the failure it exists
  for: it would otherwise trade the $864k discovery book.
- `proof_book.py:load` / `proof_book.py:save` - `proof_logs.json`, this book's own records. An
  unreadable file RAISES (the 2026-08-24 lesson: blind is not flat) so the week's gate cannot re-arm.
- `proof_book.py:sample_equity` - keeps one broker-equity row per UTC day in `proof_logs_equity.jsonl`
  and rewrites it on every open-market cycle (atomic replace), so the row holds the session's LAST mark
  (~19:52 UTC); the stint's drawdown bound is measured from daily equity, and the broker's number is the
  only one our own bookkeeping cannot flatter.
- `sandbox_proactive_lab.py:run_scheduled_cycle` - calls the proof cycle right after the discovery
  one, guarded by `proof_account.enabled`.
- `fivek_probes.py:cycle` - the same code as discovery, with `book="PROOF"` and
  `store=(proof_book.load, proof_book.save)`; condor and put-debit are refused on this book.
- Config: `proof_account` in `fade_book_spec.json` (enabled, account_id, seats, sizing).

## Exercise
- `./.venv/bin/python -c "import proof_book; print(proof_book.verify(('d','d'), 'PA3QMQJYAP59', lambda c: 'OTHER'))"`
  on the VPS - prints the refusal and its reason (the VPS has no proof keys, by design).
- Live: `gh run view <id> --log | grep -n "PROOF"`.

## Healthy
- `PROOF: no trade - no proof credentials in the environment` on the VPS or any run without secrets.
- `fivek[PROOF]: cycle cfg=ok creds=ok` then either an entry line or a stand-down line, once a week.
- `proof_logs_equity.jsonl` holds one row per trading day whose `ts_utc` is the last open-market cycle (~19:52 UTC).

## Evidence
- `proof_logs.json` (records with `book: PROOF`, `trade_set_id` prefixed `p5k`), `proof_logs_equity.jsonl`,
  and the capture denominator frozen in `proof_account.seats[0].capture_denominator`.

## Checks
- MOT 6.41: two samples on one day leave one row holding the later mark; a sample that throws leaves the file
  intact. The sentinel row "proof book equity samples" expects (19, 30, WEEKDAYS): the VPS mtime is the 20:00
  (summer) or 21:00 (winter) poller reset that lands the last cycle's write.
- MOT 6.31: the proof route refuses on a wrong account, on discovery keys and on missing keys; proof
  credentials are absent from `src/alpaca_creds.py:_pairs`; proof records never enter the discovery
  book; an unreadable proof log raises instead of reading empty.

## Traps
- 2026-09-22: the sentinel's `expired_open` and `ghost_open` rows pointed at `proactive_sandbox_logs.json`
  only, so this book had neither alarm; and its equity row expected 19:30 UTC while `proof_book.py:sample_equity`
  writes at about 13:35, which paged [TRADE] every weekday by construction. Both fixed (MOT 6.35).
- 2026-09-24: the equity row was mis-set twice (19:30 at creation, 14:30 on 2026-09-22) without reading when the
  sampler writes or when the poller's reset lands the file on the VPS (13:31 write, 13:45 mtime), so it paged every
  weekday under both. The sampler now rewrites the day's row until the close and the row expects 19:30; a schedule
  row's time is read from the writer's timestamp and the pull that lands it, never assumed (MOT 6.41).
- Proof keys must NEVER be added to `src/alpaca_creds.py:_pairs` - that function probes an
  account-agnostic market-data endpoint and caches one winner process-wide, so it is structurally
  incapable of telling two accounts apart and would silently pick either.
- The discovery sweeps (`sandbox_proactive_lab.py:reconcile_orphans`, `sandbox_proactive_lab.py:flush_positions`,
  `scripts/engine_failover_exits.py`) list positions with DISCOVERY credentials, so they cannot see
  this account at all. That isolation is load-bearing: it is also why nothing here can be swept by
  accident the way the 2026-08-25 spread was.
- `proof_logs.json` and `proof_logs_equity.jsonl` are in the persist step's fixed file list in
  `.github/workflows/v10_lab.yml`. A new state file that is not in that list is silently lost.
- One seat by design. A second strategy here would make the account's equity curve unreadable, which
  is the entire reason this account exists.
