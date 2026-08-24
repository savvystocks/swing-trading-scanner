# Regime backtest - 2026-08-23 (bear / mild / bull)

Real triggers, day-clustered day-mean%/t per SPY regime (vs 50d SMA: bull>+2, bear<-2).
Regime day coverage: {'MILD': 188, 'BULL': 241, 'BEAR': 63}.
CAVEAT: 2024-26 is mostly bull; BEAR = dip/correction days, NOT a sustained bear market.

| strategy | BEAR | MILD | BULL |
|---|---|---|---|
| FADE | +32.4% t+3.5 (63d) | -1.0% t-0.3 (188d) | -16.6% t-8.4 (241d) |
| CONSENSUS | +4.0% t+0.4 (63d) | +2.2% t+0.6 (188d) | +16.3% t+6.7 (241d) |
| CONSENSUS+calls | +111.5% t+1.6 (7d) | +17.6% t+3.0 (104d) | +17.5% t+7.1 (233d) |
| FOLLOW+calls | +32.6% t+3.8 (63d) | +12.5% t+3.3 (188d) | +14.2% t+7.0 (241d) |
| CONSENSUS+highIV+calls | +131.1% t+1.5 (7d) | +8.5% t+1.9 (104d) | +24.1% t+7.5 (233d) |
