# Historical corpus stress-test - built overnight 2026-08-13

Corpus: 3743 replayable proxy candidates (20 liquid tickers, Sep-2024 to Jul-2026,
free Alpaca hourly option bars). PROXY caveats: trigger = contract-day premium turnover
in-band (not real sweeps); entry = next session's first hourly open (signal known EOD);
trade-price paths, not bid quotes; no spread screen. HAIRCUT column = 2% round-trip cost.
Nothing here shortcuts the 10-virgin-day bar - this is regime stress-testing, not proof.

| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| FADE mild in-band (live analogue) | 552/218d | +11.28% (t=2.24) | +9.05% | +7.8 / +14.8 |
| FADE mild whale 400k-1M | 159/115d | +5.88% (t=0.88) | +3.76% | +5.1 / +6.6 |
| FADE trend days (router blocks) | 734/198d | -0.35% (t=-0.1) | -2.35% | +3.6 / -4.3 |
| CONSENSUS trend days (leg candidate) | 1049/216d | +3.81% (t=1.46) | +1.74% | -1.1 / +8.7 |
| CONSENSUS mild days | 929/244d | +5.79% (t=1.63) | +3.67% | +10.1 / +1.5 |

## By period - FADE mild in-band vs CONSENSUS trend
| period | fade mild | consensus trend |
|---|---|---|
| 2024H2 | -4.77% (120/59d t=-0.74) | -9.27% (169/47d t=-1.87) |
| 2025H1+ | +38.23% (67/32d t=1.63) | +7.48% (392/85d t=1.79) |
| 2025H2+ | +14.86% (257/88d t=2.1) | +2.92% (130/28d t=0.33) |
| 2026 | +5.36% (108/39d t=0.69) | +9.67% (358/56d t=2.01) |

## Every-day coverage (owner ask 2026-08-13: green AND red days, all strategies)
| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| EXEC_BASELINE (any shape, any day) | 2875/471d | +4.63% (t=2.34) | +2.54% | +5.2 / +4.1 |
| EXEC_BASELINE green days | 1657/263d | +5.21% (t=1.73) | +3.10% | +7.0 / +3.4 |
| EXEC_BASELINE red days | 1218/208d | +3.91% (t=1.65) | +1.83% | +4.7 / +3.1 |
| FADE mild GREEN days | 280/113d | +11.33% (t=1.93) | +9.10% | +4.5 / +18.1 |
| FADE mild RED days | 272/105d | +11.22% (t=1.34) | +9.00% | +11.1 / +11.3 |
| CONSENSUS trend GREEN (calls w/ uptrend) | 652/132d | +4.10% (t=1.27) | +2.02% | +2.8 / +5.4 |
| CONSENSUS trend RED (puts w/ downtrend) | 397/84d | +3.35% (t=0.76) | +1.29% | -5.2 / +11.9 |
| MIXED shape (neither fade nor consensus) | 320/239d | +9.27% (t=1.3) | +7.08% | +21.6 / -2.9 |
| CALLS only, green days | 1200/258d | +5.15% (t=1.92) | +3.05% | +6.5 / +3.8 |
| PUTS only, red days | 735/198d | +2.23% (t=0.57) | +0.18% | +6.0 / -1.5 |

## EARLY_STRENGTH confirmation on FADE mild in-band (enter only after +5..15% rise)
| mode | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| immediate entry (live mode) | 552/218d | +11.28% (t=2.24) | +9.05% | +7.8 / +14.8 |
| confirmed entry (early-strength) | 128/89d | +9.91% (t=1.45) | +7.71% | +12.1 / +7.8 |

## Exit variants on FADE mild in-band (raw)
| exit rule | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| live trail50/20 stop-50 | 552/218d | +11.28% (t=2.24) | +9.05% | +7.8 / +14.8 |
| stop -40 | 552/218d | +11.56% (t=2.38) | +9.33% | +10.9 / +12.2 |
| tight trail 10% | 552/218d | +8.48% (t=2.09) | +6.32% | +5.5 / +11.4 |
| early trail trig30 | 552/218d | +9.80% (t=2.06) | +7.61% | +7.3 / +12.3 |
| take-profit +80 | 552/218d | +9.45% (t=2.51) | +7.27% | +3.3 / +15.6 |
| time-stop ~3 sessions | 552/218d | +7.56% (t=1.55) | +5.41% | +3.8 / +11.4 |
