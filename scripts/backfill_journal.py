"""Backfill conviction_journal from existing scan files in data/results/.

Idempotent: re-running won't duplicate entries (skips (scan_date, ticker) keys
already in journal). Then stamps forward returns using EODHD.
"""
import os
import sys
import json
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.catalyst.conviction_journal import log_picks_from_scan, mark_forward_returns, get_journal_stats
from src.eodhd import EODHDClient


def main():
    pattern = "data/results/catalyst_2026-*.json"
    scan_files = sorted(glob.glob(pattern))
    print(f"Backfill: found {len(scan_files)} scan files")

    total_logged = 0
    for sf in scan_files:
        try:
            with open(sf, "r", encoding="utf-8") as f:
                scan = json.load(f)
        except Exception as e:
            print(f"  skip {sf}: {type(e).__name__}: {e}")
            continue
        n = log_picks_from_scan(scan, verbose=False)
        if n:
            print(f"  {os.path.basename(sf)}: logged {n} new picks")
        total_logged += n

    print(f"\nTotal new picks logged: {total_logged}")
    print()

    print("Stamping forward returns (this takes a few minutes - one EODHD bars call per unique ticker)...")
    client = EODHDClient()
    n_closed = mark_forward_returns(client, verbose=True)
    print(f"\nForward returns: {n_closed} positions closed (15d window matured)")

    print()
    print("=" * 60)
    print("JOURNAL STATS (60d lookback)")
    print("=" * 60)
    stats = get_journal_stats(days_back=60)
    if not stats:
        print("No measured rows yet (need 15+ days since scan_date for full close)")
        return
    print(f"Total measured: {stats['total_measured']}")
    print()
    print("BY SIDE:")
    for side, s in stats["by_side"].items():
        if not s:
            continue
        print(f"  {side}: n={s['n']}, win_rate={s['win_rate_pct']}%, avg_best={s['avg_best_pct']}%, avg_5d={s['avg_5d_pct']}%, avg_10d={s['avg_10d_pct']}%")
    print()
    print("BY TIER:")
    for tier, s in stats["by_tier"].items():
        if not s:
            continue
        print(f"  {tier}: n={s['n']}, win_rate={s['win_rate_pct']}%, avg_best={s['avg_best_pct']}%, avg_5d={s['avg_5d_pct']}%")
    print()
    print("BY CONVICTION SCORE BAND:")
    for band, s in stats["by_score_band"].items():
        if not s:
            continue
        print(f"  {band}: n={s['n']}, win_rate={s['win_rate_pct']}%, avg_best={s['avg_best_pct']}%, avg_5d={s['avg_5d_pct']}%")


if __name__ == "__main__":
    main()
