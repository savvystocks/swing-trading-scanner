# Historical corpus stress-test - built overnight 2026-08-13

Corpus: 1527 replayable proxy candidates (20 liquid tickers, Sep-2024 to Jul-2026,
free Alpaca hourly option bars). PROXY caveats: trigger = contract-day premium turnover
in-band (not real sweeps); entry = next session's first hourly open (signal known EOD);
trade-price paths, not bid quotes; no spread screen. HAIRCUT column = 2% round-trip cost.
Nothing here shortcuts the 10-virgin-day bar - this is regime stress-testing, not proof.

| slice | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| FADE mild in-band (live analogue) | 250/153d | +18.73% (t=2.26) | +16.36% | +26.5 / +11.0 |
| FADE mild whale 400k-1M | 76/64d | +11.63% (t=1.17) | +9.40% | +9.9 / +13.3 |
| FADE trend days (router blocks) | 330/169d | +0.34% (t=0.08) | -1.66% | +1.1 / -0.4 |
| CONSENSUS trend days (leg candidate) | 468/188d | +5.89% (t=1.66) | +3.77% | +0.9 / +10.9 |
| CONSENSUS mild days | 403/201d | +4.57% (t=1.02) | +2.47% | +11.9 / -2.7 |

## By period - FADE mild in-band vs CONSENSUS trend
| period | fade mild | consensus trend |
|---|---|---|
| 2024H2 | -1.29% (57/38d t=-0.15) | -7.16% (67/38d t=-1.07) |
| 2025H1+ | +71.94% (32/23d t=1.72) | +8.16% (163/75d t=1.42) |
| 2025H2+ | +25.10% (109/62d t=2.28) | +11.48% (72/25d t=0.97) |
| 2026 | -9.85% (52/30d t=-1.29) | +9.62% (166/50d t=1.46) |

## Exit variants on FADE mild in-band (raw)
| exit rule | n/days | day-mean raw | haircut | halves |
|---|---|---|---|---|
| live trail50/20 stop-50 | 250/153d | +18.73% (t=2.26) | +16.36% | +26.5 / +11.0 |
| stop -40 | 250/153d | +20.93% (t=2.58) | +18.51% | +29.4 / +12.5 |
| tight trail 10% | 250/153d | +16.79% (t=2.18) | +14.46% | +28.1 / +5.7 |
| early trail trig30 | 250/153d | +16.22% (t=2.11) | +13.90% | +24.3 / +8.2 |
| take-profit +80 | 250/153d | +12.04% (t=2.43) | +9.80% | +16.4 / +7.7 |
| time-stop ~3 sessions | 250/153d | +18.42% (t=2.28) | +16.05% | +29.4 / +7.5 |
