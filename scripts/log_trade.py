"""Live trade CLI logger - friction-free way to mark positions open/closed.

Usage:
  Open a position:
    python scripts/log_trade.py open ETOR call 45 2026-06-18 0.75 16

    args: ticker side(call|put) strike expiry(YYYY-MM-DD) entry_price contracts

  Close a position:
    python scripts/log_trade.py close ETOR 1.50

    args: ticker exit_price [exit_date_optional]

  Mark a partial close (trim):
    python scripts/log_trade.py trim ETOR 1.20 8

    args: ticker trim_price contracts_to_trim

  List all positions:
    python scripts/log_trade.py list

  Status of one ticker:
    python scripts/log_trade.py status ETOR

The file edited: data/paper_trades/live_positions.json
This is the source of truth read by guardrails + drift detector + position
intelligence. Keeps the system in sync with reality without you editing JSON.
"""
import os
import sys
import json
import pathlib
from datetime import datetime


PROJECT_ROOT = pathlib.Path(__file__).parent.parent
LIVE_PATH = PROJECT_ROOT / "data" / "paper_trades" / "live_positions.json"
ARCHIVE_PATH = PROJECT_ROOT / "data" / "paper_trades" / "closed_positions.json"

GBP_USD_RATE = 1.26


def _load_positions(path):
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_positions(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def open_position(args):
    if len(args) < 6:
        print("usage: log_trade.py open <ticker> <call|put> <strike> <expiry> <entry_price> <contracts>")
        sys.exit(2)
    ticker, side, strike, expiry, entry_price, contracts = args[:6]
    side = side.upper()
    if side not in ("CALL", "PUT"):
        print(f"side must be CALL or PUT, got {side}")
        sys.exit(2)

    try:
        strike_f = float(strike)
        entry_f = float(entry_price)
        contracts_i = int(contracts)
    except ValueError:
        print("strike, entry_price, contracts must be numeric")
        sys.exit(2)

    cost_usd = entry_f * 100 * contracts_i
    cost_gbp = round(cost_usd / GBP_USD_RATE, 2)
    opened_at = datetime.utcnow().date().isoformat()

    positions = _load_positions(LIVE_PATH)
    new_entry = {
        "ticker": ticker.upper(),
        "side": side,
        "strike": strike_f,
        "expiration": expiry,
        "entry_price": entry_f,
        "contracts": contracts_i,
        "cost_usd": round(cost_usd, 2),
        "cost_gbp": cost_gbp,
        "opened_at": opened_at,
        "broker": "Robinhood",
        "status": "OPEN",
        "notes": f"Logged via CLI on {opened_at}",
    }
    positions.append(new_entry)
    _save_positions(LIVE_PATH, positions)
    print(f"OPEN: {ticker.upper()} {side} ${strike_f} exp {expiry}")
    print(f"  {contracts_i}x @ ${entry_f} = ${cost_usd:.2f} (£{cost_gbp:.2f})")
    print(f"  opened {opened_at}")
    print(f"  total live positions: {sum(1 for p in positions if p.get('status') == 'OPEN')}")


def close_position(args):
    if len(args) < 2:
        print("usage: log_trade.py close <ticker> <exit_price> [exit_date]")
        sys.exit(2)
    ticker = args[0].upper()
    try:
        exit_price = float(args[1])
    except ValueError:
        print("exit_price must be numeric")
        sys.exit(2)
    exit_date = args[2] if len(args) >= 3 else datetime.utcnow().date().isoformat()

    positions = _load_positions(LIVE_PATH)
    closed_count = 0
    pnl_total_gbp = 0.0
    archive = _load_positions(ARCHIVE_PATH)

    remaining = []
    for p in positions:
        if p.get("ticker") == ticker and p.get("status") == "OPEN":
            entry = float(p.get("entry_price") or 0)
            contracts = int(p.get("contracts") or 0)
            pnl_usd = (exit_price - entry) * 100 * contracts
            pnl_gbp = round(pnl_usd / GBP_USD_RATE, 2)
            pnl_total_gbp += pnl_gbp
            closed_count += 1
            closed = dict(p)
            closed.update({
                "status": "CLOSED",
                "exit_price": exit_price,
                "closed_at": exit_date,
                "pnl_usd": round(pnl_usd, 2),
                "pnl_gbp": pnl_gbp,
                "return_pct": round((exit_price - entry) / entry * 100, 1) if entry > 0 else 0,
            })
            archive.append(closed)
        else:
            remaining.append(p)

    if closed_count == 0:
        print(f"No open positions found for {ticker}")
        sys.exit(2)

    _save_positions(LIVE_PATH, remaining)
    _save_positions(ARCHIVE_PATH, archive)
    print(f"CLOSED {closed_count} {ticker} position(s) at ${exit_price}")
    print(f"  P&L: £{pnl_total_gbp:+.2f}")
    print(f"  Remaining live positions: {sum(1 for p in remaining if p.get('status') == 'OPEN')}")


def trim_position(args):
    if len(args) < 3:
        print("usage: log_trade.py trim <ticker> <trim_price> <contracts_to_trim>")
        sys.exit(2)
    ticker = args[0].upper()
    try:
        trim_price = float(args[1])
        trim_contracts = int(args[2])
    except ValueError:
        print("trim_price + contracts must be numeric")
        sys.exit(2)

    positions = _load_positions(LIVE_PATH)
    trimmed = False
    for p in positions:
        if p.get("ticker") == ticker and p.get("status") == "OPEN":
            current = int(p.get("contracts") or 0)
            if current <= trim_contracts:
                print(f"Trimming {trim_contracts} from {current} contracts - this will close the position. Use close instead.")
                sys.exit(2)
            entry = float(p.get("entry_price") or 0)
            trim_pnl_usd = (trim_price - entry) * 100 * trim_contracts
            trim_pnl_gbp = round(trim_pnl_usd / GBP_USD_RATE, 2)
            p["contracts"] = current - trim_contracts
            p["cost_usd"] = round(p["contracts"] * entry * 100, 2)
            p["cost_gbp"] = round(p["cost_usd"] / GBP_USD_RATE, 2)
            trims = p.setdefault("trims", [])
            trims.append({
                "at": datetime.utcnow().date().isoformat(),
                "trimmed_contracts": trim_contracts,
                "trim_price": trim_price,
                "trim_pnl_gbp": trim_pnl_gbp,
            })
            trimmed = True
            print(f"TRIMMED {trim_contracts} {ticker} @ ${trim_price}")
            print(f"  Trim P&L: £{trim_pnl_gbp:+.2f}")
            print(f"  Remaining: {p['contracts']} contracts")
            break
    if not trimmed:
        print(f"No open {ticker} position found")
        sys.exit(2)
    _save_positions(LIVE_PATH, positions)


def list_positions(_args):
    positions = _load_positions(LIVE_PATH)
    open_pos = [p for p in positions if p.get("status") == "OPEN"]
    if not open_pos:
        print("No live positions logged.")
        return
    total_cost = sum(p.get("cost_gbp", 0) for p in open_pos)
    print(f"LIVE POSITIONS ({len(open_pos)})")
    print(f"Total exposure: £{total_cost:.0f}")
    print()
    for p in open_pos:
        print(f"  {p['ticker']:6} {p['side']:4} ${p.get('strike'):>6} exp {p.get('expiration')} - "
              f"{p.get('contracts')}x @ ${p.get('entry_price')} (£{p.get('cost_gbp'):.0f}) "
              f"opened {p.get('opened_at')}")


def status_position(args):
    if len(args) < 1:
        print("usage: log_trade.py status <ticker>")
        sys.exit(2)
    ticker = args[0].upper()
    positions = _load_positions(LIVE_PATH)
    found = [p for p in positions if p.get("ticker") == ticker and p.get("status") == "OPEN"]
    if not found:
        print(f"No open position for {ticker}")
        archive = _load_positions(ARCHIVE_PATH)
        closed = [p for p in archive if p.get("ticker") == ticker]
        if closed:
            print(f"\nPrior closed positions: {len(closed)}")
            for p in closed[-3:]:
                print(f"  {p.get('opened_at')} -> {p.get('closed_at')}: "
                      f"${p.get('entry_price')} -> ${p.get('exit_price')} "
                      f"= £{p.get('pnl_gbp'):+.0f} ({p.get('return_pct'):+.0f}%)")
        return
    for p in found:
        print(json.dumps(p, indent=2, default=str))


COMMANDS = {
    "open": open_position,
    "close": close_position,
    "trim": trim_position,
    "list": list_positions,
    "status": status_position,
}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    cmd = sys.argv[1].lower()
    if cmd not in COMMANDS:
        print(f"unknown command {cmd}. valid: {list(COMMANDS.keys())}")
        sys.exit(2)
    COMMANDS[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
