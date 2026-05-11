import os
import json
from collections import Counter
from datetime import datetime, timedelta


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POSITIONS_PATH = os.path.join(PROJECT_ROOT, "data", "paper_trades", "positions.json")
CLOSED_PATH = os.path.join(PROJECT_ROOT, "data", "paper_trades", "closed.json")
CATALYST_PAPER_PATH = os.path.join(PROJECT_ROOT, "data", "catalyst", "paper_trades.json")

_max_conc_raw = (os.environ.get("MAX_CONCURRENT_LOTTERY") or "").strip()
MAX_CONCURRENT = int(_max_conc_raw) if _max_conc_raw.isdigit() else 4


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else []


def get_open_positions():
    positions = _load_json(POSITIONS_PATH, [])
    if not isinstance(positions, list):
        return []
    return [p for p in positions if isinstance(p, dict) and p.get("status") == "OPEN"]


def get_position_summary():
    open_pos = get_open_positions()
    n_open = len(open_pos)
    n_free = max(0, MAX_CONCURRENT - n_open)
    sector_counter = Counter(p.get("sector") or "Unknown" for p in open_pos)
    total_at_risk = sum(p.get("cost_basis_usd", 0) for p in open_pos)
    total_marked = sum((p.get("current_mid", 0) or 0) * 100 * (p.get("size_contracts", 0) or 0)
                       for p in open_pos)
    open_pnl_usd = round(total_marked - total_at_risk, 2)
    return {
        "n_open": n_open,
        "n_free": n_free,
        "max_concurrent": MAX_CONCURRENT,
        "tickers": [p.get("ticker", "?").split(".")[0] for p in open_pos],
        "sector_breakdown": dict(sector_counter),
        "total_at_risk_usd": round(total_at_risk, 2),
        "open_pnl_usd": open_pnl_usd,
        "positions": [
            {
                "ticker": p.get("ticker", "?").split(".")[0],
                "sector": p.get("sector"),
                "opened_at": p.get("opened_at"),
                "strike": (p.get("contract") or {}).get("strike"),
                "expiration": (p.get("contract") or {}).get("expiration"),
                "dte_at_open": (p.get("contract") or {}).get("dte_at_open"),
                "cost_basis_usd": p.get("cost_basis_usd"),
                "current_pnl_pct": p.get("current_pnl_pct"),
                "current_pnl_usd": p.get("current_pnl_usd"),
            }
            for p in open_pos
        ],
    }


def check_sector_overlap(pick_sector, position_summary):
    if not pick_sector:
        return None
    sector_counts = position_summary.get("sector_breakdown", {}) or {}
    existing = sector_counts.get(pick_sector, 0)
    if existing >= 2:
        return f"{existing} open in {pick_sector} — diversification warning"
    if existing == 1:
        return f"1 open in {pick_sector} — would be 2nd"
    return None


def get_recent_paper_trade_stats(lookback_days=30):
    trades = _load_json(CATALYST_PAPER_PATH, [])
    if not isinstance(trades, list) or not trades:
        return None
    cutoff = (datetime.utcnow().date() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    recent = [t for t in trades if isinstance(t, dict) and (t.get("scan_date") or "") >= cutoff]
    if not recent:
        return None
    pnls = [t.get("pnl_pct", 0) or 0 for t in recent]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    return {
        "lookback_days": lookback_days,
        "n_trades": len(recent),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "win_rate_pct": round(len(wins) / len(recent) * 100, 1) if recent else 0,
        "avg_pnl_pct": round(sum(pnls) / len(pnls), 2) if pnls else 0,
        "best_pct": round(max(pnls), 2) if pnls else 0,
        "worst_pct": round(min(pnls), 2) if pnls else 0,
        "total_pnl_usd": round(sum(t.get("pnl_usd", 0) or 0 for t in recent), 2),
    }


def yesterdays_lottery_followup():
    closed = _load_json(CLOSED_PATH, [])
    if not isinstance(closed, list):
        return []
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.utcnow().date().strftime("%Y-%m-%d")
    relevant = [
        c for c in closed
        if isinstance(c, dict)
        and c.get("status") == "CLOSED"
        and (c.get("closed_at") or "")[:10] in (yesterday, today)
    ]
    out = []
    for c in relevant:
        contract = c.get("contract") or {}
        out.append({
            "ticker": c.get("ticker", "?").split(".")[0],
            "name": (c.get("name") or "")[:40],
            "strike": contract.get("strike"),
            "expiration": contract.get("expiration"),
            "opened_at": c.get("opened_at"),
            "closed_at": c.get("closed_at"),
            "exit_reason": c.get("exit_reason"),
            "days_held": c.get("days_held"),
            "realized_pnl_pct": c.get("realized_pnl_pct"),
            "realized_pnl_usd": c.get("total_realized_pnl_usd") or c.get("realized_pnl_usd_final_leg"),
            "entry_mid": c.get("entry_mid"),
            "exit_mid": c.get("exit_mid"),
        })
    return out


def annotate_picks_with_portfolio_warnings(picks, position_summary):
    for p in picks:
        ticket = p.get("ticket") or {}
        ticker = (ticket.get("ticker") or "").split(".")[0]
        sector = ticket.get("sector")
        warnings = []
        if ticker in position_summary.get("tickers", []):
            warnings.append("ALREADY HELD — do not double-up")
        if position_summary.get("n_free", MAX_CONCURRENT) <= 0:
            warnings.append("PORTFOLIO FULL — no slots free until you close one")
        sector_warn = check_sector_overlap(sector, position_summary)
        if sector_warn:
            warnings.append(sector_warn)
        if warnings:
            p["portfolio_warnings"] = warnings
    return picks
