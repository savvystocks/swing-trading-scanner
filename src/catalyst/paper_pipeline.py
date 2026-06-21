import os
import json
import pathlib
from datetime import datetime, date


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
PAPER_DIR = PROJECT_ROOT / "data" / "paper_trades"
OPEN_PATH = PAPER_DIR / "paper_probe_positions.json"
CLOSED_PATH = PAPER_DIR / "closed.json"
AMBUSH_LOG_DIR = PROJECT_ROOT / "data" / "ambush_logs"


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
        "hard_stop_pct": _env_float("PAPER_HARD_STOP_PCT", -50.0),
        "tier1_pct": _env_float("PAPER_TIER1_PCT", 100.0),
        "tier2_pct": _env_float("PAPER_TIER2_PCT", 200.0),
        "tier3_pct": _env_float("PAPER_TIER3_PCT", 300.0),
        "runner_trail_pct": _env_float("PAPER_RUNNER_TRAIL_PCT", 20.0),
        "min_dte": _env_float("PAPER_MIN_DTE", 7),
        "max_hold_days": _env_float("PAPER_MAX_HOLD_DAYS", 21),
        "credit_take_pct": _env_float("PAPER_CREDIT_TAKE_PCT", 50.0),
        "credit_dte_exit": _env_float("PAPER_CREDIT_DTE_EXIT", 21),
    }


def _load(path):
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _today_iso():
    return datetime.utcnow().date().isoformat()


def _days_between(start_iso, end_iso):
    try:
        a = datetime.strptime(str(start_iso)[:10], "%Y-%m-%d").date()
        b = datetime.strptime(str(end_iso)[:10], "%Y-%m-%d").date()
        return (b - a).days
    except (ValueError, TypeError):
        return 0


def log_alert(alert):
    if alert.get("defined_risk") is False:
        return _load(OPEN_PATH), f"REFUSED {alert.get('ticker')}: structure is not defined-risk"
    AMBUSH_LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.utcnow().isoformat(timespec='seconds')}Z ALERT {alert.get('ticker')} " \
           f"{alert.get('side')} {alert.get('structure')} regime={alert.get('regime')} " \
           f"entry={alert.get('entry_premium')} size={alert.get('size_pct')}%\n"
    with open(AMBUSH_LOG_DIR / f"paper_{_today_iso()}.log", "a", encoding="utf-8") as f:
        f.write(line)

    family = alert.get("family") or ("credit" if (alert.get("net_credit") or 0) > 0 else "debit")
    entry_premium = alert.get("entry_premium")
    if entry_premium is None:
        entry_premium = alert.get("net_credit") if family == "credit" else alert.get("net_debit")
    opened_at = alert.get("opened_at") or _today_iso()
    exp = str(alert.get("expiration") or "")[:10]
    pos = {
        "id": f"{alert.get('ticker')}_{opened_at}_{alert.get('structure')}_{exp.replace('-', '')}",
        "ticker": alert.get("ticker"),
        "side": alert.get("side"),
        "structure": alert.get("structure"),
        "family": family,
        "direction": alert.get("direction"),
        "regime_at_open": alert.get("regime"),
        "gates_snapshot": alert.get("gates"),
        "legs": alert.get("legs"),
        "contract": alert.get("contract"),
        "expiration": exp,
        "dte_at_open": alert.get("dte"),
        "entry_premium": entry_premium,
        "opened_at_spot": alert.get("entry_spot"),
        "size_pct": alert.get("size_pct"),
        "size_contracts": alert.get("size_contracts"),
        "max_loss_per_spread": alert.get("max_loss_per_spread"),
        "opened_at": opened_at,
        "status": "OPEN",
        "peak_pnl_pct": 0.0,
        "trough_pnl_pct": 0.0,
        "last_pnl_pct": 0.0,
        "last_marked_at": None,
        "metadata": alert.get("metadata"),
        "trims": [],
    }
    positions = _load(OPEN_PATH)
    if any(p.get("id") == pos["id"] for p in positions):
        return positions, f"skip duplicate {pos['id']}"
    positions.append(pos)
    _save(OPEN_PATH, positions)
    return positions, f"logged paper {pos['id']}"


def mark(pos, current_premium):
    entry = pos.get("entry_premium")
    if not entry or current_premium is None:
        return pos
    if pos.get("family") == "credit":
        pnl_pct = (entry - current_premium) / entry * 100.0
    else:
        pnl_pct = (current_premium - entry) / entry * 100.0
    pos["last_pnl_pct"] = round(pnl_pct, 2)
    pos["last_marked_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    pos["peak_pnl_pct"] = round(max(pos.get("peak_pnl_pct", 0.0), pnl_pct), 2)
    pos["trough_pnl_pct"] = round(min(pos.get("trough_pnl_pct", 0.0), pnl_pct), 2)
    return pos


def decide_exit(pos, now_iso=None, config=None):
    if config is None:
        config = get_config()
    now_iso = now_iso or _today_iso()
    pnl = pos.get("last_pnl_pct", 0.0)
    peak = pos.get("peak_pnl_pct", 0.0)
    trims_done = len(pos.get("trims", []))
    dte = _days_between(now_iso, pos.get("expiration")) if pos.get("expiration") else 999
    days_held = _days_between(pos.get("opened_at"), now_iso)

    if pos.get("family") == "credit":
        if pnl >= config["credit_take_pct"]:
            return {"action": "CLOSE", "result": "WIN", "reason": "PROFIT_50_CREDIT", "fraction": 1.0}
        if dte <= config["credit_dte_exit"]:
            return {"action": "CLOSE", "result": "WIN" if pnl > 0 else "LOSS", "reason": "TIME_21DTE", "fraction": 1.0}
        return {"action": "HOLD", "reason": "credit managed at 50% credit / 21 DTE (defined risk caps loss)"}

    if pnl <= config["hard_stop_pct"]:
        return {"action": "CLOSE", "result": "LOSS", "reason": "HARD_STOP", "fraction": 1.0}
    if trims_done < 1 and pnl >= config["tier1_pct"]:
        return {"action": "TRIM", "tier": 1, "reason": "TIER1_+100%_remove_risk", "fraction": 1.0 / 3.0}
    if trims_done < 2 and pnl >= config["tier2_pct"]:
        return {"action": "TRIM", "tier": 2, "reason": "TIER2_+200%_bank_growth", "fraction": 1.0 / 3.0}
    if trims_done >= 2:
        trail_floor = peak * (1.0 - config["runner_trail_pct"] / 100.0)
        if pnl <= trail_floor and peak > 0:
            return {"action": "CLOSE", "result": "WIN" if pnl > 0 else "LOSS",
                    "reason": f"RUNNER_TRAIL_20%_from_peak_{peak:.0f}%", "fraction": 1.0}
    if dte <= config["min_dte"]:
        return {"action": "CLOSE", "result": "WIN" if pnl > 0 else "LOSS", "reason": "MIN_DTE_PIN_SAFETY", "fraction": 1.0}
    if trims_done < 2 and days_held >= config["max_hold_days"]:
        return {"action": "CLOSE", "result": "WIN" if pnl > 0 else "LOSS", "reason": "STAGNANT_TIME_STOP", "fraction": 1.0}
    return {"action": "HOLD", "reason": "within scale-out bands"}


def apply_trim(pos, decision):
    pos.setdefault("trims", []).append({
        "tier": decision.get("tier"),
        "fraction": round(decision["fraction"], 4),
        "pnl_pct": pos.get("last_pnl_pct"),
        "at": _today_iso(),
        "reason": decision.get("reason"),
    })
    return pos


def close_position(pos, reason, result=None, now_iso=None):
    now_iso = now_iso or _today_iso()
    final_pnl = pos.get("last_pnl_pct", 0.0)
    trims = pos.get("trims", [])
    trimmed_fraction = sum(t.get("fraction", 0.0) for t in trims)
    remaining = max(0.0, 1.0 - trimmed_fraction)
    blended = remaining * final_pnl + sum(t.get("fraction", 0.0) * (t.get("pnl_pct") or 0.0) for t in trims)

    record = dict(pos)
    record.update({
        "status": "CLOSED",
        "closed_at": now_iso,
        "days_held": _days_between(pos.get("opened_at"), now_iso),
        "exit_reason": reason,
        "result": result or ("WIN" if blended > 0 else "LOSS"),
        "end_pct": round(final_pnl, 2),
        "peak_pct": round(pos.get("peak_pnl_pct", 0.0), 2),
        "trough_pct": round(pos.get("trough_pnl_pct", 0.0), 2),
        "realized_pnl_pct": round(blended, 2),
        "is_paper": True,
    })

    closed = _load(CLOSED_PATH)
    closed.append(record)
    _save(CLOSED_PATH, closed)

    positions = [p for p in _load(OPEN_PATH) if p.get("id") != pos.get("id")]
    _save(OPEN_PATH, positions)
    return record


def _default_price_fn(pos):
    try:
        from src.alpaca_options import get_live_price
    except Exception:
        return None
    legs = pos.get("legs")
    if legs:
        net = 0.0
        for lg in legs:
            sym = lg.get("occ_symbol")
            mid = get_live_price(sym) if sym else None
            if mid is None:
                return None
            net += lg.get("qty", 1) * mid
        return abs(net)
    contract = pos.get("contract") or {}
    sym = contract.get("occ_symbol")
    return get_live_price(sym) if sym else None


def run_mark_cycle(price_fn=None, now_iso=None, config=None):
    if config is None:
        config = get_config()
    if price_fn is None:
        price_fn = _default_price_fn
    now_iso = now_iso or _today_iso()

    positions = _load(OPEN_PATH)
    actions = []
    survivors = []
    for pos in positions:
        current = price_fn(pos)
        if current is None:
            survivors.append(pos)
            actions.append({"id": pos.get("id"), "action": "SKIP", "reason": "no mark"})
            continue
        pos = mark(pos, current)
        decision = decide_exit(pos, now_iso, config)
        if decision["action"] == "TRIM":
            pos = apply_trim(pos, decision)
            survivors.append(pos)
            actions.append({"id": pos.get("id"), "action": "TRIM", "tier": decision.get("tier"),
                            "pnl_pct": pos.get("last_pnl_pct")})
        elif decision["action"] == "CLOSE":
            rec = close_position(pos, decision["reason"], decision.get("result"), now_iso)
            actions.append({"id": pos.get("id"), "action": "CLOSE", "reason": decision["reason"],
                            "realized_pnl_pct": rec["realized_pnl_pct"]})
        else:
            survivors.append(pos)
            actions.append({"id": pos.get("id"), "action": "HOLD", "pnl_pct": pos.get("last_pnl_pct")})

    _save(OPEN_PATH, survivors)
    return {"marked": len(positions), "open_after": len(survivors), "actions": actions, "at": now_iso}


def digest():
    from src.catalyst import leak_lambda, probe_ladder, regime_compass
    leak = leak_lambda.evaluate()
    ladder = probe_ladder.evaluate()
    try:
        regime = regime_compass.evaluate()
    except Exception as e:
        regime = {"regime": "?", "bias": "?", "reason": f"regime unavailable: {type(e).__name__}"}
    open_n = len(_load(OPEN_PATH))
    text = (f"V8.5 digest {_today_iso()}\n"
            f"Regime {regime.get('regime')} ({regime.get('bias')})\n"
            f"Ladder {ladder['rung']} size {ladder['size_pct']}% active £{ladder['ratchet']['active_tranche_gbp']} "
            f"protected £{ladder['ratchet']['protected_base_gbp']}\n"
            f"Edge n={leak['n_closed']} exp={leak['expectancy_pct']}% win={leak['win_rate']} "
            f"mode={leak['mode']}\n"
            f"Open paper positions: {open_n}")
    return {"leak": leak, "ladder": ladder, "regime": regime, "open_positions": open_n, "text": text}
