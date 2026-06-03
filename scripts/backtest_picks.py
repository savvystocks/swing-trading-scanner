"""Backtest scaffold: replay past scan picks vs realized price moves.

Loops through saved flow_scan_YYYY-MM-DD.json files, looks at each pick's
ticker + side + entry date, then queries UW historical OHLC to see what
actually happened to the stock over the recommended hold period.

Computes hit rate per tier + per pattern.

Usage:
    python scripts/backtest_picks.py
    python scripts/backtest_picks.py --from 2026-05-01 --to 2026-06-03
"""

import os
import sys
import json
import glob
import argparse
from datetime import datetime, date, timedelta
from collections import defaultdict


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_scans(from_date=None, to_date=None):
    """Load all flow_scan JSON files in date range."""
    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "data", "results")
    files = sorted(glob.glob(os.path.join(results_dir, "flow_scan_*.json")))
    out = []
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
            scan_date_str = d.get("scan_date")
            if not scan_date_str:
                continue
            scan_date = datetime.strptime(scan_date_str, "%Y-%m-%d").date()
            if from_date and scan_date < from_date:
                continue
            if to_date and scan_date > to_date:
                continue
            out.append(d)
        except Exception:
            continue
    return out


def get_price_after_days(uw_client, ticker, entry_date, days_forward):
    """Pull UW daily OHLC and find close N trading days after entry."""
    try:
        ohlc = uw_client.stock_ohlc(ticker, candle_size="1d")
    except Exception:
        return None
    if not ohlc:
        return None
    rows = ohlc.get("data") if isinstance(ohlc, dict) else ohlc
    if not isinstance(rows, list):
        return None
    # Sort by date ascending
    by_date = sorted(
        [r for r in rows if isinstance(r, dict) and r.get("date")],
        key=lambda r: r["date"],
    )
    target_date = entry_date + timedelta(days=days_forward)
    for r in by_date:
        try:
            rd = datetime.strptime(r["date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if rd >= target_date:
            try:
                return float(r.get("close", 0)) or None
            except (TypeError, ValueError):
                return None
    return None


def evaluate_pick(uw_client, pick, scan_date):
    """Return win/loss/unknown for a single pick."""
    c = pick.get("_confluence") or {}
    side = c.get("side")
    tier = c.get("tier", "PASS")
    if tier == "PASS" or not side:
        return None
    ticker = pick.get("ticker")
    entry_price = pick.get("live_spot") or pick.get("price")
    if not entry_price:
        return None

    max_hold = c.get("max_hold_days", 14)
    exit_price = get_price_after_days(uw_client, ticker, scan_date, max_hold)
    if not exit_price:
        return None

    move_pct = (exit_price - entry_price) / entry_price * 100
    if side == "PUT":
        move_pct = -move_pct
    target_pct = c.get("target_pct", 50)  # we need underlying to move this much for option to hit target
    # Rough approximation: option doubles if stock moves 5%+
    won = move_pct >= 5
    breakeven = abs(move_pct) < 2
    return {
        "ticker": ticker,
        "tier": tier,
        "side": side,
        "score": c.get("score", 0),
        "entry": entry_price,
        "exit": exit_price,
        "move_pct": round(move_pct, 2),
        "won": won,
        "breakeven": breakeven,
        "patterns": [p.get("key") for p in (c.get("patterns_fired") or [])],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="from_date", default=None,
                    help="Start date YYYY-MM-DD (default all)")
    ap.add_argument("--to", dest="to_date", default=None,
                    help="End date YYYY-MM-DD (default all)")
    args = ap.parse_args()

    from_d = datetime.strptime(args.from_date, "%Y-%m-%d").date() if args.from_date else None
    to_d = datetime.strptime(args.to_date, "%Y-%m-%d").date() if args.to_date else None

    from src.unusual_whales_api import get_client
    uw = get_client()
    if not uw.enabled:
        print("UW token missing")
        sys.exit(1)

    scans = load_scans(from_date=from_d, to_date=to_d)
    print(f"Loaded {len(scans)} scan files")
    if not scans:
        print("No scans to backtest")
        return

    results = []
    for scan in scans:
        scan_date = datetime.strptime(scan["scan_date"], "%Y-%m-%d").date()
        for pick in scan.get("calls", []) + scan.get("puts", []):
            r = evaluate_pick(uw, pick, scan_date)
            if r:
                r["scan_date"] = scan["scan_date"]
                results.append(r)

    if not results:
        print("No evaluable picks (need price data N days forward)")
        return

    # Aggregate by tier
    by_tier = defaultdict(lambda: {"n": 0, "wins": 0, "avg_move": 0.0})
    for r in results:
        slot = by_tier[r["tier"]]
        slot["n"] += 1
        if r["won"]:
            slot["wins"] += 1
        slot["avg_move"] += r["move_pct"]

    print(f"\nResults across {len(results)} picks:")
    print(f"{'Tier':18} {'N':>4} {'Wins':>4} {'Hit%':>6} {'Avg Move%':>10}")
    for tier in ("GAMMA_BOMB", "MAX_CONVICTION", "ELITE", "STRONG", "MODERATE"):
        if tier in by_tier:
            s = by_tier[tier]
            hit_rate = s["wins"] / s["n"] * 100
            avg = s["avg_move"] / s["n"]
            print(f"  {tier:18} {s['n']:>4} {s['wins']:>4} {hit_rate:>5.1f}% {avg:>9.2f}%")

    # Aggregate by pattern
    pattern_stats = defaultdict(lambda: {"n": 0, "wins": 0, "avg_move": 0.0})
    for r in results:
        for p in r["patterns"]:
            slot = pattern_stats[p]
            slot["n"] += 1
            if r["won"]:
                slot["wins"] += 1
            slot["avg_move"] += r["move_pct"]

    print(f"\nBy pattern (how often each was on a winner):")
    print(f"{'Pattern':25} {'N':>4} {'Wins':>4} {'Hit%':>6} {'Avg Move%':>10}")
    for p, s in sorted(pattern_stats.items(), key=lambda kv: -kv[1]["n"]):
        hit_rate = s["wins"] / s["n"] * 100
        avg = s["avg_move"] / s["n"]
        print(f"  {p:25} {s['n']:>4} {s['wins']:>4} {hit_rate:>5.1f}% {avg:>9.2f}%")


if __name__ == "__main__":
    main()
