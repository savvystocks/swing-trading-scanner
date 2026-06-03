"""CLI for managing positions.json - run locally then SCP to Vultr.

Usage:
    python scripts/position.py add NVDA CALL 215 2026-07-02 14.63 --size 30
    python scripts/position.py remove NVDA CALL 215
    python scripts/position.py list
    python scripts/position.py push VULTR_IP   # SCPs positions.json to Vultr

After add/remove, run `push VULTR_IP` to sync to the WS worker.
The worker auto-detects changes within 60s.
"""

import argparse
import os
import sys
import subprocess


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.positions import (
    add_position, remove_position, load_positions, POSITIONS_PATH
)


def cmd_add(args):
    add_position(args.ticker, args.side, args.strike, args.expiry,
                 entry_premium=args.entry_premium, size_pct=args.size)
    print(f"Added: {args.ticker} {args.side} ${args.strike} exp {args.expiry}")
    for p in load_positions():
        print(f"  - {p['ticker']} {p['side']} ${p['strike']} exp {p['expiry']}")


def cmd_remove(args):
    remove_position(args.ticker, args.side, args.strike)
    print(f"Removed: {args.ticker} {args.side or ''} {args.strike or ''}")
    for p in load_positions():
        print(f"  - {p['ticker']} {p['side']} ${p['strike']} exp {p['expiry']}")


def cmd_list(_args):
    positions = load_positions()
    if not positions:
        print("No active positions.")
        return
    print(f"Active positions ({len(positions)}):")
    for p in positions:
        size = f"{p.get('size_pct', '?')}%"
        entry = f"@${p.get('entry_premium')}" if p.get('entry_premium') else ""
        print(f"  {p['ticker']:6} {p['side']:4} ${p['strike']} exp {p['expiry']} {size} {entry}")


def cmd_push(args):
    """SCP positions.json to Vultr."""
    target = f"root@{args.vultr_ip}:/opt/flow-ws/data/positions.json"
    cmd = ["scp", str(POSITIONS_PATH), target]
    print(f"Running: {' '.join(cmd)}")
    r = subprocess.run(cmd)
    if r.returncode == 0:
        print(f"Pushed positions.json to {args.vultr_ip}")
        print(f"Worker will pick up changes within 60s.")
    else:
        print(f"SCP failed (exit {r.returncode})")


def main():
    ap = argparse.ArgumentParser(description="Manage positions for WS worker")
    sub = ap.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="Add a position")
    add.add_argument("ticker")
    add.add_argument("side", choices=["CALL", "PUT", "call", "put"])
    add.add_argument("strike", type=float)
    add.add_argument("expiry", help="YYYY-MM-DD")
    add.add_argument("entry_premium", type=float, nargs="?", default=None)
    add.add_argument("--size", type=float, default=None, help="Account size %")
    add.set_defaults(func=cmd_add)

    rm = sub.add_parser("remove", help="Remove a position")
    rm.add_argument("ticker")
    rm.add_argument("side", nargs="?", default=None)
    rm.add_argument("strike", nargs="?", type=float, default=None)
    rm.set_defaults(func=cmd_remove)

    ls = sub.add_parser("list", help="List active positions")
    ls.set_defaults(func=cmd_list)

    push = sub.add_parser("push", help="SCP positions.json to Vultr")
    push.add_argument("vultr_ip")
    push.set_defaults(func=cmd_push)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
