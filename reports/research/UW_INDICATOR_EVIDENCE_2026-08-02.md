# Unusual Whales indicator families — external evidence review (2026-08-02)

Owner question: of everything UW offers, which indicators are BEST, proved by results. Method:
six parallel research sweeps (options flow, GEX/dealer, dark pool/short, congress/insider, IV
family, UW-specific), every claim graded peer-reviewed > practitioner-backtest > vendor-claim >
anecdote; retail-achievability (entering AFTER the signal is public, net of costs) required for
a top grade. Full agent outputs preserved in the session task file; key sources cited inline.

## The ranked table (by documented, retail-achievable results)

| rank | UW indicator family | best documented result | grade | retail-achievable? |
|---|---|---|---|---|
| 1 | Index premium selling family (IV, VRP, PUT/BXM) | Index VRP large/persistent (Carr-Wu RFS 2009); PUT index 30y live record, Sharpe ~46% above SPX (CBOE/Ibbotson); IV = best realized-vol forecaster (Christensen-Prabhala; Poon-Granger) | peer-reviewed + 30y live | YES — the only family with a live, unconditional, decades-long record. Caveats: premium compressed post-2012; SINGLE-NAME VRP ≈ zero (Carr-Wu) — index only |
| 2 | Insider transactions (opportunistic/cluster PURCHASES only) | Cohen-Malloy-Pomorski JF 2012: +82bp/mo VW long-short from public Form 4s; cluster buys strongest; routine trades = zero | peer-reviewed | PARTIALLY — 2-day disclosure, months-long drift, stock-side implementation. Decay: post-SOX broad-market drift ≈ 0 (2003-2019); FRL 2025: % alpha does not convert to $ alpha at realistic fills; surviving pocket = small-cap cluster buys, thin net edge |
| 3 | Short interest / days-to-cover (as a CONDITIONING filter) | DTC long-short ~1.2%/mo gross (Hong et al NBER); constrained stocks -215bp/mo EW (Asquith et al) | peer-reviewed | LONG-SIDE ONLY — short leg killed by borrow fees (Muravyev JF 2025); effect in small illiquid names; data twice-monthly, 9-day lag; sign INVERTS in squeeze regimes. Use to avoid/penalize, never as standalone |
| 4 | Max pain / OPEX pinning + charm drift | Pinning real: ~16.5bp per expiration (Ni-Pearson-Poteshman JFE 2005); pre-OPEX drift w/ settlement reversion (Baltussen et al 'Derivative Payoff Bias') | peer-reviewed | MARGINAL — bps-scale, below retail spreads standalone; valid as an overlay (don't expect breakouts through big-OI strikes on OPEX) |
| 5 | GEX / dealer greeks | Raw GEX→next-day vol real (rho -0.36, 8y pre-registered SPY test) BUT incremental value ≈ ZERO after controlling VIX + ATM IV; no direction signal at all (DEX rho -0.03) | peer-reviewed mechanism + practitioner null | DEFENSIVE ONLY — as a vol-regime read it duplicates free VIX/IV; zero-gamma "flip levels" are model artifacts (vendors disagree on sign for the same day). Never a trade trigger |
| 6 | Options flow alerts (UW's flagship) | Real ONLY in signed/opening form retail cannot see (Pan-Poteshman: public component carries little); informative flow is ATM/ITM, NOT OTM sweeps (Hu JFE 2014); generic large-print UOA = NOT predictive (Strong, JPM); flow impact mostly MM inventory, not information (Muravyev JF 2016); NO published UW backtest by anyone in ~6 years | peer-reviewed (against) | NO — and the retail options vehicle adds ~8-12.6% round-trip cost (Bryzgalova JF 2023; de Silva). This is the family our engine traded; four independent nulls in our own data now match the literature |
| 7 | Market tide / net premium ticks | Zero published evidence anywhere; mechanically UW's approximation of the academically-real signed imbalance (Lee-Ready-style inference misfires ~25-30% of option prints) | vendor-claim | UNKNOWN — our R2 signed-intent experiment tests exactly this on our own labels; literature expectation: bps-scale at best, fast decay |
| 8 | Dark pool prints / levels | ZERO peer-reviewed direction support; Zhu RFS 2014 mechanism argues prints skew UNinformed; DIX's one independent test self-retracted; fabricated journal citations circulate in vendor material | vendor-claim | NO as marketed. NOTE: our own rig's dark-pool accumulation read (OOS d 0.31-0.40, champion stable 4/5 vintages, below 0.68 bar) is arguably better evidence than anything published — keep as convergence-gated conditioning candidate |
| 9 | Congress trading | Post-STOCK-Act aggregate alpha ≈ 0 (J.Pub.Econ 2022); powerful-member edge died with 2012 disclosure (Karadas); live proof: NANC/KRUZ ETFs = no risk-adjusted alpha (Econ Letters 2025); UW's own 2025 report: ~68% of members LAG SPY | peer-reviewed (against) | NO at the 30-45d disclosure lag. One watch: NBER w34524 'Captain Gains' (Dec-2025 working paper) — leadership-ascension trades may retain disclosure-date alpha; unreviewed, tiny-N |
| 10 | NOPE | Abandoned by its author after regime failure; no audited record | anecdote | NO |

Cross-cutting debunkings that reshape several families: (a) Muravyev-Pearson-Pollet JFE 2025 —
IV-spread/skew "direction" signals largely proxy the stock BORROW FEE; net-of-fee alpha near
zero; (b) McLean-Pontiff — published anomalies decay ~58% post-publication; (c) earnings IV
crush: academically the LONG straddle side is positive gross pre-earnings (Gao-Xing-Zhang JFQA
2018) — indiscriminate crush-selling is negative-edge; only implied-vs-historical-move
conditioning defends it.

## What this changes for us (staged into the 08-02 deck)

1. VALIDATION, not revision, of the pivot: the world's evidence and our machine's evidence
   agree — flow-alert direction has no support (rank 6 vs our 3.8% hit/D4/four nulls); index
   premium selling is the best-documented harvest (rank 1 = our new primary lane); vol is
   predictable where direction is not (their IV literature = our 0.73-vs-0.50 split).
2. NEW actionable candidate: the insider dataset in its SURVIVING form — opportunistic/CLUSTER
   purchases, stock-side, 1-12 month horizon, liquid-enough small caps. Our July insider study
   killed the naive form (all insider trades, 7-week window) — the literature says the naive
   form IS dead; the cluster/opportunistic form at month horizons was never tested by us.
   Register properly when the window supports month-scale labels (~Sep); UW carries the data.
3. CALIBRATED expectations for R2 (signed-intent rebuild): even the true signed signal is
   bps-scale, ATM/ITM-concentrated, decays in days, and the public approximation is noisier.
   R2 stays worth doing because it is cheap and stock-side, with the pre-registered expectation
   that the honest outcome is probably null.
4. DOWNGRADE congress expectations: keep the archiver capture (free, and 'Captain Gains' may
   revive a leadership-only form) but no strategy claims; the accumulation-sensor spec is
   measurement, not signal.
5. Our shares_short discovery flicker now has literature support (the one robust cross-
   sectional family) — still convergence-gated, but its prior just improved; conditioning
   (avoid high-DTC longs) is the defensible use either way.
6. GEX/max-pain: defensive overlays only (sizing regime, OPEX awareness); never triggers.
7. Single-name premium selling: Carr-Wu's single-name-VRP-≈-zero is a standing caution FOR the
   premium lane — its index-cluster universe (SPY/QQQ/XSP) is the right side of that line, and
   drifting toward single names would cross it.

Sources are as cited by the research agents; the load-bearing ones (Pan-Poteshman RFS 2006;
Johnson-So JFE 2012; Hu JFE 2014; Muravyev JF 2016; Muravyev-Pearson-Pollet JFE 2025; Cohen-
Malloy-Pomorski JF 2012; Carr-Wu RFS 2009; Ni-Pearson-Poteshman JFE 2005; Zhu RFS 2014;
Bryzgalova-Pavlova-Sikorskaya JF 2023; CBOE PUT/BXM records; Econ Letters 2025 NANC/KRUZ)
should be page-verified before any single number becomes load-bearing in a spec.
