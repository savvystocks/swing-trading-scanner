# THE CORE STRATEGY — 2026-08-02 (owner order: "find a strategy. proven. tested. backtested.")

## 1. The verdict

The proven, published, independently backtested, currently-running automated options strategy
family is SYSTEMATIC INDEX PREMIUM SELLING — specifically the CBOE put-write methodology
(PUT/WPUT indices) and its 30-delta buy-write sibling (BXMD). No other options strategy on
earth has this evidence density:

- 29.5-YEAR ACADEMIC STUDY (Black & Szado, mid-1986→2015, CBOE-commissioned, methodology
  public): of six option benchmark indices, PUT and BXMD had the HIGHEST absolute AND
  risk-adjusted returns; PUT volatility 9.9% vs S&P 500's 14.9%.
- 30-YEAR WILSHIRE STUDY (2019): same conclusion — index-like returns, ~2/3 the volatility,
  materially smaller drawdowns.
- LIVE INDEX RECORD: our own 19.6-year pull of ^PUT: +7.1%/yr, 17% vol, −37% max drawdown vs
  SPX −57% (includes 2008).
- LIVE NET-OF-FEES ETF (PUTW, since Feb-2016): the strategy running in public with real money
  and a 0.44% fee — imperfect but real, and honest about the weakness (see §2).
- INDEPENDENT PRACTITIONER BACKTESTS (spintwig, multi-thousand-trade SPX/SPY short-put series):
  confirm the return profile; key mechanical finding — HOLD-TO-EXPIRY had the best Sharpe;
  early-management (50%/21-DTE) adds commissions, not CAGR.
- OUR OWN MARKET CHECK (07-28): options priced 9.1pts over realized vol on 79% of 866
  ticker-days — the premium exists in today's market, here and now.
- MECHANISM: the variance risk premium — investors systematically overpay for index crash
  insurance (Carr-Wu RFS 2009). It is compensation for bearing tail risk, which is why it has
  not been arbitraged away in 30 years of being published.

The methodology is PUBLISHED AND FREE (CBOE index white papers). It requires no signal, no
forecast, no direction call — which is precisely why it survives where our flow-following died:
D4 proved our data cannot call direction; this strategy never asks it to.

## 2. The honest expectation — pre-registered so a bull month cannot kill it wrongly

Put-write is NOT a beat-the-market machine. It LAGS in melt-ups: PUTW year-to-date is +1.7% vs
SPY +9.2% — that is the strategy WORKING AS DESIGNED in a bull tape. It wins on the shape:
index-like returns over full cycles with ~2/3 the volatility and roughly half the crash depth,
plus income in flat/down/choppy regimes. PRE-REGISTERED JUDGMENT RULE: this book is evaluated
on (a) premium-capture efficiency (captured vs theoretical premium after frictions) and (b)
rolling risk-adjusted return vs SPX — NEVER on whether it beat SPY in any bull month. Whoever
judges it by a bull-quarter horse race (including us) is misreading it by construction. The
fat left tail is real (2008-shaped years exist); the Treasurer's sizing caps and the VIX>32
brake are the containment, and £1-5k initial live capital (item 14) bounds the tuition.

## 3. The spec on OUR infrastructure

- BOOK A — PRIMARY: XSP cash-secured put-write, PUT-methodology-faithful. Sell one monthly XSP
  put (ATM per ^PUT, or 30-delta per BXMD-style — Phase-1 backtest decides which), fully cash-
  collateralized, HOLD TO EXPIRY (per the spintwig Sharpe evidence; also fewer commissions,
  simpler audit), roll next session after expiry. European cash-settled — tested LIVE on our
  paper account 08-02 (XSP tradable=true, quotes flowing). No assignment risk, no pin risk, by
  contract design.
- BOOK B — premium lane v2.2 exactly as approved: 5%-OTM put credit spreads, the defined-risk
  cost-measurement instrument. Unchanged.
- BOOK C (later, earn-in): BXMD-style 30-delta covered call — only after Book A runs clean for
  its pre-registered window.
- SIZING/RISK: Treasurer half-Kelly caps, VIX>=32 macro brake (built), drawdown ratchet
  (built), all books in the lifetime trials ledger, weekly Sunday scorecards from committed
  artifacts.
- The measurement machinery is unchanged and is the moat: fill ledger prices every friction;
  the harness judges; the Governor holds authority.

## 4. Free vs paid — the answer to "will that need software"

FREE covers everything: methodology (CBOE papers), validation (QuantConnect cloud — SPX index
options Jan-2012→present at minute resolution, free tier, tested; optionsDX $0 bundles for our
own harness cross-check), execution (Alpaca paper, XSP verified live), monitoring (our
reports). PAID only on a measured number, per the standing guardrails: Alpaca OPRA NBBO feed
(~$99/mo) if and only if the fill ledger shows the free indicative feed materially misprices
our entries; ThetaData Value ($40, one month, cancel-by-default) if and only if QC leaves a
named validation gap. The owner's UW-sized budget appetite is noted and NOT spent: UW runs to
its 09-27 sunset review (decision 13); after that the freed budget is redirected only when a
measured number asks for it.

## 5. Plan of attack (dated)

- TODAY (boundary): approve the core strategy + tournament; key handoff (put-write account
  first); Book A activates in paper — 1 XSP contract, counted trial.
- WEEK 1 (to 08-09): owner does two 5-minute free signups (QuantConnect, optionsDX). I run the
  SPX put-write 2012-2026 backtest on QC (ATM vs 30-delta, monthly vs weekly, through
  2018/2020/2022) and the same test through our own harness on optionsDX files. Two engines
  must agree. Parameter lock at the 08-09 boundary.
- WEEKS 2-6: paper record accumulates under the tournament's pre-registered bars; fill ledger
  answers the OPRA-feed question with data; Sunday scorecards.
- ~OCT: live-capital gate per ROADMAP item 14 (£1-5k, IBKR UK opened in parallel as the live
  venue candidate).

## 6. Pre-registered rejections (so nothing sneaks back in)

0DTE selling (no long record; gamma/feedback tail; retail-boom crowding — research watch only);
short-VIX carry (Volmageddon left tail); iron condors as core (CNDR LAGGED PUT across the
29.5-year study); single-name premium selling (Carr-Wu: structural premium ≈ zero off-index);
"the wheel" as marketed (= put-write with extra assignment friction on American-style ETF
options — our XSP form is strictly cleaner); anything from the flow/signal-platform family
(category closed).
