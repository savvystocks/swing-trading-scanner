# PERFORMANCE MAP

The returns counterpart of the engine feature map. One file per active strategy stating what the
rule is, which exact evidence cell it stands on (basis, window, exit, sizing, regime), the honest
numbers WITH their sample sizes, how to recompute them, what healthy looks like, where live results
land, the checks that guard the claim, and the traps that have already produced a wrong number.

Every number in these files is a token of the form `[[ strategies.NAME.side.key = value ]]`
(written without the inner spaces in the files) that
`scripts/returns_ledger.py --update-map` rewrites from `reports/performance/ledger.json`.
`scripts/performance_map_lint.py` (MOT 6.19) fails the gate when a token disagrees with the ledger,
when a token names a key the ledger does not hold, when an active strategy has no file, or when
the ledger is older than ten days. A number in chat that is not in the ledger is an opinion.

## The two sources and how they are read
- LIVE is the book, `proactive_sandbox_logs.json`, read exactly as the Friday court reads it:
  book PROBE, the ENTRY day, the first leg's realized return, a settled weekly structure as its
  dollars over $1,000, the student pickers pooled into STUDENT_FAMILY. Units are days, or ISO
  weeks for the weekly structures; t against the control uses the court's symmetric trim once
  eight units are shared. The tuning clock (`probe.tuning.<name>.applied`) excludes pre-change days.
- ARCHIVE is `reports/research/probe_tuner_rows_v3.jsonl`: every whale trigger of two years on the
  executable basis (ask at the qualifying print plus a ten-minute delay, bid-side exits,
  prior-close regime columns), replayed on the exit the roster runs. A cell is a day mean over
  the cell's own days, always shown beside the pool on those same days. Numbers on the older
  bases are superseded and never quoted here.
- A strategy with no honest archive cell says so (the credit spread; the winner profile's second
  leg). The student family's archive is the live pickers' executed slice from their model files.

## One command
`./.venv/bin/python scripts/returns_ledger.py` prints the table and rewrites the ledger;
add `--update-map` to refresh the tokens in these files. The Friday cron does both after the court.

## Reading a number honestly
Every row carries n. Eight days is eight days. A per-trade mean without the "best removed"
column beside it hides a jackpot. A search-window t is selection-biased by construction; only a
holdout or the live court is evidence. Capture (live over archive) exists only from 20 live days.

| file | strategy | unit |
|---|---|---|
| EXEC_BASELINE.md | the control | days |
| FOLLOW_CALLS.md | aggressive call flow, all regimes | days |
| BULL_DIP.md | bull-regime dips | days |
| DIP_CONF_MILD.md | confirmed mild-regime dips on the trigger contract | days |
| DIP_CONVEXITY.md | bear-regime dips | days |
| WINNER_PROFILE.md | the frozen secondary control | days |
| CREDIT_SPREAD_W.md | the weekly XSP credit spread | weeks |
| STUDENT_FAMILY.md | the student pickers as one book | days |
