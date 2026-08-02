# Options-bot software due diligence — 2026-08-02 (owner-ordered; anti-money-pit)

Owner questions: what software can we use; has the strategy been wrong all this time; every
alternative out there; how our system works with it; plan of attack. Pricing verified against
vendor sites/current reviews 2026-08-02 where possible.

## 0. Was the strategy wrong all this time?

The HYPOTHESIS was wrong — provably: "buy options following whale flow" failed every honest test
(3.8% hit vs 55.9% hurdle; SPRT REJECT; D4 zero direction; type-is-not-intent construction flaw;
the literature agrees the retail form has no support). The SYSTEM was right: the harvest, labels,
purged harness, and governance are what proved the failure in 8 weeks. Nothing below replaces the
system — every tool is data-in or orders-out for the machinery we already own.

## 1. What we actually need (from the week's evidence — not what vendors sell)

- A: 10+ years of historical options data to validate premium-selling parameters over real
  regimes (2018 Volmageddon, 2020, 2022) — our single biggest gap; OptionMetrics-class pricing
  (4 figures) already rejected.
- B: An options-native backtester for put-write / put credit spreads with honest fills.
- C: Execution venue(s): paper now, credible live venue at the ROADMAP item-14 gate, UK-resident.
- D: Free replacements for UW's non-flow datasets ahead of the 09-27 sunset review.
- EXPLICITLY NOT NEEDED: any flow/GEX/dark-pool dashboard (the rank-6 family, disproven), any
  new signal subscription, any AI/ML platform (the brain exists).

## 2. The landscape

### A. Historical options data
| provider | price (2026) | what you get | verdict |
|---|---|---|---|
| QuantConnect data (in-platform) | FREE with free tier | US options history (2012+) usable in unlimited cloud backtests | FIRST CHOICE — solves gap A at £0 inside its backtester |
| optionsDX | free registration downloads (bundle store for extras) | EOD/intraday US option chains incl. SPX/SPY/VIX, greeks+IV included | FIRST CHOICE for feeding OUR OWN harness at £0; verify bundle coverage at download |
| ThetaData | $40/mo Value (4y, 1-min snapshots), $80 Standard (8y, ticks), $160 Pro (12y); free 30-day EOD tier | API-first, python client, greeks | BEST PAID fallback; one month + cancel is the pattern if £0 sources fall short |
| DeltaNeutral / HistoricalData.net | one-off purchase, files kept forever, history since 2002 | EOD chains + greeks + IV, email delivery | Good one-off option (no subscription) if we want permanent local 20y EOD |
| CBOE DataShop | per-file one-off | official exchange EOD/intraday slices | Fine for a single index history file; per-file costs add up |
| Polygon.io options | ~$29+/mo tiers | API, good docs, shorter practical history on cheap tiers | Redundant vs ThetaData at our needs |
| Databento (OPRA) | pay-as-you-go historical; plans from $199/mo | institutional tick OPRA from 2013 | Overkill; tick microstructure is not our question |
| Intrinio / OptionMetrics | enterprise / 4-figures | institutional EOD | Rejected on cost (already on record) |
| Dolt community options DB | free | community-maintained EOD | Unverified quality; cross-check only, never load-bearing |

### B. Options-capable backtesters
| platform | price | fit | verdict |
|---|---|---|---|
| QuantConnect / LEAN | FREE unlimited cloud backtests; live from ~$60/mo (NOT needed — we keep our own engine); LEAN itself open-source (self-hostable) | Python, real US options data 2012+, put-write/verticals/custom exits fully supported, Alpaca bridge exists | ADOPT (free tier only). The validation lab for every tournament strategy |
| Option Omega | $99/mo or $599/yr, FREE TRIAL | purpose-built for exactly our structures: 1-min data to 2013, SPX/SPY/QQQ/IWM, preset spreads/condors, honest fill modeling | Use the FREE TRIAL as a one-shot cross-check of the lane/put-write params; pay at most one month, only if trial proves value |
| ORATS backtester/API | ~$99/mo | scan+backtest premium strategies, good data lineage | Redundant if QC + Omega-trial cover us |
| OptionAlpha | subscription, no-code automation | bot hosting, not research | Not needed — we own the engine |
| CML TradeMachine | ~$59-99/mo | retail backtester | Weaker data transparency; skip |
| MesoSim | ~€50+/mo | niche SPX structures | Skip at our scale |
| DIY: our harness + purchased EOD | data cost only | full control, our labels/weights/CV | ALREADY EXISTS — feed it optionsDX/DeltaNeutral files |

### C. Brokers / execution (UK-resident lens)
| broker | UK access | options API | costs | verdict |
|---|---|---|---|---|
| Alpaca (current) | YES — international accounts incl. UK, $1 min funding | full REST API, mleg atomic, commission-free options | $0 | KEEP as the lab + tournament venue. Known weakness: paper fills too kind — that is what the fill-ledger measures |
| Interactive Brokers UK | YES (IBKR UK entity) | TWS/Web API, industry standard; paper account; XSP/SPX index options ~$0.65/contract | account free, per-contract fees | THE LIVE-MONEY ENDGAME at ROADMAP item 14: real index-option venue, more honest paper fills, UK-native. Open in parallel later; not needed today |
| tastytrade | international program (UK on supported list historically — verify at signup) | open API + sandbox, options-first, $1/contract open, $0 close, $10 cap | low | Credible IBKR alternative; second choice |
| Tradier | US-leaning; intl limited | good API | $0.35/contract or $10/mo | Skip (UK friction) |
| Schwab / TradeStation / E*TRADE | US-resident | — | — | Not available to us |
| IG / Saxo (UK-native) | YES | no serious US-options bot API at retail tier | — | Skip for options bot |

### D. Signal platforms (UW competitors: FlowAlgo, Cheddar Flow, Tradytics, SpotGamma, MenthorQ, Quant Data, InsiderFinance, BlackBoxStocks, Market Chameleon, Barchart Premier)
Same indicator family the evidence review just graded rank 6-8 (flow/GEX/dark-pool), zero
independently documented performance anywhere in the class (UW_INDICATOR_EVIDENCE_2026-08-02.md),
mostly dashboard-first with API upsells. VERDICT: NONE. Not one pound here. Replacing UW with a
UW-shaped competitor is the definition of the money pit.

### E. Free institutional-grade replacements (for the UW sunset)
| dataset | free source | notes |
|---|---|---|
| Insider transactions (the rank-2 signal) | SEC EDGAR Form 4 — edgartools already in our repo | 2-business-day lag = the documented signal's own clock; cluster/opportunistic classification buildable from filing history |
| Short interest / short volume | FINRA files (free) | twice-monthly SI + daily short volume; conditioning filter |
| Congress disclosures | Senate/House PTR + free scrapers | expectations already downgraded to ~zero; archive-only |
| VIX/term structure, index data | CBOE free stats, yfinance | already consumed |
| Options volume/OI aggregates | OCC + CBOE free stats | replaces UW volume endpoints |
| Earnings calendar, halts, macro | yfinance/Alpaca, Nasdaq, FRED | already consumed |
| NOT replaceable free: signed net premium ticks, dark-pool prints | — | exactly the two open experiments that decide the UW sunset (decision 13) |

### F. Open source worth borrowing
LEAN (Apache-2, very active — the self-hostable engine behind QC), py_vollib/QuantLib (greeks/
pricing for our own backtester), optopsy (light EOD options backtester, useful patterns),
thetagang bot (reference premium-selling implementation on IBKR). Borrow patterns; keep our stack.

## 3. The recommended stack (total new spend: £0 now; worst case ~$40-99 once, case-by-case)

DATA: QuantConnect free + optionsDX free (+ ThetaData one-month IF a named gap survives both).
VALIDATION: QuantConnect backtests + our own harness on optionsDX files — two independent
engines must agree before any parameter is trusted (disagreement = investigate, not average).
EXECUTION: Alpaca (unchanged) now; IBKR UK opened at the live-capital gate.
SIGNALS: none purchased. EDGAR/FINRA/CBOE free stack replaces UW datasets per decision 13.
SYSTEM: unchanged — harvest, harness, school, governance, tournament. Tools feed it; nothing
replaces it.

## 4. Plan of attack (phased; every spend pre-gated; kill dates on everything)

- PHASE 0 (today, boundary): the 13 deck decisions; keys; put-write primary; lane activation;
  tournament routing build config-OFF.
- PHASE 1 (this week, £0): QuantConnect account; reproduce the put-write and 5%-OTM put-spread
  book over 2013-2026 including 2018/2020/2022; momentum shares alongside. optionsDX bundles
  into our own harness as the second, independent validation. ACCEPTANCE: multi-year evidence
  confirms or amends the lane/put-write parameters BEFORE any scale-up; results to the 08-09
  boundary.
- PHASE 2 (only on a named Phase-1 gap): ThetaData Value $40 ONE month (or Option Omega free
  trial → at most one $99 month) — each with a written question it must answer and a cancel
  date set at purchase. The math comes to the owner first (NORTH_STAR).
- PHASE 3 (live gate, ~Oct per item 14): open IBKR UK in parallel (free), paper there for fill
  realism, £1-5k live only when the pre-registered gates pass. Alpaca remains the lab.
- PHASE 4 (Sep): UW sunset review per decision 13; EDGAR insider-cluster study registered ~Sep;
  free replacements landed beforehand.

MONEY-PIT GUARDRAILS (standing): never two overlapping paid subscriptions; no purchase without
a pre-written question + kill date; signal-platform category is closed (Section D); every spend
case-by-case to the owner with the math (NORTH_STAR principle 7); default answer is the free
tier until a named, evidenced gap says otherwise.

## 5. Live-price layer, TradingView, and open-source terminals (owner follow-up, 08-02 12:00)

ARE THESE ALL APIs? Data: ThetaData/Databento/Polygon = APIs; optionsDX/DeltaNeutral = file
downloads (fine — backtests read files); QuantConnect = code platform. Backtesters: QC = API/
code; Option Omega = web UI only (no API — another reason it stays a one-shot trial). Brokers:
Alpaca/IBKR/tastytrade = full trading APIs. Signal platforms: mostly dashboards (one more
reason the category is closed).

LIVE PRICES FOR THE BUY DECISION — the bot already runs on them. Alpaca's real-time option
quote API is what sets entry_ref (real ask) and enforces the 5% spread gate at order time.
Verified today, two upgrades:
- FEED HONESTY: Alpaca Basic (free) serves the options "indicative" feed (calculated/derived
  values); the true consolidated OPRA NBBO requires Algo Trader Plus (~$99/mo). We do NOT buy
  that blind: the fill ledger (decision_mark → slip_vs_decision) measures exactly how far
  free-feed quotes sit from actual fills. If the measured gap is material, that number IS the
  case for the $99/mo, taken to the owner with math. Until then, actual fills are ground truth
  and the free feed stands.
- INDEX OPTIONS IN PAPER (major find): Alpaca's Trading API now supports index options in
  PAPER — SPX, SPXW, VIX, VIXW, DJX, XSP — cash-settled, European style. The put-write book
  can trade REAL XSP in the tournament, deleting the early-assignment and pin-risk classes by
  contract design (the exact −$930 / −$3,280 pressure-test paths). The lane's prefer-XSP gate
  becomes executable. Boundary decision 3 amended accordingly.

TRADINGVIEW — VERDICT: NOT FOR THIS BOT. It is a charting/alert front-end, not an execution
engine: no native auto-execution (bans direct broker trading), webhooks need a paid plan plus a
THIRD-PARTY bridge subscription (TradersPost-class — a new money-pit lane), and options support
is single-leg only — no atomic mleg spreads, which our premium structures require. Our GHA
cycle already is the automation layer, with atomic mleg. TradingView's only honest role here is
manual chart-reading, which costs £0 on the free tier and touches nothing.

OPEN-SOURCE TERMINALS / REPOS (the expanded field of view):
| repo | what it is | role for us |
|---|---|---|
| OpenBB (MIT, very active; Terminal → OpenBB Platform/CLI) | the open-source Bloomberg: 600+ commands, options chains, equities, macro, Python-native | ADOPT as the free research cockpit ("terminal") — data browsing/sanity checks; £0; never in the trade path |
| LEAN CLI (QuantConnect's engine, self-hostable) | the backtest engine behind QC | our Phase-1 lab; self-host later if we outgrow the cloud free tier |
| ib_insync | the standard Python client for IBKR | becomes load-bearing at Phase 3 (IBKR UK) |
| Lumibot | Python algo framework (Alpaca/IBKR/Tradier brokers, ThetaData backtests) | pattern source; we keep our own engine |
| thetagang | reference wheel/premium-selling bot on IBKR | pattern source for the put-write book mechanics |
| py_vollib / QuantLib | pricing + greeks libraries | greeks for our own backtester on optionsDX files |
| Nautilus Trader | high-performance institutional-grade framework | heavier than our needs; watch only |
| vectorbt / backtrader / optopsy | generic Python backtesters | options support weak/stale vs LEAN; optopsy patterns only |
None of these replaces the engine, harness, or governance — they are a free research terminal
(OpenBB), a free validation engine (LEAN), and the client library the live gate will need
(ib_insync).
