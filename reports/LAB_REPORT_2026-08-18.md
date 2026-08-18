# THE LAB — full report for owner review (2026-08-18, spec v2.0)

The lab is the system's court: every trading idea is a defendant, evidence is gathered
nightly, and verdicts are automatic. Nothing reaches live size without winning here, and
nothing keeps its seat after losing here. As of tonight NOTHING holds the main seat: all
fourteen strategies are equal $1k auditions (owner order 23:48).

## 1. Evidence assets (what the court can consult)
- HARVEST DB (Vultr VPS): every scored candidate since July with 97-sensor feature blocks,
  bid-path polls, and triple-barrier labels. ~750 labeled fade-cohort, ~20k labels total,
  growing ~500/day. Off-box backup nightly.
- 2.5-YEAR CORPUS: 300k option contract-days + 98-stock daily history reconstructed from
  free Alpaca data. Refreshes first Saturday monthly. Priors from it print beside every
  boundary verdict (advisory only).
- FILL LEDGER: every real order's submit/fill/slippage, book-tagged.
- TRIALS LEDGER: 30,000+ registered hypothesis tests (multiple-testing honesty).

## 2. The nightly chain (all times UTC, all automatic)
- 22:00 boundary trajectory run (SEQ_APPLY armed): every book's LLR updated; a sequential
  PASS promotes the spec THAT NIGHT (one change max, Telegram page).
- 22:10 student retrain: narrow fade model (AUC 0.468 = no pick power, honest) + WIDE
  whole-funnel model (n=16,570, AUC 0.680 - within-day verdict pending ~Aug 28).
- 21:50 shadow lab: rolling 5-day rescore of ~22 books at executable prices.
- Wed 10:00 report-only pulse; Fri 22:20+22:35 deep review (fixed-bar verdicts, priors,
  deferral audit) -> owner Telegram with the weekend to read it.

## 3. Verdict machinery (the science)
- VIRGIN-ONLY: evidence counts only from days after a hypothesis was registered.
- DAY-CLUSTERED: trades sharing a day = one observation. No 20-trades-one-lucky-day cons.
- SEQUENTIAL (SPRT): LLR >= +2.94 vs comparator = promote (earliest day 5); <= -2.94 =
  reject early; ambiguity falls to fixed 10-day bars (Friday only, look-frequency honesty).
- PROBATION: every promotion stores prior values; re-judged on its NEXT 10 virgin days;
  auto-reverted if the edge died. The ratchet turns both ways.
- ANTI-RUBIKS-CUBE: any spec change restarts all other evidence clocks (verdicts are earned
  against the system as it now is) + 14-day per-key cooldown. Changes compound in series.
- PLACEBO_RANDOM (new tonight): a book that picks candidates by hash - pure noise. If the
  machinery ever promotes it, the lab is broken and says so. Expected mean: ~0 forever.
- FAMILY-WISE honesty: ~22 parallel books means ~1 false PASS per cycle is EXPECTED at
  these thresholds; probation + placebo are the backstops that make this survivable.

## 4. Live auditions (real paper fills, $1k seats)
| strategy | trigger family | realized | standing |
|---|---|---|---|
| FADE | flow vs both trends (calm days) | $0, 3 open (day 1) | first fills 08-18; corpus t=2.26 mild-days |
| CREDIT_SPREAD_W | weekly premium structure | first entry 08-19 | backtest +$2,302/114wk 88% - strongest evidence held |
| OVERNIGHT | calendar (close->open) | +$5, 4/4 wins | matches sim; steady |
| TURN_OF_MONTH | calendar (25th->4th) | awaiting window | sim +378% long-run |
| CONSENSUS | flow with both trends | -$508, 6 open | at-risk; shadow cooled to ~-4/day |
| QUIET_TAPE | low volume pace | -$507, 2 open | weakest; likely first SPRT reject |
| EXEC_BASELINE | none (control) | -$86 | the bar everyone must beat |
| FADE_UNROUTED | fade shape, all days | 1 open (+60 peak) | the INTC surprise - watch |
| FADE_WHALE | 400k-1M prints | 1 open | corpus prior +3.4 vs -0.5 |
| DP_HEAVY / FADE_DP | dark-pool density | thin | corpus prior: dp>=150 was 40.9% vs 19.3% win |
| EARLY_STRENGTH | option's own momentum | 0 confirms yet | corpus: immediate beat confirmed |
| GEX_PIN (new) | dealer zero-gamma pin | starts 08-19 | untapped sensor family |
| IV_EXTREME (new) | vol-rank extremes | starts 08-19 | untapped sensor family |
| retired: PUTW/VRP (5k-unusable), CONDOR (backtest -$3,020), MOMENTUM (owner: options only) | | | evidence preserved |

## 5. Shadow books (nightly counterfactuals, no money)
Live-band/router family: LIVE_SPEC, BAND_50_400, SOFT_ROUTER, MILD_ONLY, V13_DEPTH,
BAND_WIDE, OPT_WINNER. Exit family: EXIT_STOP40/TIGHT_TRAIL/TRAIL30/TP80/TIME48, EARLY_CUT.
Timing: TOD_OPEN/MID/LATE. Shape: INVERSE_CONTROL, TREND_CONSENSUS, PUTS/CALLS_ONLY,
FADE_ATM, FADE_DP, FADE_WHALE, SPR_25_MILD. Brains: META_SELECT (narrow), META_WIDE (0.68).
Control: PLACEBO_RANDOM. Current LLRs (11 virgin days): BAND_WIDE -0.77 (drifting reject),
EARLY_CUT -0.22, V13_DEPTH +0.05, rest ~0 (young). TREND_CONSENSUS 3d: +13.2/-13.1/-12.0.

## 6. Verdict calendar
- ~Aug 26-28: TREND_CONSENSUS 10 days; META_WIDE within-day verdict; router dial-in from
  MILD/TREND tags. First fixed-bar promotions possible Fri Aug 21.
- ~Sep 1: fade t>1 rung; 40-fill review at current pace. Sep 27: UW subscription verdict.
- ~Mid-Oct: fade t>2 scale-or-kill; real-capital gate checklist opens if 2+ legs proven.

## 7. Known gaps (owner review items)
- UW payment = single point for 6 trigger families (structural legs immune). Sep 27 decides.
- No scheduled fire-drills of failover/rollback (tested by real incidents only, 3-0 so far).
- Congress/insider trigger needs fetch code (Sep, with EDGAR study).
- Family-wise error: accepted and controlled by probation+placebo, not eliminated.
