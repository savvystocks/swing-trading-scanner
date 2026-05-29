import json
import os
import pathlib
from datetime import datetime

from src.alpaca_options import get_options_chain, get_live_price

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
PAPER_DIR = PROJECT_ROOT / "data" / "paper_trades"
POSITIONS_PATH = PAPER_DIR / "positions.json"
CLOSED_PATH = PAPER_DIR / "closed.json"

MAX_COST_PER_POSITION = 1500
DEFAULT_CONTRACT_COUNT = 1


def _load(path):
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def load_positions():
    return _load(POSITIONS_PATH)


def load_closed():
    return _load(CLOSED_PATH)


def save_positions(positions):
    _save(POSITIONS_PATH, positions)


def save_closed(closed):
    _save(CLOSED_PATH, closed)


def _position_id(ticker, strike, expiration, opened_at):
    strike_int = int(round(strike))
    exp_compact = expiration.replace("-", "")
    return f"{ticker}_{opened_at}_C{strike_int}_{exp_compact}"


def find_open_position(positions, ticker):
    for p in positions:
        if p.get("ticker") == ticker and p.get("status") == "OPEN":
            return p
    return None


def _extract_earnings_days(fund):
    if not fund:
        return None
    history = (fund.get("Earnings") or {}).get("History") or {}
    today = datetime.now().date()
    soonest = None
    for _k, v in history.items():
        rd = v.get("reportDate")
        if not rd:
            continue
        try:
            rd_d = datetime.strptime(rd, "%Y-%m-%d").date()
        except ValueError:
            continue
        if rd_d >= today:
            d = (rd_d - today).days
            if soonest is None or d < soonest:
                soonest = d
    return soonest


def open_position(ticker, options_trade, hunter, ind, fund, vix_regime, sector="", name=""):
    if not options_trade:
        return None
    mid = options_trade.get("premium_mid") or options_trade.get("mid")
    if not mid or mid <= 0:
        return None
    cost = mid * 100 * DEFAULT_CONTRACT_COUNT
    if cost > MAX_COST_PER_POSITION:
        return None

    opened_at = datetime.now().strftime("%Y-%m-%d")
    spot = None
    try:
        spot = float(ind.iloc[-1]["close"])
    except Exception:
        spot = options_trade.get("current_price")

    return {
        "id": _position_id(ticker, options_trade["strike"], options_trade["expiration"], opened_at),
        "ticker": ticker,
        "name": name,
        "sector": sector,
        "opened_at": opened_at,
        "opened_at_spot": spot,
        "contract": {
            "strike": options_trade["strike"],
            "expiration": options_trade["expiration"],
            "right": "call",
            "dte_at_open": options_trade.get("dte", 0),
        },
        "entry_mid": float(mid),
        "entry_bid": options_trade.get("bid"),
        "entry_ask": options_trade.get("ask"),
        "entry_delta": options_trade.get("delta"),
        "entry_iv_pct": options_trade.get("iv_pct"),
        "entry_spread_pct": options_trade.get("spread_pct"),
        "size_contracts": DEFAULT_CONTRACT_COUNT,
        "cost_basis_usd": round(cost, 2),
        "hunter_snapshot": {
            "score": hunter.get("score"),
            "pct_above_50d": hunter.get("pct_above_50d"),
            "ret_20d": hunter.get("ret_20d"),
            "ret_5d": hunter.get("ret_5d"),
            "squeeze_pct": hunter.get("squeeze_pct"),
            "extension_state": hunter.get("extension_state"),
            "reasons": hunter.get("reasons", []),
            "earnings_days_at_open": hunter.get("earnings_days"),
            "sector_tilt": hunter.get("sector_tilt"),
            "lane_b_count": hunter.get("lane_b_count"),
        },
        "market_regime_at_open": {"vix_regime": vix_regime},
        "trim_levels_hit": [],
        "trims": [],
        "last_marked_at": opened_at,
        "current_mid": float(mid),
        "current_spot": spot,
        "current_pnl_pct": 0.0,
        "current_pnl_usd": 0.0,
        "status": "OPEN",
    }


def mark_to_market(position, current_mid, current_spot):
    entry = position["entry_mid"]
    pnl_pct = ((current_mid - entry) / entry * 100) if entry > 0 else 0
    pnl_usd = (current_mid - entry) * 100 * position["size_contracts"]
    position["current_mid"] = float(current_mid)
    position["current_spot"] = float(current_spot) if current_spot else None
    position["current_pnl_pct"] = round(pnl_pct, 1)
    position["current_pnl_usd"] = round(pnl_usd, 2)
    position["last_marked_at"] = datetime.now().strftime("%Y-%m-%d")
    return position


def check_exit_rules(position, current_spot, ind, fund):
    pnl_pct = position.get("current_pnl_pct", 0)
    trim_hit = position.get("trim_levels_hit", [])

    try:
        exp_date = datetime.strptime(position["contract"]["expiration"], "%Y-%m-%d")
        dte = (exp_date - datetime.now()).days
    except Exception:
        dte = 999

    if pnl_pct <= -50:
        return {"action": "CLOSE_ALL", "reason": f"hit -50% stop ({pnl_pct:+.0f}%)"}
    if pnl_pct >= 300:
        return {"action": "CLOSE_ALL", "reason": f"hit +300% max target ({pnl_pct:+.0f}%)"}
    if dte <= 21:
        return {"action": "CLOSE_ALL", "reason": f"theta cliff ({dte}d DTE)"}

    earnings_days = _extract_earnings_days(fund)
    if earnings_days is not None and earnings_days <= 1:
        return {"action": "CLOSE_ALL", "reason": f"earnings in {earnings_days}d (IV crush risk)"}

    if ind is not None and current_spot:
        try:
            last = ind.iloc[-1]
            sma_50 = last.get("sma_50")
            if sma_50 is not None and float(sma_50) > 0 and current_spot < float(sma_50):
                return {"action": "CLOSE_ALL", "reason": f"underlying broke 50d SMA (${current_spot:.2f} < ${float(sma_50):.2f})"}
        except Exception:
            pass

    if pnl_pct >= 200 and "200" not in trim_hit:
        return {"action": "TRIM_75", "reason": f"hit +200% (trim 75%, ride runner)"}
    if pnl_pct >= 100 and "100" not in trim_hit:
        return {"action": "TRIM_50", "reason": f"hit +100% (lock half)"}

    return {"action": "HOLD", "reason": None}


def close_position(position, exit_mid, exit_reason, exit_spot):
    closed_at = datetime.now().strftime("%Y-%m-%d")
    try:
        opened = datetime.strptime(position["opened_at"], "%Y-%m-%d")
        days_held = (datetime.now() - opened).days
    except Exception:
        days_held = 0
    realized_pct = ((exit_mid - position["entry_mid"]) / position["entry_mid"] * 100) if position["entry_mid"] > 0 else 0
    realized_usd = (exit_mid - position["entry_mid"]) * 100 * position["size_contracts"]
    prior_trim_usd = sum(t.get("realized_pnl_usd", 0) for t in position.get("trims", []))
    position.update({
        "closed_at": closed_at,
        "exit_mid": float(exit_mid),
        "exit_spot": float(exit_spot) if exit_spot else None,
        "exit_reason": exit_reason,
        "days_held": days_held,
        "realized_pnl_pct": round(realized_pct, 1),
        "realized_pnl_usd_final_leg": round(realized_usd, 2),
        "total_realized_pnl_usd": round(realized_usd + prior_trim_usd, 2),
        "status": "CLOSED",
    })
    return position


def trim_position(position, exit_mid, reason, trim_pct):
    level_tag = "100" if "+100%" in reason else "200" if "+200%" in reason else "x"
    position.setdefault("trim_levels_hit", []).append(level_tag)
    contracts_closed = position["size_contracts"] * trim_pct / 100
    realized_pnl = (exit_mid - position["entry_mid"]) * 100 * contracts_closed
    position.setdefault("trims", []).append({
        "at": datetime.now().strftime("%Y-%m-%d"),
        "reason": reason,
        "contracts_closed": round(contracts_closed, 2),
        "exit_mid": float(exit_mid),
        "realized_pnl_usd": round(realized_pnl, 2),
    })
    position["size_contracts"] = position["size_contracts"] - contracts_closed
    return position


def run_daily_cycle(hunter_results, vix_regime):
    positions = load_positions()
    closed = load_closed()
    events = []

    for pos in positions:
        if pos.get("status") != "OPEN":
            continue
        ticker = pos["ticker"]
        symbol = ticker.replace(".US", "")
        matching = next((r for r in hunter_results if r["ticket"]["ticker"] == ticker), None)
        ind = matching.get("ind") if matching else None
        fund = matching.get("fundamentals") if matching else None

        current_spot = get_live_price(symbol)
        if not current_spot and ind is not None:
            try:
                current_spot = float(ind.iloc[-1]["close"])
            except Exception:
                current_spot = pos.get("current_spot") or pos["opened_at_spot"]

        chain = get_options_chain(symbol, "call", current_spot) if current_spot else None
        if not chain:
            events.append({"ticker": ticker, "action": "MARK_SKIP", "reason": "no options chain available"})
            continue

        current_mid = chain["mid"]
        mark_to_market(pos, current_mid, current_spot)
        exit_sig = check_exit_rules(pos, current_spot, ind, fund)

        if exit_sig["action"] == "CLOSE_ALL":
            close_position(pos, current_mid, exit_sig["reason"], current_spot)
            closed.append(pos)
            events.append({
                "ticker": ticker, "action": "CLOSE_ALL",
                "reason": exit_sig["reason"],
                "pnl_pct": pos.get("realized_pnl_pct"),
                "pnl_usd": pos.get("total_realized_pnl_usd"),
            })
        elif exit_sig["action"].startswith("TRIM"):
            trim_pct = 50 if exit_sig["action"] == "TRIM_50" else 75
            trim_position(pos, current_mid, exit_sig["reason"], trim_pct)
            events.append({
                "ticker": ticker, "action": exit_sig["action"],
                "reason": exit_sig["reason"],
                "pnl_pct": pos.get("current_pnl_pct"),
            })

    positions = [p for p in positions if p.get("status") == "OPEN"]

    for r in hunter_results:
        t = r["ticket"]
        ticker = t["ticker"]
        if not ticker.endswith(".US"):
            continue
        if find_open_position(positions, ticker):
            continue
        options_trade = t.get("options_trade")
        if not options_trade:
            continue
        hunter = t.get("hunter", {})
        ind = r.get("ind")
        fund = r.get("fundamentals") or {}
        general = (fund.get("General") or {}) if fund else {}
        new_pos = open_position(
            ticker, options_trade, hunter, ind, fund, vix_regime,
            sector=general.get("Sector", "") or t.get("sector", ""),
            name=general.get("Name", "") or t.get("name", ""),
        )
        if new_pos:
            positions.append(new_pos)
            events.append({
                "ticker": ticker, "action": "OPEN",
                "reason": f"hunter score {hunter.get('score')} (entry ${new_pos['entry_mid']:.2f})",
                "cost": new_pos["cost_basis_usd"],
            })

    save_positions(positions)
    save_closed(closed)

    total_unrealized = sum(p.get("current_pnl_usd", 0) for p in positions if p.get("status") == "OPEN")
    total_realized = sum(p.get("total_realized_pnl_usd", 0) for p in closed)

    return {
        "positions": positions,
        "closed": closed,
        "events": events,
        "summary": {
            "open_count": len(positions),
            "closed_count": len(closed),
            "total_unrealized_pnl_usd": round(total_unrealized, 2),
            "total_realized_pnl_usd": round(total_realized, 2),
            "total_pnl_usd": round(total_unrealized + total_realized, 2),
        },
    }
