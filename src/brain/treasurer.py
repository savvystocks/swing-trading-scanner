"""School Phase 4 - the TREASURER (shadow) and the MACRO CIRCUIT BRAKE (shadow).

TREASURER: sizes a TAKEn candidate from CALIBRATED probability through fractional Kelly on the
empirical (fat-tailed) win/loss distribution, then clamps by contract liquidity and the live
drawdown ratchet. It recommends only; the engine keeps sizing a FIXED 1 contract until the Treasurer
is separately promoted by the Governor (addendum). Before any live sizing, NORTH_STAR requires the
probability of hitting the -30% halt under the fitted distribution at the chosen sizing to be
computed and reviewed - estimate_p_halt() is that number.

MACRO CIRCUIT BRAKE: a market-wide veto (VIX spike / trend break) that is the final word in the
dormant gate-mode chain. Shadow here: it records when it WOULD have braked and what that would have
cost or saved, so its eventual live arming is justified by measurement, exactly like the daily brake.

Sizing math is deliberately conservative: half-Kelly cap, liquidity never exceeded, ratchet only ever
reduces. All returns are cost-inclusive and bid-side (NORTH_STAR: executable prices only).
"""
import numpy as np

KELLY_FRACTION = 0.5              # half-Kelly ceiling (NORTH_STAR sizing ambition, capped until proven)
KELLY_HARD_CAP = 0.25            # never allocate more than 25% of sizing capital to one bet, whatever Kelly says
LEG_BUDGET = 800.0               # the $800 per-trade cap stands until the EV machinery justifies otherwise
LIQUIDITY_FRAC = 0.10           # never take more than 10% of the resting top-of-book size
HALT_DRAWDOWN = 0.30            # the NORTH_STAR automatic-halt line


def kelly_fraction(p, mu_win, mu_loss):
    """Fractional-Kelly bet size as a fraction of sizing capital. p = calibrated win prob; mu_win>0,
    mu_loss<0 are the empirical mean win/loss magnitudes. Returns 0 when the edge is non-positive."""
    if not (0 < p < 1) or mu_win <= 0 or mu_loss >= 0:
        return 0.0
    b = mu_win / abs(mu_loss)                        # payoff ratio
    f_star = (p * b - (1 - p)) / b                   # classic Kelly
    if f_star <= 0:
        return 0.0
    return float(min(KELLY_FRACTION * f_star, KELLY_HARD_CAP))


def liquidity_cap(price, top_size, budget=LEG_BUDGET):
    """Max contracts that (a) fit the per-trade budget and (b) stay within LIQUIDITY_FRAC of the
    resting top-of-book size, so the recommendation can actually fill without moving the market."""
    if price is None or price <= 0:
        return 0
    by_budget = int(budget // (price * 100.0))       # options are per-100-share contracts
    by_liquidity = int(max((top_size or 0) * LIQUIDITY_FRAC, 0))
    return max(min(by_budget, by_liquidity) if top_size else by_budget, 0)


def drawdown_ratchet(drawdown):
    """Size multiplier that only ever REDUCES as drawdown deepens toward the halt. drawdown is a
    positive fraction (0.10 = down 10% from high-water)."""
    if drawdown >= HALT_DRAWDOWN:
        return 0.0                                   # at the halt: size zero (entries stop, human review)
    if drawdown >= 0.20:
        return 0.25
    if drawdown >= 0.10:
        return 0.5
    if drawdown >= 0.05:
        return 0.75
    return 1.0


def recommend_size(p_cal, mu_win, mu_loss, price, top_size, drawdown=0.0, sizing_capital=LEG_BUDGET):
    """Full shadow recommendation. Returns the recommended contract count and the pieces behind it.
    The engine ignores this and sizes 1 until the Treasurer is promoted."""
    f = kelly_fraction(p_cal, mu_win, mu_loss)
    ratchet = drawdown_ratchet(drawdown)
    dollars = sizing_capital * f * ratchet
    by_kelly = int(dollars // (price * 100.0)) if price and price > 0 else 0
    cap = liquidity_cap(price, top_size, budget=min(sizing_capital, LEG_BUDGET))
    contracts = max(min(by_kelly, cap), 0)
    return {"contracts": contracts, "kelly_fraction": round(f, 4), "ratchet": ratchet,
            "liquidity_cap": cap, "by_kelly": by_kelly,
            "note": "SHADOW - engine sizes 1 until the Treasurer is promoted"}


def estimate_p_halt(net_returns, weights, fraction, n_paths=2000, horizon=60, seed=7):
    """NORTH_STAR pre-live requirement: P(equity path hits -HALT_DRAWDOWN from its high-water mark)
    under the EMPIRICAL (fat-tailed) net-return distribution, sizing each bet at `fraction` of capital.
    Bootstraps `horizon`-trade paths from the measured TAKE returns. Returns the probability + context."""
    r = np.asarray(net_returns, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    fin = np.isfinite(r) & np.isfinite(w) & (w > 0)
    r, w = r[fin], w[fin]
    if len(r) < 20:
        return {"p_halt": None, "note": f"UNDERPOWERED ({len(r)} TAKE returns; needs >= 20)"}
    prob = w / w.sum()
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n_paths):
        draws = r[rng.choice(len(r), size=horizon, p=prob)]
        equity = np.cumprod(1.0 + fraction * draws)
        peak = np.maximum.accumulate(equity)
        if float((equity / peak - 1.0).min()) <= -HALT_DRAWDOWN:
            hits += 1
    p = hits / n_paths
    return {"p_halt": round(p, 4), "fraction": fraction, "horizon": horizon, "n_returns": int(len(r)),
            "note": ("comfortable" if p < 0.05 else "REVIEW - reduce sizing before live" if p > 0.20 else "moderate")}


# ---- macro circuit brake (shadow) ----
VIX_SPIKE = 0.20                 # +20% VIX vs its recent level -> macro brake
VIX_ABS = 32.0                  # absolute VIX above this -> macro brake


def macro_brake_state(vix_now, vix_ref, spx_dist_sma=None):
    """CLEAR / BRAKE from macro context. vix_ref is a trailing reference (e.g. 20-day). spx_dist_sma
    (% distance of the index to its 20-day SMA) below a floor confirms a trend break. Fail-open: a
    missing sensor never brakes (a dead feed must not silence the engine)."""
    reasons = []
    if vix_now is not None and vix_now >= VIX_ABS:
        reasons.append(f"VIX {vix_now:.0f} >= {VIX_ABS:.0f}")
    if vix_now is not None and vix_ref not in (None, 0) and (vix_now / vix_ref - 1.0) >= VIX_SPIKE:
        reasons.append(f"VIX spike {(vix_now / vix_ref - 1.0) * 100:.0f}% vs ref")
    if spx_dist_sma is not None and spx_dist_sma <= -4.0:
        reasons.append(f"index {spx_dist_sma:.1f}% below 20d SMA")
    return {"state": "BRAKE" if reasons else "CLEAR", "reasons": reasons}
