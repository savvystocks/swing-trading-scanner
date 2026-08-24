# GRAND BACKTEST - 2026-08-23 (ruthless, market-neutral bar)

FLOW = real UW triggers, day-mean %. STRUCT = weekly $ P&L. DURABLE (ruthless) = positive
overall + on RED days + 2026 test + both halves (FLOW) / t>1.5 + both halves (STRUCT).
Mined/in-sample - durables become PRIORITY probes, still cleared by live virgin days.

| candidate | kind | all mean/t | red-day | 2026 test | DURABLE |
|---|---|---|---|---|---|
| FOLLOW+calls | FLOW | +15.9/+7.70 | +11.2/t+4.3 | +16.1 | YES |
| FOLLOW+calls | FLOW | +15.9/+7.70 | +11.2/t+4.3 | +16.1 | YES |
| FOLLOW+calls+highIV | FLOW | +15.1/+7.11 | +11.1/t+4.0 | +13.1 | YES |
| CONSENSUS+calls | FLOW | +19.4/+6.79 | +16.0/t+4.2 | +27.2 | YES |
| CONSENSUS+calls | FLOW | +19.4/+6.79 | +16.0/t+4.2 | +27.2 | YES |
| FOLLOW+OIbuild+calls | FLOW | +15.4/+6.79 | +10.1/t+3.6 | +16.3 | YES |
| CONSENSUS+calls+highIV | FLOW | +21.6/+6.78 | +18.9/t+4.8 | +24.0 | YES |
| CONSENSUS+OIbuild+calls | FLOW | +19.3/+6.24 | +15.6/t+3.9 | +29.1 | YES |
| FOLLOW+calls+bigprem | FLOW | +12.4/+5.96 | +9.0/t+3.2 | +12.4 | YES |
| CONSENSUS+calls+bigprem | FLOW | +16.4/+5.39 | +14.8/t+3.8 | +27.1 | YES |
| CONSENSUS+midDTE+calls | FLOW | +15.6/+5.03 | +13.4/t+3.1 | +26.2 | YES |
| FOLLOW+midDTE+calls | FLOW | +11.2/+4.85 | +5.4/t+1.9 | +14.1 | YES |
| CONSENSUS+highIV | FLOW | +11.2/+4.34 | +6.9/t+2.2 | +10.8 | YES |
| CONSENSUS+highIV | FLOW | +11.2/+4.34 | +6.9/t+2.2 | +10.8 | YES |
| FOLLOW+OIbuild+highIV | FLOW | +5.8/+4.24 | +2.3/t+1.3 | +7.4 | YES |
| FOLLOW+highIV | FLOW | +5.0/+4.21 | +2.2/t+1.4 | +5.7 | YES |
| FOLLOW+highIV | FLOW | +5.0/+4.21 | +2.2/t+1.4 | +5.7 | YES |
| CONSENSUS+OIbuild+highIV | FLOW | +12.5/+4.16 | +7.5/t+2.2 | +13.5 | YES |
| FADE+calls | FLOW | +18.6/+4.11 | +10.2/t+2.0 | +15.5 | YES |
| FADE+calls | FLOW | +18.6/+4.11 | +10.2/t+2.0 | +15.5 | YES |
| CONSENSUS | FLOW | +9.4/+4.05 | +4.5/t+1.5 | +10.3 | YES |
| CONSENSUS+OIbuild | FLOW | +9.4/+3.74 | +4.5/t+1.4 | +11.8 | YES |
| CONSENSUS+OIbuild | FLOW | +9.4/+3.74 | +4.5/t+1.4 | +11.8 | YES |
| CONSENSUS+highIV+bigprem | FLOW | +9.7/+3.74 | +10.2/t+2.5 | +8.3 | YES |
| FADE+calls+highIV | FLOW | +14.5/+3.51 | +7.5/t+1.5 | +10.9 | YES |
| FADE+OIbuild+calls | FLOW | +16.6/+3.42 | +8.1/t+1.5 | +11.0 | YES |
| FADE+calls+bigprem | FLOW | +16.4/+3.31 | +8.3/t+1.4 | +11.2 | YES |
| CONSENSUS+OIbuild+midDTE | FLOW | +7.9/+3.06 | +4.8/t+1.4 | +11.6 | YES |
| CONSENSUS+midDTE+highIV | FLOW | +8.0/+2.99 | +6.0/t+1.6 | +6.8 | YES |
| CONSENSUS+midDTE | FLOW | +7.3/+2.90 | +4.4/t+1.3 | +11.2 | YES |
| CONSENSUS+midDTE | FLOW | +7.3/+2.90 | +4.4/t+1.3 | +11.2 | YES |
| CONSENSUS+shortDTE+highIV | FLOW | +17.6/+2.79 | +14.0/t+1.5 | +34.7 | YES |
| CONSENSUS+bigprem | FLOW | +6.4/+2.64 | +2.9/t+1.0 | +8.5 | YES |
| CONSENSUS+bigprem | FLOW | +6.4/+2.64 | +2.9/t+1.0 | +8.5 | YES |
| FOLLOW+shortDTE+highIV | FLOW | +6.9/+2.51 | +3.1/t+0.8 | +12.8 | YES |

DURABLE survivors (ruthless bar): 45 -> FOLLOW+calls, FOLLOW+calls, FOLLOW+calls+highIV, CONSENSUS+calls, CONSENSUS+calls, FOLLOW+OIbuild+calls, CONSENSUS+calls+highIV, CONSENSUS+OIbuild+calls, FOLLOW+calls+bigprem, CONSENSUS+calls+bigprem, CONSENSUS+midDTE+calls, FOLLOW+midDTE+calls, CONSENSUS+highIV, CONSENSUS+highIV, FOLLOW+OIbuild+highIV, FOLLOW+highIV, FOLLOW+highIV, CONSENSUS+OIbuild+highIV, FADE+calls, FADE+calls, CONSENSUS, CONSENSUS+OIbuild, CONSENSUS+OIbuild, CONSENSUS+highIV+bigprem, FADE+calls+highIV, FADE+OIbuild+calls, FADE+calls+bigprem, CONSENSUS+OIbuild+midDTE, CONSENSUS+midDTE+highIV, CONSENSUS+midDTE, CONSENSUS+midDTE, CONSENSUS+shortDTE+highIV, CONSENSUS+bigprem, CONSENSUS+bigprem, FOLLOW+shortDTE+highIV, FOLLOW+highIV+bigprem, CONSENSUS+sweep50+calls, FOLLOW+sweep50+calls, CONSENSUS+OIbuild+sweep50, CONSENSUS+OIbuild+bigprem, CONSENSUS+sweep50+midDTE, CONSENSUS+sweep50, CONSENSUS+sweep50, FADE+sweep50+calls, FOLLOW+sweep50+midDTE
