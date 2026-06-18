import os
import math
from datetime import datetime

from src.catalyst import leak_lambda
from src.catalyst import guardrails


RUNGS = [
    {"name": "PROBE", "lambda": 0.0, "cap_pct": 1.5, "min_closed": 0, "pr_gate": 0.0, "r_floor": 0.0},
    {"name": "STAGE_2", "lambda": 0.25, "cap_pct": 8.0, "min_closed": 20, "pr_gate": 0.80, "r_floor": 1.5},
    {"name": "STAGE_3", "lambda": 0.40, "cap_pct": 15.0, "min_closed": 25, "pr_gate": 0.90, "r_floor": 1.5},
    {"name": "MAX", "lambda": 0.50, "cap_pct": 25.0, "min_closed": 30, "pr_gate": 0.95, "r_floor": 1.5},
]


def _env_float(key, default):
    raw = os.environ.get(key, "")
    if isinstance(raw, str):
        raw = raw.strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def get_config():
    return {
        "prior_a": _env_float("PROBE_PRIOR_A", 3.8),
        "prior_b": _env_float("PROBE_PRIOR_B", 6.2),
        "target_r": _env_float("TARGET_R", 1.5),
        "probe_size_pct": _env_float("PROBE_SIZE_PCT", 1.5),
        "account_base_gbp": _env_float("ACCOUNT_SIZE_GBP", 4000),
        "ratchet_step_gbp": _env_float("RATCHET_STEP_GBP", 4000),
        "protected_lock_frac": _env_float("PROTECTED_LOCK_FRAC", 0.5),
    }


def _betacf(a, b, x):
    fpmin = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 3e-12:
            break
    return h


def _betainc(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _f_kelly(p, r):
    if p is None or r <= 0:
        return 0.0
    return max(0.0, p - (1.0 - p) / r)


def _outcomes():
    records = leak_lambda._normalize()
    rets = [r["return_pct"] for r in records if r.get("return_pct") is not None]
    return rets


def _capital_ratchet(account_gbp, config):
    base = config["account_base_gbp"]
    step = config["ratchet_step_gbp"]
    frac = config["protected_lock_frac"]
    gain = account_gbp - base
    crossed = int(gain // step) if gain > 0 and step > 0 else 0
    protected = crossed * step * frac
    active = max(0.0, account_gbp - protected)
    return {
        "account_gbp": round(account_gbp, 2),
        "milestones_crossed": crossed,
        "protected_base_gbp": round(protected, 2),
        "active_tranche_gbp": round(active, 2),
    }


def evaluate(config=None, verbose=False):
    if config is None:
        config = get_config()

    rets = _outcomes()
    n = len(rets)
    wins = [x for x in rets if x > 0]
    losses = [abs(x) for x in rets if x <= 0]
    loss_mags = [abs(x) for x in rets if x < 0]
    n_win, n_loss = len(wins), len(losses)

    a = config["prior_a"] + n_win
    b = config["prior_b"] + n_loss
    posterior_mean = a / (a + b)
    r = config["target_r"]
    breakeven = 1.0 / (1.0 + r)
    pr_edge = 1.0 - _betainc(a, b, breakeven)
    realized_r = (sum(wins) / n_win) / (sum(loss_mags) / len(loss_mags)) if n_win and loss_mags else (
        99.0 if n_win and not loss_mags else 0.0)

    leak = leak_lambda.evaluate()
    rails = guardrails.evaluate()
    forced_probe = bool(leak.get("locked") or leak.get("probe_mode") or rails.get("mode") == "REVIEW_MODE")
    two_loss_streak = len(rets) >= 2 and rets[-1] <= 0 and rets[-2] <= 0

    chosen = RUNGS[0]
    if not forced_probe and not two_loss_streak:
        for rung in reversed(RUNGS):
            if rung["name"] == "PROBE":
                continue
            if n >= rung["min_closed"] and pr_edge >= rung["pr_gate"] and realized_r >= rung["r_floor"]:
                chosen = rung
                break

    ratchet = _capital_ratchet(rails.get("current_account_gbp", config["account_base_gbp"]), config)

    if chosen["name"] == "PROBE":
        size_pct = config["probe_size_pct"]
    else:
        raw = chosen["lambda"] * _f_kelly(posterior_mean, r) * pr_edge * 100.0
        size_pct = round(min(chosen["cap_pct"], raw), 2)
        size_pct = max(size_pct, config["probe_size_pct"])

    budget_gbp = round(ratchet["active_tranche_gbp"] * size_pct / 100.0, 2)

    blockers = []
    if leak.get("locked"):
        blockers.append(f"leak_lambda LOCKED: {leak.get('reason')}")
    if leak.get("probe_mode"):
        blockers.append(f"probe phase {leak.get('n_closed')}/{leak_lambda.get_config()['probe_trades']}")
    if rails.get("mode") == "REVIEW_MODE":
        blockers.append("guardrails REVIEW_MODE (drawdown/loss-streak)")
    if two_loss_streak:
        blockers.append("2 consecutive losses -> demote to probe")

    state = {
        "rung": chosen["name"],
        "lambda": chosen["lambda"],
        "size_pct": size_pct,
        "budget_gbp": budget_gbp,
        "n_closed": n,
        "wins": n_win,
        "losses": n_loss,
        "posterior_a": round(a, 2),
        "posterior_b": round(b, 2),
        "posterior_mean_p": round(posterior_mean, 4),
        "breakeven_p": round(breakeven, 4),
        "pr_edge_above_breakeven": round(pr_edge, 4),
        "realized_r": round(realized_r, 2),
        "f_kelly": round(_f_kelly(posterior_mean, r), 4),
        "ratchet": ratchet,
        "forced_probe": forced_probe,
        "blockers": blockers,
        "next_rung": _next_rung_requirement(chosen, n, pr_edge, realized_r),
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }

    if verbose:
        print(f"  probe_ladder: rung={chosen['name']} size={size_pct}% budget=£{budget_gbp} "
              f"active=£{ratchet['active_tranche_gbp']} protected=£{ratchet['protected_base_gbp']}")
        print(f"  probe_ladder: n={n}(W{n_win}/L{n_loss}) post_p={posterior_mean:.3f} "
              f"Pr(edge>BE)={pr_edge:.3f} realizedR={realized_r:.2f} f_kelly={state['f_kelly']}")
        for x in blockers:
            print(f"    blocker: {x}")

    return state


def _next_rung_requirement(current, n, pr_edge, realized_r):
    names = [x["name"] for x in RUNGS]
    idx = names.index(current["name"])
    if idx + 1 >= len(RUNGS):
        return None
    nxt = RUNGS[idx + 1]
    return {
        "name": nxt["name"],
        "needs_closed": nxt["min_closed"],
        "have_closed": n,
        "needs_pr_edge": nxt["pr_gate"],
        "have_pr_edge": round(pr_edge, 4),
        "needs_realized_r": nxt["r_floor"],
        "have_realized_r": round(realized_r, 2),
    }


def size_pct_for_alert(confluence_size_pct, state=None):
    if state is None:
        state = evaluate()
    return min(confluence_size_pct, state["size_pct"])


if __name__ == "__main__":
    evaluate(verbose=True)
