# Historical corpus stress-test - built overnight 2026-08-13

Corpus: 6835 replayable proxy candidates (20 liquid tickers, Sep-2024 to Jul-2026,
free Alpaca hourly option bars). PROXY caveats: trigger = contract-day premium turnover
in-band (not real sweeps); entry = next session's first hourly open (signal known EOD);
trade-price paths, not bid quotes; no spread screen. HAIRCUT column = 2% round-trip cost.
Nothing here shortcuts the 10-virgin-day bar - this is regime stress-testing, not proof.

| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| FADE mild in-band (live analogue) | 1013/244d | +19.71% (t=1.63) | +17.32% | +27.0 / +12.4 |
| FADE mild whale 400k-1M | 320/178d | +3.33% (t=0.77) | +1.27% | +1.2 / +5.5 |
| FADE trend days (router blocks) | 1306/213d | +3.47% (t=0.95) | +1.40% | +7.3 / -0.3 |
| CONSENSUS trend days (leg candidate) | 1775/222d | +5.31% (t=2.41) | +3.21% | +2.5 / +8.2 |
| CONSENSUS mild days | 1566/256d | +3.82% (t=1.55) | +1.74% | +8.8 / -1.2 |

## By period - FADE mild in-band vs CONSENSUS trend
| period | fade mild | consensus trend |
|---|---|---|
| 2024H2 | +41.18% (239/70d t=1.01) | -3.75% (341/49d t=-0.82) |
| 2025H1+ | +24.41% (133/35d t=1.6) | +7.06% (712/86d t=2.2) |
| 2025H2+ | +10.39% (451/95d t=1.88) | +2.72% (215/28d t=0.38) |
| 2026 | +1.97% (190/44d t=0.32) | +11.52% (507/59d t=2.58) |

## Every-day coverage (owner ask 2026-08-13: green AND red days, all strategies)
| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| EXEC_BASELINE (any shape, any day) | 5164/479d | +6.14% (t=3.42) | +4.01% | +9.1 / +3.2 |
| EXEC_BASELINE green days | 2926/267d | +5.25% (t=2.57) | +3.15% | +8.8 / +1.7 |
| EXEC_BASELINE red days | 2238/212d | +7.25% (t=2.31) | +5.11% | +9.8 / +4.7 |
| FADE mild GREEN days | 539/128d | +7.66% (t=1.55) | +5.51% | +2.3 / +13.1 |
| FADE mild RED days | 474/116d | +33.01% (t=1.33) | +30.35% | +54.4 / +11.6 |
| CONSENSUS trend GREEN (calls w/ uptrend) | 1080/133d | +5.65% (t=2.2) | +3.54% | +5.8 / +5.5 |
| CONSENSUS trend RED (puts w/ downtrend) | 695/89d | +4.81% (t=1.21) | +2.71% | -2.4 / +11.8 |
| MIXED shape (neither fade nor consensus) | 855/380d | +7.07% (t=1.75) | +4.93% | +20.9 / -6.7 |
| CALLS only, green days | 2134/266d | +6.37% (t=2.86) | +4.24% | +8.9 / +3.8 |
| PUTS only, red days | 1380/212d | +13.47% (t=0.99) | +11.20% | +30.8 / -3.8 |

## EARLY_STRENGTH confirmation on FADE mild in-band (enter only after +5..15% rise)
| mode | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| immediate entry (live mode) | 1013/244d | +19.71% (t=1.63) | +17.32% | +27.0 / +12.4 |
| confirmed entry (early-strength) | 244/133d | +14.25% (t=2.24) | +11.97% | +15.9 / +12.6 |

## Exit variants on FADE mild in-band (raw)
| exit rule | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| live trail50/20 stop-50 | 1013/244d | +19.71% (t=1.63) | +17.32% | +27.0 / +12.4 |
| stop -40 | 1013/244d | +20.70% (t=1.72) | +18.29% | +30.0 / +11.4 |
| tight trail 10% | 1013/244d | +17.16% (t=1.44) | +14.82% | +24.4 / +9.9 |
| early trail trig30 | 1013/244d | +17.77% (t=1.49) | +15.41% | +25.2 / +10.3 |
| take-profit +80 | 1013/244d | +9.60% (t=2.17) | +7.41% | +7.1 / +12.1 |
| time-stop ~3 sessions | 1013/244d | +17.23% (t=1.43) | +14.89% | +25.3 / +9.2 |
