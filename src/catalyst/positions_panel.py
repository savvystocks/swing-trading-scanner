import json
import pathlib
from datetime import datetime

from src.catalyst.exit_policy import ARM_PCT, TRAIL_FRAC, HARD_STOP_PCT
from src.catalyst.trade_ticket import _occ_symbol, _fetch_contract_data


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
LIVE_POSITIONS_PATH = PROJECT_ROOT / "data" / "paper_trades" / "live_positions.json"
MONITOR_STATE_PATH = PROJECT_ROOT / "data" / "position_monitor_state.json"

GBP_USD_RATE = 1.26


def _load_open_positions():
    if not LIVE_POSITIONS_PATH.exists():
        return []
    try:
        data = json.loads(LIVE_POSITIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [p for p in data if p.get("status") == "OPEN"]


def _load_monitor_exits():
    if not MONITOR_STATE_PATH.exists():
        return {}
    try:
        st = json.loads(MONITOR_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return st.get("exits") or {}


def _live_mid(uw, pos):
    ticker = pos.get("ticker")
    strike = pos.get("strike")
    side = pos.get("side")
    expiry_s = pos.get("expiration") or pos.get("expiry")
    if not (ticker and strike and side and expiry_s):
        return None, None
    try:
        exp = datetime.strptime(str(expiry_s)[:10], "%Y-%m-%d").date()
    except Exception:
        return None, None
    occ = _occ_symbol(ticker, exp, side, float(strike))
    quote = _fetch_contract_data(uw, ticker, occ)
    if not quote:
        return occ, None
    bid, ask, last = quote.get("bid"), quote.get("ask"), quote.get("last")
    if bid and ask:
        return occ, (bid + ask) / 2
    if last:
        return occ, last
    return occ, None


def build_positions_panel(uw):
    positions = _load_open_positions()
    if not positions:
        return []
    exits = _load_monitor_exits()
    rows = []
    for pos in positions:
        entry = pos.get("entry_price")
        contracts = int(pos.get("contracts") or 0)
        occ, mid = _live_mid(uw, pos) if (uw and uw.enabled) else (None, None)
        st = exits.get(occ) or {}
        armed = st.get("armed", False)
        peak = st.get("peak")
        signaled = st.get("exit_signaled", False)

        row = {
            "ticker": pos.get("ticker"),
            "side": pos.get("side"),
            "strike": pos.get("strike"),
            "expiration": pos.get("expiration"),
            "contracts": contracts,
            "entry": entry,
            "mid": round(mid, 2) if mid else None,
            "pct": None,
            "pnl_gbp": None,
        }

        if entry and mid and entry > 0:
            pct = (mid - entry) / entry * 100.0
            row["pct"] = round(pct, 1)
            row["pnl_gbp"] = round((mid - entry) * 100 * contracts / GBP_USD_RATE, 2)

        if armed and peak is not None:
            stop_pct = peak * (1 - TRAIL_FRAC)
            row["status"] = "TRAILING"
            row["stop_label"] = f"trail exit at {stop_pct:+.0f}% (locks {int((1 - TRAIL_FRAC) * 100)}% of {peak:+.0f}% peak)"
            row["stop_price"] = round(entry * (1 + stop_pct / 100.0), 2) if entry else None
        else:
            row["status"] = "PRE-ARM"
            row["stop_label"] = f"hard stop {HARD_STOP_PCT:+.0f}%, trail arms at +{ARM_PCT:.0f}%"
            row["stop_price"] = round(entry * (1 + HARD_STOP_PCT / 100.0), 2) if entry else None

        if signaled:
            row["status"] = "EXIT SIGNALED"

        rows.append(row)
    return rows
