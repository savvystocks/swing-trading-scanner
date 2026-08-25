# REGIME PLAYBOOK - 2026-08-25

Structural strategies regime-split over the archive (real SPY option nbbo, sell-at-bid/
buy-at-ask, settled vs real SPY close). One lot, weekly, all affordable at $1k-1.5k max
loss. Shares rows are $1k notional per day. Flow strategies: see mega_sweep (fade=bear only).
Regime day counts: BULL 284 / MILD 230 / BEAR 67

| strategy | BULL | MILD | BEAR |
|---|---|---|---|
| PUT_CREDIT | $+9/wk t+0.4 win 87% worst $-515 (n=45) | $+64/wk t+4.5 win 94% worst $-304 (n=33) | $-140/wk t-1.0 win 64% worst $-923 (n=11) |
| CALL_CREDIT | $+22/wk t+6.4 win 100% worst $+2 (n=26) | $-20/wk t-0.4 win 89% worst $-898 (n=19) | $-141/wk t-1.2 win 64% worst $-857 (n=11) |
| IRON_CONDOR | $+20/wk t+0.7 win 81% worst $-439 (n=26) | $+48/wk t+0.9 win 84% worst $-725 (n=19) | $-280/wk t-2.2 win 27% worst $-781 (n=11) |
| PUT_DEBIT | $+36/wk t+0.7 win 22% worst $-213 (n=46) | $-51/wk t-1.1 win 15% worst $-304 (n=33) | $+214/wk t+1.1 win 36% worst $-331 (n=11) |
| CALL_DEBIT | $-20/wk t-0.5 win 19% worst $-209 (n=42) | $-4/wk t-0.0 win 20% worst $-353 (n=25) | $+114/wk t+0.7 win 36% worst $-382 (n=11) |
| SHARES_OVERNIGHT | $+1/wk t+2.8 win 61% worst $-12 (n=284) | $+1/wk t+1.9 win 65% worst $-40 (n=229) | $-0/wk t-0.3 win 48% worst $-35 (n=67) |
| SHARES_TURN_OF_MONTH | $+0/wk t+0.4 win 64% worst $-20 (n=75) | $+1/wk t+0.7 win 53% worst $-29 (n=77) | $-5/wk t-1.1 win 53% worst $-58 (n=19) |
