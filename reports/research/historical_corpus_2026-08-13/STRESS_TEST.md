# Historical corpus stress-test - built overnight 2026-08-13

Corpus: 7304 replayable proxy candidates (20 liquid tickers, Sep-2024 to Jul-2026,
free Alpaca hourly option bars). PROXY caveats: trigger = contract-day premium turnover
in-band (not real sweeps); entry = next session's first hourly open (signal known EOD);
trade-price paths, not bid quotes; no spread screen. HAIRCUT column = 2% round-trip cost.
Nothing here shortcuts the 10-virgin-day bar - this is regime stress-testing, not proof.

| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| FADE mild in-band (live analogue) | 1071/246d | +19.15% (t=1.6) | +16.77% | +25.0 / +13.3 |
| FADE mild whale 400k-1M | 350/184d | +2.54% (t=0.6) | +0.49% | +0.7 / +4.4 |
| FADE trend days (router blocks) | 1399/217d | +2.95% (t=0.84) | +0.90% | +7.4 / -1.4 |
| CONSENSUS trend days (leg candidate) | 1899/222d | +5.63% (t=2.56) | +3.52% | +2.6 / +8.7 |
| CONSENSUS mild days | 1682/256d | +3.64% (t=1.51) | +1.57% | +9.1 / -1.8 |

## By period - FADE mild in-band vs CONSENSUS trend
| period | fade mild | consensus trend |
|---|---|---|
| 2024H2 | +39.24% (256/70d t=0.97) | -4.32% (366/49d t=-0.98) |
| 2025H1+ | +21.35% (146/36d t=1.45) | +7.73% (765/86d t=2.41) |
| 2025H2+ | +11.05% (470/95d t=2.02) | +3.24% (233/28d t=0.46) |
| 2026 | +3.27% (199/45d t=0.53) | +11.98% (535/59d t=2.65) |

## Every-day coverage (owner ask 2026-08-13: green AND red days, all strategies)
| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| EXEC_BASELINE (any shape, any day) | 5510/479d | +5.87% (t=3.6) | +3.75% | +8.7 / +3.0 |
| EXEC_BASELINE green days | 3125/267d | +5.22% (t=2.65) | +3.11% | +8.8 / +1.7 |
| EXEC_BASELINE red days | 2385/212d | +6.69% (t=2.45) | +4.56% | +9.0 / +4.4 |
| FADE mild GREEN days | 570/128d | +7.97% (t=1.62) | +5.81% | +2.3 / +13.6 |
| FADE mild RED days | 501/118d | +31.29% (t=1.29) | +28.66% | +49.6 / +13.0 |
| CONSENSUS trend GREEN (calls w/ uptrend) | 1162/133d | +6.25% (t=2.45) | +4.13% | +6.4 / +6.1 |
| CONSENSUS trend RED (puts w/ downtrend) | 737/89d | +4.70% (t=1.19) | +2.61% | -3.0 / +12.2 |
| MIXED shape (neither fade nor consensus) | 903/385d | +8.12% (t=2.03) | +5.96% | +21.8 / -5.4 |
| CALLS only, green days | 2286/266d | +6.78% (t=3.08) | +4.64% | +9.6 / +4.0 |
| PUTS only, red days | 1471/212d | +13.48% (t=1.0) | +11.21% | +30.2 / -3.3 |

## EARLY_STRENGTH confirmation on FADE mild in-band (enter only after +5..15% rise)
| mode | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| immediate entry (live mode) | 1071/246d | +19.15% (t=1.6) | +16.77% | +25.0 / +13.3 |
| confirmed entry (early-strength) | 259/139d | +15.65% (t=2.44) | +13.34% | +14.6 / +16.7 |

## Exit variants on FADE mild in-band (raw)
| exit rule | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| live trail50/20 stop-50 | 1071/246d | +19.15% (t=1.6) | +16.77% | +25.0 / +13.3 |
| stop -40 | 1071/246d | +20.20% (t=1.7) | +17.79% | +28.1 / +12.3 |
| tight trail 10% | 1071/246d | +16.59% (t=1.41) | +14.26% | +22.3 / +10.9 |
| early trail trig30 | 1071/246d | +16.94% (t=1.43) | +14.60% | +23.2 / +10.7 |
| take-profit +80 | 1071/246d | +9.15% (t=2.09) | +6.97% | +5.8 / +12.5 |
| time-stop ~3 sessions | 1071/246d | +16.48% (t=1.39) | +14.15% | +23.2 / +9.8 |
