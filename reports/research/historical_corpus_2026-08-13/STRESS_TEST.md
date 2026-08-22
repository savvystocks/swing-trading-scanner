# Historical corpus stress-test - built overnight 2026-08-13

Corpus: 6200 replayable proxy candidates (20 liquid tickers, Sep-2024 to Jul-2026,
free Alpaca hourly option bars). PROXY caveats: trigger = contract-day premium turnover
in-band (not real sweeps); entry = next session's first hourly open (signal known EOD);
trade-price paths, not bid quotes; no spread screen. HAIRCUT column = 2% round-trip cost.
Nothing here shortcuts the 10-virgin-day bar - this is regime stress-testing, not proof.

| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| FADE mild in-band (live analogue) | 909/239d | +8.36% (t=2.14) | +6.19% | +6.7 / +10.0 |
| FADE mild whale 400k-1M | 283/170d | +2.88% (t=0.55) | +0.82% | -1.1 / +6.9 |
| FADE trend days (router blocks) | 1198/212d | +3.04% (t=0.79) | +0.98% | +6.3 / -0.2 |
| CONSENSUS trend days (leg candidate) | 1635/222d | +5.37% (t=2.35) | +3.26% | +2.1 / +8.7 |
| CONSENSUS mild days | 1436/255d | +4.38% (t=1.75) | +2.29% | +10.2 / -1.4 |

## By period - FADE mild in-band vs CONSENSUS trend
| period | fade mild | consensus trend |
|---|---|---|
| 2024H2 | +4.34% (206/67d t=0.6) | -3.49% (305/49d t=-0.75) |
| 2025H1+ | +22.71% (121/35d t=1.48) | +6.45% (661/86d t=1.88) |
| 2025H2+ | +10.99% (416/93d t=1.95) | +4.29% (192/28d t=0.54) |
| 2026 | -2.49% (166/44d t=-0.41) | +11.65% (477/59d t=2.64) |

## Every-day coverage (owner ask 2026-08-13: green AND red days, all strategies)
| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| EXEC_BASELINE (any shape, any day) | 4694/479d | +4.59% (t=3.09) | +2.50% | +6.1 / +3.0 |
| EXEC_BASELINE green days | 2667/267d | +4.30% (t=2.04) | +2.21% | +6.8 / +1.8 |
| EXEC_BASELINE red days | 2027/212d | +4.96% (t=2.39) | +2.86% | +5.6 / +4.3 |
| FADE mild GREEN days | 475/125d | +10.29% (t=2.01) | +8.08% | +8.3 / +12.3 |
| FADE mild RED days | 434/114d | +6.25% (t=1.05) | +4.12% | +5.0 / +7.5 |
| CONSENSUS trend GREEN (calls w/ uptrend) | 995/133d | +5.23% (t=1.96) | +3.12% | +4.2 / +6.2 |
| CONSENSUS trend RED (puts w/ downtrend) | 640/89d | +5.57% (t=1.36) | +3.46% | -0.6 / +11.6 |
| MIXED shape (neither fade nor consensus) | 739/362d | +8.89% (t=2.12) | +6.72% | +21.4 / -3.6 |
| CALLS only, green days | 1930/265d | +5.96% (t=2.52) | +3.84% | +7.5 / +4.4 |
| PUTS only, red days | 1246/211d | +1.44% (t=0.47) | -0.58% | +6.6 / -3.7 |

## EARLY_STRENGTH confirmation on FADE mild in-band (enter only after +5..15% rise)
| mode | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| immediate entry (live mode) | 909/239d | +8.36% (t=2.14) | +6.19% | +6.7 / +10.0 |
| confirmed entry (early-strength) | 220/124d | +13.86% (t=1.76) | +11.58% | +13.4 / +14.3 |

## Exit variants on FADE mild in-band (raw)
| exit rule | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| live trail50/20 stop-50 | 909/239d | +8.36% (t=2.14) | +6.19% | +6.7 / +10.0 |
| stop -40 | 909/239d | +8.79% (t=2.38) | +6.62% | +9.6 / +8.0 |
| tight trail 10% | 909/239d | +5.46% (t=1.64) | +3.35% | +3.3 / +7.6 |
| early trail trig30 | 909/239d | +6.86% (t=1.95) | +4.72% | +3.9 / +9.8 |
| take-profit +80 | 909/239d | +6.83% (t=2.07) | +4.69% | +3.8 / +9.9 |
| time-stop ~3 sessions | 909/239d | +6.16% (t=1.66) | +4.03% | +4.6 / +7.7 |
