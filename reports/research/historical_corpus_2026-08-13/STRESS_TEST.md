# Historical corpus stress-test - built overnight 2026-08-13

Corpus: 8100 replayable proxy candidates (20 liquid tickers, Sep-2024 to Jul-2026,
free Alpaca hourly option bars). PROXY caveats: trigger = contract-day premium turnover
in-band (not real sweeps); entry = next session's first hourly open (signal known EOD);
trade-price paths, not bid quotes; no spread screen. HAIRCUT column = 2% round-trip cost.
Nothing here shortcuts the 10-virgin-day bar - this is regime stress-testing, not proof.

| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| FADE mild in-band (live analogue) | 1185/247d | +19.22% (t=1.62) | +16.83% | +25.3 / +13.2 |
| FADE mild whale 400k-1M | 391/193d | +1.93% (t=0.48) | -0.11% | -0.6 / +4.5 |
| FADE trend days (router blocks) | 1556/217d | +1.26% (t=0.37) | -0.77% | +6.0 / -3.4 |
| CONSENSUS trend days (leg candidate) | 2061/222d | +5.03% (t=2.37) | +2.93% | +2.3 / +7.7 |
| CONSENSUS mild days | 1920/256d | +3.43% (t=1.42) | +1.36% | +8.0 / -1.2 |

## By period - FADE mild in-band vs CONSENSUS trend
| period | fade mild | consensus trend |
|---|---|---|
| 2024H2 | +38.15% (290/71d t=0.95) | -4.51% (404/49d t=-1.06) |
| 2025H1+ | +21.97% (155/36d t=1.51) | +6.81% (828/86d t=2.15) |
| 2025H2+ | +10.69% (523/95d t=2.05) | +2.31% (254/28d t=0.36) |
| 2026 | +5.14% (217/45d t=0.8) | +11.65% (575/59d t=2.63) |

## Every-day coverage (owner ask 2026-08-13: green AND red days, all strategies)
| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| EXEC_BASELINE (any shape, any day) | 6091/479d | +5.38% (t=3.61) | +3.27% | +8.0 / +2.7 |
| EXEC_BASELINE green days | 3455/267d | +4.19% (t=2.28) | +2.10% | +7.2 / +1.2 |
| EXEC_BASELINE red days | 2636/212d | +6.88% (t=2.8) | +4.75% | +9.5 / +4.2 |
| FADE mild GREEN days | 634/129d | +7.82% (t=1.65) | +5.66% | +1.7 / +13.9 |
| FADE mild RED days | 551/118d | +31.68% (t=1.3) | +29.04% | +50.9 / +12.4 |
| CONSENSUS trend GREEN (calls w/ uptrend) | 1259/133d | +5.49% (t=2.21) | +3.38% | +5.9 / +5.1 |
| CONSENSUS trend RED (puts w/ downtrend) | 802/89d | +4.34% (t=1.14) | +2.25% | -2.9 / +11.4 |
| MIXED shape (neither fade nor consensus) | 987/390d | +8.41% (t=2.14) | +6.24% | +21.8 / -5.0 |
| CALLS only, green days | 2512/266d | +5.90% (t=2.8) | +3.79% | +8.5 / +3.3 |
| PUTS only, red days | 1634/212d | +13.00% (t=0.96) | +10.74% | +28.9 / -2.9 |

## EARLY_STRENGTH confirmation on FADE mild in-band (enter only after +5..15% rise)
| mode | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| immediate entry (live mode) | 1185/247d | +19.22% (t=1.62) | +16.83% | +25.3 / +13.2 |
| confirmed entry (early-strength) | 282/147d | +18.08% (t=2.66) | +15.72% | +13.6 / +22.5 |

## Exit variants on FADE mild in-band (raw)
| exit rule | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| live trail50/20 stop-50 | 1185/247d | +19.22% (t=1.62) | +16.83% | +25.3 / +13.2 |
| stop -40 | 1185/247d | +20.07% (t=1.7) | +17.66% | +28.4 / +11.8 |
| tight trail 10% | 1185/247d | +16.82% (t=1.43) | +14.49% | +22.8 / +10.9 |
| early trail trig30 | 1185/247d | +17.42% (t=1.48) | +15.07% | +23.9 / +11.0 |
| take-profit +80 | 1185/247d | +10.52% (t=2.38) | +8.31% | +7.5 / +13.5 |
| time-stop ~3 sessions | 1185/247d | +16.37% (t=1.38) | +14.04% | +23.7 / +9.1 |
