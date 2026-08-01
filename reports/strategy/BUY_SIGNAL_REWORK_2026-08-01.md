# Buy-signal full rework review — 2026-08-01 (owner-ordered; code-grounded)

Question set: is Unusual Whales the right system; is what we look at good; are we spread too
thin; what is the diagnostic; where is the potential. Every claim below carries a code line or a
committed report as evidence (forensics run wf_cd626bd8, three agents over the live path).

## A. What the live buy path ACTUALLY is (verified in code, not from memory)

- ONE market-wide call per cycle: GET /option-trades/flow-alerts, limit 600, min_premium 25000.
  No opening-trades filter, no sweep filter, no ask/bid-side filter, no OTM filter
  (sandbox_proactive_lab.py:1420-1449; unusual_whales_api.py:122-133).
- Of each alert the trade path reads FIVE fields: ticker, price, total_premium, type (call/put),
  underlying_price. It DISCARDS: ask-side vs bid-side premium split, sweep flag, multileg flag,
  open_interest, volume, opening-trade indication, strike, expiry, DTE, IV, rule name
  (:1435-1449).
- Direction: flow_type (call vs put by aggregated premium) contributes ±2.0; trend ±1.0; SPY
  ±0.5; thresholds ±0.5. Arithmetic consequence: WITH flow present, trend+market (max 1.5
  opposing) can NEVER flip the sign — flow alone decides every direction; the "score" only
  decorates it (:336-352). The autopsy's 3/3-vs-0/3 table was therefore DESCRIPTIVE alignment,
  not a gate — correction to the 08-02 deck's section 3 item 2, which called it a requirement.
- Selection: sort tickers by aggregated total premium DESC, take the first that survives the
  gates. Biggest-premium-first confirmed (:1455, :1702-1746).
- The 20-block/~97-field harvest is LOG-ONLY by contract (:293-294): the decision layer reads 3
  inputs; the sensing layer measures ~97. One live block fabricates on failure (alt_catalyst →
  hardcoded 540%/$1.25M/cluster=True, source='mock', :261-263) — the only non-null fail-open.
- The one SIGNED directional tape we already fetch — /stock/{t}/net-prem-ticks
  (flow_persistence: net_directional_prem, flow_direction) — is consumed log-only and read by
  no decision (sandbox_v11_sensors.py:435-457).

## B. The central mechanical flaw: TYPE IS NOT INTENT

A "put alert" is a put CONTRACT trading big — it says nothing about whether the put was BOUGHT
(bearish) or SOLD (bullish, e.g. cash-secured put selling / vertical legs). Without the ask/bid
side split, opening/closing inference, and multileg matching — all fields UW carries and the
code discards — the ±2.0 direction driver is unsigned intent. A wing of somebody's spread, a
covered call, an institutional hedge, and a conviction buy all look identical to our scanner.
The direction decision is therefore not a weak signal; it is a coin toss over intent, taken at
the most crowded moment (the alert every UW subscriber sees), on the biggest-premium (most
crowded) name, expressed in the highest-friction vehicle (long options at the ask). The 3.8%
executed hit rate, D4's 0.4955 direction AUC, and the inverted conviction table are three
instruments reading that same construction.

## C. Is Unusual Whales the right system?

KEEP THE SUBSCRIPTION; INDICT THE CONSUMPTION. The client wraps ~35 endpoints; the decision
path drinks five fields from the single most retail-crowded one. What UW uniquely provides —
signed net premium ticks, ask/bid premium splits, sweep/multileg flags, GEX/dealer greeks,
dark-pool prints, OI change, congress with disclosure timestamps — is either logged-and-ignored
or unconsumed. Sober counterweights, on the record: the correctly-signed rework may STILL find
nothing (flow→stock direction already read dead at 47-49% on our window, four flow-following
reads dead, and the pond study says these nulls are genuine, not artifacts); and our proven
positive content in this data is VOL-STRUCTURE, not direction (0.72-0.73 option-space AUC —
which contracts live or die). UW's alert feed as a direction oracle is disproven; UW as a
vol/positioning/flow-tape instrument is largely untested and is where its remaining value lies.

## D. Is what we're looking at good?

The sensing layer is mostly honest: 17 of 20 blocks fill 77-100% with real sources and null
fail-opens. Defects: (1) alt_catalyst fabricates (delete or null it); (2) the decision layer
reads 3 of ~97 fields — enormous eyes, pinhole brain; (3) the one signed tape is unread; (4)
FEATURE_SET_VERSION 'v11-37feat' no longer matches ~97 fields (hygiene). The imbalance, not the
sensors, is the problem.

## E. Are we spread too thin?

On SIGNAL BETS, yes: ~97 fields x 12 structures x 68,402 rule-trials x 10+ studies on 20
trading days of one calm regime. Nothing can validate at that n; the trials ledger (1,878) now
prices it. On MACHINERY, no: the harness/harvest/governance is the asset and is what found every
truth above. The registry discipline (pre-registration, tripwires, kill-fast) is the antidote
already in force. The tournament CONCENTRATES rather than spreads: of six books, only two are
new strategy claims, and both rest on external evidence.

## F. The rework blueprint (staged; every stage governed)

- R1 SUBTRACTIONS (08-02 boundary, Lessons Engine spec): delete biggest-premium-first (replace
  with tightest-spread-first among gate survivors); null-not-mock alt_catalyst everywhere;
  correction — there is no conviction-stack gate to remove; instead the spec states plainly
  that V10 direction = unsigned flow side, kept in the Lessons Engine ONLY for control
  comparability.
- R2 SIGNED-INTENT PLUMBING (measurement first, £0, passivity battery mandatory): compute from
  surfaces we already pull or already receive — ask-vs-bid premium imbalance per ticker
  (fields present in per-ticker flow-alerts responses), signed net premium from net-prem-ticks
  (already fetched, currently log-only), sweep/multileg flags, opening-volume-vs-OI inference
  via the oi_change sensor. Land as harvest measurement columns; evaluate against STOCK 1/3/5d
  labels first (direction is testable nearly free in stock space; options frictions come only
  after direction exists). This re-uses the registered stock-horizon question's machinery and
  tripwires — it does not create a new unregistered search.
- R3 VOL-SIDE MONETIZATION (already staged): the proven 0.73 is option-space structure; its
  honest expression is the tournament's short-premium account (put-write primary + lane cost
  instrument), not direction guessing.
- R4 WATCHES (touch nothing): discovery's first above-hurdle flicker (shares_short HIGH x
  execution_hour LOW x ATR/GEX, n_eff 14-21, needs convergence survival on consecutive weeks);
  dark-pool accumulation (d 0.31-0.40, champion stable 4/5 vintages, below its 0.68 bar);
  consensus-fade (registered 08-01, post-registration data only).

## G. The potential, stated honestly

The potential is real and it is NOT the flow-alert direction trade: it is (1) a truth machine
that catches its own errors within days, (2) a unique growing dataset (signed tape + dark pool
+ GEX + disclosure-timestamped congress + our own executable-price labels — the archiver
compounds this daily), (3) one proven profitable organ (exit machinery, +$46k on real fills),
(4) proven vol-structure predictability (0.73), and (5) an evidence-ranked lane (put-write)
with a two-decade record ready to hold the primary slot. The rework points the machine at
those; the flow-alert direction oracle retires from decision-making unless R2's signed
reconstruction passes its pre-registered bars on future data.
