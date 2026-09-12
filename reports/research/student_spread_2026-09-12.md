# STUDENT SPREAD STUDY - 2026-09-12

Picker A (EXPRET/ALL/BASE/k3) traded under the $1,000 cap as a defined-risk call spread: the FURTHEST listed strike on the same expiry whose net debit fits the cap (pre-registered; see the script header). Affordable picks (ask <= $10) are bought outright. Exit timing = the long leg's BASE rule. Real-dollar weekly t at integer lots.

## search window

| config | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean | all regimes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A LONG $1,000 notional (report basis) - search | 61 | 25 | +19.9 | 57% | +484 | +1.97 | 68% | +495/+475 | 2302 | +12112 | BULL:44/+12 MILD:17/+39 | no |
| A LONG one contract at real cost (what a $1,600 seat does) | 61 | 25 | +19.9 | 57% | +1069 | +0.76 | 56% | +2731/-466 | 13604 | +26717 | BULL:44/+12 MILD:17/+39 | no |
| CAP RULE: long if <= $10 else spread FURTHEST fit (pre-registered, <=10 lots) | 46 | 24 | +10.3 | 41% | -37 | -0.45 | 46% | -99/+25 | 1853 | -888 | BULL:29/-7 MILD:17/+39 | no |
|   same, ENGINE sizing (lots = floor($1,000/cost)) | 46 | 24 | +10.3 | 41% | +234 | +0.90 | 50% | -64/+531 | 2456 | +5612 | BULL:29/-7 MILD:17/+39 | no |
|   same, engine sizing, single best trade removed | 45 | 24 | +1.7 | 40% | +68 | +0.31 | 46% | -64/+199 | 2456 | +1625 | BULL:29/-7 MILD:16/+17 | no |
|   affordable longs only (A's picks with ask <= $10), engine sizing | 30 | 20 | +24.7 | 47% | +367 | +1.19 | 50% | +75/+658 | 2045 | +7333 | BULL:15/+4 MILD:15/+46 | no |
|   spread legs only, FURTHEST fit | 16 | 11 | -16.6 | 31% | -156 | -1.49 | 36% | -134/-175 | 2039 | -1721 | BULL:14/-18 MILD:2/-8 | no |
|   sensitivity: NEAREST fitting strike (not pre-registered) | 46 | 24 | +7.1 | 41% | -114 | -1.11 | 42% | -183/-44 | 3588 | -2735 | BULL:29/-11 MILD:17/+37 | no |
|   spread legs only, NEAREST fit | 16 | 11 | -26.0 | 31% | -324 | -2.29 | 27% | -379/-279 | 3774 | -3568 | BULL:14/-26 MILD:2/-24 | no |
| A RESTRICTED to cap-fitting candidates (0.30-9.90), 3/week, engine sizing | 82 | 32 | +5.3 | 44% | +141 | +0.48 | 47% | -2/+283 | 7125 | +4497 | BULL:52/-1 MILD:30/+15 | no |
|   same, single best trade removed | 81 | 31 | -4.2 | 43% | -101 | -0.60 | 45% | -71/-130 | 7125 | -3145 | BULL:52/-1 MILD:29/-11 | no |

pick outcomes: affordable 30, no_chain 1, no_fit 14, ok 16; stale short-leg prints rejected: 10; replay mismatches vs corpus label: 0
same-trade comparison (spread-priced picks only, n=16): long +6.5%/trade -> spread -16.6%/trade; median width 21.0, median debit $833

## HOLDOUT window

| config | trades | weeks | %/trade | win | $/week | weekly t | +weeks | halves | maxDD $ | total $ | regimes n/mean | all regimes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A LONG $1,000 notional (report basis) - HOLDOUT | 41 | 18 | +49.9 | 66% | +1135 | +2.20 | 78% | +883/+1388 | 1216 | +20439 | BEAR:12/+61 BULL:15/+18 MILD:14/+74 | YES |
| A LONG one contract at real cost (what a $1,600 seat does) | 41 | 18 | +49.9 | 66% | +4105 | +1.31 | 61% | +7586/+624 | 6535 | +73884 | BEAR:12/+61 BULL:15/+18 MILD:14/+74 | YES |
| CAP RULE: long if <= $10 else spread FURTHEST fit (pre-registered, <=10 lots) | 29 | 17 | +48.6 | 66% | +354 | +1.50 | 82% | +112/+569 | 808 | +6021 | BEAR:5/+35 BULL:12/+21 MILD:12/+82 | no |
|   same, ENGINE sizing (lots = floor($1,000/cost)) | 29 | 17 | +48.6 | 66% | +791 | +1.59 | 76% | +199/+1318 | 1064 | +13450 | BEAR:5/+35 BULL:12/+21 MILD:12/+82 | no |
|   same, engine sizing, single best trade removed | 28 | 17 | +24.1 | 64% | +374 | +2.18 | 76% | +199/+530 | 1064 | +6357 | BEAR:5/+35 BULL:12/+21 MILD:11/+23 | no |
|   affordable longs only (A's picks with ask <= $10), engine sizing | 24 | 14 | +52.1 | 62% | +883 | +1.46 | 71% | +172/+1594 | 1196 | +12363 | BEAR:2/+10 BULL:10/+25 MILD:12/+82 | no |
|   spread legs only, FURTHEST fit | 5 | 4 | +32.0 | 80% | +272 | +1.52 | 100% | +432/+112 | 0 | +1087 | BEAR:3/+51 BULL:2/+3 | no |
|   sensitivity: NEAREST fitting strike (not pre-registered) | 29 | 17 | +49.1 | 59% | +357 | +1.43 | 71% | +183/+511 | 808 | +6062 | BEAR:5/+50 BULL:12/+16 MILD:12/+82 | no |
|   spread legs only, NEAREST fit | 5 | 4 | +34.5 | 40% | +282 | +0.66 | 50% | +192/+372 | 463 | +1128 | BEAR:3/+77 BULL:2/-29 | no |
| A RESTRICTED to cap-fitting candidates (0.30-9.90), 3/week, engine sizing | 43 | 19 | +25.0 | 60% | +580 | +1.25 | 68% | -3/+1104 | 1784 | +11012 | BEAR:10/+6 BULL:15/+10 MILD:18/+48 | YES |
|   same, single best trade removed | 42 | 19 | +8.1 | 60% | +206 | +1.14 | 68% | -3/+395 | 1784 | +3920 | BEAR:10/+6 BULL:15/+10 MILD:17/+8 | YES |

pick outcomes: affordable 24, no_chain 1, no_fit 11, ok 5; stale short-leg prints rejected: 10; replay mismatches vs corpus label: 2
capture on the long's big winners (>= +100%, n=2): long mean +197% -> spread mean +73%
same-trade comparison (spread-priced picks only, n=5): long +105.3%/trade -> spread +32.0%/trade; median width 20.0, median debit $823

## Holdout picks, one per line

| day | occ | ask | K | K2 | width | credit | debit | lots | long % | spread % | exit | short exit px |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-03-02 | TLT260306C00089500 | 0.50 | 89.5 | - | - | - | - | - | -53.9 | - | stop | affordable |
| 2026-03-02 | SOFI260306C00018500 | 0.36 | 18.5 | - | - | - | - | - | +16.1 | - | trail | affordable |
| 2026-03-02 | TQQQ260306P00046000 | 0.51 | 46.0 | - | - | - | - | - | +167.9 | - | trail | affordable |
| 2026-03-09 | SOFI260313C00019000 | 0.37 | 19.0 | - | - | - | - | - | -13.2 | - | trail | affordable |
| 2026-03-09 | GOOGL271217C00345000 | 50.65 | 345.0 | 365.0 | 20.0 | 42.05 | 8.60 | 1 | +85.0 | +7.1 | trail | 84.50 (bar) |
| 2026-03-10 | NVDA261218C00183000 | 31.25 | 183.0 | - | - | - | - | - | +45.5 | - | trail | no_chain |
| 2026-03-17 | IWM261218C00210000 | 53.11 | 210.0 | - | - | - | - | - | +39.0 | - | trail | no_fit |
| 2026-03-17 | TSM270115C00185000 | 169.10 | 185.0 | - | - | - | - | - | +24.5 | - | trail | no_fit |
| 2026-03-18 | AMD270917C00250000 | 41.40 | 250.0 | 270.0 | 20.0 | 35.02 | 6.38 | 1 | +200.9 | +125.8 | trail | 110.15 (bar_prior) |
| 2026-03-23 | ASML260327C00760000 | 644.00 | 760.0 | - | - | - | - | - | -12.7 | - | time | no_fit |
| 2026-03-23 | COST260402C00610000 | 367.65 | 610.0 | - | - | - | - | - | +4.3 | - | time | no_fit |
| 2026-03-24 | COST260417C00540000 | 443.05 | 540.0 | - | - | - | - | - | +0.1 | - | time | no_fit |
| 2026-03-30 | STX280121C00120000 | 253.40 | 120.0 | - | - | - | - | - | +181.6 | - | time | no_fit |
| 2026-03-30 | PLTR271217C00082500 | 73.20 | 82.5 | - | - | - | - | - | -5.6 | - | time | no_fit |
| 2026-03-30 | AMD270319C00200000 | 47.20 | 200.0 | 220.0 | 20.0 | 39.51 | 7.69 | 1 | +194.0 | +20.8 | trail | 129.47 (bar) |
| 2026-04-10 | NVDA260417C00197500 | 0.52 | 197.5 | - | - | - | - | - | -62.3 | - | stop | affordable |
| 2026-04-10 | SPY260416C00685000 | 2.52 | 685.0 | - | - | - | - | - | -59.3 | - | stop | affordable |
| 2026-04-13 | NKE260417C00043000 | 0.38 | 43.0 | - | - | - | - | - | +82.5 | - | trail | affordable |
| 2026-04-16 | ONDS260515C00012000 | 0.49 | 12.0 | - | - | - | - | - | +45.9 | - | trail | affordable |
| 2026-04-16 | TLT280121C00086000 | 5.40 | 86.0 | - | - | - | - | - | -17.5 | - | time | affordable |
| 2026-04-22 | QQQ260423C00660000 | 0.51 | 660.0 | - | - | - | - | - | -94.2 | - | stop | affordable |
| 2026-04-28 | NFLX260501C00094000 | 0.33 | 94.0 | - | - | - | - | - | +26.4 | - | trail | affordable |
| 2026-05-22 | F260717C00016000 | 0.39 | 16.0 | - | - | - | - | - | +65.2 | - | trail | affordable |
| 2026-06-29 | MARA260702C00014000 | 0.51 | 14.0 | - | - | - | - | - | -36.6 | - | trail | affordable |
| 2026-07-14 | NVDA260724C00230000 | 0.34 | 230.0 | - | - | - | - | - | +67.7 | - | trail | affordable |
| 2026-07-20 | IBIT260724C00037000 | 0.37 | 37.0 | - | - | - | - | - | +146.7 | - | trail | affordable |
| 2026-07-21 | SMCI260724C00026500 | 0.46 | 26.5 | - | - | - | - | - | +734.2 | - | trail | affordable |
| 2026-07-22 | ONDS260724C00008000 | 0.38 | 8.0 | - | - | - | - | - | -23.1 | - | trail | affordable |
| 2026-07-29 | GEV281215C00400000 | 594.00 | 400.0 | - | - | - | - | - | +10.4 | - | time | no_fit |
| 2026-07-30 | SPY260803C00750000 | 0.33 | 750.0 | - | - | - | - | - | +32.2 | - | trail | affordable |
| 2026-08-05 | TSLA261218C00320000 | 40.55 | 320.0 | 345.0 | 25.0 | 30.91 | 9.64 | 1 | +44.5 | +7.2 | trail | 48.25 (bar) |
| 2026-08-05 | AAPL270219C00320000 | 23.85 | 320.0 | 340.0 | 20.0 | 15.62 | 8.23 | 1 | +2.3 | -0.8 | time | 16.23 (bar_prior) |
| 2026-08-05 | DELL280121C00390000 | 223.75 | 390.0 | - | - | - | - | - | -11.5 | - | time | no_fit |
| 2026-08-10 | ACHR260918C00007000 | 0.41 | 7.0 | - | - | - | - | - | +49.0 | - | trail | affordable |
| 2026-08-10 | NFLX260814C00078000 | 0.32 | 78.0 | - | - | - | - | - | +45.3 | - | trail | affordable |
| 2026-08-10 | PLTR270219C00125000 | 61.25 | 125.0 | - | - | - | - | - | -0.2 | - | time | no_fit |
| 2026-08-17 | TLT260828P00081500 | 0.45 | 81.5 | - | - | - | - | - | -69.6 | - | stop | affordable |
| 2026-08-17 | GLD261120C00370000 | 44.55 | 370.0 | - | - | - | - | - | -8.2 | - | time | no_fit |
| 2026-08-18 | TLT260831C00082000 | 0.39 | 82.0 | - | - | - | - | - | +185.3 | - | trail | affordable |
| 2026-09-01 | TLT260930P00081000 | 0.45 | 81.0 | - | - | - | - | - | +2.1 | - | trail | affordable |
| 2026-09-04 | SPY260911P00752000 | 0.44 | 752.0 | - | - | - | - | - | +13.3 | - | trail | affordable |

## Six checks

1. Edge: none new - the same picks; only the instrument changes.
2. Fat tail: a spread caps the right tail that pays A's book; the 'big winners' line above measures how much is lost.
3. Frictions: two legs, two spreads (haircut applied both ways); mleg fill quality and early assignment not modelled; bars are trade prices.
4. Data honesty: one pre-registered rule, holdout touched once; the short strike is chosen on prices completed BEFORE the entry hour; the sensitivity row is labelled and not evidence.
5. Dead weight: none added; the script is research-only.
6. Unknowns: strike lists from Alpaca's registry; a strike with no bar before entry is treated as untradeable, which biases toward liquid strikes; intrinsic settlement when the short has no exit-day bar.
7. Stale prints: trade bars on illiquid deep-in-the-money strikes lag the market; the intrinsic-value bounds above reject them at entry and floor them at exit. A live seat would see NBBO quotes instead; this study cannot.

Verdict rule (written before running): the spread variant is worth a seat design only if the HOLDOUT cap-rule row keeps a positive weekly t, positive halves and a per-trade mean above the pool; otherwise the cap and the edge do not fit together and the two remaining options stand. The SEARCH-window row is reported for consistency: a rule that passes only on the holdout while losing on the window the picker was chosen on is fragile, whatever the holdout says.

## VERDICT (2026-09-12, written after the guarded run; the first pass, without the no-arbitrage guards, is superseded)

1. THE SPREAD DOES NOT CARRY A's EDGE. Where a second leg can be priced at a verifiable price
   (search window, 16 trades) the spread turns the long's +6.5%/trade into -16.6% (nearest
   strike: -26.0%). On the holdout only 5 of the 17 pricey picks can be fitted under the cap at
   a non-stale price (10 stale prints rejected, 11 picks with no fitting strike); 5 trades at
   +32% is not evidence. The deep-in-the-money picks that make A's biggest dollars ($250-$650
   contracts) cannot become a $1,000-risk spread with any useful width. The pre-registered
   cap-rule row passes the verdict rule on the holdout (t +1.50 / +1.59 at engine sizing) only
   because 24 of its 29 trades are cheap longs, not spreads; passing on that technicality would
   be dishonest. Spread variant: REJECTED as a seat design.

2. WHAT THE RUN FOUND INSTEAD: A's edge under the cap sits in its CHEAP picks. 24 of A's 41
   holdout picks and 30 of its 61 search picks were contracts under $1 - affordable outright,
   sized by the engine's rule (lots = $1,000 / cost). Taken exactly as A ranked them among ALL
   candidates: search +24.7%/trade, weekly t +1.19, halves +75/+658 (30 trades, 20 weeks);
   holdout +52.1%/trade, t +1.46, halves +172/+1594 (24 trades, 14 weeks); about 1.5 trades a
   week. With the single best trade removed the holdout cap-rule row keeps +24.1%/trade at t
   +2.18. Both windows positive, both halves positive in both windows - but neither window
   clears the court's 1.8 alone, bear regime is nearly absent (n 2), and the 4.00-9.90 band
   inside the same cap loses (-10.9%/trade, Thursday's test). Restricting A to cap-fitting
   candidates and refilling three a week from them is weaker (search +5.3 t +0.48; holdout
   +25.0 t +1.25, all regimes positive): A's conviction against the pricey field is part of
   the signal. Two holdout picks replay 0.1-0.3 points off their corpus label because the
   hourly library has grown since the corpus was built; immaterial.

3. IMPLICATION: a live path exists WITHOUT touching the cap - A unchanged (trained and
   thresholded on ALL), executing only the picks whose ask fits the cap, at engine sizing.
   Evidence grade: suggestive (t 1.2-1.5 per window, consistent sign), not proven; the live
   court on trading days would decide. Flipping it live needs the owner's word.
