# PRELIMINARY / UNDERPOWERED — IV-rank & spread-width vs outcome (2026-07-07)

> CORRECTION (2026-07-08): the **executed-trade spread numbers below are an artifact — ignore them.**
> The harvest logged each executed row's spread from the order's own premium/limit price (bid =
> entry_premium, ask = limit_price ≈ premium × 1.01), so every executed trade came out ≈0.99% "tight"
> by construction — it was never the real market spread. The claim in the caveat bullet that "the engine
> is already only holding tight-spread contracts / dodging wide-spread bleed by fill mechanics" is
> therefore UNFOUNDED; whether our actual fills hit wide spreads is currently **unmeasured**. Fixed
> 2026-07-08: executed rows now log the real Alpaca quote spread (leg.execution_cost.bid_ask_spread_pct);
> the split becomes meaningful once new executed rows accumulate. What still stands unchanged is **View 2
> (all-graded / counterfactual)** — those rows use real Unusual Whales bid/ask, so the "wide-spread
> candidates underperform" signal there is real. The IV-rank findings are unaffected.


**Direction only, NOT a verdict.** Tiny/young data. No gate is being added — this is the "measure first"
answer to the 2026-07-07 entry-review suspicion that the engine bleeds by ignoring option expensiveness
(IV rank) and spread width at entry. Read-only cut of the current pile. Cut points: IV rank cheap <33 /
normal 33–67 / expensive ≥67; spread tight <2% / medium 2–8% / wide ≥8%.

## Plain-English summary

- **Expensiveness (IV rank): the early shape does NOT support the bleed suspicion — if anything the
  opposite.** Across ~2,400 graded ideas, expensive-IV candidates hit their +30% up-barrier slightly *more*
  often (22.7%) than cheap ones (15.8%), and their win rate is a touch higher (27.8% vs 23.8%). Average
  returns are about the same across all three bands (−0.32 to −0.41), with no worsening as IV rises. So far,
  buying "over-priced" options is not visibly costing us. Contradicts the suspicion (weakly — early).
- **Spread width: the early shape SUPPORTS the suspicion.** Wide-spread candidates (≥8%) clearly
  underperform: they hit the up-barrier least (11.4% vs ~17%), win far less (20.9% vs ~34%), and lose more
  (mean −0.34 vs −0.14). The wide-vs-tight win-rate confidence intervals don't even overlap
  ([0.18, 0.24] vs [0.30, 0.38]) — a real early signal, on decent sample.
- **Important caveat that softens the spread finding:** that wide-spread result is in the *counterfactual*
  pile (ideas we scored but mostly didn't trade). Every one of the 86 completed *executed* trades had a
  tight (<2%) spread — the engine is already, in effect, only holding tight-spread contracts, almost
  certainly because wide-spread limit orders don't fill and get cancelled. So we may already be dodging most
  of the wide-spread bleed by accident of the fill mechanics, not by a gate. The executed sample can't test
  spread at all yet (no medium/wide executed).
- **Executed trades tell us nothing yet:** all 86 resolved executed trades are losers so far (0 up-barrier
  hits) — the known fast-loser timing bias (losers resolve in hours, winners are still open). Ignore the
  executed bands until they mature.

## The numbers

### View 1 — completed executed trades (n=86, all-time; ~49 since go-live) — TINY, UNDERPOWERED
By IV rank: cheap n=24 win 0.0%; normal n=45 win 2.2%; expensive n=17 win 0.0% (means −0.65 to −0.78).
By spread: tight (<2%) n=86 win 1.2%; medium n=0; wide n=0. → the engine executes only tight-spread
contracts, so spread is untestable on executed trades.

### View 2 — all graded candidates (n=2,398) — the bigger, more useful sample
By IV rank (rows with a computed IV rank):
- cheap (<33): n=202, up-barrier-hit 0.158, win 0.238 [0.184, 0.301], mean −0.322
- normal (33–67): n=386, up-barrier-hit 0.171, win 0.225 [0.187, 0.270], mean −0.413
- expensive (≥67): n=277, up-barrier-hit **0.227**, win **0.278** [0.229, 0.334], mean −0.327

By spread width:
- tight (<2%): n=629, up-barrier-hit 0.165, win **0.339** [0.303, 0.376], mean **−0.151**
- medium (2–8%): n=1118, up-barrier-hit 0.191, win 0.336 [0.309, 0.365], mean −0.136
- wide (≥8%): n=651, up-barrier-hit **0.114**, win **0.209** [0.179, 0.242], mean **−0.338**

## What this does and does not license

- Does NOT license any gate. The IV suspicion is (weakly) contradicted; the spread suspicion is supported
  in the counterfactual but may already be handled by fill mechanics.
- The path to decision-grade: let the weekly report's two new splits accumulate to ~150 completed executed
  and ~5k graded, and add the fill-vs-intention ledger (ROADMAP Q17) to see whether wide-spread contracts,
  *when they do fill*, actually bleed. Only a severe, well-sampled band gap would be harness evidence for a
  single entry-gate change — see the ROADMAP Strategy Question List.
