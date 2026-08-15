# Historical corpus stress-test - built overnight 2026-08-13

Corpus: 5202 replayable proxy candidates (20 liquid tickers, Sep-2024 to Jul-2026,
free Alpaca hourly option bars). PROXY caveats: trigger = contract-day premium turnover
in-band (not real sweeps); entry = next session's first hourly open (signal known EOD);
trade-price paths, not bid quotes; no spread screen. HAIRCUT column = 2% round-trip cost.
Nothing here shortcuts the 10-virgin-day bar - this is regime stress-testing, not proof.

| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| FADE mild in-band (live analogue) | 775/234d | +9.86% (t=2.41) | +7.66% | +10.1 / +9.7 |
| FADE mild whale 400k-1M | 224/144d | +5.87% (t=0.89) | +3.75% | +2.0 / +9.8 |
| FADE trend days (router blocks) | 1030/211d | +3.18% (t=0.85) | +1.12% | +4.7 / +1.7 |
| CONSENSUS trend days (leg candidate) | 1383/219d | +4.65% (t=1.86) | +2.56% | +0.6 / +8.7 |
| CONSENSUS mild days | 1235/253d | +4.55% (t=1.68) | +2.46% | +8.5 / +0.7 |

## By period - FADE mild in-band vs CONSENSUS trend
| period | fade mild | consensus trend |
|---|---|---|
| 2024H2 | +8.05% (173/65d t=1.01) | -5.54% (245/48d t=-1.06) |
| 2025H1+ | +26.91% (101/35d t=1.66) | +6.04% (554/86d t=1.59) |
| 2025H2+ | +8.81% (356/92d t=1.6) | +3.53% (163/28d t=0.42) |
| 2026 | +0.77% (145/42d t=0.12) | +11.67% (421/57d t=2.51) |

## Every-day coverage (owner ask 2026-08-13: green AND red days, all strategies)
| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| EXEC_BASELINE (any shape, any day) | 3971/474d | +4.53% (t=2.86) | +2.44% | +5.3 / +3.7 |
| EXEC_BASELINE green days | 2264/264d | +3.67% (t=1.84) | +1.59% | +5.4 / +2.0 |
| EXEC_BASELINE red days | 1707/210d | +5.61% (t=2.2) | +3.50% | +6.5 / +4.8 |
| FADE mild GREEN days | 398/123d | +12.73% (t=2.4) | +10.48% | +11.6 / +13.9 |
| FADE mild RED days | 377/111d | +6.68% (t=1.06) | +4.55% | +6.9 / +6.5 |
| CONSENSUS trend GREEN (calls w/ uptrend) | 850/133d | +3.69% (t=1.26) | +1.62% | +2.4 / +5.0 |
| CONSENSUS trend RED (puts w/ downtrend) | 533/86d | +6.12% (t=1.36) | +4.00% | -1.0 / +13.2 |
| MIXED shape (neither fade nor consensus) | 555/316d | +10.46% (t=2.23) | +8.25% | +24.4 / -3.4 |
| CALLS only, green days | 1644/263d | +5.08% (t=2.08) | +2.98% | +6.6 / +3.6 |
| PUTS only, red days | 1036/207d | +2.67% (t=0.77) | +0.62% | +6.7 / -1.3 |

## EARLY_STRENGTH confirmation on FADE mild in-band (enter only after +5..15% rise)
| mode | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| immediate entry (live mode) | 775/234d | +9.86% (t=2.41) | +7.66% | +10.1 / +9.7 |
| confirmed entry (early-strength) | 177/110d | +11.03% (t=1.61) | +8.81% | +16.7 / +5.3 |

## Exit variants on FADE mild in-band (raw)
| exit rule | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| live trail50/20 stop-50 | 775/234d | +9.86% (t=2.41) | +7.66% | +10.1 / +9.7 |
| stop -40 | 775/234d | +10.55% (t=2.7) | +8.34% | +12.5 / +8.5 |
| tight trail 10% | 775/234d | +7.17% (t=2.03) | +5.03% | +5.8 / +8.5 |
| early trail trig30 | 775/234d | +7.65% (t=2.07) | +5.50% | +6.8 / +8.5 |
| take-profit +80 | 775/234d | +8.91% (t=2.54) | +6.73% | +6.3 / +11.5 |
| time-stop ~3 sessions | 775/234d | +6.93% (t=1.82) | +4.79% | +6.5 / +7.3 |
