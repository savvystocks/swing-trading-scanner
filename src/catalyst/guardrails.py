"""Account guardrails for aggressive 25% position sizing.

Savvas runs a £4k Robinhood account targeting £20k in 6 months (5x in 26
weeks). At 25% position sizing with -40% option stops, a 3-trade losing
streak burns ~30% of account. The system MUST circuit-break to force a
thesis review before that compounds.

Reads from data/paper_trades/conviction_journal.jsonl to compute:
- Current account value (from logged trade outcomes)
- Peak account value (high-water mark)
- Current drawdown % from peak
- Recent consecutive losses
- Goal pace (on track for £20k by deadline?)

Outputs:
- guardrail_state dict with mode (NORMAL / REVIEW_MODE), reason, triggers
- Read by scanner and email render to prefix subject + show banner

Config via env (with sensible defaults baked from Savvas's stated prefs):
- ACCOUNT_SIZE_GBP        (default 4000)
- POSITION_SIZE_PCT       (default 25)
- MAX_CONCURRENT          (default 2)
- TOTAL_EXPOSURE_CAP_PCT  (default 50)
- MAX_DRAWDOWN_PCT        (default 20)
- MAX_LOSS_STREAK         (default 3)
- GOAL_TARGET_GBP         (default 20000)
- GOAL_DEADLINE_ISO       (default 2026-11-29)
- GBP_USD_RATE            (default 1.26)
"""

import os
import json
import pathlib
from datetime import datetime, timedelta


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
JOURNAL_PATH = PROJECT_ROOT / "data" / "paper_trades" / "conviction_journal.jsonl"
ACCOUNT_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trades" / "account_ledger.jsonl"
LIVE_POSITIONS_PATH = PROJECT_ROOT / "data" / "paper_trades" / "live_positions.json"


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


def _env_int(key, default):
    return int(_env_float(key, default))


def _env_str(key, default):
    raw = os.environ.get(key, "")
    if isinstance(raw, str):
        raw = raw.strip()
    return raw or default


def get_config():
    return {
        "account_size_gbp": _env_float("ACCOUNT_SIZE_GBP", 4000),
        "gbp_usd_rate": _env_float("GBP_USD_RATE", 1.26),
        "position_size_pct": _env_float("POSITION_SIZE_PCT", 25),
        "max_concurrent": _env_int("MAX_CONCURRENT", 2),
        "total_exposure_cap_pct": _env_float("TOTAL_EXPOSURE_CAP_PCT", 50),
        "max_drawdown_pct": _env_float("MAX_DRAWDOWN_PCT", 20),
        "max_loss_streak": _env_int("MAX_LOSS_STREAK", 3),
        "goal_target_gbp": _env_float("GOAL_TARGET_GBP", 20000),
        "goal_deadline_iso": _env_str("GOAL_DEADLINE_ISO", "2026-11-29"),
    }


def _load_journal():
    if not JOURNAL_PATH.exists():
        return []
    rows = []
    with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _load_ledger():
    if not ACCOUNT_LEDGER_PATH.exists():
        return []
    rows = []
    with open(ACCOUNT_LEDGER_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def append_ledger(entry):
    ACCOUNT_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ACCOUNT_LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def _closed_trades_chronological():
    rows = _load_journal()
    closed = []
    for r in rows:
        o = r.get("outcomes") or {}
        if r.get("status") != "CLOSED" and not o.get("measured_at"):
            continue
        best = o.get("best_pct")
        worst = o.get("worst_pct")
        ret5 = o.get("ret_5d_pct")
        ret10 = o.get("ret_10d_pct")
        is_put = r.get("side") == "PUT"
        target_metric = ret10 if ret10 is not None else (ret5 if ret5 is not None else best)
        if target_metric is None:
            continue
        if is_put:
            target_metric = -target_metric
        closed.append({
            "scan_date": r.get("scan_date"),
            "ticker": r.get("ticker"),
            "side": r.get("side"),
            "pct": target_metric,
            "won": target_metric > 0,
        })
    closed.sort(key=lambda x: x.get("scan_date") or "")
    return closed


def get_current_account_value(config):
    """Account value is config.account_size_gbp + sum of logged real trade P&L.

    We use a separate ledger (account_ledger.jsonl) so it stays accurate when
    user manually adjusts (deposits/withdrawals). When the ledger is empty we
    derive a paper estimate from the conviction journal's closed trades."""
    ledger = _load_ledger()
    if ledger:
        last = ledger[-1]
        return float(last.get("account_value_gbp", config["account_size_gbp"]))

    base = config["account_size_gbp"]
    closed = _closed_trades_chronological()
    if not closed:
        return base
    estimated = base
    pos_size_pct = config["position_size_pct"] / 100.0
    for t in closed:
        position_value = estimated * pos_size_pct
        pnl_gbp = position_value * (t["pct"] / 100.0)
        estimated += pnl_gbp
    return estimated


def get_peak_account_value(config):
    ledger = _load_ledger()
    if ledger:
        peaks = [float(r.get("account_value_gbp", 0)) for r in ledger]
        peaks.append(config["account_size_gbp"])
        return max(peaks) if peaks else config["account_size_gbp"]

    base = config["account_size_gbp"]
    closed = _closed_trades_chronological()
    if not closed:
        return base
    running = base
    peak = base
    pos_size_pct = config["position_size_pct"] / 100.0
    for t in closed:
        position_value = running * pos_size_pct
        pnl_gbp = position_value * (t["pct"] / 100.0)
        running += pnl_gbp
        if running > peak:
            peak = running
    return peak


def get_consecutive_losses():
    closed = _closed_trades_chronological()
    streak = 0
    for t in reversed(closed):
        if not t["won"]:
            streak += 1
        else:
            break
    return streak


def get_live_positions():
    """Read real Robinhood positions Savvas has logged manually.

    Format: list of {"ticker": "LWAY", "side": "CALL", "strike": 27.50,
    "expiration": "2026-06-20", "entry_price": 0.95, "contracts": 2,
    "cost_gbp": 150, "opened_at": "2026-05-28", "status": "OPEN"}
    """
    if not LIVE_POSITIONS_PATH.exists():
        return []
    try:
        with open(LIVE_POSITIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [p for p in (data if isinstance(data, list) else []) if p.get("status") == "OPEN"]
    except Exception:
        return []


def get_open_positions_count():
    return len(get_live_positions())


def compute_pace(config, current_value):
    try:
        deadline = datetime.strptime(config["goal_deadline_iso"], "%Y-%m-%d").date()
    except Exception:
        return None
    today = datetime.utcnow().date()
    days_left = max(1, (deadline - today).days)
    target = config["goal_target_gbp"]
    if current_value <= 0:
        return None
    required_weekly_growth_pct = ((target / current_value) ** (7.0 / days_left) - 1) * 100
    return {
        "current_gbp": round(current_value, 2),
        "target_gbp": target,
        "days_left": days_left,
        "weeks_left": round(days_left / 7.0, 1),
        "required_weekly_growth_pct": round(required_weekly_growth_pct, 2),
        "multiple_remaining": round(target / current_value, 2),
        "on_pace": required_weekly_growth_pct <= 7.0,
    }


def evaluate(config=None, verbose=False):
    if config is None:
        config = get_config()

    current = get_current_account_value(config)
    peak = get_peak_account_value(config)
    drawdown_pct = (peak - current) / peak * 100 if peak > 0 else 0.0
    loss_streak = get_consecutive_losses()
    open_positions = get_open_positions_count()
    pace = compute_pace(config, current)

    triggers = []
    if drawdown_pct >= config["max_drawdown_pct"]:
        triggers.append({
            "type": "DRAWDOWN",
            "severity": "HIGH",
            "message": f"Account drawdown {drawdown_pct:.1f}% from peak £{peak:.0f} (threshold {config['max_drawdown_pct']}%). Pause new entries, review thesis.",
        })
    if loss_streak >= config["max_loss_streak"]:
        triggers.append({
            "type": "LOSS_STREAK",
            "severity": "HIGH",
            "message": f"{loss_streak} consecutive losing trades (threshold {config['max_loss_streak']}). Pause, identify what changed.",
        })
    if open_positions >= config["max_concurrent"]:
        triggers.append({
            "type": "MAX_POSITIONS",
            "severity": "MED",
            "message": f"{open_positions} of {config['max_concurrent']} position slots in use. New picks flagged WAIT.",
        })

    mode = "REVIEW_MODE" if any(t["severity"] == "HIGH" for t in triggers) else "NORMAL"

    state = {
        "config": config,
        "current_account_gbp": round(current, 2),
        "peak_account_gbp": round(peak, 2),
        "drawdown_pct": round(drawdown_pct, 2),
        "loss_streak": loss_streak,
        "open_positions": open_positions,
        "max_positions": config["max_concurrent"],
        "pace": pace,
        "triggers": triggers,
        "mode": mode,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }

    if verbose:
        print(f"  guardrails: mode={mode} account=£{current:.0f} peak=£{peak:.0f} dd={drawdown_pct:.1f}% streak={loss_streak} open={open_positions}/{config['max_concurrent']}")
        if pace:
            print(f"  guardrails pace: £{current:.0f} -> £{config['goal_target_gbp']:.0f} in {pace['weeks_left']}w, need {pace['required_weekly_growth_pct']:.1f}%/wk, on pace: {pace['on_pace']}")
        for t in triggers:
            print(f"    [{t['severity']}] {t['type']}: {t['message']}")

    return state


def position_size_for_pick(state, contract_mid_usd, confluence=None):
    """Return (contracts, gbp_cost, hit_cap_reason or None) for a new pick.

    confluence param: dict with 'recommended_size_pct' and 'sizing_tier'.
    When provided, overrides the default 25% with confluence-tiered sizing:
      ELITE (5+ signals, 3+ categories) -> 33%
      STRONG (4+ signals, 2+ categories) -> 25%
      MODERATE (3+ signals) -> 20%
      WEAK or NONE -> 0% (don't trade)
    """
    config = state["config"]
    fx = config["gbp_usd_rate"]
    account_gbp = state["current_account_gbp"]

    if confluence and confluence.get("recommended_size_pct") is not None:
        size_pct = confluence["recommended_size_pct"]
        tier = confluence.get("sizing_tier", "UNKNOWN")
    else:
        size_pct = config["position_size_pct"]
        tier = "DEFAULT"

    try:
        from src.catalyst import probe_ladder as _ladder
        _lad = _ladder.evaluate()
        if _lad["size_pct"] < size_pct:
            tier = f"{tier}/{_lad['rung']}"
            size_pct = _lad["size_pct"]
    except Exception:
        pass

    if size_pct <= 0:
        return 0, 0.0, f"confluence tier {tier} = below take threshold (need 3+ signals)"

    pos_gbp_budget = account_gbp * (size_pct / 100.0)

    open_n = state["open_positions"]
    max_concurrent = config["max_concurrent"]
    if tier == "ELITE":
        max_concurrent = max(max_concurrent, 3)
    if open_n >= max_concurrent:
        return 0, 0.0, f"max {max_concurrent} positions already open"

    if contract_mid_usd <= 0:
        return 0, 0.0, "no live contract price"

    contract_cost_gbp = (contract_mid_usd * 100) / fx
    if contract_cost_gbp > pos_gbp_budget * 1.4:
        return 0, 0.0, f"single contract £{contract_cost_gbp:.0f} > 140% of {tier} budget £{pos_gbp_budget:.0f}"

    contracts = max(1, int(round(pos_gbp_budget / contract_cost_gbp)))
    total_cost_gbp = contracts * contract_cost_gbp

    if total_cost_gbp > account_gbp * (config["total_exposure_cap_pct"] / 100.0):
        contracts = max(1, int((account_gbp * (config["total_exposure_cap_pct"] / 100.0)) / contract_cost_gbp))
        total_cost_gbp = contracts * contract_cost_gbp

    return contracts, total_cost_gbp, None
