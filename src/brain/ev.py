"""GATE 2 - EV engine v2 (empirical, not binary) + the sequential edge test.

Conditional return distributions are estimated from the dataset's realized_return by outcome class -
up-touch, down-touch, vertical-positive, vertical-negative - explicitly capturing gap-throughs
(down-touches that resolved far below -50%, up-touches beyond +30%). The EV(p) uses empirical class
means; thresholds are solved from it with BOOTSTRAP confidence intervals (never a bare point). Expected
shortfall of the loss tail is retained as a first-class output for the future Kelly stage.

The closed-form binary breakeven (0.30 p - 0.50 (1-p) - costs -> 62.5% pre-cost) is retained ONLY as a
sanity FLOOR printed beside the empirical threshold; an empirical threshold below it is a red flag.

Cost model: slippage defaults to the per-row half-spread captured at signal time (a documented
placeholder until the slippage ledger, ROADMAP item 3, supplies measured values).

Pure numpy + stdlib. Imports no execution module.
"""
import math
import numpy as np

BINARY_UP, BINARY_DOWN = 0.30, -0.50                          # the harvester's fixed barrier returns


def class_stats(realized_return, outcome):
    """Empirical conditional return distribution by outcome class, with gap-through capture."""
    r = np.asarray(realized_return, dtype=np.float64)
    o = np.asarray(outcome, dtype=object)
    classes = {
        "up_touch": r[o == "up"],
        "down_touch": r[o == "down"],
        "vertical_pos": r[(o == "vertical") & (r > 0)],
        "vertical_neg": r[(o == "vertical") & (r <= 0)],
    }
    stats = {}
    for name, arr in classes.items():
        stats[name] = {"n": int(arr.size),
                       "mean": float(arr.mean()) if arr.size else float("nan"),
                       "std": float(arr.std(ddof=1)) if arr.size > 1 else float("nan")}
    down = r[o == "down"]
    up = r[o == "up"]
    stats["gap_through"] = {
        "down_below_-0.50_rate": float(np.mean(down < BINARY_DOWN)) if down.size else float("nan"),
        "down_tail_mean": float(down[down < BINARY_DOWN].mean()) if np.any(down < BINARY_DOWN) else float("nan"),
        "up_beyond_+0.30_rate": float(np.mean(up > BINARY_UP)) if up.size else float("nan"),
        "up_tail_mean": float(up[up > BINARY_UP].mean()) if np.any(up > BINARY_UP) else float("nan"),
    }
    return stats


def cost_model(half_spread_pct):
    """Placeholder cost = per-row half-spread at signal time (fraction of premium). ROADMAP item 3
    (slippage ledger) will replace this with measured round-trip slippage."""
    hs = np.asarray(half_spread_pct, dtype=np.float64)
    hs = hs[np.isfinite(hs)]
    return float(np.nanmean(hs)) if hs.size else 0.0


def _win_loss_means(realized_return):
    r = np.asarray(realized_return, dtype=np.float64)
    r = r[np.isfinite(r)]
    win, loss = r[r > 0], r[r <= 0]
    mu_win = float(win.mean()) if win.size else BINARY_UP
    mu_loss = float(loss.mean()) if loss.size else BINARY_DOWN
    return mu_win, mu_loss


def ev_of_p(p, mu_win, mu_loss, cost=0.0):
    """EV of a bet with win-probability p, using EMPIRICAL class means (captures gap-throughs)."""
    return p * mu_win + (1 - p) * mu_loss - cost


def breakeven_threshold(mu_win, mu_loss, cost=0.0):
    """Solve EV(p*) = 0 for the empirical breakeven win-probability."""
    denom = mu_win - mu_loss
    if abs(denom) < 1e-12:
        return float("nan")
    return (cost - mu_loss) / denom


def solve_threshold(realized_return, cost=0.0, n_boot=2000, ci=0.95, seed=7):
    """Empirical breakeven probability with a bootstrap confidence interval. Returns dict with the
    point estimate, the [lo, hi] CI, the empirical class means, and the binary sanity floor + red flag."""
    r = np.asarray(realized_return, dtype=np.float64)
    r = r[np.isfinite(r)]
    mu_win, mu_loss = _win_loss_means(r)
    point = breakeven_threshold(mu_win, mu_loss, cost)
    floor = breakeven_threshold(BINARY_UP, BINARY_DOWN, cost)         # 0.625 pre-cost
    boots = []
    if r.size >= 2:
        rng = np.random.default_rng(seed)
        for _ in range(n_boot):
            samp = r[rng.integers(0, r.size, r.size)]
            mw, ml = _win_loss_means(samp)
            boots.append(breakeven_threshold(mw, ml, cost))
        lo, hi = np.nanpercentile(boots, [(1 - ci) / 2 * 100, (1 + ci) / 2 * 100])
    else:
        lo = hi = float("nan")
    return {"threshold": point, "ci": [float(lo), float(hi)], "ci_level": ci,
            "mu_win": mu_win, "mu_loss": mu_loss, "cost": cost,
            "binary_floor": floor, "below_floor_red_flag": bool(np.isfinite(point) and point < floor)}


def expected_shortfall(realized_return, alpha=0.05):
    """Expected shortfall of the loss tail (mean of the worst `alpha` fraction of returns). First-class
    output for the future Kelly stage."""
    r = np.asarray(realized_return, dtype=np.float64)
    r = np.sort(r[np.isfinite(r)])
    if r.size == 0:
        return float("nan")
    k = max(1, int(math.floor(alpha * r.size)))
    return float(r[:k].mean())


def wilson_interval(k, n, z=1.96):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (float("nan"), float("nan"))
    phat = k / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return (centre - half, centre + half)


def sprt(n_wins, n_trials, p0, p1, alpha=0.05, beta=0.20):
    """Wald SPRT on executed trades. H0: win rate = p0 (breakeven-plus-costs hurdle); H1: win rate = p1
    (stated minimum edge). Returns CONTINUE / ACCEPT (H1: edge) / REJECT (H0: no edge) with the
    log-likelihood ratio and Wald boundaries."""
    p0 = min(max(p0, 1e-6), 1 - 1e-6)
    p1 = min(max(p1, 1e-6), 1 - 1e-6)
    k, n = int(n_wins), int(n_trials)
    llr = (k * math.log(p1 / p0) + (n - k) * math.log((1 - p1) / (1 - p0))) if n > 0 else 0.0
    upper = math.log((1 - beta) / alpha)                       # accept H1 at/above this
    lower = math.log(beta / (1 - alpha))                       # accept H0 at/below this
    if n == 0:
        decision = "CONTINUE"
    elif llr >= upper:
        decision = "ACCEPT"
    elif llr <= lower:
        decision = "REJECT"
    else:
        decision = "CONTINUE"
    return {"decision": decision, "llr": llr, "upper": upper, "lower": lower,
            "n": n, "wins": k, "p0": p0, "p1": p1, "alpha": alpha, "beta": beta}
