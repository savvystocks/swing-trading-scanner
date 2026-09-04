# Historical corpus stress-test - built overnight 2026-08-13

Corpus: 7895 replayable proxy candidates (20 liquid tickers, Sep-2024 to Jul-2026,
free Alpaca hourly option bars). PROXY caveats: trigger = contract-day premium turnover
in-band (not real sweeps); entry = next session's first hourly open (signal known EOD);
trade-price paths, not bid quotes; no spread screen. HAIRCUT column = 2% round-trip cost.
Nothing here shortcuts the 10-virgin-day bar - this is regime stress-testing, not proof.

| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| FADE mild in-band (live analogue) | 1161/247d | +19.12% (t=1.61) | +16.74% | +25.4 / +12.9 |
| FADE mild whale 400k-1M | 376/190d | +2.65% (t=0.65) | +0.59% | +0.9 / +4.4 |
| FADE trend days (router blocks) | 1519/217d | +1.62% (t=0.47) | -0.41% | +6.1 / -2.8 |
| CONSENSUS trend days (leg candidate) | 2018/222d | +5.39% (t=2.51) | +3.28% | +2.3 / +8.5 |
| CONSENSUS mild days | 1849/256d | +3.98% (t=1.64) | +1.90% | +8.9 / -0.9 |

## By period - FADE mild in-band vs CONSENSUS trend
| period | fade mild | consensus trend |
|---|---|---|
| 2024H2 | +38.32% (283/71d t=0.96) | -4.70% (398/49d t=-1.1) |
| 2025H1+ | +22.33% (150/36d t=1.53) | +7.40% (807/86d t=2.31) |
| 2025H2+ | +10.22% (514/95d t=1.93) | +2.74% (251/28d t=0.42) |
| 2026 | +5.08% (214/45d t=0.79) | +12.10% (562/59d t=2.71) |

## Every-day coverage (owner ask 2026-08-13: green AND red days, all strategies)
| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| EXEC_BASELINE (any shape, any day) | 5939/479d | +5.65% (t=3.73) | +3.54% | +8.3 / +3.0 |
| EXEC_BASELINE green days | 3376/267d | +4.51% (t=2.4) | +2.42% | +7.7 / +1.4 |
| EXEC_BASELINE red days | 2563/212d | +7.08% (t=2.86) | +4.94% | +9.5 / +4.6 |
| FADE mild GREEN days | 622/129d | +7.78% (t=1.61) | +5.62% | +2.1 / +13.3 |
| FADE mild RED days | 539/118d | +31.53% (t=1.3) | +28.90% | +50.6 / +12.4 |
| CONSENSUS trend GREEN (calls w/ uptrend) | 1238/133d | +6.07% (t=2.41) | +3.95% | +5.8 / +6.3 |
| CONSENSUS trend RED (puts w/ downtrend) | 780/89d | +4.38% (t=1.15) | +2.29% | -3.0 / +11.6 |
| MIXED shape (neither fade nor consensus) | 972/388d | +8.64% (t=2.19) | +6.46% | +21.8 / -4.6 |
| CALLS only, green days | 2453/266d | +6.79% (t=3.13) | +4.66% | +9.1 / +4.5 |
| PUTS only, red days | 1588/212d | +13.07% (t=0.97) | +10.80% | +28.9 / -2.7 |

## EARLY_STRENGTH confirmation on FADE mild in-band (enter only after +5..15% rise)
| mode | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| immediate entry (live mode) | 1161/247d | +19.12% (t=1.61) | +16.74% | +25.4 / +12.9 |
| confirmed entry (early-strength) | 277/146d | +18.02% (t=2.63) | +15.66% | +13.3 / +22.7 |

## Exit variants on FADE mild in-band (raw)
| exit rule | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| live trail50/20 stop-50 | 1161/247d | +19.12% (t=1.61) | +16.74% | +25.4 / +12.9 |
| stop -40 | 1161/247d | +20.18% (t=1.7) | +17.77% | +28.6 / +11.8 |
| tight trail 10% | 1161/247d | +16.65% (t=1.42) | +14.32% | +22.8 / +10.5 |
| early trail trig30 | 1161/247d | +17.33% (t=1.47) | +14.98% | +24.0 / +10.7 |
| take-profit +80 | 1161/247d | +9.89% (t=2.24) | +7.69% | +7.4 / +12.4 |
| time-stop ~3 sessions | 1161/247d | +16.50% (t=1.39) | +14.17% | +24.0 / +9.0 |
