# Historical corpus stress-test - built overnight 2026-08-13

Corpus: 7632 replayable proxy candidates (20 liquid tickers, Sep-2024 to Jul-2026,
free Alpaca hourly option bars). PROXY caveats: trigger = contract-day premium turnover
in-band (not real sweeps); entry = next session's first hourly open (signal known EOD);
trade-price paths, not bid quotes; no spread screen. HAIRCUT column = 2% round-trip cost.
Nothing here shortcuts the 10-virgin-day bar - this is regime stress-testing, not proof.

| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| FADE mild in-band (live analogue) | 1113/247d | +19.10% (t=1.6) | +16.72% | +24.9 / +13.4 |
| FADE mild whale 400k-1M | 365/189d | +3.18% (t=0.77) | +1.11% | +1.4 / +5.0 |
| FADE trend days (router blocks) | 1467/217d | +2.13% (t=0.61) | +0.09% | +6.4 / -2.1 |
| CONSENSUS trend days (leg candidate) | 1967/222d | +5.64% (t=2.59) | +3.53% | +2.4 / +8.9 |
| CONSENSUS mild days | 1782/256d | +4.15% (t=1.7) | +2.07% | +9.3 / -1.0 |

## By period - FADE mild in-band vs CONSENSUS trend
| period | fade mild | consensus trend |
|---|---|---|
| 2024H2 | +37.84% (268/71d t=0.95) | -4.66% (385/49d t=-1.1) |
| 2025H1+ | +21.35% (146/36d t=1.45) | +7.75% (791/86d t=2.41) |
| 2025H2+ | +10.72% (492/95d t=1.97) | +3.94% (239/28d t=0.56) |
| 2026 | +5.42% (207/45d t=0.84) | +11.93% (552/59d t=2.65) |

## Every-day coverage (owner ask 2026-08-13: green AND red days, all strategies)
| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| EXEC_BASELINE (any shape, any day) | 5749/479d | +5.89% (t=3.86) | +3.77% | +8.5 / +3.3 |
| EXEC_BASELINE green days | 3264/267d | +5.03% (t=2.65) | +2.93% | +8.5 / +1.6 |
| EXEC_BASELINE red days | 2485/212d | +6.97% (t=2.8) | +4.83% | +8.9 / +5.0 |
| FADE mild GREEN days | 595/129d | +7.75% (t=1.59) | +5.60% | +1.9 / +13.5 |
| FADE mild RED days | 518/118d | +31.50% (t=1.29) | +28.87% | +49.3 / +13.7 |
| CONSENSUS trend GREEN (calls w/ uptrend) | 1204/133d | +6.42% (t=2.54) | +4.29% | +6.2 / +6.6 |
| CONSENSUS trend RED (puts w/ downtrend) | 763/89d | +4.48% (t=1.14) | +2.39% | -3.3 / +12.1 |
| MIXED shape (neither fade nor consensus) | 938/387d | +8.46% (t=2.13) | +6.29% | +22.0 / -5.0 |
| CALLS only, green days | 2381/266d | +7.01% (t=3.22) | +4.87% | +9.6 / +4.4 |
| PUTS only, red days | 1532/212d | +13.07% (t=0.97) | +10.80% | +29.1 / -3.0 |

## EARLY_STRENGTH confirmation on FADE mild in-band (enter only after +5..15% rise)
| mode | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| immediate entry (live mode) | 1113/247d | +19.10% (t=1.6) | +16.72% | +24.9 / +13.4 |
| confirmed entry (early-strength) | 267/141d | +14.76% (t=2.33) | +12.46% | +13.5 / +16.0 |

## Exit variants on FADE mild in-band (raw)
| exit rule | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| live trail50/20 stop-50 | 1113/247d | +19.10% (t=1.6) | +16.72% | +24.9 / +13.4 |
| stop -40 | 1113/247d | +20.11% (t=1.7) | +17.71% | +28.1 / +12.2 |
| tight trail 10% | 1113/247d | +16.37% (t=1.39) | +14.05% | +22.2 / +10.6 |
| early trail trig30 | 1113/247d | +16.87% (t=1.43) | +14.54% | +23.1 / +10.7 |
| take-profit +80 | 1113/247d | +9.24% (t=2.1) | +7.05% | +6.1 / +12.3 |
| time-stop ~3 sessions | 1113/247d | +16.09% (t=1.36) | +13.77% | +22.9 / +9.3 |
