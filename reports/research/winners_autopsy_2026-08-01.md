# Winners' autopsy — every real closed trade (2026-08-01, owner-ordered deep diagnostic)

Executed, closed legs only (LIVE_PAPER Alpaca fills), 2026-06-24 → 2026-07-30: 414 legs, 74
winners (17.9%), net −$151,887 (+$50,213 winners / −$202,100 losers). Interactive version with
all tables: winners_autopsy_2026-08-01.html (same directory). Diagnostic trials appended to the
lifetime ledger.

## The three structural findings

1. THE ONLY PROFITABLE ORGAN IS AN EXIT RULE. All 74 winners exited via trail (63, +$35,651),
   take-profit (7, +$10,695) or reconciled equivalents (4). All 305 stop-loss exits were losers
   (−$198,867). Asymmetry is healthy (avg winner +$678 vs avg loser −$594); the fatal number is
   frequency — break-even needs 46.7% winners at this asymmetry, entries deliver 17.9%.

2. THE BUY TRIGGER'S CONVICTION IS INVERTED (the shocking table). Joining each closed leg to its
   executed harvest row (n=379 joined, 58 winners, base 15.3%):
   - conviction stack (flow+trend+market agree with bought side): 3/3 agree → 7.0% wins (n=71);
     2/3 → 14.0%; 1/3 → 18.3%; 0/3 → 25.6% (n=43). Monotonically inverted.
   - with-trend 10.9% vs against-trend 19.9%; with-market 12.9% vs against-market 18.8%;
     alert-agrees-tape 13.3% vs contra-tape 17.8%.
   - flow premium size (the biggest-premium-first selection rule): 250k+ "whales" 13.6% and
     25–50k 10.9% vs 100–250k 17.0% — no monotone edge; the selection rule preferentially
     bought crowded consensus.
   - flow persistence strong ≥30%: 15.2% (no help). Sweep aggression: flat.
   Every cell is still net-negative. Interpretation consistent with D4 (features carry zero
   stock-direction information) and the dip-bounce context finding: by the time all signals
   agree, the move is crowded and the option fully priced.

3. HALF THE WINNER MONEY WAS ONE WEEK. 54% of all winner dollars came from 8 legs entered
   Jun 24–30 (RKLB/SOFI/PLTR/SPY/ZM/NVDA/AMD/HOOD) at ~4× today's sizing during a market rally,
   with sensors still MOCK. Additionally: alt_catalyst (insider/reddit) is mock in EVERY record
   to this day; per-trade "determining factor" narratives were generated from those mocks and
   are fiction.

## Honesty limits

- One calm month, 19 winner entry days; day-clustered n_eff shrinks every cell (~2.2× rule).
- The 0/3-aligned standout: 11 winners on 7 days — diagnosis, not strategy; the persistence
  mirage (passed run 1, died 1/5 on vintages) is the cautionary precedent.
- Cells selected after looking → all of it multiple-testing; counted into the lifetime ledger.
- No trigger state or combination is net-positive. Everything here is "loses slower".

## What it licenses (staged for the 2026-08-02 boundary, owner decides)

Evidence-backed SUBTRACTIONS for the Lessons Engine spec (no new claims): delete
biggest-premium-first selection (replace with tightest-spread-first, cost-justified); drop the
conviction-stack requirement (provably selects 7%-win trades); rip out mock blocks feeding the
score. The INVERSION itself (consensus-fade / dip-bounce entry) is NOT deployable — registered
as a pre-registered question in ROADMAP with tripwires; must hold on future weeks + convergence
angles before it can touch any entry logic.
