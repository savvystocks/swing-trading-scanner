import json
import os
import glob
from datetime import datetime, timedelta


DATA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))


def _safe_load(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def list_scan_dates():
    pattern = os.path.join(DATA_ROOT, "results", "catalyst_*.json")
    out = []
    for p in glob.glob(pattern):
        base = os.path.basename(p)
        if base.startswith("catalyst_") and base.endswith(".json"):
            dstr = base[len("catalyst_"):-len(".json")]
            if len(dstr) == 10 and dstr[4] == "-" and dstr[7] == "-":
                out.append(dstr)
    return sorted(out)


def load_scan(date=None):
    if date is None:
        dates = list_scan_dates()
        if not dates:
            return None
        date = dates[-1]
    path = os.path.join(DATA_ROOT, "results", f"catalyst_{date}.json")
    scan = _safe_load(path)
    if scan is None:
        return None
    scan["_loaded_from"] = path
    scan["_scan_date_resolved"] = date
    _backfill_overall_scores(scan)
    return scan


def _backfill_overall_scores(scan):
    try:
        from src.catalyst.overall_score import compute_overall_score
    except ImportError:
        return
    aa = scan.get("aa_results") or {}
    for tier in ("A++", "A+", "A"):
        for p in aa.get(tier, []) or []:
            if not p.get("_overall_score"):
                try:
                    p["_overall_score"] = compute_overall_score(p)
                except Exception:
                    pass


def latest_scan_date():
    dates = list_scan_dates()
    return dates[-1] if dates else None


def all_picks(scan, sort_by="overall"):
    if not scan:
        return []
    aa = scan.get("aa_results") or {}
    out = []
    for tier in ("A++", "A+", "A"):
        for p in aa.get(tier, []) or []:
            out.append(p)

    tier_rank = {"A++": 3, "A+": 2, "A": 1}

    def _overall(p):
        v = (p.get("_overall_score") or {}).get("score")
        try:
            return float(v) if v is not None else -1
        except (TypeError, ValueError):
            return -1

    def _stacked(p):
        v = p.get("_stacked_score") or p.get("score") or 0
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0

    if sort_by == "tier":
        out.sort(key=lambda p: (-tier_rank.get(p.get("_aa_tier"), 0), -_overall(p), -_stacked(p)))
    elif sort_by == "stacked":
        out.sort(key=lambda p: (-_stacked(p), -_overall(p)))
    else:
        out.sort(key=lambda p: (-_overall(p), -tier_rank.get(p.get("_aa_tier"), 0), -_stacked(p)))
    return out


def picks_by_tier(scan, tier):
    if not scan:
        return []
    return (scan.get("aa_results") or {}).get(tier, []) or []


def find_pick(scan, ticker):
    if not scan or not ticker:
        return None
    t = ticker.upper()
    for p in all_picks(scan):
        if (p.get("ticker") or "").upper() == t:
            return p
    aa = scan.get("aa_results") or {}
    for p in aa.get("REJECT", []) or []:
        if (p.get("ticker") or "").upper() == t:
            return p
    return None


def open_positions():
    return _safe_load(os.path.join(DATA_ROOT, "paper_trades", "positions.json")) or []


def closed_positions():
    return _safe_load(os.path.join(DATA_ROOT, "paper_trades", "closed.json")) or []


def live_open_positions():
    return _safe_load(os.path.join(DATA_ROOT, "live_trades", "positions.json")) or []


def live_closed_positions():
    return _safe_load(os.path.join(DATA_ROOT, "live_trades", "closed.json")) or []


def catalyst_performance():
    return _safe_load(os.path.join(DATA_ROOT, "catalyst", "catalyst_performance.json")) or {}


def predictions_for_date(date):
    return _safe_load(os.path.join(DATA_ROOT, "catalyst", "predictions", f"{date}.json"))


def list_prediction_dates():
    pattern = os.path.join(DATA_ROOT, "catalyst", "predictions", "*.json")
    out = []
    for p in glob.glob(pattern):
        base = os.path.basename(p)[:-len(".json")]
        if len(base) == 10:
            out.append(base)
    return sorted(out)


def all_predictions():
    out = []
    for date in list_prediction_dates():
        d = predictions_for_date(date)
        if not d:
            continue
        rows = d.get("predictions") or []
        for r in rows:
            r["_pred_date"] = date
            out.append(r)
    return out


def aggregate_win_rate_stats(window_days=30):
    closed = closed_positions() + live_closed_positions()
    if not closed:
        return {"n": 0, "win_rate_pct": None, "total_pnl_usd": 0, "avg_pnl_pct": None}
    cutoff = None
    if window_days:
        cutoff = (datetime.utcnow() - timedelta(days=window_days)).isoformat()
    rows = []
    for c in closed:
        closed_at = c.get("closed_at") or c.get("last_marked_at")
        if cutoff and closed_at and closed_at < cutoff:
            continue
        rows.append(c)
    if not rows:
        return {"n": 0, "win_rate_pct": None, "total_pnl_usd": 0, "avg_pnl_pct": None}
    wins = [r for r in rows if (r.get("total_realized_pnl_usd") or r.get("current_pnl_usd") or 0) > 0]
    pnls = [(r.get("total_realized_pnl_usd") or r.get("current_pnl_usd") or 0) for r in rows]
    pcts = [r.get("realized_pnl_pct") or r.get("current_pnl_pct") for r in rows if r.get("realized_pnl_pct") is not None or r.get("current_pnl_pct") is not None]
    return {
        "n": len(rows),
        "win_rate_pct": round(len(wins) / len(rows) * 100, 1),
        "total_pnl_usd": round(sum(pnls), 2),
        "avg_pnl_pct": round(sum(pcts) / len(pcts), 1) if pcts else None,
    }


def win_rate_by_catalyst(window_days=90):
    closed = closed_positions() + live_closed_positions()
    if not closed:
        return {}
    cutoff = None
    if window_days:
        cutoff = (datetime.utcnow() - timedelta(days=window_days)).isoformat()
    by_cat = {}
    for c in closed:
        closed_at = c.get("closed_at") or c.get("last_marked_at")
        if cutoff and closed_at and closed_at < cutoff:
            continue
        snap = c.get("hunter_snapshot") or {}
        cats = snap.get("catalysts") or []
        won = (c.get("total_realized_pnl_usd") or c.get("current_pnl_usd") or 0) > 0
        for cat in cats:
            k = cat.get("key") if isinstance(cat, dict) else str(cat)
            if not k:
                continue
            d = by_cat.setdefault(k, {"n": 0, "wins": 0})
            d["n"] += 1
            if won:
                d["wins"] += 1
    for k, v in by_cat.items():
        v["win_rate_pct"] = round(v["wins"] / v["n"] * 100, 1) if v["n"] else None
    return by_cat


def macro_snapshot(scan=None):
    if scan is None:
        scan = load_scan()
    if not scan:
        return {}
    return scan.get("macro") or {}


def exit_alerts_for_open():
    opens = open_positions() + live_open_positions()
    alerts = []
    for p in opens:
        pnl_pct = p.get("current_pnl_pct")
        if pnl_pct is None:
            continue
        try:
            pnl_pct = float(pnl_pct)
        except (TypeError, ValueError):
            continue
        days_held = None
        try:
            opened = p.get("opened_at")
            if opened:
                opened_dt = datetime.fromisoformat(opened.replace("Z", "+00:00"))
                days_held = (datetime.utcnow() - opened_dt.replace(tzinfo=None)).days
        except Exception:
            pass
        signal = None
        if pnl_pct <= -50:
            signal = "STOP_OUT_HARD"
        elif pnl_pct <= -30:
            signal = "STOP_WARNING"
        elif pnl_pct >= 100:
            signal = "TRIM_BIG_WIN"
        elif pnl_pct >= 50:
            signal = "TRIM_WIN"
        elif days_held is not None and days_held >= 14:
            signal = "TIME_DECAY_RISK"
        if signal:
            contract = p.get("contract")
            if isinstance(contract, dict):
                strike = contract.get("strike")
                exp = contract.get("expiration")
                right = (contract.get("right") or "call")[0].upper()
                contract_str = f"${strike}{right} {exp}" if strike and exp else str(contract)
            else:
                contract_str = str(contract or "")
            alerts.append({
                "ticker": p.get("ticker"),
                "contract": contract_str,
                "pnl_pct": round(pnl_pct, 1),
                "pnl_usd": p.get("current_pnl_usd"),
                "days_held": days_held,
                "signal": signal,
            })
    return alerts
