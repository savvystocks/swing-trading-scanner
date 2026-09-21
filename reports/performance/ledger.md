# RETURNS LEDGER - 2026-09-21T22:24:05+00:00

live from proactive_sandbox_logs.json (1096 records, the court's construction); archive from reports/research/probe_tuner_rows_v3.jsonl (90405 rows, last day 2026-09-11, ask_at_qualifying_print / d1_close).

| strategy | live n | %/trade | win | best removed | unit | units | own mean | shared | t vs control | halves | $ | archive %/day (pool) | t vs pool | archive halves | court |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EXEC_BASELINE | 65 | +10.2 | 45% | +3.5 | days | 23 | +12.4 | 23 | +0.00 | +30.9/-4.5 | +2,557 | -5.1 (-5.1) | n/a | -4.4/-5.8 | - |
| FOLLOW_CALLS | 17 | +6.2 | 59% | +0.8 | days | 10 | -6.3 | 10 | -0.39 | -57.7/+45.1 | +971 | -0.1 (-5.1) | +4.99 | +2.3/-2.6 | 7/8 live virgin days vs control - HOLD |
| BULL_DIP | 0 | n/a | n/a | n/a | days | 0 | n/a | 0 | n/a | n/a/n/a | n/a | +2.2 (-5.1) | +4.44 | +5.7/-1.4 | 0/8 live virgin days vs control - HOLD |
| DIP_CONF_MILD | 2 | -11.7 | 50% | -50.9 | days | 2 | -11.7 | 2 | n/a | -50.9/+27.5 | -236 | +0.5 (-7.4) | +2.69 | +3.8/-2.8 | 1/8 live virgin days vs control - HOLD |
| DIP_CONVEXITY | 0 | n/a | n/a | n/a | days | 0 | n/a | 0 | n/a | n/a/n/a | n/a | +8.3 (-4.8) | +3.83 | +5.7/+10.9 | 0/8 live virgin days vs control - HOLD |
| WINNER_PROFILE | 11 | +21.1 | 36% | -25.5 | days | 6 | +55.4 | 6 | +0.58 | -18.0/+128.8 | -1,256 | -5.2 (-5.1) | -2.54 | -4.5/-5.9 | - |
| CREDIT_SPREAD_W | 6 | +4.3 | 100% | +3.0 | weeks | 5 | +4.9 | 5 | -0.39 | +3.7/+5.7 | +256 | n/a (n/a) | n/a | n/a/n/a | 4/8 live virgin weeks vs control - HOLD |
| STUDENT_FAMILY | 0 | n/a | n/a | n/a | days | 0 | n/a | 0 | n/a | n/a/n/a | n/a | n/a (n/a) | n/a | n/a/n/a | 0/8 live virgin days vs control - HOLD |
| CONSENSUS (retired) | 19 | -20.1 | 21% | -29.3 | days | 11 | -20.6 | 8 | -0.31 | -10.2/-29.3 | -3,424 | n/a (n/a) | n/a | n/a/n/a | - |
| DP_HEAVY (retired) | 5 | -33.7 | 0% | -41.9 | days | 4 | -29.6 | 2 | n/a | -9.0/-50.2 | -1,426 | n/a (n/a) | n/a | n/a/n/a | - |
| FADE_DP (retired) | 1 | +387.5 | 100% | n/a | days | 1 | +387.5 | 1 | n/a | n/a/+387.5 | +767 | n/a (n/a) | n/a | n/a/n/a | - |
| FADE_UNROUTED (retired) | 4 | -48.0 | 0% | -51.0 | days | 4 | -48.0 | 4 | -3.61 | -49.6/-46.4 | -1,804 | n/a (n/a) | n/a | n/a/n/a | - |
| FADE_WHALE (retired) | 1 | -57.3 | 0% | n/a | days | 1 | -57.3 | 0 | n/a | n/a/-57.3 | -173 | n/a (n/a) | n/a | n/a/n/a | - |
| QUIET_TAPE (retired) | 10 | -5.4 | 30% | -10.6 | days | 7 | -5.8 | 4 | +1.19 | -27.4/+10.4 | -374 | n/a (n/a) | n/a | n/a/n/a | - |
| VRP_DAILY (retired) | 3 | +1.7 | 100% | +0.8 | days | 2 | +2.1 | 2 | n/a | +0.8/+3.4 | +50 | n/a (n/a) | n/a | n/a/n/a | - |

Reading the table: live units are the court's units (days, or weeks for the weekly structures and the student family); t vs control uses the court's symmetric trim once 8 units are shared; 'best removed' is the per-trade mean without the single best trade; archive cells are on the executable basis and are day means over the cell's own days with the pool on those same days beside them. A number without its n is not evidence; every row carries both.
