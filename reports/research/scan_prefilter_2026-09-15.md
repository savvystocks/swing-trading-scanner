# The scan's price pre-filter: would surfacing names by the full $0.30-9.90 band help?

Owner ruling 2026-09-15 01:45 BST ("1 and 2"): retire the fade book's reservation of the top two
flow names, and STUDY the scan's pre-filter before touching it. This is the study. Report only.

The question. `sandbox_proactive_lab.py:scan_candidates` admits a NAME into the generic candidate
pool only if a big-premium alert on it that cycle was in a $0.30-4.00 contract (the "affordable
band", built for the old two-contract $800 budget), plus a separate $4-9.90 CALL pool for the dip
seats and the student pool. Would admitting names by the full $0.30-9.90 band (both sides) give
the probes more, or better, to trade?

Data: v3 corpus (`reports/research/probe_tuner_rows_v3.jsonl`, 72,659 contract-level alert rows,
455 days, ask_at_qualifying_print basis, bid-side exits), alert spread <= 3%. Day means; "vs pool"
= mean of (cell day mean - same-day pool day mean); t over those daily differences. BASE exit
(-50/+50/0.20) except DIP_CONVEXITY on its wide exit (-70/+80/0.30).

## 1. What each band's contracts return, per strategy cell

| cell | $0.30-4.00 (the pre-filter) | $4-9.90 (the call pool) | full $0.30-9.90 |
|---|---|---|---|
| POOL (the control's universe) | -14.52/day, t -10.89, 32/day | -5.12, t -1.13, 37/day | -9.97, t -11.71, 69/day |
| FOLLOW_CALLS | -12.23, t -4.41 | -3.71, t +0.43 | -7.02, t -1.64 |
| BULL_DIP | -7.06, t -0.96 | +0.02, t +1.19 | -2.36, t +0.68 |
| DIP_CONF_MILD | -8.57, t -0.29 | -7.03, t +0.00 | -7.75, t -0.14 |
| DIP_CONVEXITY (wide) | -16.43, t -2.29 | -3.05, t +0.24 | -6.57, t -0.51 |

The cheap band is the worst slice of every cell and of the pool; the call pool is better but no
cell is positive on its own return in either band. The full band is a blend of the two: worse
than the call pool alone for every cell.

## 2. How many names each rule admits (a name is admitted when ANY alert on it that day is in band)

| rule | names per day, median (p10-p90) |
|---|---|
| cheap band $0.30-4.00 | 9 (5-19) |
| call pool $4-9.90 | 9 (3-20) |
| full $0.30-9.90 | 16 (8-37) |
| everything in the corpus | 27 (19-75) |

Names the full rule admits that NEITHER current pool admits: median 2 per day. Their $0.30-9.90
contracts: 368 days, 3.4 trades/day, own -10.82/day, vs pool -6.66, t -2.69, halves -18.7/-2.9.
They are names whose only affordable alerts were puts or pricey non-call flow; the calls among
them are already in the call pool (zero marginal call rows).

## 3. Verdict

Do not widen the pre-filter. The marginal universe is two names a day and it loses at t -2.7.
The pre-filter is not what starves the probes; the price band is (probe_funnel_2026-09-15.md
section 4): every cell's edge sits above $16 per contract, outside any surfacing rule the $1,000
slot can use.

A stricter observation for the owner, not a proposal: the cheap band ($0.30-4.00) is the pool's
worst slice (-14.5/day, t -10.9) and it is the CONTROL's universe. The control is the benchmark
every probe is judged against, so its universe choice shapes the court. Narrowing the control to
the call pool's band would raise the bar (-5.1 vs -14.5); it would also change what "the control"
means mid-experiment, which the court's construction assumes fixed. Left as is; recorded here.

## 4. Caveats

- Contract-level bands stand in for the name-level rule; section 2 does the name-level count.
- The corpus is alert-time; the live scan sees alerts as they arrive, so a name's first alert of
  the day decides which pool it enters. Directionally the same.
- Two years, one corpus, post-hoc bands (the same caveat as the price-band table).
