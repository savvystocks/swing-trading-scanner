import os
import json
import pathlib
from datetime import datetime


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
CONVICTION_LOG_PATH = PROJECT_ROOT / "data" / "conviction_log.json"
LIVE_CLOSED_PATH = PROJECT_ROOT / "data" / "live_trades" / "closed.json"
PAPER_CLOSED_PATH = PROJECT_ROOT / "data" / "paper_trades" / "closed.json"


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


def get_config():
    return {
        "probe_trades": _env_int("PROBE_TRADES", 5),
        "probe_size_pct": _env_float("PROBE_SIZE_PCT", 1.5),
        "stop_model_pct": _env_float("STOP_MODEL_PCT", -50.0),
        "slip_tolerance_pts": _env_float("SLIP_TOLERANCE_PTS", 5.0),
        "slip_tail_pct": _env_float("SLIP_TAIL_PCT", -58.0),
        "slip_tail_share": _env_float("SLIP_TAIL_SHARE", 0.25),
        "target_r": _env_float("TARGET_R", 1.5),
        "fee_drag_pct_est": _env_float("FEE_DRAG_PCT_EST", 3.0),
    }


def _load_list(path):
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _first(d, *keys):
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


def _normalize():
    records = []

    for r in _load_list(CONVICTION_LOG_PATH):
        if not isinstance(r, dict):
            continue
        o = r.get("outcome")
        if not isinstance(o, dict):
            continue
        ret = _first(o, "pct_return", "realized_pct")
        if ret is None:
            continue
        reason = (o.get("exit_reason") or "").upper()
        records.append({
            "ticker": r.get("ticker"),
            "side": r.get("side"),
            "return_pct": float(ret),
            "end_pct": o.get("end_pct"),
            "trough_pct": o.get("trough_pct"),
            "exit_reason": reason,
            "is_stop": "STOP" in reason,
            "days_held": o.get("days_held"),
            "real": False,
            "source": "conviction_log",
        })

    for path, src in ((LIVE_CLOSED_PATH, "live"), (PAPER_CLOSED_PATH, "paper")):
        for r in _load_list(path):
            if not isinstance(r, dict):
                continue
            ret = _first(r, "realized_pnl_pct", "return_pct", "realized_pct", "pct_return")
            if ret is None:
                continue
            reason = (r.get("exit_reason") or "").upper()
            records.append({
                "ticker": r.get("ticker"),
                "side": (r.get("side") or (r.get("contract") or {}).get("right") or "").upper() or None,
                "return_pct": float(ret),
                "end_pct": r.get("end_pct"),
                "trough_pct": r.get("trough_pct"),
                "exit_reason": reason,
                "is_stop": "STOP" in reason,
                "days_held": _first(r, "hold_trading_days", "hold_calendar_days", "days_held"),
                "real": True,
                "source": src,
            })

    return records


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def evaluate(config=None, verbose=False):
    if config is None:
        config = get_config()

    records = _normalize()
    rets = [r["return_pct"] for r in records if r["return_pct"] is not None]
    n = len(rets)
    n_real = sum(1 for r in records if r["real"] and r["return_pct"] is not None)

    expectancy_pct = _mean(rets)
    wins = sum(1 for x in rets if x > 0)
    win_rate = wins / n if n else None
    breakeven_win = 1.0 / (1.0 + config["target_r"])

    stop_fills = []
    for r in records:
        if not r["is_stop"]:
            continue
        v = _first(r, "end_pct", "trough_pct")
        if v is not None:
            stop_fills.append(float(v))
    mean_stop_fill = _mean(stop_fills)
    tail = [v for v in stop_fills if v <= config["slip_tail_pct"]]
    tail_share = (len(tail) / len(stop_fills)) if stop_fills else 0.0
    slippage_flag = bool(stop_fills) and (
        (mean_stop_fill is not None and mean_stop_fill < config["stop_model_pct"] - config["slip_tolerance_pts"])
        or tail_share > config["slip_tail_share"]
    )

    below_breakeven = (expectancy_pct is not None and expectancy_pct < 0) or \
                      (win_rate is not None and win_rate < breakeven_win)
    fee_drag_flag = (expectancy_pct is not None and expectancy_pct >= 0
                     and expectancy_pct - config["fee_drag_pct_est"] < 0)

    probe_mode = n == 0 or n < config["probe_trades"]
    locked = False
    leak_lambda = 1.0

    if probe_mode:
        mode = "PROBE"
        leak_lambda = 0.0
        reason = f"probe phase ({n}/{config['probe_trades']} probes resolved) - capped at {config['probe_size_pct']}%"
    elif slippage_flag:
        mode, locked, leak_lambda = "LOCKED", True, 0.0
        reason = f"slippage leak: stops mark {mean_stop_fill:.0f}% vs model {config['stop_model_pct']:.0f}%, " \
                 f"{tail_share*100:.0f}% past {config['slip_tail_pct']:.0f}% - freeze to probe size"
    elif below_breakeven:
        mode, locked, leak_lambda = "LOCKED", True, 0.0
        reason = f"expectancy {expectancy_pct:.1f}%/trade, win rate {win_rate*100:.0f}% below breakeven " \
                 f"{breakeven_win*100:.0f}% - freeze to probe size"
    else:
        mode = "NORMAL"
        leak_lambda = 1.0
        reason = f"expectancy {expectancy_pct:.1f}%/trade, win rate {win_rate*100:.0f}% above breakeven " \
                 f"{breakeven_win*100:.0f}% - no leak (probe_ladder owns sizing)"

    triggers = []
    if slippage_flag:
        triggers.append({"type": "SLIPPAGE", "severity": "HIGH", "message": reason})
    if below_breakeven and not probe_mode:
        triggers.append({"type": "EXPECTANCY", "severity": "HIGH", "message": reason})
    if fee_drag_flag:
        triggers.append({"type": "FEE_DRAG", "severity": "MED",
                         "message": f"fee/slippage drag ~{config['fee_drag_pct_est']:.0f}% would erase a "
                                    f"{expectancy_pct:.1f}% gross edge"})

    state = {
        "mode": mode,
        "leak_lambda": leak_lambda,
        "probe_mode": probe_mode,
        "locked": locked,
        "probe_size_pct": config["probe_size_pct"],
        "n_closed": n,
        "n_real": n_real,
        "expectancy_pct": round(expectancy_pct, 2) if expectancy_pct is not None else None,
        "win_rate": round(win_rate, 3) if win_rate is not None else None,
        "breakeven_win": round(breakeven_win, 3),
        "mean_stop_fill_pct": round(mean_stop_fill, 1) if mean_stop_fill is not None else None,
        "stop_tail_share": round(tail_share, 3),
        "n_stops": len(stop_fills),
        "slippage_flag": slippage_flag,
        "below_breakeven": below_breakeven,
        "fee_drag_flag": fee_drag_flag,
        "reason": reason,
        "triggers": triggers,
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }

    if verbose:
        print(f"  leak_lambda: mode={mode} lambda={leak_lambda} n={n}(real {n_real}) "
              f"exp={state['expectancy_pct']}% win={state['win_rate']} be={state['breakeven_win']} "
              f"stops={len(stop_fills)} mean_fill={state['mean_stop_fill_pct']}% slip={slippage_flag}")
        print(f"  leak_lambda: {reason}")

    return state


def apply_to_size_pct(size_pct, state=None):
    if state is None:
        state = evaluate()
    if state.get("probe_mode") or state.get("locked"):
        return state.get("probe_size_pct", 1.5)
    lam = state.get("leak_lambda")
    if lam is None:
        return size_pct
    return round(size_pct * lam, 2)


def gate_size_pct(size_pct, tier=None, state=None):
    if state is None:
        state = evaluate()
    eff = apply_to_size_pct(size_pct, state)
    if eff < size_pct:
        tier = f"{tier or 'SIZE'}/{state['mode']}"
    return eff, tier


def current_lambda():
    return evaluate().get("leak_lambda")


if __name__ == "__main__":
    evaluate(verbose=True)
